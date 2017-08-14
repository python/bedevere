import http

import gidgethub
import pytest

from bedevere import util

from .test_stage import FakeGH


def test_StatusState():
    assert util.StatusState.SUCCESS.value == 'success'
    assert util.StatusState.ERROR.value == 'error'
    assert util.StatusState.FAILURE.value == 'failure'


class TestCreateStatus:

    def test_simple_case(self):
        expected = {'state': 'success', 'context': 'me'}
        assert util.create_status('me', util.StatusState.SUCCESS) == expected

    def test_with_description(self):
        expected = {'state': 'error', 'context': 'me', 'description': 'desc'}
        status = util.create_status('me', util.StatusState.ERROR,
                                    description='desc')
        assert status == expected

    def test_with_target_url(self):
        expected = {'state': 'failure', 'context': 'me',
                    'target_url': 'https://devguide.python.org'}
        status = util.create_status('me', util.StatusState.FAILURE,
                                    target_url='https://devguide.python.org')
        assert status == expected

    def test_with_everything(self):
        expected = {'state': 'failure', 'context': 'me',
                    'description': 'desc',
                    'target_url': 'https://devguide.python.org'}
        status = util.create_status('me', util.StatusState.FAILURE,
                                    description='desc',
                                    target_url='https://devguide.python.org')
        assert status == expected


def test_skip():
    issue = {'labels': [{'name': 'CLA signed'}, {'name': 'skip something'}]}
    assert util.skip("something", issue)

    issue = {'labels': [{'name': 'CLA signed'}]}
    assert not util.skip("something", issue)


async def test_is_core_dev():
    teams = [{"name": "not Python core"}]
    gh = FakeGH(getiter={"https://api.github.com/orgs/python/teams": teams})
    with pytest.raises(ValueError):
        await util.is_core_dev(gh, "brett")

    teams = [{"name": "Python core", "id": 42}]
    getitem = {"https://api.github.com/teams/42/memberships/brett": True}
    gh = FakeGH(getiter={"https://api.github.com/orgs/python/teams": teams},
                getitem=getitem)
    assert await util.is_core_dev(gh, "brett")
    assert gh.getiter_url == "https://api.github.com/orgs/python/teams"

    teams = [{"name": "Python core", "id": 42}]
    getitem = {"https://api.github.com/teams/42/memberships/andrea":
                gidgethub.BadRequest(status_code=http.HTTPStatus(404))}
    gh = FakeGH(getiter={"https://api.github.com/orgs/python/teams": teams},
                getitem=getitem)
    assert not await util.is_core_dev(gh, "andrea")

    teams = [{"name": "Python core", "id": 42}]
    getitem = {"https://api.github.com/teams/42/memberships/andrea":
                gidgethub.BadRequest(status_code=http.HTTPStatus(400))}
    gh = FakeGH(getiter={"https://api.github.com/orgs/python/teams": teams},
                getitem=getitem)
    with pytest.raises(gidgethub.BadRequest):
        await util.is_core_dev(gh, "andrea")


def test_title_normalization():
    title = "abcd"
    body = "1234"
    assert util.normalize_title(title, body) == title

    title = "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations …"
    body = "…(GH-1478)\r\n\r\nstuff"
    expected = '[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations (GH-1478)'
    assert util.normalize_title(title, body) == expected

    title = "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations …"
    body = "…(GH-1478)"
    assert util.normalize_title(title, body) == expected

    title = "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations (GH-14…"
    body = "…78)"
    assert util.normalize_title(title, body) == expected
