import pytest

from app.api import sync as sync_module


class _DummyControl:
    def __init__(self, response):
        self._response = response

    def ping(self, timeout=1.0):
        return self._response


class _DummyCelery:
    def __init__(self, response):
        self.control = _DummyControl(response)


class _FailingControl:
    def ping(self, timeout=1.0):
        raise RuntimeError("broker unavailable")


class _FailingCelery:
    def __init__(self):
        self.control = _FailingControl()


@pytest.fixture(autouse=True)
def reset_celery_available(monkeypatch):
    # Ensure tests can force Celery availability without leaking state
    original = sync_module._celery_available
    yield
    monkeypatch.setattr(sync_module, "_celery_available", original)


def test_get_celery_status_reports_worker_count(monkeypatch):
    # Pretend Celery is configured and workers respond to ping
    monkeypatch.setattr(sync_module, "_celery_available", True)
    monkeypatch.setattr("app.worker.celery_app", _DummyCelery([{"w1": "ok"}, {"w2": "ok"}]), raising=False)

    status = sync_module.get_celery_status()

    assert status["celery_enabled"] is True
    assert status["celery_workers"] == 2
    assert "celery_error" not in status


def test_get_celery_status_handles_ping_failure(monkeypatch):
    # Pretend Celery is configured but broker/worker ping fails
    monkeypatch.setattr(sync_module, "_celery_available", True)
    monkeypatch.setattr("app.worker.celery_app", _FailingCelery(), raising=False)

    status = sync_module.get_celery_status()

    assert status["celery_enabled"] is False
    assert status["celery_workers"] == 0
    assert "broker unavailable" in status.get("celery_error", "")
