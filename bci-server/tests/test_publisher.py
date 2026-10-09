import httpx

from src.app import Publisher, Settings


def test_retry_keeps_event_id(monkeypatch):
    requests = []

    class FakeClient:
        def __init__(self, timeout):
            assert timeout == 2.0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, url, json, headers):
            requests.append((url, json["event_id"], headers["X-Event-Token"]))
            if len(requests) == 1:
                raise httpx.ConnectError("temporary network failure")
            return httpx.Response(202)

    monkeypatch.setattr("src.app.httpx.Client", FakeClient)
    publisher = Publisher(Settings(event_token="local-test-token"))
    publisher.start()
    publisher.submit({"event_id": "fixed-id"})
    publisher.queue.join()
    publisher.stop()
    assert requests == [
        ("http://127.0.0.1:3000/api/v1/focus-events", "fixed-id", "local-test-token"),
        ("http://127.0.0.1:3000/api/v1/focus-events", "fixed-id", "local-test-token"),
    ]
