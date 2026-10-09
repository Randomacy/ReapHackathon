"""Documented Reap Agentic Payments sandbox operations.

Only the Reap-hosted enrollment page should receive test card details. This
client accepts an enrollment ID and never accepts a card number or CVC.
"""

from decimal import Decimal, InvalidOperation
import httpx


BASE_URL = "https://sg.sandbox.api.reap.global"
VERSION = "2025-02-14"


class ReapAPIError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(f"Reap sandbox request failed: HTTP {status}, {code}")


def minor_units(amount):
    """Convert Reap's major-unit amount to exact SGD cents."""
    try:
        cents = Decimal(str(amount)) * 100
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid Reap amount") from None
    if not cents.is_finite() or cents < 0 or cents != cents.to_integral_value():
        raise ValueError("Invalid Reap amount precision")
    return int(cents)


class ReapClient:
    def __init__(self, api_key, transport=None):
        if not api_key:
            raise ValueError("REAP_API_KEY is required")
        self.api_key = api_key
        self.transport = transport

    def _request(self, method, path, *, body=None, idempotency_key=None, simulate=False):
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Reap-Version": VERSION, "Accept": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if simulate:
            headers["X-Simulate-Checkout"] = "COMPLETED"
        try:
            with httpx.Client(base_url=BASE_URL, timeout=8.0, transport=self.transport) as client:
                response = client.request(method, path, json=body, headers=headers)
        except httpx.RequestError as exc:
            raise ReapAPIError(0, "network_error") from exc
        if not response.is_success:
            try:
                code = response.json().get("error", {}).get("code", "request_failed")
            except ValueError:
                code = "request_failed"
            raise ReapAPIError(response.status_code, code)
        try:
            return response.json()
        except ValueError:
            raise ReapAPIError(response.status_code, "invalid_response") from None

    def create_external_enrollment(self, owner_email, return_url, key):
        return self._request("POST", "/agentic/enrollments", body={
            "source": "EXTERNAL",
            "owner": {"type": "CLIENT_REFERENCE", "id": "demo-user", "email": owner_email},
            "presentation": {"type": "REDIRECT", "returnUrl": return_url},
        }, idempotency_key=key)

    def get_enrollment(self, enrollment_id):
        return self._request("GET", f"/agentic/enrollments/{enrollment_id}")

    def search_products(self, query, country="SG", currency="SGD"):
        return self._request("POST", "/agentic/products/search", body={
            "query": query, "context": {"country": country, "currency": currency},
            "filters": {"availability": "AVAILABLE_ONLY"},
            "pagination": {"limit": 20},
        })

    def product_details(self, product_id):
        return self._request("POST", "/agentic/products/details",
                             body={"productIds": [product_id]})

    def create_quote(self, variant_id, email, key, shipping_address=None):
        body = {"items": [{"variantId": variant_id, "quantity": 1}], "email": email}
        if shipping_address is not None:
            body["shippingAddress"] = shipping_address
        return self._request("POST", "/agentic/quotes", body=body,
                             idempotency_key=key)

    def get_quote(self, quote_id):
        return self._request("GET", f"/agentic/quotes/{quote_id}")

    def create_checkout(self, quote_id, enrollment_id, return_url, key):
        return self._request("POST", "/agentic/checkouts", body={
            "quoteId": quote_id, "enrollmentId": enrollment_id,
            "presentation": {"type": "REDIRECT", "returnUrl": return_url},
        }, idempotency_key=key, simulate=True)

    def get_checkout(self, checkout_id):
        return self._request("GET", f"/agentic/checkouts/{checkout_id}")
