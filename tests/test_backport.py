from gidgethub import sansio

from bedevere import backport


class FakeGH:

    def __init__(self, *, getitem=None, delete=None, post=None):
        self._getitem_return = getitem
        self._delete_return = delete
        self._post_return = post
        self.getitem_url = None
        self.delete_url = None
        self.post_url = self.post_data = None

    async def getitem(self, url, url_vars={}):
        self.getitem_url = sansio.format_url(url, url_vars)
        return self._getitem_return

    async def delete(self, url, url_vars):
        self.delete_url = sansio.format_url(url, url_vars)

    async def post(self, url, *, data):
        self.post_url = url
        self.post_data = data


async def test_missing_branch_in_title():
    data = {
        'action': 'opened',
        'pull_request': {'title': 'Backport this (GH-1234)', 'body': ''},
    }
    event = sansio.Event(data, event='pull_request',
                         delivery_id='1')
    gh = FakeGH()
    await backport.router.dispatch(event, gh)
    assert gh.getitem_url is None


async def test_missing_pr_in_title():
    data = {
        'action': 'opened',
        'pull_request': {'title': '[3.6] Backport this', 'body': ''},
    }
    event = sansio.Event(data, event='pull_request',
                        delivery_id='1')
    gh = FakeGH()
    await backport.router.dispatch(event, gh)
    assert gh.getitem_url is None


async def test_missing_backport_label():
    title = '[3.6] Backport this (GH-1234)'
    data = {
        'action': 'opened',
        'number': 2248,
        'pull_request': {
            'title': title,
            'body': '',
            'issue_url': 'https://api.github.com/issue/2248',
        },
        'repository': {'issues_url': 'https://api.github.com/repos/python/cpython/issues{/number}'}
    }
    event = sansio.Event(data, event='pull_request',
                        delivery_id='1')
    gh = FakeGH(getitem={'labels': [{'name': 'CLA signed'}]})
    await backport.router.dispatch(event, gh)
    assert gh.getitem_url == sansio.format_url(data['repository']['issues_url'], {'number': '1234'})
    assert gh.delete_url is None


async def test_backport_label_removal_success():
    event_data = {
        'action': 'opened',
        'number': 2248,
        'pull_request': {
            'title': '[3.6] Backport this …',
            'body': '…(GH-1234)',
            'issue_url': 'https://api.github.com/issue/2248',
        },
        'repository': {
            'issues_url': 'https://api.github.com/repos/python/cpython/issues{/number}',
        },
    }
    event = sansio.Event(event_data, event='pull_request',
                        delivery_id='1')
    issue_data = {
        'labels': [{'name': 'needs backport to 3.6'}],
        'labels_url': 'https://api.github.com/repos/python/cpython/issues/1234/labels{/name}',
        'comments_url': 'https://api.github.com/repos/python/cpython/issues/1234/comments',
    }
    gh = FakeGH(getitem=issue_data)
    await backport.router.dispatch(event, gh)
    assert gh.getitem_url == sansio.format_url(event_data['repository']['issues_url'], {'number': '1234'})
    assert gh.delete_url == sansio.format_url(issue_data['labels_url'],
                                              {'name': 'needs backport to 3.6'})
    assert gh.post_url == issue_data['comments_url']
    message = gh.post_data['body']
    assert message == backport.MESSAGE_TEMPLATE.format(branch='3.6', pr='2248')
