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
        self.post_url = self.post_data = None

    async def getiter(self, url, url_vars={}):
        self.getiter_url = sansio.format_url(url, url_vars)
        for item in self._getiter_return:
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
        self.post_url = sansio.format_url(url, url_vars)
        self.post_data = data


async def test_is_core_dev():
    teams = [{"name": "not Python core"}]
    gh = FakeGH(getiter=teams)
    with pytest.raises(ValueError):
        await awaiting.is_core_dev(gh, "brett")

    teams = [{"name": "Python core", "id": 42}]
    getitem = {"https://api.github.com/teams/42/memberships/brett": True}
    gh = FakeGH(getiter=teams, getitem=getitem)
    assert await awaiting.is_core_dev(gh, "brett")
    assert gh.getiter_url == "https://api.github.com/orgs/python/teams"

    teams = [{"name": "Python core", "id": 42}]
    getitem = {"https://api.github.com/teams/42/memberships/andrea":
                gidgethub.BadRequest(status_code=http.HTTPStatus(404))}
    gh = FakeGH(getiter=teams, getitem=getitem)
    assert not await awaiting.is_core_dev(gh, "andrea")

    teams = [{"name": "Python core", "id": 42}]
    getitem = {"https://api.github.com/teams/42/memberships/andrea":
                gidgethub.BadRequest(status_code=http.HTTPStatus(400))}
    gh = FakeGH(getiter=teams, getitem=getitem)
    with pytest.raises(gidgethub.BadRequest):
        await awaiting.is_core_dev(gh, "andrea")


async def test_stage():
    issue = {"labels": [{"name": "awaiting merge"}]}
    issue_url = "https://api.github.com/some/issue"
    pull_request = {"issue_url": issue_url}
    gh = FakeGH(getitem={issue_url: issue})
    await awaiting.stage(gh, pull_request, awaiting.Blocker.merge)
    assert not gh.delete_url
    assert not gh.post_url

    issue = {
        "labels": [{"name": "awaiting review"}],
        "labels_url":
            "https://api.github.com/repos/python/cpython/issues/42/labels{/name}",
    }
    gh = FakeGH(getitem={issue_url: issue})
    await awaiting.stage(gh, pull_request, awaiting.Blocker.merge)
    assert gh.delete_url == "https://api.github.com/repos/python/cpython/issues/42/labels/awaiting%20review"
    assert gh.post_url == "https://api.github.com/repos/python/cpython/issues/42/labels"
    assert gh.post_data == ["awaiting merge"]


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
    gh = FakeGH(getiter=teams, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert gh.post_url == "https://api.github.com/labels"
    assert gh.post_data == [awaiting.Blocker.merge.value]

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
    gh = FakeGH(getiter=teams, getitem=items)
    await awaiting.router.dispatch(event, gh)
    assert gh.post_url == "https://api.github.com/labels"
    assert gh.post_data == [awaiting.Blocker.review.value]
