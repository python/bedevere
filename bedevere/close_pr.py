"""Automatically close PR that tries to merge maintenance branch into master."""
import re

import gidgethub.routing


PYTHON_MAINT_BRANCH_RE = re.compile(r'^\w+:\d+\.\d+$')

router = gidgethub.routing.Router()

@router.register("pull_request", action="opened")
@router.register("pull_request", action="synchronize")
async def close_invalid_pr(event, gh, *args, **kwargs):
    """Close the invalid PR.

    PR is considered invalid if:
    * base_label is 'python:master'
    * head_label is '<username>:<maint_branch>'
    """
    head_label = event.data["pull_request"]["head"]["label"]
    base_label = event.data["pull_request"]["base"]["label"]

    if PYTHON_MAINT_BRANCH_RE.match(head_label) and \
        base_label == "python:master":
        data = {'state': 'closed',
                'maintainer_can_modify': True}
        await gh.patch(event.data["pull_request"]["url"], data=data)


@router.register("pull_request", action="review_requested")
async def dismiss_invalid_pr_review_request(event, gh, *args, **kwargs):
    """Dismiss review request from the invalid PR.

    PR is considered invalid if:
    * base_label is 'python:master'
    * head_label is '<username>:<maint_branch>'
    """
    head_label = event.data["pull_request"]["head"]["label"]
    base_label = event.data["pull_request"]["base"]["label"]

    if PYTHON_MAINT_BRANCH_RE.match(head_label) and \
            base_label == "python:master":
        data = {"reviewers": [reviewer["login"] for reviewer in event.data["pull_request"]["requested_reviewers"]],
                "team_reviewers": [team["name"] for team in event.data["pull_request"]["requested_teams"]]
                }
        await gh.delete(f'{event.data["pull_request"]["url"]}/requested_reviewers',
                        data=data)
