"""Local BCI API: Muse OSC input or a labelled simulator."""

from contextlib import asynccontextmanager
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from queue import Empty, Full, Queue
import threading
import time
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

from .focus import Estimate, FocusEstimator

LOG = logging.getLogger("bci")
VERSION = "1.0"
VISUALIZER_FILE = Path(__file__).with_name("visualizer.html")


@dataclass(frozen=True)
class Settings:
    mode: str = "simulator"
    app_url: str = "http://127.0.0.1:3000"
    event_token: str = ""
    user_id: str = "demo-user"
    osc_host: str = "127.0.0.1"
    osc_port: int = 7000
    baseline_seconds: float = 30
    dip_seconds: float = 30
    dip_score: float = 0.35

    @classmethod
    def from_env(cls):
        return cls(
            mode=os.getenv("BCI_MODE", "simulator"),
            app_url=os.getenv("BCI_APP_URL", "http://127.0.0.1:3000"),
            event_token=os.getenv("BCI_EVENT_TOKEN", ""),
            user_id=os.getenv("BCI_USER_ID", "demo-user"),
            osc_host=os.getenv("BCI_OSC_HOST", "127.0.0.1"),
            osc_port=int(os.getenv("BCI_OSC_PORT", "7000")),
            baseline_seconds=float(os.getenv("BCI_BASELINE_SECONDS", "30")),
            dip_seconds=float(os.getenv("BCI_DIP_SECONDS", "30")),
            dip_score=float(os.getenv("BCI_DIP_SCORE", "0.35")),
        )


class DemoTrigger(BaseModel):
    state: str


def make_event(settings: Settings, source: str, estimate: Estimate):
    return {
        "schema_version": VERSION,
        "event_id": str(uuid4()),
        "user_id": settings.user_id,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source,
        "state": estimate.state,
        "focus_score": estimate.score,
        "signal_quality": estimate.quality,
        "sustained_for_ms": estimate.sustained_for_ms,
    }


class Publisher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.queue = Queue(maxsize=32)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=4)

    def submit(self, event):
        try:
            self.queue.put_nowait(event)
        except Full:
            LOG.error("Event queue full; dropped event %s", event["event_id"])

    def _run(self):
        if not self.settings.event_token:
            LOG.warning("BCI_EVENT_TOKEN is unset; events cannot be published")
            return
        url = self.settings.app_url.rstrip("/") + "/api/v1/focus-events"
        with httpx.Client(timeout=2.0) as client:
            while not self.stop_event.is_set() or not self.queue.empty():
                try:
                    event = self.queue.get(timeout=0.2)
                except Empty:
                    continue
                for attempt in range(3):
                    try:
                        response = client.post(url, json=event,
                                               headers={"X-Event-Token": self.settings.event_token})
                        if response.status_code == 202:
                            break
                        # Authentication/validation errors are not transient.
                        if response.status_code in (401, 422):
                            LOG.error("Agent rejected event %s: HTTP %s",
                                      event["event_id"], response.status_code)
                            break
                        response.raise_for_status()
                        LOG.error("Unexpected agent response: HTTP %s", response.status_code)
                        break
                    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                        if attempt == 2:
                            LOG.error("Delivery failed for event %s: %s", event["event_id"], exc)
                        else:
                            time.sleep(0.3 * (2 ** attempt))
                self.queue.task_done()


class BCIService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lock = threading.Lock()
        self.estimator = FocusEstimator(settings.baseline_seconds,
                                        settings.dip_seconds, settings.dip_score)
        self.publisher = Publisher(settings)
        self.latest_event = None
        self.latest_estimate = Estimate("unknown", None, "disconnected", 0,
                                        "disconnected")
        self.score_history = deque(maxlen=120)
        self.connection = "simulated" if settings.mode == "simulator" else "disconnected"
        self.stop_event = threading.Event()
        self.osc_server = None
        self.osc_thread = None
        self.evaluate_thread = None
        self.last_published_condition = None

    def start(self):
        self.publisher.start()
        if self.settings.mode == "live":
            dispatcher = Dispatcher()
            dispatcher.map("/muse/eeg", self.on_eeg)
            dispatcher.map("/muse/acc", self.on_acc)
            self.osc_server = ThreadingOSCUDPServer(
                (self.settings.osc_host, self.settings.osc_port), dispatcher)
            self.osc_thread = threading.Thread(target=self.osc_server.serve_forever, daemon=True)
            self.osc_thread.start()
            self.evaluate_thread = threading.Thread(target=self._evaluate_loop, daemon=True)
            self.evaluate_thread.start()

    def stop(self):
        self.stop_event.set()
        if self.osc_server:
            self.osc_server.shutdown()
            self.osc_server.server_close()
        if self.evaluate_thread:
            self.evaluate_thread.join(timeout=2)
        self.publisher.stop()

    def on_eeg(self, _address, *values):
        with self.lock:
            self.estimator.ingest_eeg(values)

    def on_acc(self, _address, *values):
        with self.lock:
            self.estimator.ingest_acc(values)

    def _evaluate_loop(self):
        while not self.stop_event.wait(0.5):
            with self.lock:
                estimate = self.estimator.evaluate()
                self.connection = estimate.connection
                self.latest_estimate = estimate
                self.score_history.append({
                    "at_ms": int(time.time() * 1000),
                    "score": estimate.score,
                    "quality": estimate.quality,
                })
            condition = (estimate.state, estimate.quality, estimate.connection)
            if condition != self.last_published_condition:
                self.last_published_condition = condition
                event = make_event(self.settings, "muse2", estimate)
                with self.lock:
                    self.latest_event = event
                self.publisher.submit(event)

    def trigger(self, state):
        if state not in ("focused", "focus_dip", "unknown"):
            raise HTTPException(status_code=422, detail={"code": "invalid_state", "message": "Invalid demo state"})
        estimate = Estimate(state, {"focused": 0.75, "focus_dip": 0.28,
                                    "unknown": None}[state],
                            "good" if state != "unknown" else "poor",
                            int(self.settings.dip_seconds * 1000) if state == "focus_dip" else 0,
                            "simulated")
        event = make_event(self.settings, "simulator", estimate)
        with self.lock:
            self.latest_event = event
            self.latest_estimate = estimate
            self.connection = "simulated"
            self.score_history.append({
                "at_ms": int(time.time() * 1000),
                "score": estimate.score,
                "quality": estimate.quality,
            })
        self.publisher.submit(event)
        return event

    def visualization_payload(self):
        with self.lock:
            estimate = self.latest_estimate
            diagnostics = self.estimator.diagnostics()
            return {
                "schema_version": VERSION,
                "mode": self.settings.mode,
                "connection_state": self.connection,
                "state": estimate.state,
                "signal_quality": estimate.quality,
                "focus_score": estimate.score,
                "sustained_for_ms": estimate.sustained_for_ms,
                "dip_score_threshold": self.settings.dip_score,
                "dip_seconds": self.settings.dip_seconds,
                "baseline_seconds": self.settings.baseline_seconds,
                "latest_focus_event": self.latest_event,
                "score_history": list(self.score_history),
                **diagnostics,
            }


def create_app(settings=None):
    settings = settings or Settings.from_env()
    if settings.mode not in ("simulator", "live"):
        raise ValueError("BCI_MODE must be simulator or live")
    service = BCIService(settings)

    @asynccontextmanager
    async def lifespan(_app):
        service.start()
        try:
            yield
        finally:
            service.stop()

    app = FastAPI(title="Tempo BCI", version=VERSION, lifespan=lifespan)
    app.state.service = service

    @app.get("/health")
    def health():
        return {"service": "bci", "version": VERSION, "mode": settings.mode,
                "connection_state": service.connection}

    @app.get("/v1/state")
    def state():
        with service.lock:
            return {"schema_version": VERSION, "latest_focus_event": service.latest_event,
                    "connection_state": service.connection}

    @app.get("/v1/visualization")
    def visualization_data():
        return JSONResponse(service.visualization_payload(),
                            headers={"Cache-Control": "no-store"})

    @app.get("/visualizer")
    def visualizer():
        return FileResponse(VISUALIZER_FILE, media_type="text/html",
                            headers={"Cache-Control": "no-store"})

    @app.post("/v1/demo/trigger")
    def demo_trigger(body: DemoTrigger):
        if settings.mode != "simulator":
            raise HTTPException(status_code=403, detail={"code": "live_mode", "message": "Demo trigger disabled in live mode"})
        return service.trigger(body.state)

    return app


app = create_app()
