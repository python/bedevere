"""Automatically remove a backport label."""
import re

import gidgethub.routing

from . import util


router = gidgethub.routing.Router()

TITLE_RE = re.compile(r'\[(?P<branch>\d+\.\d+)\].+?(?P<pr>\d+)\)')
BACKPORT_LABEL = 'needs backport to {branch}'
MESSAGE_TEMPLATE = ('[GH-{pr}](https://github.com/python/cpython/pull/{pr}) is '
                    'a backport of this pull request to the '
                    '[{branch} branch](https://github.com/python/cpython/tree/{branch}).')


async def _copy_over_labels(gh, original_issue, backport_issue):
    """Copy over relevant labels from the original PR to the backport PR."""
    label_prefixes = "skip", "type", "sprint"
    labels = list(filter(lambda x: x.startswith(label_prefixes),
                    util.labels(original_issue)))
    if labels:
        await gh.post(backport_issue["labels_url"], data=labels)


async def _remove_backport_label(gh, original_issue, branch, backport_pr_number):
    """Remove the appropriate "backport to" label on the original PR.

    Also leave a comment on the original PR referencing the backport PR.
    """
    backport_label = BACKPORT_LABEL.format(branch=branch)
    if backport_label not in util.labels(original_issue):
        return
    await gh.delete(original_issue['labels_url'], {'name': backport_label})
    message = MESSAGE_TEMPLATE.format(branch=branch, pr=backport_pr_number)
    await gh.post(original_issue['comments_url'], data={'body': message})


@router.register("pull_request", action="opened")
@router.register("pull_request", action="edited")
async def manage_labels(event, gh, *args, **kwargs):
    if event.data["action"] == "edited" and "title" not in event.data["changes"]:
        return
    pull_request = event.data["pull_request"]
    title = util.normalize_title(pull_request['title'],
                                 pull_request['body'])
    title_match = TITLE_RE.match(title)
    if title_match is None:
        return
    branch = title_match.group('branch')
    original_pr_number = title_match.group('pr')

    original_issue = await gh.getitem(event.data['repository']['issues_url'],
                                      {'number': original_pr_number})
    await _remove_backport_label(gh, original_issue, branch,
                                 event.data["number"])

    backport_issue = await util.issue_for_PR(gh, pull_request)
    await _copy_over_labels(gh, original_issue, backport_issue)
