# Tempo — Codex implementation plan

## Product and scope

Build a browser-based companion web app that responds to an experimental focus estimate from a Muse 2 EEG pipeline. When a sustained focus dip occurs, the app proposes a coffee purchase through Reap Agentic Payments. The user explicitly approves the exact quoted order on Reap's hosted approval page. All checkout is sandbox-only; no real purchase or delivery is claimed.

The two implementation areas are app/ and bci-server/. `app/` is a single Next.js app containing both the user interface and the server-side agent/payment routes. Build a non-native web app; no Electron or native desktop wrapper. Do not add eye tracking until the core integration works. Muse 2 integration is a stretch goal; a clearly labelled simulator must work first.

Dutch Colony is the intended merchant. Search Reap's Singapore sandbox catalogue first with queries such as `Dutch Colony coffee`, using country `SG`, currency `SGD`, and `AVAILABLE_ONLY`. The endpoint supports a merchant *preference*, not a merchant-only filter, so code must verify the exact returned `merchant.name` before any product can be proposed. Record the confirmed name and actual product/variant IDs in a fixture. Prepared drinks, pickup, delivery timing and in-store inventory are NOT assumed supported. If only beans are supported, label the demo as a coffee-supply purchase, not an immediate drink order.

## Folder ownership — strict boundaries

| Folder | Owner | Contains |
| --- | --- | --- |
| app/ | Companion and agent team | Next.js web app, pet assets, UI, server-side agent/payment routes, local state, tests, package.json and lockfile |
| bci-server/ | Muse/BCI team | Signal acquisition, focus estimator, event publisher, simulator, tests, Python dependency lock/config |
| contracts/ | Integration lead only | Versioned OpenAPI/JSON schemas and fixtures; read-only for component teams |
| integration/ | Integration lead only | Launch scripts, cross-service smoke checks, demo instructions |
| Root files | Integration lead only | README.md, AGENTS.md, .gitignore, ownership and top-level documentation |

Each component must contain its source, tests/, README.md, AGENTS.md and .env.example. BCI also owns recordings/ (ignored by git) and scripts/; the Next.js app owns assets/, app/api/, lib/ and data/ (ignored by git). No team edits another team's folder, root configuration, shared schemas or another team's dependency files. No shared writable package or root lockfile. Root AGENTS.md must document these ownership rules; component AGENTS.md files must repeat the allowed edit boundary.

The integration lead scaffolds the root and contracts first, then freezes contract v1. Contract changes require coordination and a new version; do not silently change field names. Teams may read all folders. Shared schemas are documentation/validation inputs, not a shared runtime library. If using separate branches or worktrees, use feature/app and feature/bci-server; commits stay within the assigned folder. Do not reset or overwrite teammates' work.

## Technology defaults and topology

- Companion and agent app: Next.js + TypeScript, using the App Router. It renders the animated pet, settings and dashboard, and exposes same-origin route handlers for focus events, state, mandate actions and Reap calls. Keep `REAP_API_KEY` server-only; it must never be prefixed `NEXT_PUBLIC_`. Offer a user-clicked button to open the compact view in a separate ordinary browser window. No Electron, native wrapper, transparent OS overlay or guaranteed always-on-top behavior. No ChatGPT Pets integration is required. Optional PWA installation is a stretch goal, not a prerequisite.
- BCI: Python + FastAPI; acquisition adapter selected after checking the team's actual Muse streaming setup. An existing Mind Monitor OSC stream or a verified direct BLE pipeline can be used. Do not assume device addresses, sample rates or library APIs.
- Local state: SQLite or a small file-backed store inside the Next.js server runtime. It holds mandate, focus events, order state, idempotency keys and Reap resource IDs.
- Local ports: Next.js app 3000; BCI API 8001. Each backend defaults to loopback binding.
- BCI posts focus events to the Next.js app. The web UI polls same-origin `/api/v1/state` once per second for authoritative state. The Next.js server owns purchase decisions and order status. BCI never calls Reap and never commands a purchase directly.
- The BCI target URL and event token are environment variables. If services run on different machines, configure a reachable HTTPS URL, narrow CORS and an event token. Do not solve networking through an unauthenticated public tunnel.

### Reap sandbox integration facts

- Base URL: `https://sg.sandbox.api.reap.global`; include `Authorization: Bearer <REAP_API_KEY>` and `Reap-Version: 2025-02-14` on every request.
- Product search: `POST /agentic/products/search`, with a free-text query, `{ country: "SG", currency: "SGD" }`, `AVAILABLE_ONLY`, and a bounded page limit. Read product details or resolve options before quoting when a default variant is insufficient.
- Enrollment happens before a purchase. Use `POST /agentic/enrollments`, redirect the browser to `nextAction.url`, then verify with `GET /agentic/enrollments/:id` that the status is `ACTIVE`. The external-card sandbox flow uses Reap's hosted entry page; test cards and OTP are supplied by Reap's docs. Raw card data never reaches this app.
- Quote: `POST /agentic/quotes` creates merchant pricing. Quotes expire, and only `amountBreakdown.finalAmount` is eligible for approval. Use a unique `Idempotency-Key`.
- Checkout: `POST /agentic/checkouts` accepts an active enrollment and an unexpired quote. Redirect the user to its hosted `nextAction.url`, then on the return route read `GET /agentic/checkouts/:id`; success is only `status: COMPLETED`, with `orderId` and `finalAmount`. For sandbox simulation, send `X-Simulate-Checkout: COMPLETED`; never send that header in production.
- REAP's hosted approval is the actual payment approval. For this MVP, use `each_order` only; no unattended or preauthorized checkout is in scope.

## Contract v1

Use application/json, UTC ISO-8601 timestamps, UUID identifiers, and integer minor units for money. Demo identity is user_id=demo-user. All payloads carry schema_version="1.0". Return errors as {"code":"...","message":"..."}; no stack traces or secrets.

### BCI API (port 8001)

- GET /health: service, version, mode, connection state.
- GET /v1/state: latest focus event or null; device connection state.
- POST /v1/demo/trigger: simulator-only; accepts state=focused|focus_dip|unknown, emits a clearly simulated event through the same publisher as live data. Disabled in live mode unless explicit demo controls are enabled.

### BCI → Next.js: POST /api/v1/focus-events

Header: X-Event-Token, configured identically on the two servers. Return 202 for a valid recorded event, including duplicates; return 422 for malformed payloads, 401 for missing/invalid token.

Example:

```json
{
  "schema_version": "1.0",
  "event_id": "bffcc82e-1f76-4f82-b22c-01cb14f092c6",
  "user_id": "demo-user",
  "observed_at": "2026-10-09T10:00:00Z",
  "source": "simulator",
  "state": "focus_dip",
  "focus_score": 0.28,
  "signal_quality": "good",
  "sustained_for_ms": 30000
}
```

source is simulator|muse2|replay; state is focused|focus_dip|unknown; signal_quality is good|poor|disconnected. focus_score is a heuristic normalized 0–1 value or null, not a clinical measurement. Missing or poor data produces unknown; it must not be interpreted as a focus dip. Agent ignores stale events (default older than 15 seconds), future timestamps beyond a small clock-skew tolerance, unknown states and poor/disconnected quality. Threshold and duration are configurable; defaults are demonstration settings, not validated physiology.

### Browser and BCI → Next.js API (port 3000)

- GET /health: service, version, purchase_mode=mock|reap_sandbox and readiness; never return secrets.
- GET /api/v1/state?user_id=demo-user: current state snapshot below.
- PUT /api/v1/mandate: save the explicit user mandate; return stored mandate and its revision.
- POST /api/v1/actions: {schema_version, user_id, action_id, action, order_id}; action is approve|cancel|pause|resume. order_id is required for approve/cancel. action_id is idempotent. Return updated state. Approval binds to the exact final priced basket.
- POST /api/v1/focus-events: accepts the BCI event contract below with `X-Event-Token` and returns 202 for a recorded event. Implement it as a Next.js route handler, not a separate Python agent service.
- GET /payment/return: the user-facing return route from Reap enrollment and checkout flows. It reads the stored resource ID, fetches the authoritative Reap status server-side, and redirects to the dashboard state.

Mandate fields:

```json
{
  "schema_version": "1.0",
  "user_id": "demo-user",
  "enabled": true,
  "currency": "SGD",
  "max_order_minor": 1000,
  "daily_budget_minor": 2000,
  "max_orders_per_day": 2,
  "cooldown_seconds": 7200,
  "allowed_merchant_names": ["Dutch Colony (exact Reap name pending discovery)"],
  "preferred_product_id": null,
  "approval_mode": "each_order"
}
```

`approval_mode` is fixed to `each_order` for this MVP. Delivery address, if the sandbox needs one, is configured server-side in the Next.js app; it is never guessed by the LLM. Compute daily limits using Asia/Singapore dates. A preferred product must be an actual discovered merchant SKU; null means the agent proposes a suitable available candidate.

State snapshot fields: schema_version, user_id, revision, updated_at, mandate_revision, pet_state, latest_focus_event, order, message, paused. pet_state is idle|focused|focus_dip|thinking|awaiting_approval|ordering|success|blocked|error|paused. order is null or {order_id, status, product_id, product_name, merchant_name, currency, total_minor, purchase_mode, checkout_reference, block_reason}. checkout_reference is null until an actual sandbox response supplies it. Order statuses are proposed|awaiting_approval|submitting|succeeded|cancelled|blocked|failed|unknown. Also expose non-sensitive daily spend/order count to the settings UI.

### Purchase lifecycle

1. Validate focus event, deduplicate event_id, and persist it.
2. Require an enabled mandate, healthy eligible signal, no active order, budget available, and expired cooldown.
3. Discover/select a supported product and obtain the final priced basket through documented Reap operations.
4. Verify the exact Reap merchant name, product, currency and all costs against the mandate. Unknown final costs block submission.
5. Persist the proposal and wait for the user's in-app approval to open the Reap checkout.
6. Immediately before checkout, atomically recheck mandate revision, pause/cancel status, limits and exact basket. Changed price/items require a new proposal and approval.
7. Record submission intent, reserve the budget and call sandbox checkout with a unique provider idempotency key. Redirect to Reap's hosted approval URL. A timeout after submission produces `unknown`, never an automatic second charge. On the return route, reconcile with `GET /agentic/checkouts/:id`.
8. Persist result; consume budget for success, release reservation on definitive failure/cancellation. Keep unknown reservations until resolved. Begin cooldown after successful purchase. A focus episode may produce at most one proposal; re-arm after focused recovery. Cancel/failure must not produce an immediate retry loop.

Daily spend checks include in-flight reservations. Action requests and concurrent focus events must not create duplicate orders. Pause/cancel can stop an order only before submission; never claim a completed purchase was cancelled. Show late cancellation attempts honestly.

## Next.js companion and agent deliverables (app/)

- Animated companion with visibly distinct focused, thinking, waiting, ordering, success and error states. Simple local sprites/CSS are sufficient; polished custom artwork is optional.
- Settings for coffee preference, merchant, budget, cooldown and explicit purchasing consent; save through `/api/v1/mandate`.
- Approval/cancel UI with product name and final total. Keep the pet responsive during API work.
- Display source label: Live Muse / Simulated / Replay. Show "Experimental focus signal"; do not assert fatigue, read thoughts or promise caffeine restores focus.
- Poll state, recover from backend unavailability, and keep interactive controls keyboard-accessible. Fetch a fresh snapshot on reconnect or tab visibility change. Browser components contain no purchase policy or financial secrets.
- The pet lives inside the browser, not over other applications. Browser background throttling must not control payment timing: Next.js route handlers own order state and checkout transitions. Do not submit checkout from a browser timer. `each_order` always waits for explicit approval, including when the tab was hidden or closed.
- Use relative `/api` URLs in the browser. Reap calls, SQLite/file persistence, Reap API keys, and delivery address data stay in server-only modules. For tonight, run the Next.js app and BCI server locally; deployment is outside the MVP. Muse acquisition remains in bci-server/, not browser Bluetooth.
- Implement the server routes and Reap adapter in the Next.js app: `discoverProducts`, `getProductDetails`/`resolveVariant`, `createQuote`, `createEnrollment`, `createCheckout`, and `getCheckout`. Use a labelled mock adapter until Dutch Colony discovery succeeds; never silently switch to mock after an API failure.
- Local fixtures/mock adapter allow all UI states to run before the sandbox flow exists. README documents install, start, mock mode and sandbox integration mode.

## BCI team deliverables

- Implement event publishing and simulator first. Post to the Next.js `/api/v1/focus-events` route, retry the same event_id on delivery failure, and use timeouts and bounded retries.
- Connect the team's verified Muse data source next. Measure a short individual baseline, gate on signal quality, and use a sustained-window experimental heuristic. Document features, normalization and limitations; do not label an unvalidated score as a fatigue classifier.
- Emit unknown on disconnection, poor contact or insufficient data. Do not treat eye closure or motion artifacts as proof of tiredness.
- Publish only aggregate event data to the agent; raw EEG stays local. Recordings are optional, git-ignored and explicitly enabled.
- README documents hardware/stream setup, simulator, live mode, thresholds, source labels and event replay. Replay retains source=replay and uses fresh delivery timestamps with original recording time recorded separately if needed.

## Server-side agent rules

- Implement the contract, persisted mandate, state machine and mock purchase adapter inside `app/` first.
- Validate Dutch Colony discovery, availability, final-price retrieval and sandbox checkout against actual Reap responses. Do not invent endpoint names, response fields, delivery options or supported card flows.
- Use a small adapter interface: `discoverProducts`, `priceBasket`, `createCheckout`, and `getCheckoutStatus`. Real and mock adapters use the same internal result types.
- Use agent reasoning for selecting among available products and explaining tradeoffs. The agent must have a real selection task, such as finding the preferred eligible product or proposing a budget-compatible alternative; avoid describing a fixed webhook as autonomous reasoning.
- Deterministic policy code owns money, SKU validation, exact merchant-name allowlists, consent, concurrency, duplicate prevention and cooldowns. An LLM never overrides it.
- Reap credentials and any required payment data remain server-side. No raw card data in prompts, browser responses, logs, fixtures or git. Follow the documented enrollment, quote, hosted approval and checkout-status sequence.
- Explicit `REAP_MODE=mock|sandbox`. Never switch silently to mock after an API failure. Return clear errors with the active mode visible.

## Build sequence before 9 pm SGT submission

| Time target | Work and checkpoint |
| --- | --- |
| 6:00–6:15 pm | Integration lead freezes contracts and ownership; Next.js team verifies one merchant search immediately |
| 6:15–6:50 pm | Each team builds independently: Next.js pet plus mock server routes, BCI simulator |
| 6:50–7:15 pm | Connect simulator → Next.js → pet; demonstrate consent, trigger, proposal and completion |
| 7:15–7:45 pm | Replace mock checkout with Reap sandbox; BCI team adds live Muse if feasible |
| 7:45–8:10 pm | Exercise failure cases; freeze scope; record working end-to-end demo |
| 8:10–8:40 pm | Capture merchant footage if practical and permitted; edit the three-minute video; prepare submission |
| By 8:45 pm | Submit with buffer before the 9 pm deadline |

If running behind, cut eye tracking, elaborate animations, stablecoin funding, multi-user features and deployment. Keep source labels, real sandbox checkout, purchasing permission and duplicate prevention. Do not spend the remaining time implementing a new wallet stack unless it already works.

## Integration acceptance checks

1. With no mandate, a focus dip produces no checkout.
2. Simulator → Next.js → pet completes a labelled mock flow, then a labelled Reap sandbox flow.
3. `each_order` never creates checkout before in-app approval, and never reports success before Reap checkout status is `COMPLETED`.
4. Repeated event IDs, repeated action IDs and simultaneous events cannot duplicate purchases.
5. Poor/disconnected/stale signal cannot initiate an order. Restart/disconnect produces a truthful UI state.
6. Wrong currency, over-budget total, unavailable SKU or unapproved merchant blocks checkout.
7. Changed prices or revoked consent cannot use an old approval. Cooldown and daily caps survive restart.
8. Checkout timeout produces unknown and does not blindly retry. API failure remains a failure rather than a mock success.

Each owner tests their own critical behavior inside their folder. Integration lead owns the cross-service smoke test. Tests should protect contracts and purchase behavior; do not spend time mirroring trivial rendering code.

## Three-minute demo outline

- 0:00–0:25: Person working with Tempo in a compact browser window and Muse headset; explain the interruption problem.
- 0:25–0:45: Set coffee preference, spending permission and daily cap.
- 0:45–1:15: Show live or explicitly simulated signal and the pet reacting to a focus dip.
- 1:15–2:00: Show agent product choice, policy check, explicit approval, Reap hosted approval page and sandbox result.
- 2:00–2:25: Send a second event; show cooldown prevents another order.
- 2:25–3:00: Physical merchant/product footage if available; close with the biosignal-to-authorized-action architecture. Never imply the simulated checkout fulfilled a physical purchase.

## Prompts to paste into separate Codex sessions

### Integration lead

Read this plan. Scaffold ONLY root files, contracts/ and integration/. Create frozen v1 schemas and fixtures covering focus events, mandates, actions and state snapshots. Write ownership rules in root AGENTS.md. Coordinate the Next.js and BCI owners without editing their implementation folders. Create startup documentation and an end-to-end smoke check after their services exist. Do not launch other agents unless explicitly asked. Report contract changes before making them.

### Next.js companion and agent owner

Read Tempo-Codex-Plan.md and contracts/. You own ONLY app/. Implement the Next.js/TypeScript companion web app, compact pet view, dashboard, settings, approval/cancel controls, source labels, state client, server route handlers, durable order state and Reap adapter described in the plan. Do not add Electron or a native wrapper. Support a user-opened compact browser window and same-origin `/api` routes. Keep Reap credentials and all payment operations in server-only code. Start against fixtures and `REAP_MODE=mock`, then integrate the documented sandbox enrollment, discovery, quote, hosted approval and checkout-status flow. Never invent Reap API fields or claim physical fulfillment. Keep dependencies, assets, tests, README.md and AGENTS.md inside app/. Do not edit root files, contracts/ or teammate folders. If a contract is missing, use the specification here and flag it to the integration lead.

### Muse 2 BCI owner

Read Tempo-Codex-Plan.md and contracts/. You own ONLY bci-server/. Implement FastAPI port 8001, the labelled simulator, quality-gated experimental focus estimate and event publisher to the Next.js app's `/api/v1/focus-events` endpoint on port 3000. Simulator first, then the team's verified Muse stream. Keep dependencies, tests, README.md and AGENTS.md inside bci-server/. Send state events, never buy commands. Do not edit root files, contracts/ or teammate folders. Do not claim clinical fatigue detection.
