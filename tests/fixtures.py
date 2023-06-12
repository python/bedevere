import os
import pytest


@pytest.fixture
def tmp_event_name(request, monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", request.param)

@pytest.fixture
def tmp_job_id(monkeypatch):
    monkeypatch.setenv("GITHUB_JOB", "12345")

@pytest.fixture
def tmp_webhook(tmp_path, monkeypatch):
    """Create a temporary file for an actions webhook event."""
    tmp_file_path = tmp_path / "event.json"
    monkeypatch.setenv("GITHUB_EVENT_PATH", os.fspath(tmp_file_path))
    return tmp_file_path
