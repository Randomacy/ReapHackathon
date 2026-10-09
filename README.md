# Tempo

**A focus-aware companion for user-approved coffee purchases.** Tempo combines a Muse 2 EEG pipeline, a live signal visualizer, a companion interface, and Reap Agentic Payments. It turns a sustained change in an experimental focus estimate into a timely coffee suggestion while keeping the person in control of payment. The buildathon experience uses Reap's sandbox, where checkout is simulated.

## Why we built it

Losing momentum during a work session is easy to miss. Tempo explores how an agent can respond to a signal from the physical world while making its evidence and payment authority visible. The experience pairs a quiet nudge with an optional coffee proposal, explicit permission, and spending limits chosen by the user.

## What is in this repository

| Component | Location | Role |
| --- | --- | --- |
| Muse 2 bridge and BCI service | [`bci-server/`](bci-server/README.md) | Streams four EEG channels over local OSC, estimates an experimental focus score, and publishes aggregate focus events. Includes a simulator and live visualizer. |
| Companion app | [`app/`](app/README.md) | Next.js UI, onboarding, order and pending pages, companion overlay, and Electron shell. |
| Reap integration | `app/app/api/reap/` | Server-side sandbox enrollment, fixed Dutch Colony product quote, checkout, and status routes. Card entry and approval use Reap-hosted pages. |

These components make both sides of Tempo's idea visible: the visualizer explains the signal, while the companion and Reap pages present the proposed action and payment approval.

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

## Reap Agentic Payments

Reap's Agentic module provides sandbox card enrollment, merchant pricing, hosted payment approval, checkout, and order status. Tempo's server routes keep the API credential off the client and use a Dutch Colony **Coffee: Brew On-The-Go** product for the sandbox flow. The user enters card details and reviews each charge on pages hosted by Reap. The companion presents the interaction in the context of the person's focus and purchasing preferences.

## What to watch in the demo

1. A Muse 2 streams live EEG into the visualizer, where the wearer can see signal quality, baseline calibration, frequency bands, and the resulting focus estimate.
2. The companion presents a small, understandable nudge rather than a generic shopping chat.
3. Reap prices the coffee product and hosts the user's sandbox payment approval. Tempo shows the resulting order state.

For the product concept, see [`Tempo.md`](Tempo.md). For implementation details, see [`Tempo-Codex-Plan.md`](Tempo-Codex-Plan.md) and the component READMEs.
