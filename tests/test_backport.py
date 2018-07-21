import pytest

from gidgethub import sansio

from bedevere import backport


class FakeGH:

    def __init__(self, *, getitem=None, delete=None, post=None):
        self._getitem_return = getitem
        self._delete_return = delete
        self._post_return = post
        self.getitem_url = None
        self.delete_url = None
        self.post_ = []

    async def getitem(self, url, url_vars={}):
        self.getitem_url = sansio.format_url(url, url_vars)
        return self._getitem_return[self.getitem_url]

    async def delete(self, url, url_vars):
        self.delete_url = sansio.format_url(url, url_vars)

    async def post(self, url, url_vars={}, *, data):
        post_url = sansio.format_url(url, url_vars)
        self.post_.append((post_url, data))


async def test_edit_not_title():
    data = {
        'action': 'edited',
        'pull_request': {'title': 'Backport this (GH-1234)', 'body': ''},
        'changes': {},
    }
    event = sansio.Event(data, event='pull_request',
                         delivery_id='1')
    gh = FakeGH()
    await backport.router.dispatch(event, gh)
    assert gh.getitem_url is None


async def test_missing_branch_in_title():
    data = {
        'action': 'opened',
        'pull_request': {
            'title': 'Backport this (GH-1234)',
            'body': '',
            'base': {
                'ref': '3.6',
            },
            'statuses_url': 'https://api.github.com/repos/python/cpython/statuses/somehash',
        },
    }
    event = sansio.Event(data, event='pull_request',
                         delivery_id='1')
    gh = FakeGH()
    await backport.router.dispatch(event, gh)
    assert gh.getitem_url is None


async def test_missing_pr_in_title():
    data = {
        'action': 'opened',
        'pull_request': {
            'title': '[3.6] Backport this',
            'body': '',
            'base': {
                'ref': '3.6',
            },
            'statuses_url': 'https://api.github.com/repos/python/cpython/statuses/somehash',
        },
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
            'base': {
                'ref': '3.6',
            },
            'statuses_url': 'https://api.github.com/repos/python/cpython/statuses/somehash',
        },
        'repository': {'issues_url': 'https://api.github.com/issue{/number}'}
    }
    event = sansio.Event(data, event='pull_request',
                        delivery_id='1')
    getitem = {
        'https://api.github.com/issue/1234':
            {'labels': [{'name': 'CLA signed'}]},
        'https://api.github.com/issue/2248': {},
    }
    gh = FakeGH(getitem=getitem)
    await backport.router.dispatch(event, gh)
    assert gh.delete_url is None


async def test_backport_label_removal_success():
    event_data = {
        'action': 'opened',
        'number': 2248,
        'pull_request': {
            'title': '[3.6] Backport this …',
            'body': '…(GH-1234)',
            'issue_url': 'https://api.github.com/issue/2248',
            'base': {
                'ref': '3.6',
            },
            'statuses_url': 'https://api.github.com/repos/python/cpython/statuses/somehash',
        },
        'repository': {
            'issues_url': 'https://api.github.com/issue{/number}',
        },
    }
    event = sansio.Event(event_data, event='pull_request',
                        delivery_id='1')
    getitem_data = {
        'https://api.github.com/issue/1234': {
            'labels': [{'name': 'needs backport to 3.6'}],
            'labels_url': 'https://api.github.com/issue/1234/labels{/name}',
            'comments_url': 'https://api.github.com/issue/1234/comments',
        },
        'https://api.github.com/issue/2248': {},
    }
    gh = FakeGH(getitem=getitem_data)
    await backport.router.dispatch(event, gh)
    issue_data = getitem_data['https://api.github.com/issue/1234']
    assert gh.delete_url == sansio.format_url(issue_data['labels_url'],
                                              {'name': 'needs backport to 3.6'})
    post = gh.post_[0]
    assert post[0] == issue_data['comments_url']
    message = post[1]['body']
    assert message == backport.MESSAGE_TEMPLATE.format(branch='3.6', pr='2248')


async def test_backport_label_removal_with_leading_space_in_title():
    event_data = {
        'action': 'opened',
        'number': 2248,
        'pull_request': {
            'title': '  [3.6] Backport this (GH-1234)',
            'body': '…',
            'issue_url': 'https://api.github.com/issue/2248',
            'base': {
                'ref': '3.6',
            },
            'statuses_url': 'https://api.github.com/repos/python/cpython/statuses/somehash',
        },
        'repository': {
            'issues_url': 'https://api.github.com/issue{/number}',
        },
    }
    event = sansio.Event(event_data, event='pull_request',
                        delivery_id='1')
    getitem_data = {
        'https://api.github.com/issue/1234': {
            'labels': [{'name': 'needs backport to 3.6'}],
            'labels_url': 'https://api.github.com/issue/1234/labels{/name}',
            'comments_url': 'https://api.github.com/issue/1234/comments',
        },
        'https://api.github.com/issue/2248': {},
    }
    gh = FakeGH(getitem=getitem_data)
    await backport.router.dispatch(event, gh)
    issue_data = getitem_data['https://api.github.com/issue/1234']
    assert gh.delete_url == sansio.format_url(issue_data['labels_url'],
                                              {'name': 'needs backport to 3.6'})


async def test_backport_label_removal_with_parentheses_in_title():
    event_data = {
        'action': 'opened',
        'number': 2248,
        'pull_request': {
            'title': '[3.6] Backport (0.9.6) this (more bpo-1234) (GH-1234)',
            'body': '…',
            'issue_url': 'https://api.github.com/issue/2248',
            'base': {
                'ref': '3.6',
            },
            'statuses_url': 'https://api.github.com/repos/python/cpython/statuses/somehash',
        },
        'repository': {
            'issues_url': 'https://api.github.com/issue{/number}',
        },
    }
    event = sansio.Event(event_data, event='pull_request',
                        delivery_id='1')
    getitem_data = {
        'https://api.github.com/issue/1234': {
            'labels': [{'name': 'needs backport to 3.6'}],
            'labels_url': 'https://api.github.com/issue/1234/labels{/name}',
            'comments_url': 'https://api.github.com/issue/1234/comments',
        },
        'https://api.github.com/issue/2248': {},
    }
    gh = FakeGH(getitem=getitem_data)
    await backport.router.dispatch(event, gh)
    issue_data = getitem_data['https://api.github.com/issue/1234']
    assert gh.delete_url == sansio.format_url(issue_data['labels_url'],
                                              {'name': 'needs backport to 3.6'})


async def test_label_copying():
    event_data = {
        'action': 'opened',
        'number': 2248,
        'pull_request': {
            'title': '[3.6] Backport this (GH-1234)',
            'body': 'N/A',
            'issue_url': 'https://api.github.com/issue/2248',
            'base': {
                'ref': '3.6',
            },
            'statuses_url': 'https://api.github.com/repos/python/cpython/statuses/somehash',
        },
        'repository': {
            'issues_url': 'https://api.github.com/issue{/number}',
        },
    }
    event = sansio.Event(event_data, event='pull_request',
                        delivery_id='1')
    labels_to_test = "CLA signed", "skip news", "type-enhancement", "sprint"
    getitem_data = {
        'https://api.github.com/issue/1234': {
            'labels': [{'name': label} for label in labels_to_test],
            'labels_url': 'https://api.github.com/issue/1234/labels{/name}',
            'comments_url': 'https://api.github.com/issue/1234/comments',
        },
        'https://api.github.com/issue/2248': {
            'labels_url': 'https://api.github.com/issue/1234/labels{/name}',
        },
    }
    gh = FakeGH(getitem=getitem_data)
    await backport.router.dispatch(event, gh)
    post = gh.post_[0]
    assert post[0] == 'https://api.github.com/issue/1234/labels'
    assert {'skip news', 'type-enhancement', 'sprint'} == frozenset(post[1])


@pytest.mark.parametrize('action', ['opened', 'reopened', 'edited', 'synchronize'])
async def test_valid_backport_pr_title(action):
    title = '[3.6] Backport this (GH-1234)'
    data = {
        'action': action,
        'number': 2248,
        'pull_request': {
            'title': title,
            'body': '',
            'issue_url': 'https://api.github.com/issue/2248',
            'base': {
                'ref': '3.6',
            },
            'statuses_url': 'https://api.github.com/repos/python/cpython/statuses/somehash',
        },
        'repository': {'issues_url': 'https://api.github.com/issue{/number}'},
        'changes': {'title': title},
    }
    event = sansio.Event(data, event='pull_request',
                        delivery_id='1')
    getitem = {
        'https://api.github.com/issue/1234':
            {'labels': [{'name': 'CLA signed'}]},
        'https://api.github.com/issue/2248': {},
    }
    gh = FakeGH(getitem=getitem)
    await backport.router.dispatch(event, gh)
    post = gh.post_[0]
    assert post[0] == 'https://api.github.com/repos/python/cpython/statuses/somehash'
    assert post[1]['context'] == 'bedevere/backport-pr'
    assert post[1]['description'] == 'Valid backport PR title.'
    assert post[1]['state'] == 'success'


@pytest.mark.parametrize('action', ['opened', 'reopened', 'edited', 'synchronize'])
async def test_not_valid_backport_pr_title(action):
    title = 'Fix some typo'
    data = {
        'action': action,
        'number': 2248,
        'pull_request': {
            'title': title,
            'body': '',
            'issue_url': 'https://api.github.com/issue/2248',
            'base': {
                'ref': '3.6',
            },
            'statuses_url': 'https://api.github.com/repos/python/cpython/statuses/somehash',
        },
        'repository': {'issues_url': 'https://api.github.com/issue{/number}'},
        'changes': {'title': title},
    }
    event = sansio.Event(data, event='pull_request',
                        delivery_id='1')
    getitem = {
        'https://api.github.com/issue/1234':
            {'labels': [{'name': 'CLA signed'}]},
        'https://api.github.com/issue/2248': {},
    }
    gh = FakeGH(getitem=getitem)
    await backport.router.dispatch(event, gh)
    post = gh.post_[0]
    assert post[0] == 'https://api.github.com/repos/python/cpython/statuses/somehash'
    assert post[1]['context'] == 'bedevere/backport-pr'
    assert post[1]['description'] == 'Not a valid backport PR title.'
    assert post[1]['state'] == 'failure'
    assert post[1]['target_url'] == 'https://devguide.python.org/committing/#backport-pr-title'


@pytest.mark.parametrize('action', ['opened', 'reopened', 'edited', 'synchronize'])
async def test_backport_pr_status_not_posted_on_master(action):
    title = 'Fix some typo'
    data = {
        'action': action,
        'number': 2248,
        'pull_request': {
            'title': title,
            'body': '',
            'issue_url': 'https://api.github.com/issue/2248',
            'base': {
                'ref': 'master',
            },
            'statuses_url': 'https://api.github.com/repos/python/cpython/statuses/somehash',
        },
        'repository': {'issues_url': 'https://api.github.com/issue{/number}'},
        'changes': {'title': title},
    }
    event = sansio.Event(data, event='pull_request',
                        delivery_id='1')
    getitem = {
        'https://api.github.com/issue/1234':
            {'labels': [{'name': 'CLA signed'}]},
        'https://api.github.com/issue/2248': {},
    }
    gh = FakeGH(getitem=getitem)
    await backport.router.dispatch(event, gh)
    assert len(gh.post_) == 0
