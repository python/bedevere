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


GOOD_BASENAME = '2017-06-16.bpo-1234.nonce.rst'

class TestFilenameRE:

    def test_not_in_directory(self):
        assert news.FILENAME_RE.match('some/other/dir/' + GOOD_BASENAME) is None

    def test_not_in_subdirectory(self):
        assert news.FILENAME_RE.match('Misc/NEWS.d/' + GOOD_BASENAME) is None

    def test_malformed_basename(self):
        assert news.FILENAME_RE.match('Misc/NEWS.d/Library/2017-06-16.bpo-1234.rst') is None

    def test_success(self):
        assert news.FILENAME_RE.match('Misc/NEWS.d/Library/' + GOOD_BASENAME)

    def test_multiple_issue_numbers(self):
        basename = '2018-01-01.bpo-1234,5678,9012.nonce.rst'
        assert news.FILENAME_RE.match('Misc/NEWS.d/Security/' + basename)


async def test_edited_misc_news():
    gh = FakeGH(getiter=[{'filename': 'README'}, {'filename': 'Misc/NEWS'}])
    event_data = {
        'number': 1234,
        'pull_request': {'statuses_url': 'https://api.github.com/some/status'},
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id=1)
    await news.check_news(event, gh)
    assert gh.getiter_url == '/repos/python/cpython/pulls/1234/files'
    assert gh.post_url == 'https://api.github.com/some/status'
    assert gh.post_data['state'] == 'failure'


async def test_no_news_file():
    files = [{'filename': 'README'}, {'filename': 'Misc/NEWS.d/' + GOOD_BASENAME}]
    issue = {'labels': []}
    gh = FakeGH(getiter=files, getitem=issue)
    event_data = {
        'number': 1234,
        'pull_request': {
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id=1)
    await news.check_news(event, gh)
    assert gh.getiter_url == '/repos/python/cpython/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert gh.post_url == 'https://api.github.com/some/status'
    assert gh.post_data['state'] == 'failure'


async def test_trivial():
    files = [{'filename': 'README'}, {'filename': 'Misc/NEWS.d/' + GOOD_BASENAME}]
    issue = {'labels': [{'name': 'trivial'}]}
    gh = FakeGH(getiter=files, getitem=issue)
    event_data = {
        'number': 1234,
        'pull_request': {
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id=1)
    await news.check_news(event, gh)
    assert gh.getiter_url == '/repos/python/cpython/pulls/1234/files'
    assert gh.getitem_url == 'https://api.github.com/repos/cpython/python/issue/1234'
    assert gh.post_url == 'https://api.github.com/some/status'
    assert gh.post_data['state'] == 'success'


async def test_news_file():
    files = [{'filename': 'README'},
             {'filename': 'Misc/NEWS.d/Library/' + GOOD_BASENAME}]
    issue = {'labels': [{'name': 'CLA signed'}]}
    gh = FakeGH(getiter=files, getitem=issue)
    event_data = {
        'number': 1234,
        'pull_request': {
            'statuses_url': 'https://api.github.com/some/status',
            'issue_url': 'https://api.github.com/repos/cpython/python/issue/1234',
        },
    }
    event = sansio.Event(event_data, event='pull_request', delivery_id=1)
    await news.check_news(event, gh)
    assert gh.getiter_url == '/repos/python/cpython/pulls/1234/files'
    assert gh.post_url == 'https://api.github.com/some/status'
    assert gh.post_data['state'] == 'success'
