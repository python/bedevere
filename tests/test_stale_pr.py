import pytest
from datetime import datetime
from gidgethub import sansio

from bedevere import stale_pr


class FakeGH:

    async def getiter(self, url):
        for issue in self._issues:
            yield issue

    def __init__(self, *, issues, getitem=None):
        self.post_url = None
        self.post_data = None
        self._issues = issues

    async def post(self, url, data):
        self.post_url = url
        self.post_data = data


@pytest.mark.asyncio
async def test_stale_pr_labelled_stale():
    issue = {
        "labels_url": "https://api.github.com/repos/python/cpython/issues/3919/labels{/name}",
        "id": 263653898,
        "number": 3919,
        "labels": [{
            "name": "awaiting review"
        },
        {
            "name": "CLA signed"
        }
        ],
        "state": "open",
        "created_at": "2017-08-07T16:34:58Z",
        "updated_at": "2017-08-07T16:35:01Z",
        "pull_request": {
            "url": "https://api.github.com/repos/python/cpython/pulls/3919"
        }
    }
    gh = FakeGH(issues=[issue])
    await stale_pr.label_stale_prs(gh)
    assert gh.post_data == ["stale"]


@pytest.mark.asyncio
async def test_no_action_on_labelled_stale_pr():
    issue = {
        "labels_url": "https://api.github.com/repos/python/cpython/issues/3919/labels{/name}",
        "id": 263653898,
        "number": 3919,
        "labels": [{
            "name": "awaiting review"
        },
        {
            "name": "stale"
        }
        ],
        "state": "open",
        "created_at": "2017-10-07T16:34:58Z",
        "updated_at": "2017-10-07T16:35:01Z",
        "pull_request": {
            "url": "https://api.github.com/repos/python/cpython/pulls/3919"
        }
    }
    gh = FakeGH(issues=[issue])
    await stale_pr.label_stale_prs(gh)
    assert gh.post_data == None

@pytest.mark.asyncio
async def test_no_action_on_active_pr():
    updated_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    issue = {
        "labels_url": "https://api.github.com/repos/python/cpython/issues/3919/labels{/name}",
        "id": 263653898,
        "number": 3919,
        "labels": [{
            "name": "awaiting review"
        },
        {
            "name": "CLA signed"
        }
        ],
        "state": "open",
        "created_at": "2016-10-07T16:34:58Z",
        "updated_at": updated_at,
        "pull_request": {
            "url": "https://api.github.com/repos/python/cpython/pulls/3919"
        }
    }
    gh = FakeGH(issues=[issue])
    await stale_pr.label_stale_prs(gh)
    assert gh.post_data == None

@pytest.mark.asyncio
async def test_invoke():
    async def stub(self):
        return "done"
    stale_pr.label_stale_prs = stub
    result = await stale_pr.invoke() 
    assert result == "done"