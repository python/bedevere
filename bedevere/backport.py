import re

import gidgethub.routing


router = gidgethub.routing.Router()

TITLE_RE = re.compile(r'\[(?P<branch>\d+\.\d+)\].+?(?P<pr>\d+)\)')
BACKPORT_LABEL = 'needs backport to {branch}'
MESSAGE_TEMPLATE = ('[GH-{pr}](https://github.com/python/cpython/pull/{pr}) is '
                    'a backport of this pull request to the '
                    '[{branch} branch](https://github.com/python/cpython/tree/{branch})')


def normalize_title(title, body):
    """Normalize the title if it spills over into the PR's body."""
    if not (title.endswith('…') and body.startswith('…')):
        return title
    else:
        # Being paranoid in case \r\n is used.
        return title[:-1] + body[1:].partition('\r\n')[0]


router.register('pull_request', action='opened')
async def remove_backport_label(event, gh, *args, **kwargs):
    title = normalize_title(event.data['pull_request']['title'], event.data['pull_request']['body'])
    title_match = TITLE_RE.match(title)
    if title_match is None:
        return
    branch = title_match.group('branch')
    backport_label = BACKPORT_LABEL.format(branch=branch)
    pr_to_backport = title_match.group('pr')
    backported_pr = event.data['number']

    issue_to_backport = await gh.getitem(event.data['repository']['issues_url'], {'number': pr_to_backport})
    if not any(backport_label == label['name'] for label in issue_to_backport['labels']):
        return
    await gh.delete(issue_to_backport['labels_url'], {'name': backport_label})
    message = MESSAGE_TEMPLATE.format(branch=branch, pr=backported_pr)
    await gh.post(issue_to_backport['comments_url'], data={'body': message})
