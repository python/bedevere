import pytest

from gidgethub import sansio

from bedevere import news


class FakeGH:

    def __init__(self, *, getiter=None, getitem=None, post=None):
        self._getitem_return = getitem
        self._getiter_return = getiter
        self._post_return = post
        self.getitem_url = None
        self.getiter_url = None
        self.post_url = self.post_data = None

    async def getitem(self, url):
        self.getitem_url = url
        return self._getitem_return

    async def getiter(self, url):
        self.getiter_url = url
        for item in self._getiter_return:
            yield item

    async def post(self, url, *, data):
        self.post_url = url
        self.post_data = data
        return self._post_return


GOOD_BASENAME = '2017-06-16-20-32-50.bpo-1234.nonce.rst'

class TestFilenameRE:

    def test_malformed_basename(self):
        assert news.FILENAME_RE.match('2017-06-16.bpo-1234.rst') is None

    def test_success(self):
        assert news.FILENAME_RE.match(GOOD_BASENAME)
        live_result = '2017-08-14-15-13-50.bpo-1612262.-x_Oyq.rst'
        assert news.FILENAME_RE.match(live_result)

    def test_multiple_issue_numbers(self):
        basename = '2018-01-01.bpo-1234,5678,9012.nonce.rst'
        assert news.FILENAME_RE.match(basename)

    def test_date_only(self):
        basename = '2017-08-14.bpo-1234.nonce.rst'
        assert news.FILENAME_RE.match(basename)


async def failure_testing(path, action):
    files = [{'filename': 'README', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
             {'filename': path, 'patch': '@@ -0,0 +1 @@ +Fix inspect.getsourcelines for module level frames/tracebacks'},
             ]
    issue = {'labels': []}
    gh = FakeGH(getiter=files, getitem=issue)
    event_data = {
        'action': action,
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    await news.check_news(gh, event_data['pull_request'])
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert gh.post_url == 'https://api.github.com/some/status'
    assert gh.post_data['state'] == 'failure'
    assert gh.post_data['target_url'] == news.BLURB_IT_URL


@pytest.mark.parametrize('action', ['opened', 'reopened', 'synchronize'])
async def test_bad_news_entry(action):
    # Not in Misc/NEWS.d.
    await failure_testing(f'some/other/dir/{GOOD_BASENAME}', action)
    # Not in next/.
    await failure_testing(f'Misc/NEWS.d/{GOOD_BASENAME}', action)
    # Not in a classifying subdirectory.
    await failure_testing(f'Misc/NEWS.d/next/{GOOD_BASENAME}', action)
    # Missing the nonce.
    await failure_testing(f'Misc/NEWS.d/next/Library/2017-06-16.bpo-1234.rst', action)


@pytest.mark.parametrize('action', ['opened', 'reopened', 'synchronize'])
async def test_skip_news(action):
    files = [{'filename': 'README', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
             {'filename': f'Misc/NEWS.d/next/{GOOD_BASENAME}', 'patch': '@@ -0,0 +1 @@ +Fix inspect.getsourcelines for module level frames/tracebacks'},
             ]
    issue = {'labels': [{'name': 'skip news'}]}
    gh = FakeGH(getiter=files, getitem=issue)
    event_data = {
        'action': action,
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    await news.check_news(gh, event_data['pull_request'])
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert gh.post_url == 'https://api.github.com/some/status'
    assert gh.post_data['state'] == 'success'
    assert gh.post_data.get('target_url') is None


@pytest.mark.parametrize('action', ['opened', 'reopened', 'synchronize'])
async def test_news_file(action):
    files = [{'filename': 'README', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
             {'filename': f'Misc/NEWS.d/next/Library/{GOOD_BASENAME}', 'patch': '@@ -0,0 +1 @@ +Fix inspect.getsourcelines for module level frames/tracebacks'},
             ]
    issue = {'labels': [{'name': 'CLA signed'}]}
    gh = FakeGH(getiter=files, getitem=issue)
    event_data = {
        'action': action,
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    await news.check_news(gh, event_data['pull_request'])
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.post_url == 'https://api.github.com/some/status'
    assert gh.post_data['state'] == 'success'
    assert gh.post_data.get('target_url') is None


@pytest.mark.parametrize('action', ['opened', 'reopened', 'synchronize'])
async def test_empty_news_file(action):
    files = [{'filename': 'README', 'patch': '@@ -31,3 +31,7 @@ '},
             {'filename': f'Misc/NEWS.d/next/Library/{GOOD_BASENAME}'},
             ]
    issue = {'labels': [{'name': 'CLA signed'}]}
    gh = FakeGH(getiter=files, getitem=issue)
    event_data = {
        'action': action,
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    await news.check_news(gh, event_data['pull_request'])
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.post_url == 'https://api.github.com/some/status'
    assert gh.post_data['state'] == 'failure'
    assert gh.post_data['target_url'] == news.BLURB_IT_URL


@pytest.mark.parametrize('action', ['opened', 'reopened', 'synchronize'])
async def test_news_file_not_empty(action):
    files = [{'filename': 'README', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
             {'filename': f'Misc/NEWS.d/next/Library/{GOOD_BASENAME}', 'patch': '@@ -0,0 +1 @@ +A'}]
    issue = {'labels': [{'name': 'CLA signed'}]}
    gh = FakeGH(getiter=files, getitem=issue)
    event_data = {
        'action': action,
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    await news.check_news(gh, event_data['pull_request'])
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.post_url == 'https://api.github.com/some/status'
    assert gh.post_data['state'] == 'success'
    assert gh.post_data.get('target_url') is None


async def test_adding_skip_news_label():
    gh = FakeGH()
    event_data = {
        "action": "labeled",
        "label": {"name": news.SKIP_NEWS_LABEL},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "An easy fix",
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id='1')
    await news.router.dispatch(event, gh)
    assert gh.post_data['state'] == 'success'


async def test_adding_benign_label():
    gh = FakeGH()
    event_data = {
        "action": "labeled",
        "label": {"name": "unimportant"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "An easy fix",
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id='1')
    await news.router.dispatch(event, gh)
    assert gh.post_data is None


async def test_deleting_label():
    gh = FakeGH()
    event_data = {
        "action": "unlabeled",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "An easy fix",
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id='1')
    await news.router.dispatch(event, gh)
    assert gh.post_data is None


async def test_removing_skip_news_label():
    files = [
        {'filename': 'README', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
        {'filename': f'Misc/NEWS.d/next/{GOOD_BASENAME}', 'patch': '@@ -0,0 +1 @@ +Fix inspect.getsourcelines for module level frames/tracebacks'},
        ]
    issue = {'labels': []}
    gh = FakeGH(getiter=files, getitem=issue)
    event_data = {
        "action": "unlabeled",
        "label": {"name": news.SKIP_NEWS_LABEL},
        "number": 1234,
        "pull_request": {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            "title": "An easy fix",
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id='1')
    await news.router.dispatch(event, gh)
    assert gh.post_data["state"] == "failure"


async def test_removing_benign_label():
    gh = FakeGH()
    event_data = {
        "action": "unlabeled",
        "label": {"name": "unimportant"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "An easy fix",
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id='1')
    await news.router.dispatch(event, gh)
    assert gh.post_data is None
