"""Check if a bugs.python.org issue number is specified in the pull request's title."""
import re

from gidgethub import routing

from . import util


router = routing.Router()
TAG_NAME = "issue-number"
CLOSING_TAG = f"<!-- /{TAG_NAME} -->"
BODY = f"""\
{{body}}

<!-- {TAG_NAME}: bpo-{{issue_number}} -->
https://bugs.python.org/issue{{issue_number}}
{CLOSING_TAG}
"""

ISSUE_RE = re.compile(r"bpo-(?P<issue>\d+)")
SKIP_ISSUE_LABEL = util.skip_label("issue")
STATUS_CONTEXT = "bedevere/issue-number"
# Try to keep descriptions at or below 50 characters, else GitHub's CSS will truncate it.
_FAILURE_DESCRIPTION = 'No issue # in title or "skip issue" label found'
_FAILURE_URL = "https://devguide.python.org/pullrequest/#submitting"
FAILURE_STATUS = util.create_status(STATUS_CONTEXT, util.StatusState.FAILURE,
                                    description=_FAILURE_DESCRIPTION,
                                    target_url=_FAILURE_URL)
del _FAILURE_DESCRIPTION
del _FAILURE_URL
SKIP_ISSUE_STATUS = util.create_status(STATUS_CONTEXT, util.StatusState.SUCCESS,
                                       description="Issue report skipped")


@router.register("pull_request", action="opened")
@router.register("pull_request", action="synchronize")
@router.register("pull_request", action="reopened")
async def set_status(event, gh, *args, **kwargs):
    """Set the issue number status on the pull request."""
    issue_number_found = ISSUE_RE.search(event.data["pull_request"]["title"])
    if not issue_number_found:
        issue = await util.issue_for_PR(gh, event.data["pull_request"])
        status = SKIP_ISSUE_STATUS if util.skip("issue", issue) else FAILURE_STATUS
    else:
        if "body" in event.data["pull_request"]:
            body = event.data["pull_request"]["body"] or ""
            if not body or CLOSING_TAG not in body:
                issue_number = issue_number_found.group("issue")
                new_body = BODY.format(body=body, issue_number=issue_number)
                body_data = {"body": new_body, "maintainer_can_modify": True}
                await gh.patch(event.data["pull_request"]["url"], data=body_data)
        status = create_success_status(issue_number_found)
    await util.post_status(gh, event, status)


@router.register("pull_request", action="edited")
async def title_edited(event, gh, *args, **kwargs):
    """Set the status on a pull request that has changed its title."""
    if "title" not in event.data["changes"]:
        return
    await set_status(event, gh)


@router.register("pull_request", action="labeled")
async def new_label(event, gh, *args, **kwargs):
    """Update the status if the "skip issue" label was added."""
    if util.label_name(event.data) == SKIP_ISSUE_LABEL:
        issue_number_found = ISSUE_RE.search(
            event.data["pull_request"]["title"])
        if issue_number_found:
            status = create_success_status(issue_number_found)
        else:
            status = SKIP_ISSUE_STATUS
        await util.post_status(gh, event, status)


@router.register("pull_request", action="unlabeled")
async def removed_label(event, gh, *args, **kwargs):
    """Re-check the status if the "skip issue" label is removed."""
    if util.no_labels(event.data):
        return
    elif util.label_name(event.data) == SKIP_ISSUE_LABEL:
        await set_status(event, gh)


def create_success_status(found_issue):
    """Create a success status for when an issue number was found in the title."""
    issue_number = found_issue.group("issue")
    url = f"https://bugs.python.org/issue{issue_number}"
    return util.create_status(STATUS_CONTEXT, util.StatusState.SUCCESS,
                              description=f"Issue number {issue_number} found",
                              target_url=url)
