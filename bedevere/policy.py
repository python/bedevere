"""Respond to AI policy labels applied by triage and core teams."""

import os

import gidgethub.routing

from . import util

router = gidgethub.routing.Router()

COMMENT_LABEL = "AI policy comment"
CLOSE_LABEL = "AI policy close"

_PR_MESSAGE_TEMPLATE = """\
Thank you for your interest in contributing to Python. This is a community-driven \
project, and we want it to be a welcoming place to learn and collaborate.

Contributors are responsible for reviewing and \
understanding what they submit, checking its claims, and being able to explain \
changes in their own words. This helps reviewers focus on the contribution and \
leaves more time to support other contributors.

{action}

Please read our [guidelines for using AI tools]\
(https://devguide.python.org/getting-started/ai-tools/index.html)."""

PR_COMMENT_MESSAGE = _PR_MESSAGE_TEMPLATE.format(
    action=(
        "This contribution appears to have been authored with AI assistance. "
        "Please explain your contribution in your own words and describe how you "
        "checked its correctness."
    )
)

PR_CLOSE_MESSAGE = _PR_MESSAGE_TEMPLATE.format(
    action=(
        "We believe this contribution does not meet our guidelines for using AI "
        "tools, so we're closing it. "
        "If you think we've misunderstood your contribution, please let us know. "
        "You're welcome to explain your approach or ask questions about the guidelines."
    )
)

_ISSUE_MESSAGE_TEMPLATE = """\
Thank you for taking the time to open this issue. Python is a community-driven \
project, and we want it to be a welcoming place to learn and collaborate.

{action}

Please read our [guidelines for using AI tools]\
(https://devguide.python.org/getting-started/ai-tools/index.html)."""

ISSUE_COMMENT_MESSAGE = _ISSUE_MESSAGE_TEMPLATE.format(
    action=(
        "This issue appears to have been written with AI assistance. "
        "Please explain your issue in your own words and describe how you checked "
        "the information you provided. This helps us understand your issue and "
        "leaves more time to address other issues."
    )
)

ISSUE_CLOSE_MESSAGE = _ISSUE_MESSAGE_TEMPLATE.format(
    action=(
        "We expect issues to be explained in your own words. "
        "We believe this issue does not meet our guidelines for using AI tools, "
        "so we're closing it. "
        "If you think we've misunderstood, you're welcome to clarify the issue "
        "or ask questions about the guidelines."
    )
)


@router.register("issues", action="labeled")
@router.register("pull_request", action="labeled")
async def label_added(event, gh, *args, **kwargs):
    """Post a policy reminder and close the contribution when requested."""
    label = util.label_name(event.data)
    if label not in {COMMENT_LABEL, CLOSE_LABEL}:
        return
    if event.data["sender"]["type"] == "Bot":
        return

    if "pull_request" in event.data:
        target = event.data["pull_request"]
        issue_url = target["issue_url"]
        comment_message, close_message = PR_COMMENT_MESSAGE, PR_CLOSE_MESSAGE
        close_data = {"state": "closed"}
    else:
        target = event.data["issue"]
        issue_url = target["url"]
        comment_message, close_message = ISSUE_COMMENT_MESSAGE, ISSUE_CLOSE_MESSAGE
        close_data = {"state": "closed", "state_reason": "not_planned"}

    if target["state"] != "open":
        return

    issue = await gh.getitem(issue_url)
    if issue["state"] != "open" or label not in util.labels(issue):
        return

    marker = f"<!-- bedevere: {label} -->"
    app_id = os.environ.get("GH_APP_ID")
    async for comment in gh.getiter(issue["comments_url"]):
        app = comment.get("performed_via_github_app") or {}
        if str(app.get("id")) == app_id and marker in comment["body"]:
            break
    else:
        message = close_message if label == CLOSE_LABEL else comment_message
        await gh.post(issue["comments_url"], data={"body": f"{message}\n\n{marker}"})

    if label == CLOSE_LABEL:
        # A maintainer may remove the label while the comment is being posted.
        issue = await gh.getitem(issue_url)
        if issue["state"] != "open" or label not in util.labels(issue):
            return
        await gh.patch(target["url"], data=close_data)
