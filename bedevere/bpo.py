"""Check if a bugs.python.org issue number is specified in the pull request's title."""
import re
import sys

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
SKIP_ISSUE_LABEL = "skip issue"
STATUS_CONTEXT = "bedevere/issue-number"
_FAILURE_DESCRIPTION = 'No issue number prepended to the title or "skip issue" label found'
_FAILURE_URL = "https://devguide.python.org/pullrequest/#submitting"
FAILURE_STATUS = util.create_status(STATUS_CONTEXT, util.StatusState.FAILURE,
                                    description=_FAILURE_DESCRIPTION,
                                    target_url=_FAILURE_URL)
del _FAILURE_DESCRIPTION
del _FAILURE_URL
SKIP_ISSUE_STATUS = util.create_status(STATUS_CONTEXT, util.StatusState.SUCCESS,
                                       description="Issue report skipped")


async def _post_status(event, gh, status):
    """Post a status in reaction to an event."""
    await gh.post(event.data["pull_request"]["statuses_url"], data=status)


@router.register("pull_request", action="opened")
@router.register("pull_request", action="synchronize")
async def set_status(event, gh, *args, **kwargs):
    """Set the issue number status on the pull request."""
    issue_number_found = ISSUE_RE.search(event.data["pull_request"]["title"])
    if not issue_number_found:
        issue_url = event.data["pull_request"]["issue_url"]
        issue = await gh.getitem(issue_url)
        status = SKIP_ISSUE_STATUS if util.skip("issue", issue) else FAILURE_STATUS
    else:
        if "body" in event.data["pull_request"]:
            body = event.data["pull_request"]["body"]
            if CLOSING_TAG not in body:
                issue_number = issue_number_found.group("issue")
                new_body = BODY.format(body=body, issue_number=issue_number)
                body_data = {"body": new_body, "maintainer_can_modify": True}
                await gh.patch(event.data["pull_request"]["url"], data=body_data)
        status = create_success_status(issue_number_found)
    await _post_status(event, gh, status)


@router.register("pull_request", action="edited")
async def title_edited(event, gh, *args, **kwargs):
    """Set the status on a pull request that has changed its title."""
    if "title" not in event.data["changes"]:
        return
    await set_status(event, gh)


@router.register("pull_request", action="labeled")
async def new_label(event, gh, *args, **kwargs):
    """Update the status if the "skip issue" label was added."""
    if event.data["label"]["name"] == SKIP_ISSUE_LABEL:
        issue_number_found = ISSUE_RE.search(
            event.data["pull_request"]["title"])
        if issue_number_found:
            status = create_success_status(issue_number_found)
        else:
            status = SKIP_ISSUE_STATUS
        await _post_status(event, gh, status)


@router.register("pull_request", action="unlabeled")
async def removed_label(event, gh, *args, **kwargs):
    """Re-check the status if the "skip issue" label is removed."""
    if "label" not in event.data:
        print("no 'label' key in payload; "
              "'unlabeled' event triggered by label deletion?",
              file=sys.stderr)
    elif event.data["label"]["name"] == SKIP_ISSUE_LABEL:
        await set_status(event, gh)


def create_success_status(found_issue):
    """Create a success status for when an issue number was found in the title."""
    issue_number = found_issue.group("issue")
    url = f"https://bugs.python.org/issue{issue_number}"
    return util.create_status(STATUS_CONTEXT, util.StatusState.SUCCESS,
                              description=f"Issue number {issue_number} found",
                              target_url=url)
