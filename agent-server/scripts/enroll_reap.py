"""Create an EXTERNAL enrollment, then enter the card on Reap's hosted page.

Requires REAP_API_KEY, REAP_EMAIL, and an HTTPS REAP_RETURN_URL in the
process environment. This script never reads or accepts card details.
"""

import os
from src.reap_client import ReapClient


email = os.environ["REAP_EMAIL"]
return_url = os.environ["REAP_RETURN_URL"]
if not return_url.startswith("https://"):
    raise SystemExit("REAP_RETURN_URL must be HTTPS")
response = ReapClient(os.environ["REAP_API_KEY"]).create_external_enrollment(
    email, return_url, os.environ["REAP_ENROLLMENT_IDEMPOTENCY_KEY"])
print("Enrollment ID:", response["id"])
print("Enrollment status:", response["status"])
print("Open Reap's hosted card-entry page:", response["nextAction"]["url"])
