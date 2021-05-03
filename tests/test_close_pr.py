import pytest

from gidgethub import sansio

from bedevere import close_pr


class FakeGH:

    def __init__(self, *, getitem=None, post=None):
        self._getitem_return = getitem
        self.patch_url = None
        self.patch_data = None
        self.delete_url = None
        self.delete_data = None
        self.data = None
        self._post_return = post
        self.post_url = []
        self.post_data = []

    async def patch(self, url, data):
        self.patch_url = url
        self.patch_data = data

    async def delete(self, url, data):
        self.delete_url = url
        self.delete_data = data

    async def post(self, url, *, data):
        self.post_url.append(url)
        self.post_data.append(data)
        return self._post_return


@pytest.mark.asyncio
async def test_close_invalid_pr_on_open():
    data = {
        "action": "opened",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "https://api.github.com/org/repo/issues/123",
            "url": "https://api.github.com/org/repo/pulls/123",
            "head": {
                "label": "python:3.6"
            },
            "base": {
                "label": "python:main"
            }
        },
    }
    pr_data = {
        "labels": [
            {"name": "non-trivial"},
        ]
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=pr_data)
    await close_pr.router.dispatch(event, gh)
    patch_data = gh.patch_data
    assert patch_data["state"] == "closed"

    assert len(gh.post_url) == 2
    assert gh.post_url[0] == 'https://api.github.com/org/repo/issues/123/labels'
    assert gh.post_data[0] == ['invalid']
    assert gh.post_url[1] == 'https://api.github.com/org/repo/issues/123/comments'
    assert gh.post_data[1] == {'body': close_pr.INVALID_PR_COMMENT}


@pytest.mark.asyncio
async def test_close_invalid_pr_on_synchronize():
    data = {
        "action": "synchronize",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "https://api.github.com/org/repo/issues/123",
            "url": "https://api.github.com/org/repo/pulls/123",
            "head": {
                "label": "python:3.6"
            },
            "base": {
                "label": "python:main"
            }
        },
    }
    pr_data = {
        "labels": [
            {"name": "non-trivial"},
        ]
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=pr_data)
    await close_pr.router.dispatch(event, gh)
    patch_data = gh.patch_data
    assert patch_data["state"] == "closed"

    assert len(gh.post_url) == 2
    assert gh.post_url[0] == 'https://api.github.com/org/repo/issues/123/labels'
    assert gh.post_data[0] == ['invalid']
    assert gh.post_url[1] == 'https://api.github.com/org/repo/issues/123/comments'
    assert gh.post_data[1] == {'body': close_pr.INVALID_PR_COMMENT}


@pytest.mark.asyncio
async def test_valid_pr_not_closed():
    data = {
        "action": "opened",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
            "url": "https://api.github.com/org/repo/pulls/123",
            "head": {
                "label": "someuser:bpo-3.6"
            },
            "base": {
                "label": "python:main"
            }
        },
    }
    pr_data = {
        "labels": [
            {"name": "non-trivial"},
        ]
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=pr_data)
    await close_pr.router.dispatch(event, gh)
    patch_data = gh.patch_data
    assert patch_data is None


@pytest.mark.asyncio
async def test_close_invalid_pr_on_open_not_python_as_head():
    data = {
        "action": "opened",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
            "url": "https://api.github.com/org/repo/pulls/123",
            "head": {
                "label": "username123:3.6"
            },
            "base": {
                "label": "python:main"
            }
        },
    }
    pr_data = {
        "labels": [
            {"name": "non-trivial"},
        ]
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=pr_data)
    await close_pr.router.dispatch(event, gh)
    patch_data = gh.patch_data
    assert patch_data["state"] == "closed"


@pytest.mark.asyncio
async def test_pr_with_head_branch_containing_all_digits_not_closed():
    data = {
        "action": "opened",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
            "url": "https://api.github.com/org/repo/pulls/123",
            "head": {
                "label": "someuser:12345"
            },
            "base": {
                "label": "python:main"
            }
        },
    }
    pr_data = {
        "labels": [
            {"name": "non-trivial"},
        ]
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=pr_data)
    await close_pr.router.dispatch(event, gh)
    patch_data = gh.patch_data
    assert patch_data is None


@pytest.mark.asyncio
async def test_dismiss_review_request_for_invalid_pr():
    data = {
        "action": "review_requested",
        "pull_request": {
            "number": 123,
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
            "url": "https://api.github.com/org/repo/pulls/123",
            "head": {
                "label": "python:3.6"
            },
            "base": {
                "label": "python:main"
            },
            "requested_reviewers": [
                {
                    "login": "gpshead",
                },
                {
                    "login": "gvanrossum",
                },
            ],
            "requested_teams": [
                {
                    "name": "import-team",
                },
                {
                    "name": "windows-team",
                },
            ]
        },
    }

    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await close_pr.router.dispatch(event, gh)
    assert gh.delete_data == {'reviewers': ['gpshead', 'gvanrossum'],
                              'team_reviewers': ['import-team', 'windows-team']
                              }
    assert gh.delete_url == f"https://api.github.com/org/repo/pulls/123/requested_reviewers"


@pytest.mark.asyncio
async def test_valid_pr_review_request_not_dismissed():
    data = {
        "action": "review_requested",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
            "url": "https://api.github.com/org/repo/pulls/123",
            "head": {
                "label": "someuser:bpo-3.6"
            },
            "base": {
                "label": "python:main"
            },
            "requested_reviewers": [
                {
                    "login": "gpshead",
                },
                {
                    "login": "gvanrossum",
                },
            ],
            "requested_teams": [
                {
                    "name": "import-team",
                },
                {
                    "name": "windows-team",
                },
            ]
        },
    }

    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await close_pr.router.dispatch(event, gh)
    assert gh.delete_data is None
    assert gh.delete_url is None
