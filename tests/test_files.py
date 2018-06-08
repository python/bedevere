from gidgethub import sansio

from bedevere import files


class FakeGH:

    def __init__(self, *, getiter=None, getitem=None, post=None):
        self._getitem_return = getitem
        self._getiter_return = getiter
        self._post_return = post
        self.getitem_url = None
        self.getiter_url = None
        self.post_url = []
        self.post_data = []

    async def getitem(self, url):
        self.getitem_url = url
        return self._getitem_return

    async def getiter(self, url):
        self.getiter_url = url
        for item in self._getiter_return:
            yield item

    async def post(self, url, *, data):
        self.post_url.append(url)
        self.post_data.append(data)
        return self._post_return


GOOD_BASENAME = '2017-06-16-20-32-50.bpo-1234.nonce.rst'


async def test_news_only():
    filenames = [{'filename': 'README'}, {'filename': 'Misc/NEWS.d/next/Lib/' + GOOD_BASENAME}]
    issue = {'labels': []}
    gh = FakeGH(getiter=filenames, getitem=issue)
    event_data = {
        'action': 'opened',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id=1)
    await files.router.dispatch(event, gh)
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert len(gh.post_url) == 1
    assert gh.post_url[0] == 'https://api.github.com/some/status'
    assert gh.post_data[0]['state'] == 'success'


async def test_docs_only():
    filenames = [{'filename': '/path/to/docs1.rst'}, {'filename': 'docs2.rst'}]
    issue = {'labels': [],
             'labels_url': 'https://api.github.com/some/label'}
    gh = FakeGH(getiter=filenames, getitem=issue)
    event_data = {
        'action': 'opened',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id=1)
    await files.router.dispatch(event, gh)
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert len(gh.post_url) == 2
    assert gh.post_url[0] == 'https://api.github.com/some/status'
    assert gh.post_data[0]['state'] == 'failure'
    assert gh.post_url[1] == 'https://api.github.com/some/label'
    assert gh.post_data[1] == ['type-documentation']


async def test_tests_only():
    filenames = [{'filename': '/path/to/test_docs1.py'}, {'filename': 'test_docs2.py'}]
    issue = {'labels': [],
             'labels_url': 'https://api.github.com/some/label'}
    gh = FakeGH(getiter=filenames, getitem=issue)
    event_data = {
        'action': 'opened',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id=1)
    await files.router.dispatch(event, gh)
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert len(gh.post_url) == 2
    assert gh.post_url[0] == 'https://api.github.com/some/status'
    assert gh.post_data[0]['state'] == 'failure'
    assert gh.post_url[1] == 'https://api.github.com/some/label'
    assert gh.post_data[1] == ['type-tests']


async def test_docs_and_tests():
    filenames = [{'filename': '/path/to/docs.rst'}, {'filename': 'test_docs2.py'}]
    issue = {'labels': [{'name': 'skip news'}],
             'labels_url': 'https://api.github.com/some/label'}
    gh = FakeGH(getiter=filenames, getitem=issue)
    event_data = {
        'action': 'opened',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id=1)
    await files.router.dispatch(event, gh)
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    # Only creates type-tests label.
    assert len(gh.post_url) == 2
    assert gh.post_url[0] == 'https://api.github.com/some/status'
    assert gh.post_data[0]['state'] == 'success'
    assert gh.post_url[1] == 'https://api.github.com/some/label'
    assert gh.post_data[1] == ['type-tests']


async def test_news_and_tests():
    filenames = [{'filename': '/path/to/docs.rst'}, {'filename': 'test_docs2.py'},
                 {'filename': 'Misc/NEWS.d/next/Lib/' + GOOD_BASENAME}]
    issue = {'labels': [],
             'labels_url': 'https://api.github.com/some/label'}
    gh = FakeGH(getiter=filenames, getitem=issue)
    event_data = {
        'action': 'opened',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id=1)
    await files.router.dispatch(event, gh)
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    # Only creates type-tests label.
    assert len(gh.post_url) == 2
    assert gh.post_url[0] == 'https://api.github.com/some/status'
    assert gh.post_data[0]['state'] == 'success'
    assert gh.post_url[1] == 'https://api.github.com/some/label'
    assert gh.post_data[1] == ['type-tests']


async def test_synchonize():
    filenames = [{'filename': '/path/to/docs.rst'}, {'filename': 'test_docs2.py'},
                 {'filename': 'Misc/NEWS.d/next/Lib/' + GOOD_BASENAME}]
    issue = {'labels': [],
             'labels_url': 'https://api.github.com/some/label'}
    gh = FakeGH(getiter=filenames, getitem=issue)
    event_data = {
        'action': 'synchronize',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id=1)
    await files.router.dispatch(event, gh)
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url is None
    # Only creates type-tests label.
    assert len(gh.post_url) == 1
    assert gh.post_url[0] == 'https://api.github.com/some/status'
    assert gh.post_data[0]['state'] == 'success'
