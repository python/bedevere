from unittest import mock

import http
import aiohttp
import pytest
import gidgethub

from gidgethub import sansio

from bedevere import gh_issue


class FakeGH:

    def __init__(self, *, getitem=None, post=None, patch=None):
        self._getitem_return = getitem
        self._post_return = post
        self._patch_return = patch
        self.post_url = []
        self.post_data = []
        self.patch_url = []
        self.patch_data = []

    async def getitem(self, url):
        if isinstance(self._getitem_return, Exception):
            raise self._getitem_return
        return self._getitem_return

    async def post(self, url, *, data):
        self.post_url.append(url)
        self.post_data.append(data)
        return self._post_return

    async def patch(self, url, *, data):
        self.patch_url.append(url)
        self.patch_data.append(data)
        return self._patch_return


@pytest.fixture
async def issue_number():
    return 1234


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_set_status_failure(action, monkeypatch):
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=True))
    data = {
        "action": action,
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
            "url": "url",
            "number": 1234,
        },
    }
    issue_data = {
        "url": "url",
        "labels": [
            {"name": "non-trivial"},
        ]
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh, session=None)
    status = gh.post_data[0]
    assert status["state"] == "failure"
    assert status["target_url"].startswith("https://devguide.python.org")
    assert status["context"] == "bedevere/issue-number"
    gh_issue._validate_issue_number.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_set_status_failure_via_issue_not_found_on_github(action, monkeypatch):
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=False))

    data = {
        "action": action,
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "gh-123: Invalid issue number",
            "issue_url": "issue URL",
            "url": "url",
            "number": 1234,
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    async with aiohttp.ClientSession() as session:
        await gh_issue.router.dispatch(event, gh, session=session)
    status = gh.post_data[0]
    assert status["state"] == "failure"
    assert status["target_url"] == "https://github.com/python/cpython/issues/123"
    assert status["context"] == "bedevere/issue-number"
    assert status["description"] == "GH Issue #123 is not valid."


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_set_status_success_issue_found_on_bpo(action):
    data = {
        "action": action,
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "bpo-12345: An issue on b.p.o",
            "issue_url": "issue URL",
            "url": "url",
            "number": 1234,
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    async with aiohttp.ClientSession() as session:
        await gh_issue.router.dispatch(event, gh, session=session)
    status = gh.post_data[0]
    assert status["state"] == "success"
    assert status["target_url"].endswith("bpo=12345")
    assert "12345" in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.post_url[0]

    assert len(gh.patch_data) == 0
    assert len(gh.patch_url) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_set_status_success(action, monkeypatch):
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=True))
    data = {
        "action": action,
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "url": "",
            "title": "[3.6] gh-1234: an issue!",
            "issue_url": "issue URL",
            "number": 1234,
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh, session=None)
    status = gh.post_data[0]
    assert status["state"] == "success"
    assert status["target_url"] == "https://github.com/python/cpython/issues/1234"
    assert "1234" in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.post_url[0]
    gh_issue._validate_issue_number.assert_awaited_with(gh, 1234, session=None, kind="gh")


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_set_status_success_issue_found_on_gh(action, monkeypatch, issue_number):
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=True))
    data = {
        "action": action,
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": f"gh-{issue_number}: an issue!",
            "url": "url",
            "issue_url": "issue URL",
            "number": 1234,
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    async with aiohttp.ClientSession() as session:
        await gh_issue.router.dispatch(event, gh, session=session)
    status = gh.post_data[0]
    assert status["state"] == "success"
    assert status["target_url"] == f"https://github.com/python/cpython/issues/{issue_number}"
    assert str(issue_number) in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.post_url[0]

    assert len(gh.patch_data) > 0
    assert f"<!-- gh-issue-number: gh-{issue_number} -->" in gh.patch_data[0]["body"]
    assert (
        "\n\n<!-- gh-linked-prs -->\n"
        f"### Linked PRs\n* gh-{issue_number}\n"
        "<!-- /gh-linked-prs -->\n"
    ) in gh.patch_data[1]["body"]
    assert len(gh.patch_url) == 2
    assert gh.patch_url[0] == data["pull_request"]["url"]
    assert gh.patch_url[1] == issue_data["url"]


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_set_status_success_issue_found_on_gh_ignore_case(action, monkeypatch, issue_number):
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=True))
    data = {
        "action": action,
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": f"GH-{issue_number}: an issue!",
            "url": "url",
            "issue_url": "issue URL",
            "number": 1234,
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    async with aiohttp.ClientSession() as session:
        await gh_issue.router.dispatch(event, gh, session=session)
    status = gh.post_data[0]
    assert status["state"] == "success"
    assert status["target_url"] == f"https://github.com/python/cpython/issues/{issue_number}"
    assert str(issue_number) in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.post_url[0]

    assert len(gh.patch_data) > 0
    assert f"<!-- gh-issue-number: gh-{issue_number} -->" in gh.patch_data[0]["body"]
    assert (
        "\n\n<!-- gh-linked-prs -->\n"
        f"### Linked PRs\n* gh-{issue_number}\n"
        "<!-- /gh-linked-prs -->\n"
    ) in gh.patch_data[1]["body"]
    assert len(gh.patch_url) == 2
    assert gh.patch_url[0] == data["pull_request"]["url"]
    assert gh.patch_url[1] == issue_data["url"]


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_set_status_success_via_skip_issue_label(action, monkeypatch):
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=True))
    data = {
        "action": action,
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
            "url": "url",
            "number": 1234,
        },
    }
    issue_data = {
        "url": "url",
        "labels": [
            {"name": "skip issue"},
        ]
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh, session=None)
    status = gh.post_data[0]
    assert status["state"] == "success"
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.post_url[0]
    gh_issue._validate_issue_number.assert_not_awaited()

    assert len(gh.patch_data) == 0
    assert len(gh.patch_url) == 0

@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_set_status_success_via_skip_issue_label_pr_in_title(action, monkeypatch):
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=False))
    data = {
        "action": action,
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "GH-93644: An issue with a PR as issue number",
            "issue_url": "issue URL",
            "url": "url",
            "number": 1234,
        },
    }
    issue_data = {
        "url": "url",
        "labels": [
            {"name": "skip issue"},
        ]
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh, session=None)
    status = gh.post_data[0]
    assert status["state"] == "success"
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.post_url[0]
    gh_issue._validate_issue_number.assert_not_awaited()

    assert len(gh.patch_data) == 0
    assert len(gh.patch_url) == 0


@pytest.mark.asyncio
async def test_edit_title(monkeypatch, issue_number):
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=True))
    data = {
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": f"gh-{issue_number}: an issue!",
            "url": "url",
            "issue_url": "issue URL",
            "number": 1234,
        },
        "action": "edited",
        "changes": {"title": "thingy"},
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh, session=None)
    assert len(gh.post_data) == 1
    gh_issue._validate_issue_number.assert_awaited_with(gh, issue_number, session=None, kind="gh")

@pytest.mark.asyncio
async def test_no_body_when_edit_title(monkeypatch, issue_number):
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=True))
    data = {
        "action": "edited",
        "pull_request": {
            "url": "https://api.github.com/repos/python/cpython/pulls/5291",
            "title": f"gh-{issue_number}: Fix @asyncio.coroutine debug mode bug",
            "body": None,
            "issue_url": "issue URL",
            "statuses_url": "https://api.github.com/repos/python/cpython/statuses/98d60953c85df9f0f28e04322a4c4ebec7b180f4",
            "number": 1234,
        },
        "changes": {
            "title": f"gh-{issue_number}: Fix @asyncio.coroutine debug mode bug exposed by #5250."
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh, session=None)
    gh_issue._validate_issue_number.assert_awaited_with(gh, issue_number, session=None, kind="gh")

    assert len(gh.patch_data) > 0
    assert f"<!-- gh-issue-number: gh-{issue_number} -->" in gh.patch_data[0]["body"]
    assert (
        "\n\n<!-- gh-linked-prs -->\n"
        f"### Linked PRs\n* gh-{issue_number}\n"
        "<!-- /gh-linked-prs -->\n"
    ) in gh.patch_data[1]["body"]
    assert len(gh.patch_url) == 2
    assert gh.patch_url[0] == data["pull_request"]["url"]
    assert gh.patch_url[1] == issue_data["url"]


@pytest.mark.asyncio
async def test_edit_other_than_title(monkeypatch):
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=True))
    data = {
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "bpo-1234: an issue!",
            "url": "url",
            "issue_url": "issue URL",
            "number": 1234,
        },
        "action": "edited",
        "changes": {"stuff": "thingy"},
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh, session=None)
    assert len(gh.post_data) == 0
    gh_issue._validate_issue_number.assert_not_awaited()

    assert len(gh.patch_data) == 0
    assert len(gh.patch_url) == 0


@pytest.mark.asyncio
async def test_new_label_skip_issue_no_issue():
    data = {
        "action": "labeled",
        "label": {"name": "skip issue"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "An easy fix",
            "url": "url",
            "issue_url": "issue URL",
            "number": 1234,
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh)
    assert gh.post_data[0]["state"] == "success"
    assert "git-sha" in gh.post_url[0]


@pytest.mark.asyncio
async def test_new_label_skip_issue_with_issue_number():
    data = {
        "action": "labeled",
        "label": {"name": "skip issue"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "Revert gh-1234: revert an easy fix",
            "url": "url",
            "issue_url": "issue URL",
            "number": 1234,
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh)
    status = gh.post_data[0]
    assert status["state"] == "success"
    assert status["target_url"] == "https://github.com/python/cpython/issues/1234"
    assert "1234" in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.post_url[0]


@pytest.mark.asyncio
async def test_new_label_skip_issue_with_issue_number_ignore_case():
    data = {
        "action": "labeled",
        "label": {"name": "skip issue"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "Revert Gh-1234: revert an easy fix",
            "url": "url",
            "issue_url": "issue URL",
            "number": 1234,
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh)
    status = gh.post_data[0]
    assert status["state"] == "success"
    assert status["target_url"] == "https://github.com/python/cpython/issues/1234"
    assert "1234" in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.post_url[0]

@pytest.mark.asyncio
async def test_new_label_not_skip_issue():
    data = {
        "action": "labeled",
        "label": {"name": "non-trivial"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "url": "url",
            "issue_url": "issue URL",
            "number": 1234,
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh)
    assert len(gh.post_data) == 0


@pytest.mark.asyncio
async def test_removed_label_from_label_deletion(monkeypatch):
    """When a label is completely deleted from a repo, it triggers an 'unlabeled'
    event, but the payload has no details about the removed label."""
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=True))
    data = {
        "action": "unlabeled",
        # No "label" key.
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "gh-1234: an issue!",
            "url": "url",
            "issue_url": "issue URL",
            "number": 1234,
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh, session=None)
    assert len(gh.post_data) == 0
    gh_issue._validate_issue_number.assert_not_awaited()


@pytest.mark.asyncio
async def test_removed_label_skip_issue(monkeypatch):
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=True))
    data = {
        "action": "unlabeled",
        "label": {"name": "skip issue"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "gh-1234: an issue!",
            "url": "url",
            "issue_url": "issue URL",
            "number": 1234,
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh, session=None)
    status = gh.post_data[0]
    assert status["state"] == "success"
    assert status["target_url"] == "https://github.com/python/cpython/issues/1234"
    assert "1234" in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.post_url[0]
    gh_issue._validate_issue_number.assert_awaited_with(gh, 1234, session=None, kind="gh")


@pytest.mark.asyncio
async def test_removed_label_non_skip_issue(monkeypatch):
    monkeypatch.setattr(gh_issue, '_validate_issue_number',
                        mock.AsyncMock(return_value=True))
    data = {
        "action": "unlabeled",
        "label": {"name": "non-trivial"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "url": "url",
            "issue_url": "issue URL",
            "number": 1234,
        },
    }
    issue_data = {"url": "url", "labels": []}
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await gh_issue.router.dispatch(event, gh, session=None)
    assert len(gh.post_data) == 0
    gh_issue._validate_issue_number.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_issue_number_valid_on_github():

    gh = FakeGH(getitem={"number": 123})
    async with aiohttp.ClientSession() as session:
        response = await gh_issue._validate_issue_number(gh, 123, session=session)
    assert response is True


@pytest.mark.asyncio
async def test_validate_issue_number_valid_on_bpo():
    gh = FakeGH(getitem={"number": 1234})
    async with aiohttp.ClientSession() as session:
        response = await gh_issue._validate_issue_number(
            gh, 1234, kind="bpo", session=session
        )
    assert response is True


@pytest.mark.asyncio
async def test_validate_issue_number_is_pr_on_github():

    gh = FakeGH(getitem={
        "number": 123,
        "pull_request": {
            "html_url": "https://github.com/python/cpython/pull/123",
            "url": "url",
            "number": 1234,
        }
    })
    async with aiohttp.ClientSession() as session:
        response = await gh_issue._validate_issue_number(gh, 123, session=session)
    assert response is False


@pytest.mark.asyncio
async def test_validate_issue_number_is_not_valid():
    gh = FakeGH(
        getitem=gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        )
    )
    async with aiohttp.ClientSession() as session:
        response = await gh_issue._validate_issue_number(gh, 123, session=session)
    assert response is False


@pytest.mark.asyncio
async def test_validate_issue_number_coverage100():
    gh = FakeGH(getitem={"number": 1234})
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ValueError):
            await gh_issue._validate_issue_number(
                gh, 123, session=session, kind="invalid"  # type: ignore
            )
