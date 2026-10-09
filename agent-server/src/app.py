"""Loopback HTTP API for the Tempo purchase decision engine."""

from dataclasses import dataclass
import os
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .agent import AgentError, AgentService
from .models import Action, FocusEvent, Mandate


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("data/agent.sqlite3")
    event_token: str = ""
    mode: str = "mock"

    @classmethod
    def from_env(cls):
        return cls(Path(os.getenv("AGENT_DB_PATH", "data/agent.sqlite3")),
                   os.getenv("BCI_EVENT_TOKEN", ""),
                   os.getenv("REAP_MODE", "mock"))


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    service = AgentService(settings.db_path, settings.event_token, settings.mode)
    app = FastAPI(title="Tempo Agent", version="1.0")
    app.add_middleware(CORSMiddleware,
                       allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
                       allow_methods=["GET", "PUT", "POST"],
                       allow_headers=["Content-Type"])
    app.state.service = service

    @app.exception_handler(AgentError)
    async def agent_error(_request: Request, exc: AgentError):
        return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        return JSONResponse({"code": "invalid_request", "message": "Request does not match the v1 contract."},
                            status_code=422)

    @app.get("/health")
    def health():
        return {"service": "tempo-agent", "version": "1.0", "purchase_mode": service.adapter.mode,
                "ready": bool(settings.event_token) and
                         (service.adapter.mode == "mock" or service.adapter.ready)}

    @app.get("/v1/state")
    def state(user_id: str = "demo-user"):
        if user_id != "demo-user":
            raise AgentError("unknown_user", "Only demo-user is configured.", 404)
        return service.snapshot()

    @app.put("/v1/mandate")
    def mandate(body: Mandate):
        return service.save_mandate(body)

    @app.post("/v1/focus-events", status_code=202)
    def focus_event(body: FocusEvent, x_event_token: str | None = Header(default=None)):
        return service.receive_event(body, x_event_token)

    @app.post("/v1/actions")
    def action(body: Action):
        return service.act(body)

    @app.post("/v1/orders/{order_id}/refresh")
    def refresh_order(order_id: UUID):
        return service.refresh_order(order_id)

    return app


app = create_app()
