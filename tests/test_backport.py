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


@pytest.fixture(params=['gh', 'GH'])
def pr_prefix(request):
    return request.param


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
        "https://api.github.com/issue/1234": {
            "labels": [{"name": "CLA signed"}],
            "comments_url": "https://api.github.com/issue/1234/comments",
        },
        "https://api.github.com/issue/2248": {},
    }
    gh = FakeGH(getitem=getitem)
    await backport.router.dispatch(event, gh)
    assert gh.delete_url is None


async def test_backport_label_removal_success(pr_prefix):
    event_data = {
        'action': 'opened',
        'number': 2248,
        'pull_request': {
            'title': '[3.6] Backport this …',
            'body': f'…({pr_prefix}-1234)',
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
    assert len(gh.post_) > 0
    expected_post = None
    for post in gh.post_:
        if post[0] == issue_data['comments_url']:
            expected_post = post
            message = post[1]['body']
            assert message == backport.MESSAGE_TEMPLATE.format(branch='3.6', pr='2248')

    assert expected_post is not None


async def test_backport_link_comment_without_label(pr_prefix):
    event_data = {
        "action": "opened",
        "number": 2248,
        "pull_request": {
            "title": f"[3.6] Backport this ({pr_prefix}-1234)",
            "body": "",
            "issue_url": "https://api.github.com/issue/2248",
            "base": {
                "ref": "3.6",
            },
            "statuses_url": "https://api.github.com/repos/python/cpython/statuses/somehash",
        },
        "repository": {
            "issues_url": "https://api.github.com/issue{/number}",
        },
    }
    event = sansio.Event(event_data, event="pull_request", delivery_id="1")
    getitem_data = {
        "https://api.github.com/issue/1234": {
            "labels": [],
            "comments_url": "https://api.github.com/issue/1234/comments",
        },
        "https://api.github.com/issue/2248": {},
    }
    gh = FakeGH(getitem=getitem_data)
    await backport.router.dispatch(event, gh)
    issue_data = getitem_data["https://api.github.com/issue/1234"]
    assert gh.delete_url is None
    assert len(gh.post_) > 0
    expected_post = None
    for post in gh.post_:
        if post[0] == issue_data["comments_url"]:
            expected_post = post
            message = post[1]["body"]
            assert message == backport.MESSAGE_TEMPLATE.format(branch="3.6", pr="2248")
    
    assert expected_post is not None


async def test_backport_label_removal_with_leading_space_in_title(pr_prefix):
    event_data = {
        'action': 'opened',
        'number': 2248,
        'pull_request': {
            'title': f'  [3.6] Backport this ({pr_prefix}-1234)',
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


async def test_backport_label_removal_with_parentheses_in_title(pr_prefix):
    event_data = {
        'action': 'opened',
        'number': 2248,
        'pull_request': {
            'title': f'[3.6] Backport (0.9.6) this (more bpo-1234) ({pr_prefix}-1234)',
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


async def test_label_copying(pr_prefix):
    event_data = {
        'action': 'opened',
        'number': 2248,
        'pull_request': {
            'title': f'[3.6] Backport this ({pr_prefix}-1234)',
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
    assert len(gh.post_) > 0
    expected_post = None
    for post in gh.post_:
        if post[0] == 'https://api.github.com/issue/1234/labels':
            assert {'skip news', 'type-enhancement', 'sprint'} == frozenset(post[1])
            expected_post = post

    assert expected_post is not None


@pytest.mark.parametrize('action', ['opened', 'reopened', 'edited', 'synchronize'])
async def test_valid_maintenance_branch_pr_title(action):
    title = '[3.6] Fix to a maintenance branch'
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
    assert post[1]['context'] == 'bedevere/maintenance-branch-pr'
    assert post[1]['description'] == 'Valid maintenance branch PR title.'
    assert post[1]['state'] == 'success'


@pytest.mark.parametrize('action', ['opened', 'reopened', 'edited', 'synchronize'])
async def test_not_valid_maintenance_branch_pr_title(action):
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
    assert post[1]['context'] == 'bedevere/maintenance-branch-pr'
    assert post[1]['description'] == 'Not a valid maintenance branch PR title.'
    assert post[1]['state'] == 'failure'
    assert post[1]['target_url'] == 'https://devguide.python.org/committing/#backport-pr-title'


@pytest.mark.parametrize('action', ['opened', 'reopened', 'edited', 'synchronize'])
async def test_maintenance_branch_pr_status_not_posted_on_main(action):
    title = 'Fix some typo'
    data = {
        'action': action,
        'number': 2248,
        'pull_request': {
            'title': title,
            'body': '',
            'issue_url': 'https://api.github.com/issue/2248',
            'base': {
                'ref': 'main',
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


@pytest.mark.parametrize('action', ['opened', 'reopened', 'edited', 'synchronize'])
async def test_not_maintenance_branch_pr_status_not_posted_alt_base(action):
    """
    When a PR is proposed against a non-maintenance branch, such
    as another PR, it pass without status (same as with main). See
    #381 for a detailed justification.
    """
    title = 'Fix some typo'
    data = {
        'action': action,
        'number': 2248,
        'pull_request': {
            'title': title,
            'body': '',
            'issue_url': 'https://api.github.com/issue/2248',
            'base': {
                'ref': 'gh-1234/dependent-change',
            },
            'statuses_url': 'https://api.github.com/repos/python/cpython/statuses/somehash',
        },
        'repository': {'issues_url': 'https://api.github.com/issue{/number}'},
        'changes': {'title': title},
    }
    event = sansio.Event(data, event='pull_request', delivery_id='1')
    getitem = {
        'https://api.github.com/issue/1234':
            {'labels': [{'name': 'CLA signed'}]},
        'https://api.github.com/issue/2248': {},
    }
    gh = FakeGH(getitem=getitem)
    await backport.router.dispatch(event, gh)
    assert not gh.post_


@pytest.mark.parametrize('ref', ['3.9', '4.0', '3.10'])
async def test_maintenance_branch_created(ref):
    event_data = {
        'ref': ref,
        'ref_type': "branch",

    }
    event = sansio.Event(event_data, event='create',
                        delivery_id='1')
    gh = FakeGH()
    await backport.router.dispatch(event, gh)
    label_creation_post = gh.post_[0]
    assert label_creation_post[0] == "https://api.github.com/repos/python/cpython/labels"
    assert label_creation_post[1] == {'name': f"needs backport to {ref}", 'color': 'c2e0c6',
                                      'description': 'bug and security fixes'}


@pytest.mark.parametrize('ref', ['backport-3.9', 'test', 'Mariatta-patch-1'])
async def test_other_branch_created(ref):
    event_data = {
        'ref': ref,
        'ref_type': "branch",

    }
    event = sansio.Event(event_data, event='create', delivery_id='1')
    gh = FakeGH()
    await backport.router.dispatch(event, gh)
    assert gh.post_ == []
