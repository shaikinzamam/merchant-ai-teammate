from sqlalchemy.exc import OperationalError


def test_root_returns_api_info(client) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["docs"] == "/docs"


def test_health_check_confirms_database_and_simulated_tools(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["database"] == "connected"
    assert r.json()["tools"] == "SIMULATED"
    assert r.json()["configuration"]["service_api_key_configured"] is True
    assert "svc-test-key" not in r.text


def test_health_check_reports_database_failure(client, container, monkeypatch) -> None:
    class Engine:
        def connect(self):
            raise OperationalError("connect", {}, RuntimeError("unavailable"))

    monkeypatch.setattr(container.db, "engine", Engine())
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "internal_error"
