{'name': 'Python core', 'id': 2011335, 'slug': 'python-core', 'description': 'Core developers of CPython & the Python language', 'privacy': 'closed', 'url': 'https://api.github.com/teams/2011335', 'members_url': 'https://api.github.com/teams/2011335/members{/member}', 'repositories_url': 'https://api.github.com/teams/2011335/repos', 'permission': 'pull'}

import http

import gidgethub
from gidgethub import sansio
import pytest

from bedevere import awaiting


class FakeGH:

    def __init__(self, *, getiter=None, getitem=None, delete=None, post=None):
        self._getiter_return = getiter
        self._getitem_return = getitem
        self._delete_return = delete
        self._post_return = post
        self.getitem_url = None
        self.delete_url = None
        self.post_ = []

    async def getiter(self, url, url_vars={}):
        self.getiter_url = sansio.format_url(url, url_vars)
        to_iterate = self._getiter_return[self.getiter_url]
        for item in to_iterate:
            yield item

    async def getitem(self, url, url_vars={}):
        self.getitem_url = sansio.format_url(url, url_vars)
        to_return = self._getitem_return[self.getitem_url]
        if isinstance(to_return, Exception):
            raise to_return
        else:
            return to_return

    async def delete(self, url, url_vars={}):
        self.delete_url = sansio.format_url(url, url_vars)

    async def post(self, url, url_vars={}, *, data):
        post_url = sansio.format_url(url, url_vars)
        self.post_.append((post_url, data))


async def test_is_core_dev():
    teams = [{"name": "not Python core"}]
    gh = FakeGH(getiter={"https://api.github.com/orgs/python/teams": teams})
    with pytest.raises(ValueError):
        await awaiting.is_core_dev(gh, "brett")

    teams = [{"name": "Python core", "id": 42}]
    getitem = {"https://api.github.com/teams/42/memberships/brett": True}
    gh = FakeGH(getiter={"https://api.github.com/orgs/python/teams": teams},
                getitem=getitem)
    assert await awaiting.is_core_dev(gh, "brett")
    assert gh.getiter_url == "https://api.github.com/orgs/python/teams"

    teams = [{"name": "Python core", "id": 42}]
    getitem = {"https://api.github.com/teams/42/memberships/andrea":
                gidgethub.BadRequest(status_code=http.HTTPStatus(404))}
    gh = FakeGH(getiter={"https://api.github.com/orgs/python/teams": teams},
                getitem=getitem)
    assert not await awaiting.is_core_dev(gh, "andrea")

    teams = [{"name": "Python core", "id": 42}]
    getitem = {"https://api.github.com/teams/42/memberships/andrea":
                gidgethub.BadRequest(status_code=http.HTTPStatus(400))}
    gh = FakeGH(getiter={"https://api.github.com/orgs/python/teams": teams},
                getitem=getitem)
    with pytest.raises(gidgethub.BadRequest):
        await awaiting.is_core_dev(gh, "andrea")


async def test_stage():
    # Test label removal.
    issue = {"labels": [{"name": "awaiting merge"}, {"name": "skip issue"}]}
    issue_url = "https://api.github.com/some/issue"
    pull_request = {"issue_url": issue_url}
    gh = FakeGH(getitem={issue_url: issue})
    await awaiting.stage(gh, pull_request, awaiting.Blocker.merge)
    assert not gh.post_

    # Test adding a label.
    issue = {
        "labels": [{"name": "awaiting review"}],
        "labels_url":
            "https://api.github.com/repos/python/cpython/issues/42/labels{/name}",
    }
    gh = FakeGH(getitem={issue_url: issue})
    await awaiting.stage(gh, pull_request, awaiting.Blocker.merge)
    assert gh.delete_url == "https://api.github.com/repos/python/cpython/issues/42/labels/awaiting%20review"
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/repos/python/cpython/issues/42/labels"
    assert post_[1] == [awaiting.Blocker.merge.value]


async def test_opened_pr():
    username = "brettcannon"
    issue_url = "https://api.github.com/issue/42"
    data = {
        "action": "opened",
        "pull_request": {
            "user": {
                "login": username,
            },
            "issue_url": issue_url,
        }
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    teams = [
        {"name": "python core", "id": 6}
    ]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": "OK",
        issue_url: {"labels": [], "labels_url": "https://api.github.com/labels"}
    }
    gh = FakeGH(getiter={"https://api.github.com/orgs/python/teams": teams},
                getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/labels"
    assert post_[1] == [awaiting.Blocker.merge.value]

    username = "andreamcinnes"
    issue_url = "https://api.github.com/issue/42"
    data = {
        "action": "opened",
        "pull_request": {
            "user": {
                "login": username,
            },
            "issue_url": issue_url,
        }
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    teams = [
        {"name": "python core", "id": 6}
    ]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}":
            gidgethub.BadRequest(status_code=http.HTTPStatus(404)),
        issue_url: {"labels": [], "labels_url": "https://api.github.com/labels"}
    }
    gh = FakeGH(getiter={"https://api.github.com/orgs/python/teams": teams},
                getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/labels"
    assert post_[1] == [awaiting.Blocker.review.value]


async def test_new_review():
    username = "andreamcinnes"
    data = {
        "action": "submitted",
        "review": {
            "user": {
                "login": username,
            },
        },
        "pull_request": {
            "url": "https://api.github.com/pr/42",
            "issue_url": "https://api.github.com/issue/42",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    teams = [
        {"name": "python core", "id": 6}
    ]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}":
            gidgethub.BadRequest(status_code=http.HTTPStatus(404)),
        "https://api.github.com/issue/42": {
            "labels": [],
            "labels_url": "https://api.github.com/labels/42",
        }
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/labels/42"
    assert post_[1] == [awaiting.Blocker.core_review.value]

    items = {
        f"https://api.github.com/teams/6/memberships/{username}":
            gidgethub.BadRequest(status_code=http.HTTPStatus(404)),
        "https://api.github.com/teams/6/memberships/brettcannon": True,
        "https://api.github.com/issue/42": {
            "labels": [],
            "labels_url": "https://api.github.com/labels/42",
        }
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews":
            [{"user": {"login": "brettcannon"}}],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert not gh.post_

    username = "brettcannon"
    data = {
        "action": "submitted",
        "review": {
            "user": {
                "login": username,
            },
            "state": "APPROVED",
        },
        "pull_request": {
            "url": "https://api.github.com/pr/42",
            "issue_url": "https://api.github.com/issue/42",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    teams = [
        {"name": "python core", "id": 6}
    ]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": True,
        "https://api.github.com/issue/42": {
            "labels": [],
            "labels_url": "https://api.github.com/labels/42",
        }
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/labels/42"
    assert post_[1] == [awaiting.Blocker.merge.value]

    data = {
        "action": "submitted",
        "review": {
            "user": {
                "login": username,
            },
            "state": "changes_requested".upper(),
        },
        "pull_request": {
            "url": "https://api.github.com/pr/42",
            "issue_url": "https://api.github.com/issue/42",
            "comments_url": "https://api.github.com/comment/42",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 2
    labeling = gh.post_[0]
    assert labeling[0] == "https://api.github.com/labels/42"
    assert labeling[1] == [awaiting.Blocker.changes.value]
    message = gh.post_[1]
    assert message[0] == "https://api.github.com/comment/42"
    assert awaiting.REQUEST_CHANGE_REVIEW in message[1]["body"]
    
    data = {
        "action": "submitted",
        "review": {
            "user": {
                "login": username,
            },
            "state": "comment".upper(),
        },
        "pull_request": {
            "url": "https://api.github.com/pr/42",
            "issue_url": "https://api.github.com/issue/42",
            "comments_url": "https://api.github.com/comment/42",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert not len(gh.post_)


async def test_new_comment():
    # Comment not from PR author.
    data = {
        "action": "created",
        "issue": {"user": {"login": "andreamcinnes"}},
        "comment": {
            "user": {"login": "brettcannon"},
            "body": awaiting.REQUEST_CHANGE_REVIEW,
        },
    }
    event = sansio.Event(data, event="issue_comment", delivery_id="12345")
    gh = FakeGH()
    await awaiting.router.dispatch(event, gh)
    assert not len(gh.post_)

    # Comment from PR author but missing trigger phrase.
    data = {
        "action": "created",
        "issue": {"user": {"login": "andreamcinnes"}},
        "comment": {
            "user": {"login": "andreamcinnes"},
            "body": "I DID expect the Spanish Inquisition",
        },
    }
    event = sansio.Event(data, event="issue_comment", delivery_id="12345")
    gh = FakeGH()
    await awaiting.router.dispatch(event, gh)
    assert not len(gh.post_)

    # Everything is right with the world.
    data = {
        "action": "created",
        "issue": {
            "user": {"login": "andreamcinnes"},
            "labels": [],
            "labels_url": "https://api.github.com/labels/42",
            "url": "https://api.github.com/issue/42",
            "pull_request": {"url": "https://api.github.com/pr/42"},
            "comments_url": "https://api.github.com/comments/42",
        },
        "comment": {
            "user": {"login": "andreamcinnes"},
            "body": awaiting.REQUEST_CHANGE_REVIEW,
        },
    }
    event = sansio.Event(data, event="issue_comment", delivery_id="12345")
    items = {
        "https://api.github.com/teams/6/memberships/brettcannon": True,
        "https://api.github.com/teams/6/memberships/gvanrossum": True,
        "https://api.github.com/teams/6/memberships/not-core-dev":
            gidgethub.BadRequest(status_code=http.HTTPStatus(404)),
    }
    iterators = {
        "https://api.github.com/orgs/python/teams":
            [{"name": "python core", "id": 6}],
        "https://api.github.com/pr/42/reviews":
            [
                {"user": {"login": "brettcannon"}},
                {"user": {"login": "gvanrossum"}},
                {"user": {"login": "not-core-dev"}},
            ],
    }
    gh = FakeGH(getitem=items, getiter=iterators)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 2
    labeling, comment = gh.post_
    assert labeling[0] == "https://api.github.com/labels/42"
    assert labeling[1] == [awaiting.Blocker.change_review.value]
    assert comment[0] == "https://api.github.com/comments/42"
    comment_body = comment[1]["body"]
    assert "@brettcannon" in comment_body
    assert "@gvanrossum" in comment_body
    assert "not-core-dev" not in comment_body
