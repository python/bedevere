import re

from . import router


REVERT_RE = re.compile(r"^Revert")
STATUS_TEMPLATE = {"context": "bedevere/revert-pr"}
SUCCESS_STATUS = STATUS_TEMPLATE.copy()
SUCCESS_STATUS["state"] = "success"
SUCCESS_STATUS["description"] = "Found the reason to revert the PR."
FAILURE_STATUS = STATUS_TEMPLATE.copy()
FAILURE_STATUS["state"] = "failure"
FAILURE_STATUS["target_url"] = "https://cpython-devguide.readthedocs.io/committing.html#reverting-a-commit"
FAILURE_STATUS["description"] = "Reason for reverting the commit is missing."


async def _post_status(gh, event, status):
    """Post a status in reaction to an event."""
    await gh.post(event.data["pull_request"]["statuses_url"], data=status)


@router.route("pull_request", "opened")
@router.route("pull_request", "synchronize")
async def set_status(gh, event):
    """Set the revert pr status on the pull request."""
    revert_found = REVERT_RE.search(event.data["pull_request"]["title"])
    if revert_found:
        pr_body = event.data["pull_request"]["body"]
        if "Reason:" in pr_body:
            status = SUCCESS_STATUS
        else:
            status = FAILURE_STATUS
        await _post_status(gh, event, status)


@router.route("pull_request", "edited")
async def title_edited(gh, event):
    """Set the status on a pull request that has changed its title."""
    if "title" not in event.data["changes"]:
        return
    await set_status(gh, event)

