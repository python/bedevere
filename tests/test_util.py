import http

import gidgethub
import pytest
from unittest.mock import patch

from bedevere import util

from .test_stage import FakeGH


def test_StatusState():
    assert util.StatusState.SUCCESS.value == "success"
    assert util.StatusState.ERROR.value == "error"
    assert util.StatusState.FAILURE.value == "failure"


class TestCreateStatus:
    def test_simple_case(self):
        expected = {"state": "success", "context": "me"}
        assert util.create_status("me", util.StatusState.SUCCESS) == expected

    def test_with_description(self):
        expected = {"state": "error", "context": "me", "description": "desc"}
        status = util.create_status("me", util.StatusState.ERROR, description="desc")
        assert status == expected

    def test_with_target_url(self):
        expected = {
            "state": "failure",
            "context": "me",
            "target_url": "https://devguide.python.org",
        }
        status = util.create_status(
            "me", util.StatusState.FAILURE, target_url="https://devguide.python.org"
        )
        assert status == expected

    def test_with_everything(self):
        expected = {
            "state": "failure",
            "context": "me",
            "description": "desc",
            "target_url": "https://devguide.python.org",
        }
        status = util.create_status(
            "me",
            util.StatusState.FAILURE,
            description="desc",
            target_url="https://devguide.python.org",
        )
        assert status == expected


def test_skip():
    issue = {"labels": [{"name": "CLA signed"}, {"name": "skip something"}]}
    assert util.skip("something", issue)

    issue = {"labels": [{"name": "CLA signed"}]}
    assert not util.skip("something", issue)


async def test_is_core_dev():
    teams = [{"name": "not Python core"}]
    gh = FakeGH(getiter={"https://api.github.com/orgs/python/teams": teams})
    with pytest.raises(ValueError):
        await util.is_core_dev(gh, "brett")

    teams = [{"name": "Python core", "id": 42}]
    getitem = {"https://api.github.com/teams/42/memberships/brett": True}
    gh = FakeGH(
        getiter={"https://api.github.com/orgs/python/teams": teams}, getitem=getitem
    )
    assert await util.is_core_dev(gh, "brett")
    assert gh.getiter_url == "https://api.github.com/orgs/python/teams"

    teams = [{"name": "Python core", "id": 42}]
    getitem = {
        "https://api.github.com/teams/42/memberships/andrea": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        )
    }
    gh = FakeGH(
        getiter={"https://api.github.com/orgs/python/teams": teams}, getitem=getitem
    )
    assert not await util.is_core_dev(gh, "andrea")

    teams = [{"name": "Python core", "id": 42}]
    getitem = {
        "https://api.github.com/teams/42/memberships/andrea": gidgethub.BadRequest(
            status_code=http.HTTPStatus(400)
        )
    }
    gh = FakeGH(
        getiter={"https://api.github.com/orgs/python/teams": teams}, getitem=getitem
    )
    with pytest.raises(gidgethub.BadRequest):
        await util.is_core_dev(gh, "andrea")


def test_title_normalization():
    title = "abcd"
    body = "1234"
    assert util.normalize_title(title, body) == title

    title = "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations …"
    body = "…(GH-1478)\r\n\r\nstuff"
    expected = (
        "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations (GH-1478)"
    )
    assert util.normalize_title(title, body) == expected

    title = "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations …"
    body = "…(GH-1478)"
    assert util.normalize_title(title, body) == expected

    title = (
        "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations (GH-14…"
    )
    body = "…78)"
    assert util.normalize_title(title, body) == expected


async def test_get_pr_for_commit():
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    gh = FakeGH(
        getitem={
            f"https://api.github.com/search/issues?q=type:pr+repo:python/cpython+sha:{sha}": {
                "total_count": 1,
                "items": [
                    {
                        "number": 5547,
                        "title": "[3.6] bpo-32720: Fixed the replacement field grammar documentation. (GH-5544)",
                        "body": "\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>",
                    }
                ],
            }
        }
    )
    result = await util.get_pr_for_commit(gh, sha)
    assert result == {
        "number": 5547,
        "title": "[3.6] bpo-32720: Fixed the replacement field grammar documentation. (GH-5544)",
        "body": "\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>",
    }


async def test_get_pr_for_commit_not_found():
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    gh = FakeGH(
        getitem={
            f"https://api.github.com/search/issues?q=type:pr+repo:python/cpython+sha:{sha}": {
                "total_count": 0,
                "items": [],
            }
        }
    )
    result = await util.get_pr_for_commit(gh, sha)

    assert result is None


async def test_patch_body_adds_issue_if_not_present():
    """Updates the description of a PR/Issue with the gh issue/pr number if it exists.

    returns if body exists with issue/pr number
    """
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    gh = FakeGH(
        getitem={
            f"https://api.github.com/search/issues?q=type:pr+repo:python/cpython+sha:{sha}": {
                "total_count": 0,
                "items": [],
            }
        }
    )
    vals = {}
    vals["url"] = "https://fake.com"
    vals["body"] = "GH-1234\n"

    with patch.object(gh, "patch") as mock:
        await util.patch_body(gh, util.PR, vals, 1234)
        mock.assert_not_called()
    with patch.object(gh, "patch") as mock:
        vals["body"] = "Multiple\nlines\nwith gh-1234 in some prose"
        await util.patch_body(gh, util.PR, vals, 1234)
        mock.assert_not_called()
    with patch.object(gh, "patch") as mock:
        vals["body"] = "#1234 in some prose"
        await util.patch_body(gh, util.PR, vals, 1234)
        mock.assert_not_called()
    with patch.object(gh, "patch") as mock:
        vals["body"] = "Some prose mentioning gh-12345 but not our issue"
        await util.patch_body(gh, util.PR, vals, 1234)
        mock.assert_called_once()
    with patch.object(gh, "patch") as mock:
        vals["body"] = None
        await util.patch_body(gh, util.PR, vals, 1234)
        mock.assert_called_once()
    with patch.object(gh, "patch") as mock:
        vals["body"] = ""
        await util.patch_body(gh, util.PR, vals, 1234)
        data = {"body": "\n\n<!-- gh-issue-number: gh-1234 -->\n* Issue: gh-1234\n<!-- /gh-issue-number -->\n"}
        mock.assert_called_once_with("https://fake.com", data=data)
    assert await gh.patch(vals["url"], data=vals) == None


async def test_patch_body_adds_pr_if_not_present():
    """Updates the description of a PR/Issue with the gh issue/pr number if it exists.

    returns if body exists with issue/pr number
    """
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    gh = FakeGH(
        getitem={
            f"https://api.github.com/search/issues?q=type:pr+repo:python/cpython+sha:{sha}": {
                "total_count": 0,
                "items": [],
            }
        }
    )
    vals = {}
    vals["url"] = "https://fake.com"
    vals["body"] = "GH-1234\n"

    with patch.object(gh, "patch") as mock:
        await util.patch_body(gh, util.ISSUE, vals, 1234)
        mock.assert_not_called()
    with patch.object(gh, "patch") as mock:
        vals["body"] = "Multiple\nlines\nwith gh-1234 in some prose"
        await util.patch_body(gh, util.ISSUE, vals, 1234)
        mock.assert_not_called()
    with patch.object(gh, "patch") as mock:
        vals["body"] = "#1234 in some prose"
        await util.patch_body(gh, util.ISSUE, vals, 1234)
        mock.assert_not_called()
    with patch.object(gh, "patch") as mock:
        vals["body"] = "Some prose mentioning gh-12345 but not our issue"
        await util.patch_body(gh, util.ISSUE, vals, 1234)
        mock.assert_called_once()
    with patch.object(gh, "patch") as mock:
        vals["body"] = None
        await util.patch_body(gh, util.ISSUE, vals, 1234)
        mock.assert_called_once()
    with patch.object(gh, "patch") as mock:
        vals["body"] = ""
        await util.patch_body(gh, util.ISSUE, vals, 1234)
        data = {
            "body": (
                "\n\n<!-- gh-linked-prs -->\n"
                "### Linked PRs\n* gh-1234\n"
                "<!-- /gh-linked-prs -->\n"
            )
        }
        mock.assert_called_once_with("https://fake.com", data=data)
    with patch.object(gh, "patch") as mock:
        vals["body"] = (
            "\n\n<!-- gh-linked-prs -->\n"
            "### Linked PRs\n* gh-1234\n"
            "<!-- /gh-linked-prs -->\n"
        )
        await util.patch_body(gh, util.ISSUE, vals, 54321)
        data = {
            "body": (
                "\n\n<!-- gh-linked-prs -->\n"
                "### Linked PRs\n* gh-1234\n* gh-54321\n"
                "<!-- /gh-linked-prs -->\n"
            )
        }
        mock.assert_called_once_with("https://fake.com", data=data)
    assert await gh.patch(vals["url"], data=vals) == None


async def test_patch_body_adds_pr_to_legacy_issue_body():
    """Updates the description of a PR/Issue with the gh issue/pr number if it exists.

    returns if body exists with issue/pr number
    """
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    gh = FakeGH(
        getitem={
            f"https://api.github.com/search/issues?q=type:pr+repo:python/cpython+sha:{sha}": {
                "total_count": 0,
                "items": [],
            }
        }
    )
    vals = {}
    vals["url"] = "https://fake.com"
    vals["body"] = "GH-1234\n"

    with patch.object(gh, "patch") as mock:
        vals["body"] = (
            "<!-- gh-pr-number: gh-103 -->\n"
            "* PR: gh-103\n"
            "<!-- /gh-pr-number -->\n"
        )
        await util.patch_body(gh, util.ISSUE, vals, 54321)
        data = {
            "body": (
                "<!-- gh-pr-number: gh-103 -->\n"
                "* PR: gh-103\n"
                "<!-- /gh-pr-number -->\n"
                "\n\n<!-- gh-pr-number: gh-54321 -->\n"
                "* PR: gh-54321\n"
                "<!-- /gh-pr-number -->\n"
            )
        }
        mock.assert_called_once_with("https://fake.com", data=data)
    assert await gh.patch(vals["url"], data=vals) == None
