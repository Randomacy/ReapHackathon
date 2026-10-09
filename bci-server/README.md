# Tempo BCI service

Runs on the same Windows PC as the Muse 2 bridge. The bridge sends four EEG
channels (`TP9, AF7, AF8, TP10`) as `/muse/eeg` and acceleration as
`/muse/acc` over OSC UDP to `127.0.0.1:7000`. This service listens there in
live mode and posts aggregate focus events to the Next.js app at
`127.0.0.1:3000/api/v1/focus-events`.
Only one process can bind OSC port 7000, so close the reference classifier GUI
before starting live mode.

The focus score is an **experimental heuristic**, not a validated attention or
fatigue measurement. It uses Welch beta/(alpha+theta) power on four-second EEG
windows. After a 30-second individual baseline, the ratio is normalized so the
baseline is approximately 0.5. A score below 0.35 for 30 seconds emits one
`focus_dip` per episode. Five seconds of recovery re-arms it. Missing packets,
bad channel values, a flat channel, excessive motion, and insufficient baseline
data return `unknown`; they never become a focus dip. Defaults can be changed
with the variables in `.env.example` and need tuning for the actual wearer.

## Install

Use a Python environment with compatible `numpy` and `scipy`, then:

```powershell
cd bci-server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock.txt
```

Set `BCI_EVENT_TOKEN` to the same value as the Next.js server. Optionally set
`BCI_APP_URL` (default `http://127.0.0.1:3000`). Both APIs should bind to
loopback on this one PC. The `.env.example` file lists all configuration but
is not loaded automatically; set the variables in the terminal before launch.

## Simulator first

```powershell
$env:BCI_EVENT_TOKEN = 'your-local-event-token'
.\scripts\Start-BCI.ps1 -Mode simulator
```

In another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8001/v1/demo/trigger -Method Post -ContentType application/json -Body '{"state":"focus_dip"}'
Invoke-RestMethod http://127.0.0.1:8001/v1/state
```

`focused`, `focus_dip`, and `unknown` are accepted demo states. All simulator
events have `source=simulator`. The publisher retries delivery up to three
times with the **same event ID**. Delivery failure is logged; the BCI API does
not buy anything or fabricate agent success.

## Live Muse 2

The Windows release bridge and its required `libmuse.dll` are staged into
`bridge/local/`, which is git-ignored. Both files have already been staged on
this machine from a successful build of this repo's bridge source. If you move
or delete them, run:

```powershell
.\scripts\Stage-Bridge.ps1
```

In separate terminals, with the headband powered on:

```powershell
.\scripts\Start-Bridge.ps1
```

```powershell
$env:BCI_EVENT_TOKEN = 'your-local-event-token'
.\scripts\Start-BCI.ps1 -Mode live
```

Wait for `[Status] Connected!` in the bridge terminal. `GET /health` reports
whether EEG packets are arriving. `POST /v1/demo/trigger` is disabled in live
mode. If the bridge disconnects, restart it; the BCI service emits `unknown`
when packets stop.

## Local signal visualizer

With the BCI service running in either mode, open
**http://127.0.0.1:8001/visualizer** in a browser. In live mode, it shows the
four raw EEG traces, packet age and rate, theta/alpha/beta power, engagement
ratio, baseline progress, focus score, and dip hold time. Allow at least four
seconds for the EEG window and another 30 seconds for the personal baseline.
Simulator mode has clearly labelled state buttons and no pretend EEG waveform.

The page reads `GET /v1/visualization`, a local diagnostic endpoint containing
a decimated four-second EEG buffer. Keep the service bound to `127.0.0.1` as
the provided launcher does. This diagnostic data is **never included** in the
focus event sent to the Next.js app. The visualizer has no purchase controls.

## Bridge source and binary handling

`bridge/windows/` contains only the bridge's C++ source and Visual Studio
project selected from the local Muse2Demo reference. It keeps the reference
bridge's four-channel preset and OSC format. To rebuild, run
`scripts/Build-Bridge.ps1`; it uses the SDK installed in the reference folder,
leaves its build output ignored, and stages that build in `bridge/local/`.
`Stage-Bridge.ps1` uses the repo's build output if available, or the existing
reference build otherwise. The bridge executable, SDK DLL, headers,
libraries, PDBs, and raw EEG recordings are not committed. Verify your
applicable Muse SDK terms before distributing a binary bundle.

## API

- `GET /health`: mode and connection state.
- `GET /v1/state`: latest aggregate focus event and connection state.
- `GET /visualizer`: local browser diagnostic dashboard.
- `GET /v1/visualization`: local, no-cache diagnostic data for that dashboard.
- `POST /v1/demo/trigger`: simulator-only event trigger.

The service posts v1 focus events to the Next.js app's `/api/v1/focus-events` with
`X-Event-Token`. Raw EEG is never sent to the agent. `source` is `muse2` or
`simulator`. All event timestamps are UTC. Each transition to a new state or
signal condition gets a UUID. The BCI service does not call Reap.

## Tests

```powershell
python -m pytest tests -q
```

The signal tests cover baseline, sustained dips, recovery, dropout, and bad
samples. The API tests cover simulator labelling and live-mode restrictions;
the publisher test checks retrying the same event ID.
