import pytest

from gidgethub import sansio

from bedevere import bpo


class FakeGH:

    def __init__(self, *, getitem=None):
        self._getitem_return = getitem
        self.patch_url = None
        self.patch_data = None
        self.data = None

    async def getitem(self, url):
        return self._getitem_return

    async def post(self, url, data):
        self.url = url
        self.data = data

    async def patch(self, url, data):
        self.patch_url = url
        self.patch_data = data


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_set_status_failure(action):
    data = {
        "action": action,
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
        },
    }
    issue_data = {
        "labels": [
            {"name": "non-trivial"},
        ]
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await bpo.router.dispatch(event, gh)
    status = gh.data
    assert status["state"] == "failure"
    assert status["target_url"].startswith("https://devguide.python.org")
    assert status["context"] == "bedevere/issue-number"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_set_status_success(action):
    data = {
        "action": action,
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "[3.6] bpo-1234: an issue!",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    status = gh.data
    assert status["state"] == "success"
    assert status["target_url"].endswith("issue1234")
    assert "1234" in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.url


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_set_status_success_via_skip_issue_label(action):
    data = {
        "action": action,
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
        },
    }
    issue_data = {
        "labels": [
            {"name": "skip issue"},
        ]
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await bpo.router.dispatch(event, gh)
    status = gh.data
    assert status["state"] == "success"
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.url


@pytest.mark.asyncio
async def test_edit_title():
    data = {
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "bpo-1234: an issue!",
        },
        "action": "edited",
        "changes": {"title": "thingy"},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.data is not None


@pytest.mark.asyncio
async def test_no_body_when_edit_title():
    data = {
        "action": "edited",
        "pull_request": {
            "url": "https://api.github.com/repos/python/cpython/pulls/5291",
            "title": "bpo-32636: Fix @asyncio.coroutine debug mode bug",
            "body": None,
            "statuses_url": "https://api.github.com/repos/python/cpython/statuses/98d60953c85df9f0f28e04322a4c4ebec7b180f4",
        },
        "changes": {
            "title": "bpo-32636: Fix @asyncio.coroutine debug mode bug exposed by #5250."
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.patch_data is not None
    assert gh.patch_data["body"] == "\n\n<!-- issue-number: bpo-32636 -->\nhttps://bugs.python.org/issue32636\n<!-- /issue-number -->\n"


@pytest.mark.asyncio
async def test_edit_other_than_title():
    data = {
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "bpo-1234: an issue!",
        },
        "action": "edited",
        "changes": {"stuff": "thingy"},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.data is None


@pytest.mark.asyncio
async def test_new_label_skip_issue_no_issue():
    data = {
        "action": "labeled",
        "label": {"name": "skip issue"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "An easy fix",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.data["state"] == "success"
    assert "git-sha" in gh.url


@pytest.mark.asyncio
async def test_new_label_skip_issue_with_issue_number():
    data = {
        "action": "labeled",
        "label": {"name": "skip issue"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "Revert bpo-1234: revert an easy fix",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    status = gh.data
    assert status["state"] == "success"
    assert status["target_url"].endswith("issue1234")
    assert "1234" in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.url


@pytest.mark.asyncio
async def test_new_label_not_skip_issue():
    data = {
        "action": "labeled",
        "label": {"name": "non-trivial"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.data is None


@pytest.mark.asyncio
async def test_removed_label_from_label_deletion():
    """When a label is completely deleted from a repo, it triggers an 'unlabeled'
    event, but the payload has no details about the removed label."""
    data = {
        "action": "unlabeled",
        # No "label" key.
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "bpo-1234: an issue!",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.data is None


@pytest.mark.asyncio
async def test_removed_label_skip_issue():
    data = {
        "action": "unlabeled",
        "label": {"name": "skip issue"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "bpo-1234: an issue!",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    status = gh.data
    assert status["state"] == "success"
    assert status["target_url"].endswith("issue1234")
    assert "1234" in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.url


@pytest.mark.asyncio
async def test_removed_label_non_skip_issue():
    data = {
        "action": "unlabeled",
        "label": {"name": "non-trivial"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.data is None


@pytest.mark.asyncio
async def test_set_body_success():
    data = {
        "action": "opened",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "url": "https://api.github.com/repos/blah/blah/pulls/1347",
            "title": "[3.6] bpo-1234: an issue!",
            "body": "This is the body of the PR.\nSecond line is here."
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    status = gh.patch_data
    assert "https://bugs.python.org/issue1234" in status["body"]
    assert "1347" in gh.patch_url


@pytest.mark.asyncio
async def test_set_body_failure():
    data = {
        "action": "opened",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "url": "https://api.github.com/repos/blah/blah/pulls/1347",
            "title": "[3.6] bpo-1234: an issue!",
            "body": """The body.\n<!-- issue-number: bpo-1234 -->\n"https://bugs.python.org/issue1234"\n<!-- /issue-number -->"""
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.patch_data is None
    assert gh.patch_url is None


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "edited"])
async def test_set_pull_request_body_success(action):
    data = {
        "action": action,
        "pull_request": {
            "title": "[3.6] bpo-12345: some issue",
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "issue_url": "https://api.github.com/repos/blah/blah/issues/comments/123456",
            "url": "https://api.github.com/repos/python/cpython/pulls/4321",
            "body": "An issue bpo-12345 in the body"
        },
        "changes": {"stuff": "thingy"}
    }

    event = sansio.Event(data, event="pull_request", delivery_id="123123")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    body_data = gh.patch_data
    assert "[bpo-12345](https://www.bugs.python.org/issue12345)" in body_data["body"]
    assert "123456" in gh.patch_url

@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["created", "edited"])
async def test_set_comment_body_success(action):
    data = {
        "action": action,
        "comment": {
            "url": "https://api.github.com/repos/blah/blah/issues/comments/123456",
            "body": "An issue bpo-12345 in the body"
        }
    }

    event = sansio.Event(data, event="issue_comment", delivery_id="123123")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    body_data = gh.patch_data
    assert "[bpo-12345](https://www.bugs.python.org/issue12345)" in body_data["body"]
    assert "123456" in gh.patch_url

@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "edited"])
async def test_set_pull_request_body_without_bpo(action):
    data = {
        "action": action,
        "pull_request": {
            "title": "[3.6] bpo-12345: some issue",
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "issue_url": "https://api.github.com/repos/blah/blah/issues/comments/123456",
            "url": "https://api.github.com/repos/blah/blah/issues/comments/123456",
            "body": "This bpo - 123 doesn't qualify for hyperlinking"
        },
        "changes": {"stuff": "thingy"}
    }

    event = sansio.Event(data, event="pull_request", delivery_id="123123")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    if gh.patch_data:
        assert "[bpo-123](https://www.bugs.python.org/issue123)" not in gh.patch_data


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["created", "edited"])
async def test_set_comment_body_without_bpo(action):
    data = {
        "action": action,
        "comment": {
            "url": "https://api.github.com/repos/blah/blah/issues/comments/123456",
            "body": "This body doesn't contain any bpo text"
        }
    }

    event = sansio.Event(data, event="issue_comment", delivery_id="123123")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.patch_data is None
    assert gh.patch_url is None


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "edited"])
async def test_set_pull_request_body_already_hyperlinked_bpo(action):
    data = {
        "action": action,
        "pull_request": {
            "title": "[3.6] bpo-12345: some issue",
            "url": "https://api.github.com/repos/python/cpython/pulls/4321",
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "issue_url": "https://api.github.com/repos/blah/blah/issues/comments/123456",
            "body": ("bpo-123"
                    "[bpo-123](https://www.bugs.python.org/issue123)"
                    "<a href='https://www.bugs.python.org/issue123'>bpo-123</a>"
                   )
        },
        "changes": {"stuff": "thingy"}
    }

    event = sansio.Event(data, event="pull_request", delivery_id="123123")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    body_data = gh.patch_data
    assert body_data["body"].count("[bpo-123](https://www.bugs.python.org/issue123)") == 2
    assert "123456" in gh.patch_url


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["created", "edited"])
async def test_set_comment_body_already_hyperlinked_bpo(action):
    data = {
        "action": action,
        "comment": {
            "url": "https://api.github.com/repos/blah/blah/issues/comments/123456",
            "body": ("bpo-123"
                    "[bpo-123](https://www.bugs.python.org/issue123)"
                    "<a href='https://www.bugs.python.org/issue123'>bpo-123</a>"
                   )
        }
    }

    event = sansio.Event(data, event="issue_comment", delivery_id="123123")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    body_data = gh.patch_data
    assert body_data["body"].count("[bpo-123](https://www.bugs.python.org/issue123)") == 2
    assert "123456" in gh.patch_url
