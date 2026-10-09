# Tempo

**A focus-aware companion for user-approved coffee purchases.** Tempo combines a local Muse 2 EEG pipeline, a live signal visualizer, a companion interface, and Reap Agentic Payments in a sandbox. A sustained change in an experimental focus estimate can become a coffee suggestion; the person remains responsible for approving a charge. Sandbox checkout does not place a real merchant order or arrange delivery.

## Why we built it

Losing momentum during a work session is easy to miss. Tempo explores whether an agent can respond to a signal from the physical world while making its evidence and payment authority visible. The intended experience is a quiet nudge and an optional coffee proposal, with clear consent and spending limits.

## What is in this repository

| Component | Location | Current role |
| --- | --- | --- |
| Muse 2 bridge and BCI service | [`bci-server/`](bci-server/README.md) | Streams four EEG channels over local OSC, estimates an experimental focus score, and publishes aggregate focus events. Includes a simulator and live visualizer. |
| Companion app | [`app/`](app/README.md) | Next.js UI, onboarding, order and pending pages, companion overlay, and Electron shell. |
| Reap integration | `app/app/api/reap/` | Server-side sandbox enrollment, fixed Dutch Colony product quote, checkout, and status routes. Card entry and approval use Reap-hosted pages. |

The BCI visualizer is working with a live Muse 2 on the development machine. The companion overlay still uses placeholder product data, and its Muse-triggered nudge is not yet wired to the BCI event stream. The Reap routes are a separate fixed-product sandbox flow; they are not yet a complete policy-gated purchase agent. Do not present the placeholder overlay checkout as a completed Reap payment.

## Muse 2 and focus estimation

The local bridge sends TP9, AF7, AF8, and TP10 EEG channels to the BCI service. The service filters the signal, measures theta, alpha, and beta activity in short windows, and calibrates a baseline for the wearer. A configurable sustained dip can emit one aggregate `focus_dip` event; recovery re-arms the detector. Missing data, motion, poor contact, and incomplete calibration produce `unknown` instead of a purchase trigger. Raw EEG stays in the local BCI service and its diagnostic visualizer.

This score is an experimental interaction heuristic, **not** a diagnosis of attention, fatigue, or a medical condition.

## Run locally

### BCI visualizer

On Windows, from `bci-server/`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\scripts\Start-BCI.ps1 -Mode simulator
```

Open <http://127.0.0.1:8001/visualizer>. Simulator mode shows labelled test controls but no EEG waveform. For live data, stop the simulator, power on and pair the Muse 2, then run these in separate terminals:

```powershell
.\scripts\Start-Bridge.ps1
```

```powershell
.\scripts\Start-BCI.ps1 -Mode live
```

Wait for the bridge to connect and for the visualizer's 30-second baseline to finish. The bridge binary and `libmuse.dll` are staged locally and ignored by Git. See the [BCI setup guide](bci-server/README.md) for rebuilding, signal-quality rules, and API details.

### Companion app and Reap sandbox

From `app/`:

```powershell
npm ci
npm run dev
```

Open <http://localhost:3000/onboarding>. `npm run overlay` also starts the Electron companion shell. Reap API calls run in Next.js server routes; supply `REAP_API_KEY`, `REAP_CUSTOMER_EMAIL`, and an HTTPS `REAP_RETURN_URL` in the server environment before exercising hosted enrollment and checkout. A shipping product may require `REAP_SHIPPING_ADDRESS_JSON`; `REAP_ENROLLMENT_ID` can pin a previously activated sandbox enrollment. See the route implementations in `app/app/api/reap/` for the current request flow. Never put the API key or test card in source, browser code, screenshots, or recordings. Enter card details only on Reap's hosted sandbox page.

## Payment and demo boundaries

- Reap's Agentic module supplies the sandbox card enrollment, merchant quote, hosted approval, checkout, and status read. The currently configured product is Dutch Colony **Coffee: Brew On-The-Go**. The companion overlay's iced latte is placeholder data.
- The intended finished flow checks merchant, exact final total, per-order and daily limits, cooldown, and explicit user approval before checkout. Those controls are not fully connected in the current app. A BCI event alone does not complete a Reap order.
- The visualizer can be demonstrated independently of Reap. A Reap sandbox checkout must be shown separately and labelled as simulated unless the full integration has been verified.
- If the checkout outcome is unavailable, show it as pending or uncertain. Do not claim physical fulfillment.

For the product concept, see [`Tempo.md`](Tempo.md). For the detailed implementation plan and component contracts, see [`Tempo-Codex-Plan.md`](Tempo-Codex-Plan.md). Those documents describe intended behavior and may be ahead of the running code.
