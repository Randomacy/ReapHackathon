"""Durable, single-host Tempo decision engine. No payment data enters this module."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
from uuid import uuid4
from urllib.parse import urlparse

from .models import Action, FocusEvent, Mandate
from .reap_client import ReapAPIError, ReapClient, minor_units


SGT = timezone(timedelta(hours=8), name="Asia/Singapore")
MOCK_PRODUCTS = (
    {"product_id": "mock-iced-black", "product_name": "Iced Black (menu-price demo)",
     "merchant_domain": "order.dutchcolony.sg", "currency": "SGD", "total_minor": 690},
    {"product_id": "mock-iced-latte", "product_name": "Iced Latte (menu-price demo)",
     "merchant_domain": "order.dutchcolony.sg", "currency": "SGD", "total_minor": 794},
)


def merchant_allowed(domain, allowed):
    return any(domain == candidate or domain.endswith("." + candidate)
               for candidate in allowed)


class AgentError(Exception):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class MockCheckout:
    mode = "mock"

    def select_and_price(self, mandate):
        candidates = [item for item in MOCK_PRODUCTS
                      if merchant_allowed(item["merchant_domain"], mandate.allowed_merchant_domains)
                      and item["currency"] == mandate.currency]
        if mandate.preferred_product_id:
            candidates = [item for item in candidates
                          if item["product_id"] == mandate.preferred_product_id]
        if not candidates:
            raise AgentError("no_product", "No eligible mock product matches the mandate.")
        return min(candidates, key=lambda item: item["total_minor"]).copy()

    def checkout(self, order):
        return {"status": "COMPLETED", "checkout_id": "mock-" + order["order_id"],
                "order_id": "mock-" + order["order_id"], "final_minor": order["total_minor"]}


class ReapSandboxCheckout:
    mode = "reap_sandbox"

    def __init__(self, config=None, client=None):
        config = config or os.environ
        self.product_id = config.get("REAP_PRODUCT_ID", "prd_99565ffb46d346c0aaa1f1aaa35be015")
        self.product_query = config.get("REAP_PRODUCT_QUERY", "Dutch Colony")
        self.merchant_name = config.get("REAP_MERCHANT_NAME", "Dutch Colony Coffee Co.")
        self.merchant_domain = config.get("REAP_MERCHANT_DOMAIN", "order.dutchcolony.sg")
        self.email = config.get("REAP_EMAIL", "")
        self.enrollment_id = config.get("REAP_ENROLLMENT_ID", "")
        self.return_url = config.get("REAP_RETURN_URL", "")
        try:
            self.shipping_address = json.loads(config["REAP_SHIPPING_ADDRESS_JSON"]) if config.get("REAP_SHIPPING_ADDRESS_JSON") else None
        except ValueError as exc:
            raise ValueError("REAP_SHIPPING_ADDRESS_JSON must be valid JSON") from exc
        self.ready = (all((config.get("REAP_API_KEY"), self.product_id, self.email,
                           self.enrollment_id, self.return_url)) and
                      urlparse(self.return_url).scheme == "https")
        self.client = client or (ReapClient(config["REAP_API_KEY"]) if self.ready else None)

    def select_and_price(self, mandate):
        if not self.ready:
            raise AgentError("sandbox_unconfigured", "Reap sandbox setup is incomplete.", 503)
        if not merchant_allowed(self.merchant_domain, mandate.allowed_merchant_domains):
            raise AgentError("merchant_blocked", "Merchant is outside the mandate.")
        try:
            enrollment = self.client.get_enrollment(self.enrollment_id)
            if enrollment.get("status") != "ACTIVE":
                raise AgentError("enrollment_inactive", "Reap enrollment is not active.")
            search = self.client.search_products(self.product_query)
            match = next((item for item in search.get("products", [])
                          if item.get("id") == self.product_id
                          and item.get("merchant", {}).get("name") == self.merchant_name
                          and item.get("available") is True), None)
            if not match:
                raise AgentError("product_unavailable", "Configured Reap product was not found at the intended merchant.")
            details = self.client.product_details(self.product_id)
            product = next((item for item in details.get("products", [])
                            if item.get("id") == self.product_id), None)
            variant = product.get("defaultVariant") if product else None
            if not variant or variant.get("available") is not True:
                raise AgentError("variant_unavailable", "Default Reap variant is unavailable.")
            if variant.get("requiresShipping") and not self.shipping_address:
                raise AgentError("address_required", "A configured shipping address is required for this quote.")
            quote = self.client.create_quote(variant["id"], self.email, str(uuid4()),
                                             self.shipping_address)
            final = quote["amountBreakdown"]["finalAmount"]
            expires = datetime.fromisoformat(quote["expiresAt"].replace("Z", "+00:00"))
            if expires <= datetime.now(timezone.utc):
                raise AgentError("quote_expired", "Reap quote expired before proposal.")
            return {"product_id": self.product_id, "product_name": product["name"],
                    "merchant_domain": self.merchant_domain, "currency": final["currency"],
                    "total_minor": minor_units(final["amount"]),
                    "quote_id": quote["id"], "quote_expires_at": quote["expiresAt"]}
        except (ReapAPIError, KeyError, ValueError) as exc:
            raise AgentError("reap_quote_failed", "Reap could not produce a verified final quote.", 503) from exc

    def verify_quote(self, order):
        expires = datetime.fromisoformat(order["quote_expires_at"].replace("Z", "+00:00"))
        if expires <= datetime.now(timezone.utc):
            raise AgentError("quote_expired", "The quoted price expired; a new proposal is required.")
        try:
            quote = self.client.get_quote(order["quote_id"])
            final = quote["amountBreakdown"]["finalAmount"]
            if final["currency"] != order["currency"] or minor_units(final["amount"]) != order["total_minor"]:
                raise AgentError("quote_changed", "The final total changed; a new approval is required.")
            if self.client.get_enrollment(self.enrollment_id).get("status") != "ACTIVE":
                raise AgentError("enrollment_inactive", "Reap enrollment is not active.")
        except (ReapAPIError, KeyError, ValueError) as exc:
            raise AgentError("reap_quote_failed", "Reap quote could not be verified.", 503) from exc

    def checkout(self, order):
        result = self.client.create_checkout(order["quote_id"], self.enrollment_id,
                                             self.return_url, order["order_id"])
        checkout_id = result["id"]
        if result["status"] == "COMPLETED":
            confirmed = self.client.get_checkout(checkout_id)
            amount = confirmed.get("finalAmount", {})
            return {"status": "COMPLETED", "checkout_id": checkout_id,
                    "order_id": confirmed.get("orderId"),
                    "final_minor": minor_units(amount.get("amount")) if amount else None}
        if result["status"] in ("REQUIRES_ACTION", "PROCESSING"):
            action = result.get("nextAction") or {}
            approval_url = action.get("url")
            if approval_url and urlparse(approval_url).scheme != "https":
                raise AgentError("invalid_approval_url", "Reap returned an invalid approval URL.", 503)
            return {"status": result["status"], "checkout_id": checkout_id,
                    "approval_url": approval_url}
        return {"status": result["status"], "checkout_id": checkout_id}


class AgentService:
    def __init__(self, db_path: str | Path, event_token: str, mode="mock",
                 now=None, sandbox_config=None, reap_client=None):
        if mode not in ("mock", "reap_sandbox"):
            raise ValueError("REAP_MODE must be mock or reap_sandbox")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.event_token = event_token
        self.adapter = (MockCheckout() if mode == "mock" else
                        ReapSandboxCheckout(sandbox_config, reap_client))
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.lock = threading.RLock()
        with self._db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS mandates (
                  user_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS state (
                  user_id TEXT PRIMARY KEY, revision INTEGER NOT NULL DEFAULT 0,
                  armed INTEGER NOT NULL DEFAULT 1, paused INTEGER NOT NULL DEFAULT 0,
                  latest_event TEXT, message TEXT NOT NULL DEFAULT 'Set a mandate to begin.');
                CREATE TABLE IF NOT EXISTS events (
                  event_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS orders (
                  order_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, event_id TEXT UNIQUE NOT NULL,
                  status TEXT NOT NULL, product_id TEXT NOT NULL, product_name TEXT NOT NULL,
                  merchant_domain TEXT NOT NULL, currency TEXT NOT NULL,
                  total_minor INTEGER NOT NULL, mandate_revision INTEGER NOT NULL,
                  purchase_mode TEXT NOT NULL, approval_deadline_at TEXT,
                  checkout_reference TEXT, block_reason TEXT,
                  quote_id TEXT, quote_expires_at TEXT, checkout_id TEXT, approval_url TEXT,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS actions (
                  action_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, body TEXT NOT NULL);
            """)
            db.execute("INSERT OR IGNORE INTO state(user_id) VALUES ('demo-user')")

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.db_path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    def _timestamp(self):
        return self.now().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _bump(db, message):
        db.execute("UPDATE state SET revision=revision+1, message=? WHERE user_id='demo-user'", (message,))

    @staticmethod
    def _mandate(db):
        row = db.execute("SELECT * FROM mandates WHERE user_id='demo-user'").fetchone()
        return (Mandate.model_validate_json(row["body"]), row["revision"]) if row else (None, 0)

    @staticmethod
    def _latest_order(db):
        row = db.execute("SELECT * FROM orders WHERE user_id='demo-user' ORDER BY rowid DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def _usage(self, db):
        day = self.now().astimezone(SGT).date()
        rows = db.execute("SELECT status,total_minor,created_at FROM orders WHERE user_id='demo-user'").fetchall()
        eligible = [row for row in rows if row["status"] in ("succeeded", "submitting", "awaiting_reap_approval", "unknown")
                    and datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")).astimezone(SGT).date() == day]
        return sum(row["total_minor"] for row in eligible), len(eligible)

    def _snapshot(self, db):
        state = db.execute("SELECT * FROM state WHERE user_id='demo-user'").fetchone()
        mandate, mandate_revision = self._mandate(db)
        order = self._latest_order(db)
        spent, count = self._usage(db)
        pet = "paused" if state["paused"] else "idle"
        if not state["paused"] and order:
            pet = {"awaiting_approval": "awaiting_approval", "awaiting_reap_approval": "awaiting_approval",
                   "submitting": "ordering",
                   "succeeded": "success", "cancelled": "idle", "blocked": "blocked",
                   "failed": "error", "unknown": "error"}.get(order["status"], "idle")
        public_order = None
        if order:
            keys = ("order_id", "status", "product_id", "product_name", "merchant_domain",
                    "currency", "total_minor", "approval_deadline_at", "purchase_mode",
                    "checkout_reference", "block_reason", "approval_url")
            public_order = {key: order[key] for key in keys}
        return {"schema_version": "1.0", "user_id": "demo-user",
                "revision": state["revision"], "updated_at": self._timestamp(),
                "mandate_revision": mandate_revision,
                "mandate": mandate.model_dump(mode="json") if mandate else None,
                "pet_state": pet,
                "latest_focus_event": json.loads(state["latest_event"]) if state["latest_event"] else None,
                "order": public_order, "message": state["message"], "paused": bool(state["paused"]),
                "daily_spend_minor": spent, "daily_order_count": count,
                "purchase_mode": self.adapter.mode}

    def snapshot(self):
        with self.lock, self._db() as db:
            return self._snapshot(db)

    def save_mandate(self, mandate: Mandate):
        if any(domain != domain.strip().lower() or "/" in domain or not domain
               for domain in mandate.allowed_merchant_domains):
            raise AgentError("invalid_merchant", "Merchant domains must be lowercase hostnames.", 422)
        with self.lock, self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM orders WHERE status IN ('submitting','awaiting_reap_approval','unknown') LIMIT 1").fetchone():
                raise AgentError("checkout_in_progress", "Resolve the Reap checkout before changing the mandate.")
            _, revision = self._mandate(db)
            revision += 1
            db.execute("INSERT INTO mandates(user_id,revision,body) VALUES (?,?,?) "
                       "ON CONFLICT(user_id) DO UPDATE SET revision=excluded.revision, body=excluded.body",
                       (mandate.user_id, revision, mandate.model_dump_json()))
            db.execute("UPDATE orders SET status='blocked', block_reason='Mandate changed; approve a new proposal.', updated_at=? "
                       "WHERE user_id='demo-user' AND status='awaiting_approval'", (self._timestamp(),))
            self._bump(db, "Mandate saved. Awaiting an eligible focus event.")
            db.commit()
            return self._snapshot(db)

    def _eligible(self, db, mandate, candidate):
        if not mandate.enabled:
            raise AgentError("mandate_disabled", "Purchasing is disabled by the mandate.")
        if not merchant_allowed(candidate["merchant_domain"], mandate.allowed_merchant_domains):
            raise AgentError("merchant_blocked", "Merchant is outside the mandate.")
        if candidate["currency"] != mandate.currency:
            raise AgentError("currency_blocked", "Currency is outside the mandate.")
        if candidate["total_minor"] > mandate.max_order_minor:
            raise AgentError("order_cap", "Final total exceeds the order cap.")
        spent, count = self._usage(db)
        if spent + candidate["total_minor"] > mandate.daily_budget_minor:
            raise AgentError("daily_budget", "Daily budget would be exceeded.")
        if count >= mandate.max_orders_per_day:
            raise AgentError("daily_orders", "Daily order count would be exceeded.")
        active = db.execute("SELECT 1 FROM orders WHERE status IN ('awaiting_approval','awaiting_reap_approval','submitting','unknown') LIMIT 1").fetchone()
        if active:
            raise AgentError("active_order", "An order is already active or needs resolution.")
        last = db.execute("SELECT updated_at FROM orders WHERE status='succeeded' ORDER BY updated_at DESC LIMIT 1").fetchone()
        if last and self.now() < datetime.fromisoformat(last["updated_at"].replace("Z", "+00:00")) + timedelta(seconds=mandate.cooldown_seconds):
            raise AgentError("cooldown", "The purchase cooldown has not expired.")

    def receive_event(self, event: FocusEvent, token: str | None):
        if not self.event_token or not token or not secrets.compare_digest(token, self.event_token):
            raise AgentError("unauthorized", "Invalid event token.", 401)
        body = event.model_dump(mode="json")
        with self.lock, self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT body FROM events WHERE event_id=?", (str(event.event_id),)).fetchone()
            if existing:
                if json.loads(existing["body"]) != body:
                    raise AgentError("event_id_conflict", "Event ID was reused with different content.")
                db.commit()
                return {"accepted": True, "duplicate": True}
            db.execute("INSERT INTO events VALUES (?,?,?)",
                       (str(event.event_id), event.user_id, json.dumps(body)))
            db.execute("UPDATE state SET latest_event=? WHERE user_id='demo-user'", (json.dumps(body),))
            age = (self.now() - event.observed_at.astimezone(timezone.utc)).total_seconds()
            if not -5 <= age <= 15:
                message = "Ignored an event outside the allowed time window."
            elif event.signal_quality != "good" or event.state == "unknown":
                message = "Signal is insufficient for a purchase decision."
            elif event.state == "focused":
                db.execute("UPDATE state SET armed=1 WHERE user_id='demo-user'")
                message = "Focus recovered; ready for a future dip."
            else:
                state = db.execute("SELECT armed,paused FROM state WHERE user_id='demo-user'").fetchone()
                mandate, mandate_revision = self._mandate(db)
                if state["paused"] or not state["armed"]:
                    message = "Purchasing is paused or this focus episode was handled."
                elif not mandate:
                    message = "Set a purchasing mandate before a focus dip can propose an order."
                else:
                    try:
                        candidate = self.adapter.select_and_price(mandate)
                        self._eligible(db, mandate, candidate)
                        order_id = str(uuid4())
                        stamp = self._timestamp()
                        db.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                   (order_id, event.user_id, str(event.event_id), "awaiting_approval",
                                    candidate["product_id"], candidate["product_name"],
                                    candidate["merchant_domain"], candidate["currency"],
                                    candidate["total_minor"], mandate_revision, self.adapter.mode,
                                    None, None, None, candidate.get("quote_id"),
                                    candidate.get("quote_expires_at"), None, None, stamp, stamp))
                        db.execute("UPDATE state SET armed=0 WHERE user_id='demo-user'")
                        message = ("Mock product proposed. Approval is required before checkout." if
                                   self.adapter.mode == "mock" else
                                   "Reap quote obtained. Approval is required before checkout.")
                    except AgentError as exc:
                        message = exc.message
            self._bump(db, message)
            db.commit()
            return {"accepted": True, "duplicate": False}

    def act(self, action: Action):
        with self.lock, self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT body FROM actions WHERE action_id=?", (str(action.action_id),)).fetchone()
            if existing:
                if json.loads(existing["body"]) != action.model_dump(mode="json"):
                    raise AgentError("action_id_conflict", "Action ID was reused with different content.")
                db.commit()
                return self._snapshot(db)
            if action.action in ("approve", "cancel") and action.order_id is None:
                raise AgentError("order_required", "order_id is required for approve or cancel.", 422)
            order = None
            if action.order_id:
                row = db.execute("SELECT * FROM orders WHERE order_id=? AND user_id=?",
                                 (str(action.order_id), action.user_id)).fetchone()
                order = dict(row) if row else None
            if action.action in ("approve", "cancel") and not order:
                raise AgentError("order_missing", "Order was not found.", 404)
            if action.action == "approve":
                if order["status"] != "awaiting_approval":
                    raise AgentError("order_not_pending", "This order cannot be approved now.")
                state = db.execute("SELECT paused FROM state WHERE user_id='demo-user'").fetchone()
                mandate, mandate_revision = self._mandate(db)
                if state["paused"] or not mandate or order["mandate_revision"] != mandate_revision:
                    raise AgentError("mandate_changed", "Mandate changed or purchasing is paused.")
                self._eligible_for_approval(db, mandate, order)
                if self.adapter.mode == "reap_sandbox":
                    self.adapter.verify_quote(order)
                db.execute("UPDATE orders SET status='submitting', updated_at=? WHERE order_id=?",
                           (self._timestamp(), order["order_id"]))
                message = "Opening the checkout."
            elif action.action == "cancel":
                if order["status"] != "awaiting_approval":
                    raise AgentError("too_late", "This order is no longer cancellable.")
                db.execute("UPDATE orders SET status='cancelled', updated_at=? WHERE order_id=?",
                           (self._timestamp(), order["order_id"]))
                message = "Order proposal cancelled."
            else:
                paused = action.action == "pause"
                if paused and db.execute("SELECT 1 FROM orders WHERE status IN ('submitting','awaiting_reap_approval','unknown') LIMIT 1").fetchone():
                    raise AgentError("checkout_in_progress", "A Reap checkout is already in progress; resolve it before pausing.")
                db.execute("UPDATE state SET paused=? WHERE user_id='demo-user'", (int(paused),))
                if paused:
                    db.execute("UPDATE orders SET status='cancelled', updated_at=? "
                               "WHERE status='awaiting_approval'", (self._timestamp(),))
                message = "Purchasing paused." if paused else "Purchasing resumed."
            db.execute("INSERT INTO actions VALUES (?,?,?)",
                       (str(action.action_id), action.user_id, action.model_dump_json()))
            self._bump(db, message)
            db.commit()
            if action.action != "approve":
                return self._snapshot(db)

        # Submission intent is durable before the external call. Never retry a
        # timeout automatically: an uncertain checkout may already have charged.
        try:
            result = self.adapter.checkout(order)
            if result["status"] == "COMPLETED" and result.get("final_minor") == order["total_minor"] and result.get("order_id"):
                status, reason = "succeeded", None
            elif result["status"] == "REQUIRES_ACTION" and result.get("approval_url"):
                status, reason = "awaiting_reap_approval", None
            elif result["status"] == "FAILED":
                status, reason = "failed", "Reap checkout failed."
            else:
                status, reason = "unknown", "Checkout outcome needs reconciliation."
        except ReapAPIError as exc:
            result = {}
            status = "unknown" if exc.status == 0 else "failed"
            reason = "Checkout outcome is uncertain; resolve manually." if status == "unknown" else "Reap rejected checkout."
        except Exception:
            result = {}
            status, reason = "unknown", "Checkout outcome is uncertain; resolve manually."
        with self.lock, self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE orders SET status=?, checkout_reference=?, checkout_id=?, approval_url=?, block_reason=?, updated_at=? WHERE order_id=? AND status='submitting'",
                       (status, result.get("order_id"), result.get("checkout_id"),
                        result.get("approval_url"), reason, self._timestamp(), order["order_id"]))
            self._bump(db, "Checkout completed." if status == "succeeded" else
                       "Approve on Reap's hosted page." if status == "awaiting_reap_approval" else reason)
            db.commit()
            return self._snapshot(db)

    def refresh_order(self, order_id):
        if self.adapter.mode != "reap_sandbox":
            raise AgentError("not_sandbox", "Only Reap sandbox orders can be refreshed.", 403)
        with self.lock, self._db() as db:
            row = db.execute("SELECT * FROM orders WHERE order_id=? AND user_id='demo-user'",
                             (str(order_id),)).fetchone()
            if not row or not row["checkout_id"]:
                raise AgentError("checkout_missing", "Checkout is not available for this order.", 404)
            order = dict(row)
        try:
            result = self.adapter.client.get_checkout(order["checkout_id"])
        except ReapAPIError as exc:
            raise AgentError("reap_status_failed", "Reap checkout status is unavailable.", 503) from exc
        status = {"COMPLETED": "succeeded", "FAILED": "failed",
                  "EXPIRED": "failed", "REQUIRES_ACTION": "awaiting_reap_approval",
                  "PROCESSING": "unknown"}.get(result.get("status"), "unknown")
        reference = result.get("orderId") if status == "succeeded" else None
        amount = result.get("finalAmount") or {}
        if status == "succeeded":
            try:
                amount_matches = (amount.get("currency") == order["currency"] and
                                  minor_units(amount.get("amount")) == order["total_minor"])
            except ValueError:
                amount_matches = False
            if not reference or not amount_matches:
                status = "unknown"
                reference = None
        with self.lock, self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE orders SET status=?, checkout_reference=?, block_reason=?, updated_at=? WHERE order_id=? AND status IN ('awaiting_reap_approval','unknown','submitting')",
                       (status, reference,
                        "Checkout outcome needs manual resolution." if status == "unknown" else None,
                        self._timestamp(), order["order_id"]))
            self._bump(db, "Reap checkout status refreshed.")
            db.commit()
            return self._snapshot(db)

    def _eligible_for_approval(self, db, mandate, order):
        if not mandate.enabled:
            raise AgentError("mandate_disabled", "Purchasing is disabled.")
        if not merchant_allowed(order["merchant_domain"], mandate.allowed_merchant_domains):
            raise AgentError("merchant_blocked", "Merchant is outside the mandate.")
        if order["currency"] != mandate.currency:
            raise AgentError("currency_blocked", "Currency is outside the mandate.")
        if order["total_minor"] > mandate.max_order_minor:
            raise AgentError("order_cap", "Final total exceeds the order cap.")
        spent, count = self._usage(db)
        if spent + order["total_minor"] > mandate.daily_budget_minor or count >= mandate.max_orders_per_day:
            raise AgentError("daily_limit", "Daily purchase limit would be exceeded.")
        last = db.execute("SELECT updated_at FROM orders WHERE status='succeeded' ORDER BY updated_at DESC LIMIT 1").fetchone()
        if last and self.now() < datetime.fromisoformat(last["updated_at"].replace("Z", "+00:00")) + timedelta(seconds=mandate.cooldown_seconds):
            raise AgentError("cooldown", "The purchase cooldown has not expired.")
