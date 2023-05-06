import http

import gidgethub
from gidgethub import sansio
import pytest

from bedevere import stage as awaiting

from bedevere.stage import ACK


class FakeGH:
    def __init__(self, *, getiter=None, getitem=None, delete=None, post=None):
        self._getiter_return = getiter
        self._getitem_return = getitem
        self._delete_return = delete
        self._post_return = post
        self.getitem_url = None
        self.delete_url = None
        self.post_ = []
        self.patch_ = []

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

    async def patch(self, url, url_vars={}, *, data):
        patch_url = sansio.format_url(url, url_vars)
        self.patch_.append((patch_url, data))


async def test_stage():
    # Skip changing labels if the label is already set.
    issue = {"labels": [{"name": "awaiting merge"}, {"name": "skip issue"}]}
    issue_url = "https://api.github.com/some/issue"
    gh = FakeGH()
    await awaiting.stage(gh, issue, awaiting.Blocker.merge)
    assert not gh.delete_url
    assert not gh.post_

    # Test deleting an old label and adding a new one.
    issue = {
        "labels": [{"name": "awaiting review"}, {"name": "skip issue"}],
        "labels_url": "https://api.github.com/repos/python/cpython/issues/42/labels{/name}",
    }
    gh = FakeGH()
    await awaiting.stage(gh, issue, awaiting.Blocker.merge)
    assert (
        gh.delete_url
        == "https://api.github.com/repos/python/cpython/issues/42/labels/awaiting%20review"
    )
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/repos/python/cpython/issues/42/labels"
    assert post_[1] == [awaiting.Blocker.merge.value]


async def test_opened_draft_pr():
    # New Draft PR from a core dev.
    username = "brettcannon"
    issue_url = "https://api.github.com/issue/42"
    data = {
        "action": "opened",
        "pull_request": {
            "user": {
                "login": username,
            },
            "issue_url": issue_url,
            "draft": True,
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": "OK",
        issue_url: {"labels": [], "labels_url": "https://api.github.com/labels"},
    }
    gh = FakeGH(
        getiter={"https://api.github.com/orgs/python/teams": teams}, getitem=items
    )
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 0

    # Draft PR is published
    data["action"] = "ready_for_review"
    data["pull_request"]["draft"] = False
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(
        getiter={"https://api.github.com/orgs/python/teams": teams}, getitem=items
    )
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/labels"
    assert post_[1] == [awaiting.Blocker.core_review.value]

    # Published PR is unpublished (converted to Draft)
    data["action"] = "converted_to_draft"
    data["pull_request"]["draft"] = True
    encoded_label = "awaiting%20core%20review"
    items[issue_url] = {
        "labels": [
            {
                "url": f"https://api.github.com/repos/python/cpython/labels/{encoded_label}",
                "name": "awaiting core review",
            },
            {
                "url": "https://api.github.com/repos/python/cpython/labels/CLA%20signed",
                "name": "CLA signed",
            },
        ],
        "labels_url": "https://api.github.com/repos/python/cpython/issues/12345/labels{/name}",
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(
        getiter={"https://api.github.com/orgs/python/teams": teams}, getitem=items
    )
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 0
    assert (
        gh.delete_url ==
        f"https://api.github.com/repos/python/cpython/issues/12345/labels/{encoded_label}"
    )


async def test_edited_pr_title():
    # regression test for https://github.com/python/bedevere/issues/556
    # test that editing the PR title doesn't change the Blocker labels
    username = "itamaro"
    issue_url = "https://api.github.com/issue/42"
    data = {
        "action": "edited",
        "pull_request": {
            "user": {
                "login": username,
            },
            "issue_url": issue_url,
            "draft": False,
            "title": "So long and thanks for all the fish",
        },
        "changes": {
            "title": "So long and thanks for all the phish",
        }
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    teams = [{"name": "python core", "id": 6}]
    encoded_label = "awaiting%20review"
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        issue_url: {
            "labels": [
                {
                    "url": f"https://api.github.com/repos/python/cpython/labels/{encoded_label}",
                    "name": "awaiting review",
                },
                {
                    "url": "https://api.github.com/repos/python/cpython/labels/CLA%20signed",
                    "name": "CLA signed",
                },
            ],
            "labels_url": "https://api.github.com/repos/python/cpython/issues/12345/labels{/name}",
        },
    }
    gh = FakeGH(
        getiter={"https://api.github.com/orgs/python/teams": teams}, getitem=items
    )
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 0
    assert gh.delete_url is None


async def test_opened_pr():
    # New PR from a core dev.
    username = "brettcannon"
    issue_url = "https://api.github.com/issue/42"
    data = {
        "action": "opened",
        "pull_request": {
            "user": {
                "login": username,
            },
            "issue_url": issue_url,
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": "OK",
        issue_url: {"labels": [], "labels_url": "https://api.github.com/labels"},
    }
    gh = FakeGH(
        getiter={"https://api.github.com/orgs/python/teams": teams}, getitem=items
    )
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/labels"
    assert post_[1] == [awaiting.Blocker.core_review.value]

    # New PR from a non-core dev.
    username = "andreamcinnes"
    issue_url = "https://api.github.com/issue/42"
    data = {
        "action": "opened",
        "pull_request": {
            "user": {
                "login": username,
            },
            "issue_url": issue_url,
            "draft": False,
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        issue_url: {"labels": [], "labels_url": "https://api.github.com/labels"},
    }
    gh = FakeGH(
        getiter={"https://api.github.com/orgs/python/teams": teams}, getitem=items
    )
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/labels"
    assert post_[1] == [awaiting.Blocker.review.value]


async def test_new_review():
    # First non-comment review from a non-core dev.
    username = "andreamcinnes"
    data = {
        "action": "submitted",
        "review": {
            "state": "approved",
            "user": {
                "login": username,
            },
        },
        "pull_request": {
            "url": "https://api.github.com/pr/42",
            "issue_url": "https://api.github.com/issue/42",
            "state": "open",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        "https://api.github.com/teams/6/memberships/brettcannon": True,
        "https://api.github.com/issue/42": {
            "labels": [],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": "brettcannon"}, "state": "commented"}
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/labels/42"
    assert post_[1] == [awaiting.Blocker.core_review.value]

    # First and second review from a non-core dev.
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        "https://api.github.com/teams/6/memberships/brettcannon": True,
        "https://api.github.com/issue/42": {
            "labels": [],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": "brettcannon"}, "state": "approved"}
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert not gh.post_

    # First comment review from a non-core dev.
    data = {
        "action": "submitted",
        "review": {
            "state": "comment",
            "user": {
                "login": username,
            },
        },
        "pull_request": {
            "url": "https://api.github.com/pr/42",
            "issue_url": "https://api.github.com/issue/42",
            "state": "open",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        "https://api.github.com/teams/6/memberships/brettcannon": True,
        "https://api.github.com/issue/42": {
            "labels": [],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": "brettcannon"}, "state": "approved"}
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert not gh.post_

    # Core dev submits an approving review.
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
            "state": "open",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": True,
        "https://api.github.com/issue/42": {
            "labels": [{"name": awaiting.Blocker.changes.value}],
            "labels_url": "https://api.github.com/labels/42",
        },
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

    # Core dev submits an approving review on an already closed pull request.
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
            "state": "closed",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": True,
        "https://api.github.com/issue/42": {
            "labels": [{"name": awaiting.Blocker.changes.value}],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert not gh.post_

    # Core dev requests changes.
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
            "user": {"login": "miss-islington"},
            "state": "open",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": True,
        f"https://api.github.com/teams/6/memberships/miss-islington": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        "https://api.github.com/issue/42": {
            "labels": [],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 2
    labeling = gh.post_[0]
    assert labeling[0] == "https://api.github.com/labels/42"
    assert labeling[1] == [awaiting.Blocker.changes.value]
    message = gh.post_[1]
    assert message[0] == "https://api.github.com/comment/42"
    assert awaiting.BORING_TRIGGER_PHRASE in message[1]["body"]

    # Comment reviews do nothing.
    data = {
        "action": "submitted",
        "review": {
            "user": {
                "login": username,
            },
            "state": "commented".upper(),
        },
        "pull_request": {
            "url": "https://api.github.com/pr/42",
            "issue_url": "https://api.github.com/issue/42",
            "comments_url": "https://api.github.com/comment/42",
            "state": "open",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert not len(gh.post_)

    # Skip commenting if "awaiting changes" is already set.
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
            "state": "open",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": True,
        "https://api.github.com/issue/42": {
            "labels": [{"name": awaiting.Blocker.changes.value}],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert not len(gh.post_)


async def test_dismissed_review():
    # Last non-core review is dismissed > downgrade
    username = "andreamcinnes"
    data = {
        "action": "dismissed",
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
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        "https://api.github.com/teams/6/memberships/brettcannon": True,
        "https://api.github.com/issue/42": {
            "labels": [{"name": awaiting.Blocker.core_review.value}],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": "brettcannon"}, "state": "commented"}
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/labels/42"
    assert post_[1] == [awaiting.Blocker.review.value]

    # Non-core review is dismissed, but core review remains > no change
    username = "andreamcinnes"
    data = {
        "action": "dismissed",
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
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        "https://api.github.com/teams/6/memberships/brettcannon": True,
        "https://api.github.com/issue/42": {
            "labels": [{"name": awaiting.Blocker.merge.value}],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": "brettcannon"}, "state": "approved"}
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 0

    # Non-core review is dismissed, but non-core review remains > no change
    username = "andreamcinnes"
    data = {
        "action": "dismissed",
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
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        f"https://api.github.com/teams/6/memberships/notbrettcannon": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        "https://api.github.com/issue/42": {
            "labels": [{"name": awaiting.Blocker.core_review.value}],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": "notbrettcannon"}, "state": "approved"}
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 0

    # Last core review is dismissed > double downgrade
    username = "brettcannon"
    data = {
        "action": "dismissed",
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
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": True,
        f"https://api.github.com/teams/6/memberships/notbrettcannon": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        "https://api.github.com/issue/42": {
            "labels": [{"name": awaiting.Blocker.merge.value}],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": "notbrettcannon"}, "state": "commented"}
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/labels/42"
    assert post_[1] == [awaiting.Blocker.review.value]

    # Last core review is dismissed, non-core remains > downgrade
    username = "brettcannon"
    data = {
        "action": "dismissed",
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
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": True,
        f"https://api.github.com/teams/6/memberships/notbrettcannon": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        "https://api.github.com/issue/42": {
            "labels": [{"name": awaiting.Blocker.merge.value}],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": "notbrettcannon"}, "state": "approved"}
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/labels/42"
    assert post_[1] == [awaiting.Blocker.core_review.value]

    # Core review is dismissed, but one core remains > no change
    username = "brettcannon"
    data = {
        "action": "dismissed",
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
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": True,
        f"https://api.github.com/teams/6/memberships/brettcannonalias": True,
        "https://api.github.com/issue/42": {
            "labels": [{"name": awaiting.Blocker.merge.value}],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": "brettcannonalias"}, "state": "approved"}
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 0


async def test_non_core_dev_does_not_downgrade():
    core_dev = "brettcannon"
    non_core_dev = "andreamcinnes"
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{non_core_dev}": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        f"https://api.github.com/teams/6/memberships/{core_dev}": True,
        "https://api.github.com/issue/42": {
            "labels": [],
            "labels_url": "https://api.github.com/labels/42",
        },
    }

    # Approval from a core dev changes the state to "Awaiting merge".
    data = {
        "action": "submitted",
        "review": {
            "state": "approved",
            "user": {
                "login": core_dev,
            },
        },
        "pull_request": {
            "url": "https://api.github.com/pr/42",
            "issue_url": "https://api.github.com/issue/42",
            "state": "open",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": core_dev}, "state": "approved"}
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 1
    post_ = gh.post_[0]
    assert post_[0] == "https://api.github.com/labels/42"
    assert post_[1] == [awaiting.Blocker.merge.value]

    # Non-comment review from a non-core dev doesn't "downgrade" the PR's state.
    data = {
        "action": "submitted",
        "review": {
            "state": "approved",
            "user": {
                "login": non_core_dev,
            },
        },
        "pull_request": {
            "url": "https://api.github.com/pr/42",
            "issue_url": "https://api.github.com/issue/42",
            "state": "open",
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": core_dev}, "state": "approved"},
            {"user": {"login": non_core_dev}, "state": "approved"},
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert not gh.post_


async def test_new_comment():
    # Comment not from PR author.
    data = {
        "action": "created",
        "issue": {"user": {"login": "andreamcinnes"}},
        "comment": {
            "user": {"login": "brettcannon"},
            "body": awaiting.BORING_TRIGGER_PHRASE,
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
            "body": awaiting.BORING_TRIGGER_PHRASE,
        },
    }
    event = sansio.Event(data, event="issue_comment", delivery_id="12345")
    items = {
        "https://api.github.com/teams/6/memberships/brettcannon": True,
        "https://api.github.com/teams/6/memberships/gvanrossum": True,
        "https://api.github.com/teams/6/memberships/not-core-dev": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": [{"name": "python core", "id": 6}],
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": "brettcannon"}, "state": "approved"},
            {"user": {"login": "gvanrossum"}, "state": "changes_requested"},
            {"user": {"login": "not-core-dev"}, "state": "approved"},
        ],
    }
    gh = FakeGH(getitem=items, getiter=iterators)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 3
    labeling, comment, review_request = gh.post_
    assert labeling[0] == "https://api.github.com/labels/42"
    assert labeling[1] == [awaiting.Blocker.change_review.value]
    assert comment[0] == "https://api.github.com/comments/42"
    comment_body = comment[1]["body"]
    assert "@brettcannon" in comment_body
    assert "@gvanrossum" in comment_body
    assert "not-core-dev" not in comment_body
    assert review_request[0] == "https://api.github.com/pr/42/requested_reviewers"
    requested_reviewers = review_request[1]["reviewers"]
    assert "brettcannon" in requested_reviewers
    assert "gvanrossum" in requested_reviewers
    assert "not-core-dev" not in requested_reviewers

    # All is right with the Monty Python world.
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
            "body": awaiting.FUN_TRIGGER_PHRASE,
        },
    }
    event = sansio.Event(data, event="issue_comment", delivery_id="12345")
    gh = FakeGH(getitem=items, getiter=iterators)
    await awaiting.router.dispatch(event, gh)
    assert len(gh.post_) == 3
    labeling, comment, review_request = gh.post_
    assert labeling[0] == "https://api.github.com/labels/42"
    assert labeling[1] == [awaiting.Blocker.change_review.value]
    assert comment[0] == "https://api.github.com/comments/42"
    comment_body = comment[1]["body"]
    assert "@brettcannon" in comment_body
    assert "@gvanrossum" in comment_body
    assert "not-core-dev" not in comment_body
    assert review_request[0] == "https://api.github.com/pr/42/requested_reviewers"
    requested_reviewers = review_request[1]["reviewers"]
    assert "brettcannon" in requested_reviewers
    assert "gvanrossum" in requested_reviewers
    assert "not-core-dev" not in requested_reviewers


async def test_change_requested_for_core_dev():
    data = {
        "action": "submitted",
        "review": {
            "user": {
                "login": "gvanrossum",
            },
            "state": "changes_requested".upper(),
        },
        "pull_request": {
            "url": "https://api.github.com/pr/42",
            "issue_url": "https://api.github.com/issue/42",
            "comments_url": "https://api.github.com/comment/42",
            "user": {"login": "brettcannon"},
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/gvanrossum": True,
        "https://api.github.com/teams/6/memberships/brettcannon": True,
        "https://api.github.com/issue/42": {
            "labels": [],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": "brettcannon"}, "state": "changes_requested"}
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)

    assert len(gh.post_) == 2
    labeling = gh.post_[0]
    assert labeling[0] == "https://api.github.com/labels/42"
    assert labeling[1] == [awaiting.Blocker.changes.value]
    message = gh.post_[1]
    assert message[0] == "https://api.github.com/comment/42"

    core_dev_message = awaiting.CORE_DEV_CHANGES_REQUESTED_MESSAGE.replace(
        "{easter_egg}", ""
    ).strip()
    assert core_dev_message in message[1]["body"]


async def test_change_requested_for_non_core_dev():
    data = {
        "action": "submitted",
        "review": {
            "user": {
                "login": "gvanrossum",
            },
            "state": "changes_requested".upper(),
        },
        "pull_request": {
            "url": "https://api.github.com/pr/42",
            "issue_url": "https://api.github.com/issue/42",
            "comments_url": "https://api.github.com/comment/42",
            "user": {"login": "miss-islington"},
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="12345")
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/gvanrossum": True,
        "https://api.github.com/teams/6/memberships/miss-islington": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        ),
        "https://api.github.com/issue/42": {
            "labels": [],
            "labels_url": "https://api.github.com/labels/42",
        },
    }
    iterators = {
        "https://api.github.com/orgs/python/teams": teams,
        "https://api.github.com/pr/42/reviews": [
            {"user": {"login": "brettcannon"}, "state": "changes_requested"}
        ],
    }
    gh = FakeGH(getiter=iterators, getitem=items)
    await awaiting.router.dispatch(event, gh)

    assert len(gh.post_) == 2
    labeling = gh.post_[0]
    assert labeling[0] == "https://api.github.com/labels/42"
    assert labeling[1] == [awaiting.Blocker.changes.value]
    message = gh.post_[1]
    assert message[0] == "https://api.github.com/comment/42"

    change_requested_message = awaiting.CHANGES_REQUESTED_MESSAGE.replace(
        "{easter_egg}", ""
    ).strip()
    assert change_requested_message in message[1]["body"]


awaiting_labels = (
    "awaiting change review",
    "awaiting changes",
    "awaiting core review",
    "awaiting merge",
    "awaiting review",
)


@pytest.mark.parametrize("label", awaiting_labels)
async def test_awaiting_label_removed_when_pr_merged(label):
    encoded_label = label.replace(" ", "%20")

    issue_url = "https://api.github.com/repos/org/proj/issues/3749"
    data = {
        "action": "closed",
        "pull_request": {
            "merged": True,
            "issue_url": issue_url,
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")

    issue_data = {
        issue_url: {
            "labels": [
                {
                    "url": f"https://api.github.com/repos/python/cpython/labels/{encoded_label}",
                    "name": label,
                },
                {
                    "url": "https://api.github.com/repos/python/cpython/labels/CLA%20signed",
                    "name": "CLA signed",
                },
            ],
            "labels_url": "https://api.github.com/repos/python/cpython/issues/12345/labels{/name}",
        },
    }

    gh = FakeGH(getitem=issue_data)

    await awaiting.router.dispatch(event, gh)
    assert (
        gh.delete_url
        == f"https://api.github.com/repos/python/cpython/issues/12345/labels/{encoded_label}"
    )


@pytest.mark.parametrize("label", awaiting_labels)
async def test_awaiting_label_not_removed_when_pr_not_merged(label):
    encoded_label = label.replace(" ", "%20")

    issue_url = "https://api.github.com/repos/org/proj/issues/3749"
    data = {
        "action": "closed",
        "pull_request": {
            "merged": False,
            "issue_url": issue_url,
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")

    issue_data = {
        issue_url: {
            "labels": [
                {
                    "url": f"https://api.github.com/repos/python/cpython/labels/{encoded_label}",
                    "name": label,
                },
                {
                    "url": "https://api.github.com/repos/python/cpython/labels/CLA%20signed",
                    "name": "CLA signed",
                },
            ],
            "labels_url": "https://api.github.com/repos/python/cpython/issues/12345/labels{/name}",
        },
    }

    gh = FakeGH(getitem=issue_data)

    await awaiting.router.dispatch(event, gh)
    assert gh.delete_url is None


async def test_new_commit_pushed_to_approved_pr():
    # There is new commit on approved PR
    username = "brettcannon"
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    data = {"commits": [{"id": sha}]}
    event = sansio.Event(data, event="push", delivery_id="12345")
    teams = [{"name": "python core", "id": 6}]
    items = {
        f"https://api.github.com/teams/6/memberships/{username}": "OK",
        f"https://api.github.com/search/issues?q=type:pr+repo:python/cpython+sha:{sha}": {
            "total_count": 1,
            "items": [
                {
                    "number": 5547,
                    "title": "[3.6] bpo-32720: Fixed the replacement field grammar documentation. (GH-5544)",
                    "body": "\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>",
                    "labels": [
                        {
                            "name": "CLA signed",
                        },
                        {
                            "name": "awaiting merge",
                        },
                    ],
                    "issue_url": "/repos/python/cpython/issues/5547",
                }
            ],
        },
        "https://api.github.com/repos/python/cpython/issues/5547": {
            "labels": [{"name": "awaiting merge"}],
            "labels_url": "https://api.github.com/repos/python/cpython/issues/5547/labels{/name}",
            "pull_request": {
                "url": "https://api.github.com/repos/python/cpython/pulls/5547",
            },
            "comments_url": "https://api.github.com/repos/python/cpython/issues/5547/comments",
        },
    }
    gh = FakeGH(
        getiter={
            "https://api.github.com/orgs/python/teams": teams,
            "https://api.github.com/repos/python/cpython/pulls/5547/reviews": [
                {"user": {"login": "brettcannon"}, "state": "approved"}
            ],
        },
        getitem=items,
    )
    await awaiting.router.dispatch(event, gh)

    # 3 posts:
    # - change the label
    # - leave a comment
    # - re-request review
    assert len(gh.post_) == 3

    assert (
        gh.post_[0][0]
        == "https://api.github.com/repos/python/cpython/issues/5547/labels"
    )
    assert gh.post_[0][1] == [awaiting.Blocker.core_review.value]

    assert (
        gh.post_[1][0]
        == "https://api.github.com/repos/python/cpython/issues/5547/comments"
    )
    assert gh.post_[1][1] == {
        "body": ACK.format(
            greeting="There's a new commit after the PR has been approved.",
            core_devs="@brettcannon",
        )
    }


async def test_new_commit_pushed_to_not_approved_pr():
    # There is new commit on approved PR
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    data = {"commits": [{"id": sha}]}
    event = sansio.Event(data, event="push", delivery_id="12345")
    items = {
        f"https://api.github.com/search/issues?q=type:pr+repo:python/cpython+sha:{sha}": {
            "total_count": 1,
            "items": [
                {
                    "number": 5547,
                    "title": "[3.6] bpo-32720: Fixed the replacement field grammar documentation. (GH-5544)",
                    "body": "\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>",
                    "labels": [
                        {
                            "name": "CLA signed",
                        },
                        {
                            "name": "awaiting review",
                        },
                    ],
                    "issue_url": "/repos/python/cpython/issues/5547",
                }
            ],
        },
    }
    gh = FakeGH(getitem=items)
    await awaiting.router.dispatch(event, gh)

    # no posts
    assert len(gh.post_) == 0


async def test_pushed_without_commits():
    # There is new commit on approved PR
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    data = {"commits": []}
    event = sansio.Event(data, event="push", delivery_id="12345")
    gh = FakeGH()
    await awaiting.router.dispatch(event, gh)

    # no posts
    assert len(gh.post_) == 0
