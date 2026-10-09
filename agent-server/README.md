# Tempo agent server

Local FastAPI service on `127.0.0.1:8002`. It accepts aggregate focus events
from `bci-server/`, stores purchasing mandates and orders in SQLite, and
exposes state for the browser app. The default `mock` mode demonstrates an
explicitly simulated checkout. `reap_sandbox` uses Reap's documented search,
product details, quote, hosted approval, and checkout status APIs after its
configuration is complete. It never falls back to mock after a sandbox failure.

## Start

```powershell
cd agent-server
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:BCI_EVENT_TOKEN = 'choose-a-random-local-token'
.\scripts\Start-Agent.ps1
```

Set the same `BCI_EVENT_TOKEN` in the BCI service terminal and restart it.
The BCI publisher targets `http://127.0.0.1:8002/v1/focus-events` by default.
Only the local services should reach this development API. The SQLite database
in `data/` and `.env` files are git-ignored.

## Flow

1. `PUT /v1/mandate` stores explicit user limits and consent.
2. `POST /v1/focus-events` requires `X-Event-Token`. It deduplicates event IDs,
   ignores stale, future, poor-quality, and unknown signals, and proposes at
   most one mock order per focus episode.
3. `GET /v1/state?user_id=demo-user` gives the current mandate, aggregate
   signal, proposal, order result, and daily usage.
4. `POST /v1/actions` accepts `approve`, `cancel`, `pause`, and `resume` with
   an idempotent `action_id`. Approval is required for every order. Changes to
   the mandate invalidate an outstanding proposal. Mock checkout results are
   labelled `mock`; an uncertain checkout remains `unknown` for resolution.
   A Reap checkout that requires hosted approval exposes `order.approval_url`.
   After the user returns, `POST /v1/orders/{order_id}/refresh` reads its
   authoritative status and merchant order reference from Reap.

Money is stored in integer SGD cents. Daily limits use the Singapore date.
The local mock catalogue uses the current menu prices for Iced Black and Iced
Latte on `order.dutchcolony.sg`. These are demo figures without delivery,
tax, or add-ons; they do **not** assert that Reap supports those products or
that a Reap quote would have the same total.
The agent's purchasing policy is deterministic and does not ask an LLM to
authorize spending.

## Reap sandbox integration boundary

This adapter follows [Reap Agentic Payments](https://docs.reap.global/agentic-payments/overview).
The Reap Protocol SDK is a separate product. The documented flow is external-card
enrollment on a Reap-hosted page,
product search/details, an expiring merchant quote, checkout with a hosted
approval, and a checkout status read. `src/reap_client.py` implements those
HTTP operations against `https://sg.sandbox.api.reap.global` with the
`2025-02-14` version and idempotency keys on creation requests. The test card
is entered only on Reap's hosted page; this server has no card-number field.
The API key is supplied via `REAP_API_KEY` in the process environment, never
in source or `.env.example`. Set `REAP_MODE=reap_sandbox` only after providing
`REAP_EMAIL`, an active `REAP_ENROLLMENT_ID`, and an HTTPS `REAP_RETURN_URL`.
If the quote requires delivery, set `REAP_SHIPPING_ADDRESS_JSON` server-side
with the shipping fields required by Reap. The product ID and merchant fields
are documented in `.env.example`. `GET /health` reports whether the sandbox
configuration is complete without exposing these values.

To enroll an external test card, run `python -m scripts.enroll_reap` after
setting the key, email, HTTPS return URL, and a stable
`REAP_ENROLLMENT_IDEMPOTENCY_KEY` UUID. Reuse that key if the request times out.
Open the returned Reap-hosted
card-entry link yourself and enter the test card there. Confirm the enrollment
becomes `ACTIVE`, then set its ID as `REAP_ENROLLMENT_ID`. Card data never goes
through Tempo. Reap's hosted approval may be required again for each checkout.

A read-only sandbox catalogue search on 9 October 2026 found Dutch Colony
`Coffee: Brew On-The-Go`, with an available S$35 default variant. It did not
return Iced Black in the searches used. The final quote may add shipping or
tax and must fit the user's mandate. The merchant states this product needs
four hours of preparation, so Tempo must present it as a planned coffee order.

Tempo's `PUT /v1/mandate` is a local spending policy. Reap also describes a
separate mandate resource in its [one-time purchase guide](https://docs.reap.global/agentic-payments/one-time-purchases),
but the published Agentic Payments API reference currently lists a read endpoint
for mandates and no create endpoint, and its checkout request takes a quote ID
and enrollment ID without a mandate ID. We therefore do not claim that the
local policy creates or updates a Reap mandate. Confirm mandate provisioning
with Reap before claiming full end-to-end mandate coverage.

The one-time guide describes quoting a merchant checkout URL when the merchant
domain is allowlisted. Reap's [FAQ](https://docs.reap.global/agentic-payments/faq)
says that custom checkout URLs are enabled per account and may not yet be live.
The linked Dutch Colony item page is not itself a checkout URL. Tempo uses the
catalogue variant flow until Reap confirms that this merchant and account can
use a constructed checkout URL.

Read [Reap's setup guide](https://docs.reap.global/agentic-payments/setup)
and [one-time purchase flow](https://docs.reap.global/agentic-payments/one-time-purchases).
The Reap adapter is tested with fake API responses. A real sandbox quote,
enrollment, hosted approval, and checkout have not yet been exercised.

## Buildathon demo readiness

The Reap × 65labs buildathon page lists `dutchcolony.sg` in the Singapore
coffee category, while warning that a listed merchant does not guarantee a
working sandbox checkout. The event requires an Agentic Payments or Kwal
sandbox flow; Tempo's local `mock` mode is only a development aid. Checkout
simulation creates no real merchant purchase or delivery.

Before presenting the payment integration, complete the external-card
enrollment on Reap's hosted page, obtain a final sandbox quote for an
available item, show the Tempo spending limit and per-order approval, follow
Reap's hosted approval, and refresh the checkout to show its final status and
merchant order reference. If the Reap flow fails, show the explicit blocked or
unknown state rather than describing a mock order as a Reap checkout.

The event page asks for a demo recording of at most three minutes, a source
repository link, and a brief integration explanation. Its 9 October 2026
project submission deadline is 9:00 pm Singapore time. The team also needs to
confirm that the repository has an approved open-source licence before
submission; this PR does not choose one on behalf of the team.

## Tests

From `agent-server/`, install `requirements-dev.txt` and run
`python -m pytest tests -q`. On Windows sandboxed shells, pass
`--basetemp=data/pytest` after
creating `data/`. The tests cover authorization, signal gating, event/action
idempotency, mandate changes, cooldown persistence, and Reap request shaping.
