"""Automatically close PR that tries to merge maintenance branch into main."""
import asyncio
import json
import os
import re
import traceback

import aiohttp
from gidgethub.aiohttp import GitHubAPI
# import gidgethub.routing


PYTHON_MAINT_BRANCH_RE = re.compile(r'^\w+:\d+\.\d+$')

INVALID_PR_COMMENT = """\
PRs attempting to merge a maintenance branch into the \
main branch are deemed to be spam and automatically closed. \
If you were attempting to report a bug, please go to \
https://github.com/python/cpython/issues; \
see devguide.python.org for further instruction as needed."""


# @router.register("pull_request", action="review_requested")
async def dismiss_invalid_pr_review_request(gh, *args, **kwargs):
    """Dismiss review request from the invalid PR.

    PR is considered invalid if:
    * base_label is 'python:main'
    * head_label is '<username>:<maint_branch>'
    """
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
        head_label = event["pull_request"]["head"]["label"]
        base_label = event["pull_request"]["base"]["label"]

    if PYTHON_MAINT_BRANCH_RE.match(head_label) and \
            base_label == "python:main":
        data = {"reviewers": [reviewer["login"] for reviewer in event["pull_request"]["requested_reviewers"]],
                "team_reviewers": [team["name"] for team in event["pull_request"]["requested_teams"]]
                }
        await gh.delete(f'{event["pull_request"]["url"]}/requested_reviewers',
                        data=data)

async def main():
    try:
        async with aiohttp.ClientSession() as session:
            gh = GitHubAPI(session, "sabderemane", oauth_token=os.getenv("GH_AUTH"))
            await dismiss_invalid_pr_review_request(gh)  
    except Exception:
        traceback.print_exc()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
