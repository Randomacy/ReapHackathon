from fastapi.testclient import TestClient

from src.app import Settings, create_app


def test_simulator_exposes_labelled_event_and_state():
    app = create_app(Settings(mode="simulator"))
    with TestClient(app) as client:
        response = client.post("/v1/demo/trigger", json={"state": "focus_dip"})
        assert response.status_code == 200
        event = response.json()
        assert event["source"] == "simulator"
        assert event["state"] == "focus_dip"
        assert event["signal_quality"] == "good"
        assert "eeg" not in event
        assert client.get("/v1/state").json()["latest_focus_event"] == event
        visualizer = client.get("/visualizer")
        assert visualizer.status_code == 200
        assert "Tempo Signal Lab" in visualizer.text
        diagnostics = client.get("/v1/visualization").json()
        assert diagnostics["mode"] == "simulator"
        assert diagnostics["focus_score"] == 0.28
        assert diagnostics["eeg"] == [[], [], [], []]
        assert "quality_reason" in diagnostics
        assert diagnostics["latest_focus_event"] == event


def test_live_mode_rejects_demo_trigger():
    app = create_app(Settings(mode="live", osc_port=0))
    with TestClient(app) as client:
        assert client.post("/v1/demo/trigger", json={"state": "focus_dip"}).status_code == 403
