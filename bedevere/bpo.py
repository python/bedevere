import re

from gidgethub import routing


router = routing.Router()
TAG_NAME = "issue-number"
CLOSING_TAG = f"<!-- /{TAG_NAME} -->"

ISSUE_RE = re.compile(r"bpo-(?P<issue>\d+)")
STATUS_TEMPLATE = {"context": "bedevere/issue-number"}
FAILURE_STATUS = STATUS_TEMPLATE.copy()
FAILURE_STATUS["state"] = "failure"
FAILURE_STATUS["target_url"] = "https://cpython-devguide.readthedocs.io/pullrequest.html#submitting"
FAILURE_STATUS["description"] = """No issue number prepended to the title or "trivial" label found."""
TRIVIAL_LABEL = "trivial"
TRIVIAL_STATUS = STATUS_TEMPLATE.copy()
TRIVIAL_STATUS["state"] = "success"
TRIVIAL_STATUS["description"] = "No issue number necessary."


async def _post_status(event, gh, status):
    """Post a status in reaction to an event."""
    await gh.post(event.data["pull_request"]["statuses_url"], data=status)


async def _patch_body(event, gh, data):
    """Patch the body of the PR in reaction to an event."""
    await gh.patch(event.data["pull_request"]["url"], data=data)


@router.register("pull_request", action="opened")
@router.register("pull_request", action="synchronize")
async def set_status(event, gh, *args, **kwargs):
    """Set the issue number status on the pull request."""
    issue_number_found = ISSUE_RE.search(event.data["pull_request"]["title"])
    if not issue_number_found:
        issue_url = event.data["pull_request"]["issue_url"]
        data = await gh.getitem(issue_url)
        for label in data["labels"]:
            if label["name"] == TRIVIAL_LABEL:
                status = TRIVIAL_STATUS
                break
        else:
            status = FAILURE_STATUS
    else:
        if "body" in event.data["pull_request"]:
            body = event.data["pull_request"]["body"]
            if CLOSING_TAG not in body:
                issue_number = issue_number_found.group("issue")
                BPO_MSG = f"""{body}\n
<!-- {TAG_NAME}: bpo-{issue_number} -->
https://bugs.python.org/issue{issue_number}
{CLOSING_TAG}
"""
                data = {"body": BPO_MSG}
                await _patch_body(event, gh, data)
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
    """Update the status if the "trivial" label was added."""
    if event.data["label"]["name"] == TRIVIAL_LABEL:
        issue_number_found = ISSUE_RE.search(
            event.data["pull_request"]["title"])
        if issue_number_found:
            status = create_success_status(issue_number_found)
        else:
            status = TRIVIAL_STATUS
        await _post_status(event, gh, status)


@router.register("pull_request", action="unlabeled")
async def removed_label(event, gh, *args, **kwargs):
    """Re-check the status if the "trivial" label is removed."""
    if event.data["label"]["name"] == TRIVIAL_LABEL:
        await set_status(event, gh)


def create_success_status(found_issue):
    """Create a success status for when an issue number was found in the title."""
    status = STATUS_TEMPLATE.copy()
    status["state"] = "success"
    issue_number = found_issue.group("issue")
    status["description"] = f"Issue number {issue_number} found."
    status["target_url"] = f"https://bugs.python.org/issue{issue_number}"
    return status
