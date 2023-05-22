"""Automatically remove a backport label, and check backport PR validity."""
import functools
import re

import gidgethub.routing

from . import util

create_status = functools.partial(util.create_status, 'bedevere/maintenance-branch-pr')


router = gidgethub.routing.Router()

TITLE_RE = re.compile(r'\s*\[(?P<branch>\d+\.\d+)\].+\((?:GH-|#)(?P<pr>\d+)\)', re.IGNORECASE)
MAINTENANCE_BRANCH_TITLE_RE = re.compile(r'\s*\[(?P<branch>\d+\.\d+)\].+')
MAINTENANCE_BRANCH_RE = re.compile(r'\s*(?P<branch>\d+\.\d+)')
BACKPORT_LABEL = 'needs backport to {branch}'
MESSAGE_TEMPLATE = ('[GH-{pr}](https://github.com/python/cpython/pull/{pr}) is '
                    'a backport of this pull request to the '
                    '[{branch} branch](https://github.com/python/cpython/tree/{branch}).')


BACKPORT_TITLE_DEVGUIDE_URL = "https://devguide.python.org/committing/#backport-pr-title"

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
    message = MESSAGE_TEMPLATE.format(branch=branch, pr=backport_pr_number)
    await gh.post(original_issue['comments_url'], data={'body': message})
    if backport_label not in util.labels(original_issue):
        return
    await gh.delete(original_issue['labels_url'], {'name': backport_label})


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


def is_maintenance_branch(ref):
    """
    Return True if the ref refers to a maintenance branch.

    >>> is_maintenance_branch("3.11")
    True
    >>> is_maintenance_branch("main")
    False
    >>> is_maintenance_branch("gh-1234/something-completely-different")
    False
    """
    maintenance_branch_pattern = r'\d+\.\d+'
    return bool(re.fullmatch(maintenance_branch_pattern, ref))


@router.register("pull_request", action="opened")
@router.register("pull_request", action="reopened")
@router.register("pull_request", action="edited")
@router.register("pull_request", action="synchronize")
async def validate_maintenance_branch_pr(event, gh, *args, **kwargs):
    """Check the PR title for maintenance branch pull requests.

    If the PR was made against maintenance branch, and the title does not
    match the maintenance branch PR pattern, then post a failure status.

    The maintenance branch PR has to start with `[X.Y]`
    """
    if event.data["action"] == "edited" and "title" not in event.data["changes"]:
        return
    pull_request = event.data["pull_request"]
    base_branch = pull_request["base"]["ref"]

    if not is_maintenance_branch(base_branch):
        return

    title = util.normalize_title(pull_request["title"],
                                 pull_request["body"])
    title_match = MAINTENANCE_BRANCH_TITLE_RE.match(title)

    if title_match is None:
        status = create_status(util.StatusState.FAILURE,
                               description="Not a valid maintenance branch PR title.",
                               target_url=BACKPORT_TITLE_DEVGUIDE_URL)
    else:
        status = create_status(util.StatusState.SUCCESS,
                               description="Valid maintenance branch PR title.")
    await util.post_status(gh, event, status)


@router.register("create", ref_type="branch")
async def maintenance_branch_created(event, gh, *args, **kwargs):
    """Create the `needs backport label` when the maintenance branch is created.

    If a maintenance branch was created (e.g.: 3.9, or 4.0),
    automatically create the `needs backport to ` label.

    The maintenance branch PR has to start with `[X.Y]`
    """
    branch_name = event.data["ref"]

    if MAINTENANCE_BRANCH_RE.match(branch_name):
        await gh.post(
            "/repos/python/cpython/labels",
            data={"name": f"needs backport to {branch_name}", "color": "c2e0c6",
                  "description": "bug and security fixes"},
        )
