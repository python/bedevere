import re

from . import router


ISSUE_RE = re.compile(r"bpo-(?P<issue>\d+)")
STATUS_TEMPLATE = {"context": "bedevere/issue-number"}
FAILURE_STATUS = {
    "state": "failure",
    "target_url": "https://cpython-devguide.readthedocs.io/pullrequest.html?highlight=bpo-#submitting",
    "description": """No issue number of the form "bpo-NNNN" found in the pull request's title.""",
}


@router.route("pull_request", "opened")
@router.route("pull_request", "synchronize")
async def set_status(gh, event):
    """Set the issue number status on the pull request."""
    status = STATUS_TEMPLATE.copy()
    sha = event.data["pull_request"]["head"]["sha"]
    issue_number_match = ISSUE_RE.match(event.data["pull_request"]["title"])
    if not issue_number_match:
        # XXX check for a "trivial" label.
        #     If the even is pull_request/labeled, check if the label is "trivial".
        status.update(FAILURE_STATUS)
    else:
        status["state"] = "success"
        issue_number = issue_number_match.group("issue")
        status["description"] = f"Issue number {issue_number} found."
        status["target_url"] = f"https://bugs.python.org/issue{issue_number}"
    await gh.post(f"/repos/python/cpython/status/{sha}", data=status)


@router.route("pull_request", "edited")
async def title_edited(gh, event):
    """Set the status on a pull request that has changed its title."""
    if "title" not in event.data["changes"]:
        return
    await set_status(gh, event)


# XXX @router.route("pull_request", "labeled")
