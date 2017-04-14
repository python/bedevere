import re

from . import router


ISSUE_RE = re.compile(r"bpo-(?P<issue>\d+)")
STATUS_TEMPLATE = {"context": "bedevere/issue-number"}
FAILURE_STATUS = STATUS_TEMPLATE.copy()
FAILURE_STATUS["state"] = "failure"
FAILURE_STATUS["target_url"] = "https://cpython-devguide.readthedocs.io/pullrequest.html#submitting"
FAILURE_STATUS["description"] = """No issue number in the title or "trivial" label."""
TRIVIAL_LABEL = "trivial"
TRIVIAL_STATUS = STATUS_TEMPLATE.copy()
TRIVIAL_STATUS["state"] = "success"
TRIVIAL_STATUS["description"] = "No issue number necessary."


async def _post_status(gh, event, status):
    """Post a status in reaction to an event."""
    await gh.post(event.data["pull_request"]["statuses_url"], data=status)


@router.route("pull_request", "opened")
@router.route("pull_request", "synchronize")
async def set_status(gh, event):
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
        status = get_found_issue_number_status(issue_number_found)
    await _post_status(gh, event, status)


@router.route("pull_request", "edited")
async def title_edited(gh, event):
    """Set the status on a pull request that has changed its title."""
    if "title" not in event.data["changes"]:
        return
    await set_status(gh, event)


@router.route("pull_request", "labeled")
async def new_label(gh, event):
    """Update the status if the "trivial" label was added."""
    if event.data["label"]["name"] == TRIVIAL_LABEL:
        issue_number_found = ISSUE_RE.search(
            event.data["pull_request"]["title"])
        if issue_number_found:
            status = get_found_issue_number_status(issue_number_found)
        else:
            status = TRIVIAL_STATUS
        await _post_status(gh, event, status)


@router.route("pull_request", "unlabeled")
async def removed_label(gh, event):
    """Re-check the status if the "trivial" label is removed."""
    if event.data["label"]["name"] == TRIVIAL_LABEL:
        await set_status(gh, event)


def get_found_issue_number_status(found_issue):
    """Get the status for when an issue number was found in the title"""
    status = STATUS_TEMPLATE.copy()
    status["state"] = "success"
    issue_number = found_issue.group("issue")
    status["description"] = f"Issue number {issue_number} found."
    status[
        "target_url"] = f"https://bugs.python.org/issue{issue_number}"
    return status