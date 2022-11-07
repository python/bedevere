"""Check if a GitHub issue number is specified in the pull request's title."""
import re
from typing import Dict, Literal

from aiohttp import ClientSession
import gidgethub
from gidgethub import routing
from gidgethub.abc import GitHubAPI

from . import util


router = routing.Router()

IssueKind = Literal["gh", "bpo"]

ISSUE_RE = re.compile(r"(?P<kind>bpo|gh)-(?P<issue>\d+)", re.IGNORECASE)
SKIP_ISSUE_LABEL = util.skip_label("issue")
STATUS_CONTEXT = "bedevere/issue-number"
# Try to keep descriptions at or below 50 characters, else GitHub's CSS will truncate it.
SKIP_ISSUE_STATUS = util.create_status(STATUS_CONTEXT, util.StatusState.SUCCESS,
                                       description="Issue report skipped")
ISSUE_URL: Dict[IssueKind, str] = {
    "gh": "https://github.com/python/cpython/issues/{issue_number}",
    "bpo": "https://bugs.python.org/issue?@action=redirect&bpo={issue_number}"
}
ISSUE_CHECK_URL: Dict[IssueKind, str] = {
    "gh": "https://api.github.com/repos/python/cpython/issues/{issue_number}",
    "bpo": "https://bugs.python.org/issue{issue_number}"
}


@router.register("pull_request", action="opened")
@router.register("pull_request", action="synchronize")
@router.register("pull_request", action="reopened")
async def set_status(
    event, gh: GitHubAPI, *args, session: ClientSession, **kwargs
):
    """Set the issue number status on the pull request."""
    pull_request = event.data["pull_request"]
    issue = await util.issue_for_PR(gh, pull_request)

    if util.skip("issue", issue):
        await util.post_status(gh, event, SKIP_ISSUE_STATUS)
        return

    issue_number_found = ISSUE_RE.search(pull_request["title"])

    if not issue_number_found:
        status = create_failure_status_no_issue()
    else:
        issue_number = int(issue_number_found.group("issue"))
        issue_kind = issue_number_found.group("kind").lower()
        issue_found = await _validate_issue_number(
            gh, issue_number, session=session, kind=issue_kind
        )
        if issue_found:
            status = create_success_status(issue_number, kind=issue_kind)
            if issue_kind == "gh":
                # Add the issue number to the pull request's body
                await util.patch_body(gh, util.PR, pull_request, issue_number)
                # Get GitHub Issue data
                issue_data = await gh.getitem(
                    ISSUE_CHECK_URL[issue_kind].format(issue_number=issue_number)
                )
                # Add the pull request number to the issue's body
                await util.patch_body(
                    gh, util.ISSUE, issue_data, pull_request["number"]
                )
        else:
            status = create_failure_status_issue_not_present(
                issue_number, kind=issue_kind
            )
    await util.post_status(gh, event, status)


@router.register("pull_request", action="edited")
async def title_edited(event, gh, *args, session, **kwargs):
    """Set the status on a pull request that has changed its title."""
    if "title" not in event.data["changes"]:
        return
    await set_status(event, gh, session=session)


@router.register("pull_request", action="labeled")
async def new_label(event, gh, *args, **kwargs):
    """Update the status if the "skip issue" label was added."""
    if util.label_name(event.data) == SKIP_ISSUE_LABEL:
        issue_number_found = ISSUE_RE.search(
            event.data["pull_request"]["title"])
        if issue_number_found:
            status = create_success_status(issue_number_found.group("issue"))
        else:
            status = SKIP_ISSUE_STATUS
        await util.post_status(gh, event, status)


@router.register("pull_request", action="unlabeled")
async def removed_label(event, gh, *args, session, **kwargs):
    """Re-check the status if the "skip issue" label is removed."""
    if util.no_labels(event.data):
        return
    elif util.label_name(event.data) == SKIP_ISSUE_LABEL:
        await set_status(event, gh, session=session)


def create_success_status(issue_number: int, *, kind: IssueKind = "gh"):
    """Create a success status for when an issue number was found in the title."""
    url = ISSUE_URL[kind].format(issue_number=issue_number)
    return util.create_status(STATUS_CONTEXT, util.StatusState.SUCCESS,
                              description=f"Issue number {issue_number} found",
                              target_url=url)


def create_failure_status_issue_not_present(issue_number: int, *, kind: IssueKind = "gh"):
    """Create a failure status for when an issue does not exist on the GitHub issue tracker."""
    url = ISSUE_URL[kind].format(issue_number=issue_number)
    description = f"{kind.upper()} Issue #{issue_number} is not valid."
    return util.create_status(STATUS_CONTEXT, util.StatusState.FAILURE,
                              description=description,
                              target_url=url)


def create_failure_status_no_issue():
    """Create a failure status for when no issue number was found in the title."""
    description = 'No issue # in title or "skip issue" label found'
    url = "https://devguide.python.org/getting-started/pull-request-lifecycle.html#submitting"
    return util.create_status(STATUS_CONTEXT, util.StatusState.FAILURE,
                              description=description,
                              target_url=url)


async def _validate_issue_number(
    gh: GitHubAPI,
    issue_number: int,
    *,
    session: ClientSession,
    kind: IssueKind = "gh"
) -> bool:
    """Ensure the GitHub Issue number is valid."""
    if kind == "bpo":
        url = ISSUE_CHECK_URL[kind].format(issue_number=issue_number)
        async with session.head(url) as res:
            return res.status != 404

    if kind != "gh":
        raise ValueError(f"Unknown issue kind {kind}")

    url = ISSUE_CHECK_URL[kind].format(issue_number=issue_number)
    try:
        response = await gh.getitem(url)
    except gidgethub.BadRequest:
        return False
    # It is an issue if the response does not have the `pull_request` key.
    return "pull_request" not in response
