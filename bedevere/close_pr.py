"""Automatically close PR that tries to merge maintenance branch into main."""
import re

import gidgethub.routing


PYTHON_MAINT_BRANCH_RE = re.compile(r'^\w+:\d+\.\d+$')

INVALID_PR_COMMENT = """\
PRs attempting to merge a maintenance branch into the \
main branch are deemed to be spam and automatically closed. \
If you were attempting to report a bug, please go to \
https://github.com/python/cpython/issues; \
see devguide.python.org for further instruction as needed."""


router = gidgethub.routing.Router()

@router.register("pull_request", action="opened")
@router.register("pull_request", action="synchronize")
async def close_invalid_pr(event, gh, *args, **kwargs):
    """Close the invalid PR, add 'invalid' label, and post a message.

    PR is considered invalid if:
    * base_label is 'python:main'
    * head_label is '<username>:<maint_branch>'
    """
    head_label = event.data["pull_request"]["head"]["label"]
    base_label = event.data["pull_request"]["base"]["label"]

    if PYTHON_MAINT_BRANCH_RE.match(head_label) and \
        base_label == "python:main":
        data = {'state': 'closed'}
        await gh.patch(event.data["pull_request"]["url"], data=data)
        await gh.post(
            f'{event.data["pull_request"]["issue_url"]}/labels',
            data=["invalid"]
        )
        await gh.post(
            f'{event.data["pull_request"]["issue_url"]}/comments',
            data={'body': INVALID_PR_COMMENT}
        )


@router.register("pull_request", action="review_requested")
async def dismiss_invalid_pr_review_request(event, gh, *args, **kwargs):
    """Dismiss review request from the invalid PR.

    PR is considered invalid if:
    * base_label is 'python:main'
    * head_label is '<username>:<maint_branch>'
    """
    head_label = event.data["pull_request"]["head"]["label"]
    base_label = event.data["pull_request"]["base"]["label"]

    if PYTHON_MAINT_BRANCH_RE.match(head_label) and \
            base_label == "python:main":
        data = {"reviewers": [reviewer["login"] for reviewer in event.data["pull_request"]["requested_reviewers"]],
                "team_reviewers": [team["name"] for team in event.data["pull_request"]["requested_teams"]]
                }
        await gh.delete(f'{event.data["pull_request"]["url"]}/requested_reviewers',
                        data=data)
