import httpx
import pytest

from src.reap_client import BASE_URL, ReapClient, minor_units


def test_documented_sandbox_headers_and_no_card_data():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "enrollment-test", "status": "REQUIRES_ACTION"})

    client = ReapClient("test-only-key", transport=httpx.MockTransport(respond))
    response = client.create_external_enrollment("test@example.com", "https://example.com/return", "fixed-key")
    assert response["id"] == "enrollment-test"
    request = requests[0]
    assert str(request.url) == BASE_URL + "/agentic/enrollments"
    assert request.headers["Reap-Version"] == "2025-02-14"
    assert request.headers["Idempotency-Key"] == "fixed-key"
    assert request.headers["Authorization"] == "Bearer test-only-key"
    assert b"cardNumber" not in request.content and b"cvv" not in request.content


def test_exact_money_conversion():
    assert minor_units("6.50") == 650
    with pytest.raises(ValueError):
        minor_units("6.501")
