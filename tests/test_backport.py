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

    async def getitem(self, url):
        self.getitem_url = url
        return self._getitem_return

    async def delete(self, url, url_vars):
        self.delete_url = sansio.format_url(url, url_vars)

    async def post(self, url, *, data):
        self.post_url = url
        self.post_data = data


def test_title_normalization():
    title = "abcd"
    body = "1234"
    assert backport.normalize_title(title, body) == title

    title = "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations …"
    body = """…(GH-1478)

    stuff"""
    expected = '[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations (GH-1478)'
    assert backport.normalize_title(title, body) == expected

    title = "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations …"
    body = "…(GH-1478)"
    assert backport.normalize_title(title, body) == expected

    title = "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations (GH-14…"
    body = "…78)"
    assert backport.normalize_title(title, body) == expected


async def test_missing_branch_in_title():
    event = sansio.Event({'title': 'Backport this (GH-1234)', 'body': ''}, event='pull_request',
                         delivery_id='1')
    gh = FakeGH()
    await backport.remove_backport_label(event, gh)
    assert gh.getitem_url is None


async def test_missing_pr_in_title():
    event = sansio.Event({'title': '[3.6] Backport this', 'body': ''}, event='pull_request',
                        delivery_id='1')
    gh = FakeGH()
    await backport.remove_backport_label(event, gh)
    assert gh.getitem_url is None


async def test_missing_label():
    title = '[3.6] Backport this (GH-1234)'
    data = {
        'title': title,
        'body': '',
        'issue_url': 'https://api.github.com/repos/python/cpython/issues/1234',
    }
    event = sansio.Event(data, event='pull_request',
                        delivery_id='1')
    gh = FakeGH(getitem={'labels': [{'name': 'CLA signed'}]})
    await backport.remove_backport_label(event, gh)
    assert gh.getitem_url == data['issue_url']
    assert gh.delete_url is None


async def test_success():
    event_data = {
        'title': '[3.6] Backport this …',
        'body': '…(GH-1234)',
        'issue_url': 'https://api.github.com/repos/python/cpython/issues/2248',
    }
    event = sansio.Event(event_data, event='pull_request',
                        delivery_id='1')
    issue_data = {
        'labels': [{'name': 'needs backport to 3.6'}],
        'labels_url': 'https://api.github.com/repos/python/cpython/issues/2248/labels{/name}',
        'comments_url': 'https://api.github.com/repos/python/cpython/issues/2248/comments',
    }
    gh = FakeGH(getitem=issue_data)
    await backport.remove_backport_label(event, gh)
    assert gh.getitem_url == event_data['issue_url']
    assert gh.delete_url == sansio.format_url(issue_data['labels_url'],
                                              {'name': 'needs backport to 3.6'})
    assert gh.post_url == issue_data['comments_url']
    message = gh.post_data['body']
    assert message == backport.MESSAGE_TEMPLATE.format(branch='3.6', pr='1234')
