from bedevere import prtype
from bedevere.prtype import Labels


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

    async def post(self, url, *, data):
        self.post_url.append(url)
        self.post_data.append(data)
        return self._post_return


GOOD_BASENAME = '2017-06-16-20-32-50.bpo-1234.nonce.rst'



async def test_no_files():
    filenames = {}
    issue = {'labels': []}
    gh = FakeGH(getitem=issue)
    event_data = {
        'action': 'opened',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    await prtype.classify_by_filepaths(gh, event_data['pull_request'], filenames)
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    # When no files are present, no labels are added.
    assert len(gh.post_url) == 0
    assert len(gh.post_data) == 0


async def test_news_only():
    filenames = {'README', f'Misc/NEWS.d/next/Lib/{GOOD_BASENAME}'}
    issue = {'labels': []}
    gh = FakeGH(getitem=issue)
    event_data = {
        'action': 'opened',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    await prtype.classify_by_filepaths(gh, event_data['pull_request'], filenames)
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    # News only .rst does not add a docs label.
    assert len(gh.post_url) == 0
    assert len(gh.post_data) == 0


async def test_docs_no_news():
    filenames = {'path/to/docs1.rst'}
    issue = {'labels': [],
             'labels_url': 'https://api.github.com/some/label'}
    gh = FakeGH(getitem=issue)
    event_data = {
        'action': 'opened',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    await prtype.classify_by_filepaths(gh, event_data['pull_request'], filenames)
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert len(gh.post_url) == 1
    assert gh.post_url[0] == 'https://api.github.com/some/label'
    assert gh.post_data[0] == [Labels.docs.value, Labels.skip_news.value]


async def test_docs_and_news():
    filenames = {'/path/to/docs1.rst', f'Misc/NEWS.d/next/Lib/{GOOD_BASENAME}'}
    issue = {'labels': [],
             'labels_url': 'https://api.github.com/some/label'}
    gh = FakeGH(getitem=issue)
    event_data = {
        'action': 'opened',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    await prtype.classify_by_filepaths(gh, event_data['pull_request'], filenames)
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert len(gh.post_url) == 1
    assert gh.post_url[0] == 'https://api.github.com/some/label'
    assert gh.post_data[0] == [Labels.docs.value]


async def test_tests_only():
    filenames = {'/path/to/test_docs1.py', 'test_docs2.py'}
    issue = {'labels': [],
             'labels_url': 'https://api.github.com/some/label'}
    gh = FakeGH(getitem=issue)
    event_data = {
        'action': 'opened',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    await prtype.classify_by_filepaths(gh, event_data['pull_request'], filenames)
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert len(gh.post_url) == 1
    assert gh.post_url[0] == 'https://api.github.com/some/label'
    assert gh.post_data[0] == [Labels.tests.value]


async def test_docs_and_tests():
    filenames = {'/path/to/docs.rst', 'test_docs2.py'}
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
    await prtype.classify_by_filepaths(gh, event_data['pull_request'], filenames)
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    # Only creates type-tests label.
    assert len(gh.post_url) == 1
    assert gh.post_url[0] == 'https://api.github.com/some/label'
    assert gh.post_data[0] == [Labels.tests.value]


async def test_leave_existing_type_labels():
    filenames = {'/path/to/docs.rst', 'test_docs2.py'}
    issue = {'labels': [{'name': 'skip news'}, {'name': 'docs'}],
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
    await prtype.classify_by_filepaths(gh, event_data['pull_request'], filenames)
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert len(gh.post_url) == 1
    assert gh.post_url[0] == "https://api.github.com/some/label"
    # This should only add the tests label as the docs label is already applied
    assert gh.post_data[0] == [Labels.tests.value]


async def test_do_not_post_if_nothing_to_apply():
    filenames = {'/path/to/docs.rst'}
    issue = {'labels': [{'name': 'skip news'}, {'name': 'docs'}],
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
    await prtype.classify_by_filepaths(gh, event_data['pull_request'], filenames)
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    # This should not post anything as docs is already applied
    assert len(gh.post_url) == 0


async def test_news_and_tests():
    filenames = {'test_docs2.py', f'Misc/NEWS.d/next/Lib/{GOOD_BASENAME}'}
    issue = {'labels': [],
             'labels_url': 'https://api.github.com/some/label'}
    gh = FakeGH(getitem=issue)
    event_data = {
        'action': 'opened',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    await prtype.classify_by_filepaths(gh, event_data['pull_request'], filenames)
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    # Creates type-tests label.
    assert len(gh.post_url) == 1
    assert gh.post_url[0] == 'https://api.github.com/some/label'
    assert gh.post_data[0] == [Labels.tests.value]


async def test_other_files():
    filenames = {'README', '/path/to/docs.rst', 'test_docs2.py',
                 f'Misc/NEWS.d/next/Lib/{GOOD_BASENAME}'}
    issue = {'labels': [],
             'labels_url': 'https://api.github.com/some/label'}
    gh = FakeGH(getitem=issue)
    event_data = {
        'action': 'opened',
        'number': 1234,
        'pull_request': {
            'url': 'https://api.github.com/repos/cpython/python/pulls/1234',
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    await prtype.classify_by_filepaths(gh, event_data['pull_request'], filenames)
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    # No labels if a file other than doc or test exists.
    assert len(gh.post_url) == 0


