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
        return title[:-1] + body[1:].partition('\n')[0].rstrip()


router.register('pull_request', action='opened')
async def remove_backport_label(event, gh, *args, **kwargs):
    title = normalize_title(event.data['title'], event.data['body'])
    title_match = TITLE_RE.match(title)
    if title_match is None:
        return
    branch = title_match.group('branch')
    backport_label = BACKPORT_LABEL.format(branch=branch)
    pr_to_backport = title_match.group('pr')

    issue = await gh.getitem(event.data['issue_url'])
    if backport_label not in {label['name'] for label in issue['labels']}:
        return
    await gh.delete(issue['labels_url'], {'name': backport_label})
    message = MESSAGE_TEMPLATE.format(branch=branch, pr=pr_to_backport)
    await gh.post(issue['comments_url'], data={'body': message})
