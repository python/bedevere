import re

from gidgethub import routing


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
STATUS_TEMPLATE = {"context": "bedevere/issue-number"}
FAILURE_STATUS = STATUS_TEMPLATE.copy()
FAILURE_STATUS["state"] = "failure"
FAILURE_STATUS["target_url"] = "https://devguide.python.org/pullrequest/#submitting"
FAILURE_STATUS["description"] = """No issue number prepended to the title or "skip issue" label found"""
SKIP_ISSUE_LABEL = "skip issue"
SKIP_ISSUE_STATUS = STATUS_TEMPLATE.copy()
SKIP_ISSUE_STATUS["state"] = "success"
SKIP_ISSUE_STATUS["description"] = "No issue number necessary"


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
        data = await gh.getitem(issue_url)
        for label in data["labels"]:
            if label["name"] == SKIP_ISSUE_LABEL:
                status = SKIP_ISSUE_STATUS
                break
        else:
            status = FAILURE_STATUS
    else:
        if "body" in event.data["pull_request"]:
            body = event.data["pull_request"]["body"]
            if CLOSING_TAG not in body:
                issue_number = issue_number_found.group("issue")
                new_body = BODY.format(body=body, issue_number=issue_number)
                body_data = {"body": new_body,
                             "maintainer_can_modify": True
                            }
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
    if event.data["label"]["name"] == SKIP_ISSUE_LABEL:
        await set_status(event, gh)


def create_success_status(found_issue):
    """Create a success status for when an issue number was found in the title."""
    status = STATUS_TEMPLATE.copy()
    status["state"] = "success"
    issue_number = found_issue.group("issue")
    status["description"] = f"Issue number {issue_number} found"
    status["target_url"] = f"https://bugs.python.org/issue{issue_number}"
    return status
