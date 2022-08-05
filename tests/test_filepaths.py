import pytest

from gidgethub import sansio

from bedevere import filepaths

from bedevere.prtype import Labels

from .test_news import check_n_pop_nonews_events


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
    filenames = [{'filename': 'README', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
                 {'filename': f'Misc/NEWS.d/next/Lib/{GOOD_BASENAME}', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
                 ]
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
    event = sansio.Event(event_data, event='pull_request', delivery_id='1')
    await filepaths.router.dispatch(event, gh)
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert len(gh.post_url) == 1
    assert gh.post_url[0] == 'https://api.github.com/some/status'
    assert gh.post_data[0]['state'] == 'success'


@pytest.mark.parametrize('author_association', ['OWNER', 'MEMBER', 'CONTRIBUTOR', 'NONE'])
async def test_docs_only(author_association):
    filenames = [{'filename': '/path/to/docs1.rst', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
                 {'filename': 'docs2.rst', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
                 ]
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
            'issue_comment_url': 'https://api.github.com/repos/cpython/python/issue/1234/comments',
            'author_association': author_association,
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id='1')
    await filepaths.router.dispatch(event, gh)
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert len(gh.post_url) == 1
    assert gh.post_url[0] == 'https://api.github.com/some/label'
    assert gh.post_data[0] == [Labels.docs.value, Labels.skip_news.value]


@pytest.mark.parametrize('author_association', ['OWNER', 'MEMBER', 'CONTRIBUTOR', 'NONE'])
async def test_tests_only(author_association):
    filenames = [{'filename': '/path/to/test_docs1.py', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
                 {'filename': 'test_docs2.py', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
                 ]
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
            'issue_comment_url': 'https://api.github.com/repos/cpython/python/issue/1234/comments',
            'author_association': author_association,
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id='1')
    await filepaths.router.dispatch(event, gh)
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert len(gh.post_url) == 3 if author_association == 'NONE' else 2
    assert gh.post_url.pop(0) == 'https://api.github.com/some/label'
    assert gh.post_data.pop(0) == [Labels.tests.value]
    check_n_pop_nonews_events(gh, author_association == 'NONE')


async def test_docs_and_tests():
    filenames = [{'filename': '/path/to/docs.rst', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
                 {'filename': 'test_docs2.py', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
                 ]
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
    event = sansio.Event(event_data, event='pull_request', delivery_id='1')
    await filepaths.router.dispatch(event, gh)
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    # Only creates type-tests label.
    assert len(gh.post_url) == 2
    assert gh.post_url[0] == 'https://api.github.com/some/label'
    assert gh.post_data[0] == [Labels.tests.value]
    assert gh.post_url[1] == 'https://api.github.com/some/status'
    assert gh.post_data[1]['state'] == 'success'


async def test_news_and_tests():
    filenames = [{'filename': '/path/to/docs.rst', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
                 {'filename': 'test_docs2.py', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
                 {'filename': f'Misc/NEWS.d/next/Lib/{GOOD_BASENAME}', 'patch': '@@ -0,0 +1 @@ +Fix inspect.getsourcelines for module level frames/tracebacks'}]

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
    event = sansio.Event(event_data, event='pull_request', delivery_id='1')
    await filepaths.router.dispatch(event, gh)
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    # Only creates type-tests label.
    assert len(gh.post_url) == 2
    assert gh.post_url[0] == 'https://api.github.com/some/label'
    assert gh.post_data[0] == [Labels.tests.value]
    assert gh.post_url[1] == 'https://api.github.com/some/status'
    assert gh.post_data[1]['state'] == 'success'


async def test_synchronize():
    filenames = [{'filename': '/path/to/docs.rst', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
                 {'filename': 'test_docs2.py', 'patch': '@@ -31,3 +31,7 @@ # Licensed to PSF under a Contributor Agreement.'},
                 {'filename': f'Misc/NEWS.d/next/Lib/{GOOD_BASENAME}', 'patch': '@@ -0,0 +1 @@ +Fix inspect.getsourcelines for module level frames/tracebacks'}]
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
    event = sansio.Event(event_data, event='pull_request', delivery_id='1')
    await filepaths.router.dispatch(event, gh)
    assert gh.getiter_url == 'https://api.github.com/repos/cpython/python/pulls/1234/files'
    assert gh.getitem_url is None
    # Only creates type-tests label.
    assert len(gh.post_url) == 1
    assert gh.post_url[0] == 'https://api.github.com/some/status'
    assert gh.post_data[0]['state'] == 'success'
