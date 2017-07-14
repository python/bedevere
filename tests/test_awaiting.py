{'name': 'Python core', 'id': 2011335, 'slug': 'python-core', 'description': 'Core developers of CPython & the Python language', 'privacy': 'closed', 'url': 'https://api.github.com/teams/2011335', 'members_url': 'https://api.github.com/teams/2011335/members{/member}', 'repositories_url': 'https://api.github.com/teams/2011335/repos', 'permission': 'pull'}

import http

import pytest

import gidgethub
from gidgethub import sansio

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
        if isinstance(self._getitem_return, Exception):
            raise self._getitem_return
        else:
            return self._getitem_return

    async def delete(self, url, url_vars={}):
        self.delete_url = sansio.format_url(url, url_vars)

    async def post(self, url, *, data):
        self.post_url = url
        self.post_data = data


async def test_is_core_dev():
    teams = [{"name": "not Python core"}]
    gh = FakeGH(getiter=teams)
    with pytest.raises(ValueError):
        await awaiting.is_core_dev(gh, "brett")
    teams = [{"name": "Python core", "id": 42}]
    gh = FakeGH(getiter=teams)
    assert await awaiting.is_core_dev(gh, "brett")
    assert gh.getiter_url == "https://api.github.com/orgs/python/teams"
    assert gh.getitem_url == "https://api.github.com/teams/42/memberships/brett"
    teams = [{"name": "Python core", "id": 42}]
    gh = FakeGH(getiter=teams,
                getitem=gidgethub.BadRequest(status_code=http.HTTPStatus(404)))
    assert not await awaiting.is_core_dev(gh, "andrea")
    teams = [{"name": "Python core", "id": 42}]
    gh = FakeGH(getiter=teams,
                getitem=gidgethub.BadRequest(status_code=http.HTTPStatus(400)))
    with pytest.raises(gidgethub.BadRequest):
        await awaiting.is_core_dev(gh, "andrea")


async def test_stage():
    # XXX not doing any work if label already set
    # XXX remove any old "awaiting" labels
    # XXX add new label
