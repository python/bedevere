import pytest

from gidgethub import sansio
from gidgethub import abc as gh_abc

from bedevere import bpo


class FakeGH:
    async def post(self, url, data):
        self.data = data


@pytest.mark.asyncio
async def test_status_failure():
    data = {
        "pull_request":
            {
                "head": {"sha": "git-sha"},
                "title": "No issue in title",
            },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.set_status(gh, event)
    status = gh.data
    assert status["state"] == "failure"
    assert status["target_url"].startswith("https://cpython-devguide")
    assert status["context"] == "bedevere/issue-number"


@pytest.mark.asyncio
async def test_status_success():
    data = {
        "pull_request":
            {
                "head": {"sha": "git-sha"},
                "title": "bpo-1234: an issue!",
            },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.set_status(gh, event)
    status = gh.data
    assert status["state"] == "success"
    assert status["target_url"].endswith("issue1234")
    assert "1234" in status["description"]
    assert status["context"] == "bedevere/issue-number"


@pytest.mark.asyncio
async def test_edit_other_than_title():
    data = {
        "pull_request":
            {
                "head": {"sha": "git-sha"},
                "title": "bpo-1234: an issue!",
            },
        "action": "edited",
        "changes": {"stuff": "thingy"},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.title_edited(gh, event)
    assert not hasattr(gh, "data")
