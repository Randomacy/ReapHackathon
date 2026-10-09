from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.agent import AgentError, AgentService
from src.models import Action, FocusEvent, Mandate


NOW = datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc)


def service(tmp_path):
    return AgentService(tmp_path / "agent.sqlite3", "local-test-token", now=lambda: NOW)


def mandate(**changes):
    values = dict(schema_version="1.0", user_id="demo-user", enabled=True,
                  currency="SGD", max_order_minor=1000, daily_budget_minor=1500,
                  max_orders_per_day=2, cooldown_seconds=7200,
                  allowed_merchant_domains=["dutchcolony.sg"],
                  preferred_product_id=None, approval_mode="each_order",
                  cancel_window_seconds=15)
    values.update(changes)
    return Mandate(**values)


def event(state="focus_dip", quality="good", when=NOW, event_id=None):
    return FocusEvent(schema_version="1.0", event_id=event_id or uuid4(),
                      user_id="demo-user", observed_at=when, source="simulator",
                      state=state, focus_score=.28 if state == "focus_dip" else .75,
                      signal_quality=quality, sustained_for_ms=30000)


def action(name, order_id=None, action_id=None):
    return Action(schema_version="1.0", user_id="demo-user", action_id=action_id or uuid4(),
                  action=name, order_id=order_id)


def test_no_mandate_or_bad_signal_cannot_buy(tmp_path):
    agent = service(tmp_path)
    agent.receive_event(event(), "local-test-token")
    assert agent.snapshot()["order"] is None
    agent.save_mandate(mandate())
    agent.receive_event(event(quality="poor"), "local-test-token")
    agent.receive_event(event(when=NOW - timedelta(seconds=16)), "local-test-token")
    assert agent.snapshot()["order"] is None


def test_approval_is_idempotent_and_cooldown_survives_restart(tmp_path):
    agent = service(tmp_path)
    agent.save_mandate(mandate())
    dip = event()
    agent.receive_event(dip, "local-test-token")
    agent.receive_event(dip, "local-test-token")
    with pytest.raises(AgentError):
        agent.receive_event(event("focused", event_id=dip.event_id), "local-test-token")
    proposed = agent.snapshot()["order"]
    assert proposed["status"] == "awaiting_approval"
    assert proposed["purchase_mode"] == "mock"
    approve = action("approve", proposed["order_id"])
    result = agent.act(approve)
    assert result["order"]["status"] == "succeeded"
    assert result["order"]["checkout_reference"].startswith("mock-")
    assert agent.act(approve)["order"]["order_id"] == proposed["order_id"]
    with pytest.raises(AgentError):
        agent.act(action("cancel", proposed["order_id"], action_id=approve.action_id))
    restarted = service(tmp_path)
    restarted.receive_event(event("focused"), "local-test-token")
    restarted.receive_event(event(), "local-test-token")
    assert restarted.snapshot()["order"]["order_id"] == proposed["order_id"]
    assert "cooldown" in restarted.snapshot()["message"].lower()


def test_changed_mandate_and_pause_block_approval(tmp_path):
    agent = service(tmp_path)
    agent.save_mandate(mandate())
    agent.receive_event(event(), "local-test-token")
    order_id = agent.snapshot()["order"]["order_id"]
    agent.save_mandate(mandate(max_order_minor=500))
    with pytest.raises(AgentError):
        agent.act(action("approve", order_id))
    assert agent.snapshot()["order"]["status"] == "blocked"
    agent.receive_event(event("focused"), "local-test-token")
    agent.save_mandate(mandate())
    agent.receive_event(event(), "local-test-token")
    new_id = agent.snapshot()["order"]["order_id"]
    agent.act(action("pause"))
    assert agent.snapshot()["order"]["status"] == "cancelled"
    with pytest.raises(AgentError):
        agent.act(action("approve", new_id))


def test_bad_token_and_over_budget(tmp_path):
    agent = service(tmp_path)
    agent.save_mandate(mandate(max_order_minor=500))
    with pytest.raises(AgentError) as error:
        agent.receive_event(event(), "wrong")
    assert error.value.status == 401
    agent.receive_event(event(), "local-test-token")
    assert agent.snapshot()["order"] is None
    assert "order cap" in agent.snapshot()["message"].lower()


def test_sandbox_quote_hosted_approval_and_reconciliation(tmp_path):
    class FakeReap:
        def get_enrollment(self, _id):
            return {"status": "ACTIVE"}

        def search_products(self, _query):
            return {"products": [{"id": "reap-iced-black", "available": True,
                                  "merchant": {"name": "Dutch Colony Coffee Co."}}]}

        def product_details(self, _id):
            return {"products": [{"id": "reap-iced-black", "name": "Iced Black",
                                  "defaultVariant": {"id": "variant-1", "available": True,
                                                     "requiresShipping": False}}]}

        def create_quote(self, _variant, _email, _key, _address):
            return {"id": "quote-1", "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                    "amountBreakdown": {"finalAmount": {"amount": "6.90", "currency": "SGD"}}}

        def get_quote(self, _id):
            return {"amountBreakdown": {"finalAmount": {"amount": "6.90", "currency": "SGD"}}}

        def create_checkout(self, _quote, _enrollment, _url, _key):
            return {"id": "checkout-1", "status": "REQUIRES_ACTION",
                    "nextAction": {"url": "https://sandbox.example/approve"}}

        def get_checkout(self, _id):
            return {"status": "COMPLETED", "orderId": "merchant-order-1",
                    "finalAmount": {"amount": "6.90", "currency": "SGD"}}

    config = {"REAP_API_KEY": "test-only", "REAP_PRODUCT_ID": "reap-iced-black",
              "REAP_EMAIL": "test@example.com", "REAP_ENROLLMENT_ID": "enrollment-1",
              "REAP_RETURN_URL": "https://example.com/return"}
    agent = AgentService(tmp_path / "reap.sqlite3", "local-test-token", "reap_sandbox",
                         now=lambda: NOW, sandbox_config=config, reap_client=FakeReap())
    agent.save_mandate(mandate())
    agent.receive_event(event(), "local-test-token")
    order = agent.snapshot()["order"]
    assert order["total_minor"] == 690
    assert order["purchase_mode"] == "reap_sandbox"
    original_get_quote = agent.adapter.client.get_quote
    agent.adapter.client.get_quote = lambda _id: {
        "amountBreakdown": {"finalAmount": {"amount": "7.90", "currency": "SGD"}}}
    with pytest.raises(AgentError) as changed:
        agent.act(action("approve", order["order_id"]))
    assert changed.value.code == "quote_changed"
    assert agent.snapshot()["order"]["status"] == "awaiting_approval"
    agent.adapter.client.get_quote = original_get_quote
    awaiting = agent.act(action("approve", order["order_id"]))
    assert awaiting["order"]["status"] == "awaiting_reap_approval"
    assert awaiting["order"]["approval_url"] == "https://sandbox.example/approve"
    completed = agent.refresh_order(order["order_id"])
    assert completed["order"]["status"] == "succeeded"
    assert completed["order"]["checkout_reference"] == "merchant-order-1"
