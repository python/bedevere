import pytest

from gidgethub import sansio
from gidgethub import abc as gh_abc

from bedevere import revert_pr


class FakeGH:

    def __init__(self, *, getitem=None):
        self._getitem_return = getitem

    async def getitem(self, url):
        return self._getitem_return

    async def post(self, url, data):
        self.url = url
        self.data = data


@pytest.mark.asyncio
async def test_set_status_failure():
    data = {
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": 'Revert "bpo-1234: a bug fix"',
            "body": "Reverts python/cpython#111",
            "issue_url": "issue URL",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await revert_pr.set_status(gh, event)
    status = gh.data
    assert status["state"] == "failure"
    assert status["target_url"].startswith("https://cpython-devguide")
    assert status["context"] == "bedevere/revert-pr"


@pytest.mark.asyncio
async def test_set_status_success():
    data = {
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": 'Revert "bpo-1234: a bug fix"',
            "body": """Reverts python/cpython#111
                Reason: Not approved by RM.
            """
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await revert_pr.set_status(gh, event)
    status = gh.data
    assert status["state"] == "success"
    assert status["description"] == "Found the reason to revert the PR."
    assert status["context"] == "bedevere/revert-pr"
    assert "git-sha" in gh.url


@pytest.mark.asyncio
async def test_no_revert_in_title():
    data = {
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "bpo-1234: a bug fix",
            "body": """Fixes to spam module"""
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await revert_pr.set_status(gh, event)
    assert not hasattr(gh, "data")


@pytest.mark.asyncio
async def test_edit_other_than_title():
    data = {
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "Revert bpo-1234",
        },
        "action": "edited",
        "changes": {"stuff": "thingy"},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await revert_pr.title_edited(gh, event)
    assert not hasattr(gh, "data")

