import enum
import re
import sys
from typing import Any, Dict

import gidgethub
from gidgethub.abc import GitHubAPI

NEWS_NEXT_DIR = "Misc/NEWS.d/next/"
PR = 'pr'
ISSUE = 'issue'
DEFAULT_BODY = ""

PR_BODY_TAG_NAME = f"gh-{{tag_type}}-number"
PR_BODY_OPENING_TAG = f"<!-- {PR_BODY_TAG_NAME}: gh-{{pr_or_issue_number}} -->"
PR_BODY_CLOSING_TAG = f"<!-- /{PR_BODY_TAG_NAME} -->"
PR_BODY_TEMPLATE = f"""\
{{body}}

{PR_BODY_OPENING_TAG}
* {{key}}: gh-{{pr_or_issue_number}}
{PR_BODY_CLOSING_TAG}
"""

ISSUE_BODY_TAG_NAME = f"gh-linked-{PR}s"
ISSUE_BODY_OPENING_TAG = f'<!-- {ISSUE_BODY_TAG_NAME} -->'
ISSUE_BODY_CLOSING_TAG = f'<!-- /{ISSUE_BODY_TAG_NAME} -->'
ISSUE_BODY_TASK_LIST_TEMPLATE = f"""\n
{ISSUE_BODY_OPENING_TAG}
### Linked PRs
* gh-{{pr_number}}
{ISSUE_BODY_CLOSING_TAG}
"""

# Regex pattern to search for tasklist in the issue body
ISSUE_BODY_TASK_LIST_PATTERN = re.compile(
    rf"(?P<start>{ISSUE_BODY_OPENING_TAG})"
    rf"(?P<tasks>.*?)"
    rf"(?P<end>{ISSUE_BODY_CLOSING_TAG})",
    flags=re.DOTALL
)


@enum.unique
class StatusState(enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    FAILURE = "failure"


def create_status(context, state, *, description=None, target_url=None):
    """Create the data for a status.

    The argument order is such that you can use functools.partial() to set the
    context to avoid repeatedly specifying it throughout a module.
    """
    status = {
        "context": context,
        "state": state.value,
    }
    if description is not None:
        status["description"] = description
    if target_url is not None:
        status["target_url"] = target_url

    return status


async def post_status(gh, event, status):
    """Post a status in reaction to an event."""
    await gh.post(event.data["pull_request"]["statuses_url"], data=status)


def skip_label(what):
    """Generate a "skip" label name."""
    return f"skip {what}"


def labels(issue):
    return {label_data["name"] for label_data in issue["labels"]}


def skip(what, issue):
    """See if an issue has a "skip {what}" label."""
    return skip_label(what) in labels(issue)


def label_name(event_data):
    """Get the label name from a label-related webhook event."""
    return event_data["label"]["name"]


def user_login(item):
    return item["user"]["login"]


async def files_for_PR(gh, pull_request):
    """Get files for a pull request."""
    # For some unknown reason there isn't any files URL in a pull request
    # payload.
    files_url = f'{pull_request["url"]}/files'
    data = []
    async for filedata in gh.getiter(files_url):  # pragma: no branch
        data.append(
            {
                "file_name": filedata["filename"],
                "patch": filedata.get("patch", ""),
            }
        )
    return data


async def issue_for_PR(gh, pull_request):
    """Return a dict with data about the given PR."""
    # "issue_url" is the API endpoint for the given pull_request (despite the name)
    return await gh.getitem(pull_request["issue_url"])


def build_pr_body(issue_number: int, body: str) -> str:
    """Update the Pull Request body with related Issue."""
    return PR_BODY_TEMPLATE.format(
        body=body,
        pr_or_issue_number=issue_number,
        key=ISSUE.title(),
        tag_type=ISSUE,
    )


def build_issue_body(pr_number: int, body: str) -> str:
    """Update the Issue body with related Pull Request."""
    # If the body already contains a legacy closing tag
    # (e.g. <!-- /gh-pr-number -->), then we use the legacy template
    # TODO: Remove this when all the open issues using the legacy tag are closed
    if PR_BODY_CLOSING_TAG.format(tag_type=PR) in body:
        return PR_BODY_TEMPLATE.format(
            body=body,
            pr_or_issue_number=pr_number,
            key=PR.upper(),
            tag_type=PR,
        )

    # Check if the body already contains a tasklist
    result = ISSUE_BODY_TASK_LIST_PATTERN.search(body)

    if not result:
        # If the body doesn't contain a tasklist, we add one using the template
        body += ISSUE_BODY_TASK_LIST_TEMPLATE.format(pr_number=pr_number)
        return body

    # If the body already contains a tasklist, only append the new PR to the list
    return ISSUE_BODY_TASK_LIST_PATTERN.sub(
        fr"\g<start>\g<tasks>* gh-{pr_number}\n\g<end>",
        body,
        count=1,
    )


async def patch_body(
    gh: GitHubAPI,
    content_type: str,
    pr_or_issue: Dict[str, Any],
    pr_or_issue_number: int,
) -> Any:
    """Updates the description of a PR/Issue with the gh issue/pr number if it exists.

    returns if body exists with issue/pr number
    """
    body = pr_or_issue.get("body", None) or DEFAULT_BODY
    body_search_pattern = rf"(^|\b)(GH-|gh-|#){pr_or_issue_number}\b"

    if not body or not re.search(body_search_pattern, body):
        updated_body = (
            build_issue_body(pr_or_issue_number, body)
            if content_type == ISSUE
            else build_pr_body(pr_or_issue_number, body)
        )
        return await gh.patch(pr_or_issue["url"], data={"body": updated_body})
    return None


async def is_core_dev(gh, username):
    """Check if the user is a CPython core developer."""
    org_teams = "/orgs/python/teams"
    team_name = "python core"
    async for team in gh.getiter(org_teams):
        if team["name"].lower() == team_name:  # pragma: no branch
            break
    else:
        raise ValueError(f"{team_name!r} not found at {org_teams!r}")
    # The 'teams' object only provides a URL to a deprecated endpoint,
    # so manually construct the URL to the non-deprecated team membership
    # endpoint.
    membership_url = f"/teams/{team['id']}/memberships/{username}"
    try:
        await gh.getitem(membership_url)
    except gidgethub.BadRequest as exc:
        if exc.status_code == 404:
            return False
        raise
    else:
        return True


def is_news_dir(filename):
    "Return True if file is in the News directory."
    return filename.startswith(NEWS_NEXT_DIR)


def normalize_title(title, body):
    """Normalize the title if it spills over into the PR's body."""
    if not (title.endswith("…") and body.startswith("…")):
        return title
    else:
        # Being paranoid in case \r\n is used.
        return title[:-1] + body[1:].partition("\r\n")[0]


def no_labels(event_data):
    if "label" not in event_data:
        print(
            "no 'label' key in payload; "
            "'unlabeled' event triggered by label deletion?",
            file=sys.stderr,
        )
        return True
    else:
        return False


async def get_pr_for_commit(gh, sha):
    """Find the PR containing the specific commit hash."""
    prs_for_commit = await gh.getitem(
        f"/search/issues?q=type:pr+repo:python/cpython+sha:{sha}"
    )
    if prs_for_commit["total_count"] > 0:  # there should only be one
        return prs_for_commit["items"][0]
    return None
