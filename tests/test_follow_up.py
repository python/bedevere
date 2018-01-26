import pytest

from gidgethub import sansio

from bedevere import follow_up


class FakeGH:

    def __init__(self, *, getitem=None, post=None):
        self._getitem_return = getitem
        self._post_return = post
        self.getitem_url = None
        self.post_url = self.post_data = None

    async def getitem(self, url, url_vars={}):
        self.getitem_url = sansio.format_url(url, url_vars)
        return self._getitem_return[self.getitem_url]

    async def post(self, url, url_vars={}, *, data):
        self.post_url = sansio.format_url(url, url_vars)
        self.post_data = data


@pytest.mark.asyncio
async def test_remind_to_replace_gh_number():
    data = {
        "action": "closed",
        "pull_request": {
            "number": 5326,
            "merged": True,
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
            "merge_commit_sha": "6ab62920c87930dedc31fe633ecda3e51d3d7503",
            "comments_url": "https://api.github.com/repos/python/cpython/pulls/5326/comments",
        },
        "repository": {
            "commits_url": "https://api.github.com/repos/python/cpython/commits{/sha}"
        }
    }

    getitem = {
        "https://api.github.com/repos/python/cpython/commits/6ab62920c87930dedc31fe633ecda3e51d3d7503": {
            "sha": "6ab62920c87930dedc31fe633ecda3e51d3d7503",
            "commit": {
                "message": "bpo-32436: Fix a refleak; var GC tracking; a GCC warning (#5326)\n\nThe refleak in question wasn't really important, as context vars\r\nare usually created at the toplevel and live as long as the interpreter\r\nlives, so the context var name isn't ever GCed anyways."
            },
            "author": {
                "login": "1st1",
            }
        }
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=getitem)
    await follow_up.router.dispatch(event, gh)
    post_data = gh.post_data
    print(getitem)
    assert post_data["body"] == follow_up.REPLACE_GH_NUMBER_MESSAGE.format(
        committer=getitem["https://api.github.com/repos/python/cpython/commits/6ab62920c87930dedc31fe633ecda3e51d3d7503"]["author"]["login"])


@pytest.mark.asyncio
async def test_no_remind_when_gh_replaced():
    data = {
        "action": "closed",
        "pull_request": {
            "number": 5326,
            "merged": True,
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
            "merge_commit_sha": "6ab62920c87930dedc31fe633ecda3e51d3d7503",
            "comments_url": "https://api.github.com/repos/python/cpython/pulls/5326/comments",
        },
        "repository": {
            "commits_url": "https://api.github.com/repos/python/cpython/commits{/sha}"
        }
    }

    getitem = {
        "https://api.github.com/repos/python/cpython/commits/6ab62920c87930dedc31fe633ecda3e51d3d7503": {
            "sha": "6ab62920c87930dedc31fe633ecda3e51d3d7503",
            "commit": {
                "message": "bpo-32436: Fix a refleak; var GC tracking; a GCC warning (GH-5326)\n\nThe refleak in question wasn't really important, as context vars\r\nare usually created at the toplevel and live as long as the interpreter\r\nlives, so the context var name isn't ever GCed anyways."
            },
            "author": {
                "login": "1st1"
            }
        }
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=getitem)
    await follow_up.router.dispatch(event, gh)
    post_data = gh.post_data
    assert post_data is None


@pytest.mark.asyncio
async def test_no_reminder_when_pr_closed_not_merged():
    data = {
        "action": "closed",
        "pull_request": {
            "number": 5326,
            "merged": False,
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
            "merge_commit_sha": None,
            "comments_url": "https://api.github.com/repos/python/cpython/pulls/5326/comments",
        },
        "repository": {
            "commits_url": "https://api.github.com/repos/python/cpython/commits{/sha}"
        }
    }

    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await follow_up.router.dispatch(event, gh)
    post_data = gh.post_data
    assert post_data is None
