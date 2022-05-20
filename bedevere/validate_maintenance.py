"""Automatically remove a backport label, and check backport PR validity."""
import asyncio
import functools
import json
import os
import re
import traceback

import aiohttp
from gidgethub.aiohttp import GitHubAPI

from . import util

create_status = functools.partial(util.create_status, 'bedevere/maintenance-branch-pr')


MAINTENANCE_BRANCH_TITLE_RE = re.compile(r'\s*\[(?P<branch>\d+\.\d+)\].+')
BACKPORT_TITLE_DEVGUIDE_URL = "https://devguide.python.org/committing/#backport-pr-title"


async def validate_maintenance_branch_pr(gh, *args, **kwargs):
    """Check the PR title for maintenance branch pull requests.

    If the PR was made against maintenance branch, and the title does not
    match the maintenance branch PR pattern, then post a failure status.

    The maintenance branch PR has to start with `[X.Y]`
    """
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
        if event.data["action"] == "edited" and "title" not in event.data["changes"]:
            return
        pull_request = event.data["pull_request"]
        base_branch = pull_request["base"]["ref"]

        if base_branch == "main":
            return

        title = util.normalize_title(pull_request["title"],
                                    pull_request["body"])
        title_match = MAINTENANCE_BRANCH_TITLE_RE.match(title)

        if title_match is None:
            status = create_status(util.StatusState.FAILURE,
                                description="Not a valid maintenance branch PR title.",
                                target_url=BACKPORT_TITLE_DEVGUIDE_URL)
        else:
            status = create_status(util.StatusState.SUCCESS,
                               description="Valid maintenance branch PR title.")
        await util.post_status(gh, event, status)


async def main():
    try:
        async with aiohttp.ClientSession() as session:
            gh = GitHubAPI(session, "sabderemane", oauth_token=os.getenv("GH_AUTH"))
            await validate_maintenance_branch_pr(gh)  
    except Exception:
        traceback.print_exc()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())