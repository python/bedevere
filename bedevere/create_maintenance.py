
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


# router = gidgethub.routing.Router()

MAINTENANCE_BRANCH_RE = re.compile(r'\s*(?P<branch>\d+\.\d+)')


# @router.register("create", ref_type="branch")
async def maintenance_branch_created(gh, *args, **kwargs):
    """Create the `needs backport label` when the maintenance branch is created.

    Also post a reminder to add the maintenance branch to the list of
    `ALLOWED_BRANCHES` in CPython-emailer-webhook.

    If a maintenance branch was created (e.g.: 3.9, or 4.0),
    automatically create the `needs backport to ` label.

    The maintenance branch PR has to start with `[X.Y]`
    """
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
        branch_name = event.data["ref"]

    if MAINTENANCE_BRANCH_RE.match(branch_name):
        await gh.post(
            "/repos/python/cpython/labels",
            data={"name": f"needs backport to {branch_name}", "color": "#c2e0c6"},
        )

        await gh.post(
            "/repos/berkerpeksag/cpython-emailer-webhook/issues",
            data={
                "title": f"Please add {branch_name} to ALLOWED_BRANCHES",
                "body": (
                    f"A new CPython maintenance branch `{branch_name}` has just been created.",
                    "\nThis is a reminder to add `{branch_name}` to the list of `ALLOWED_BRANCHES`",
                    "\nhttps://github.com/berkerpeksag/cpython-emailer-webhook/blob/e164cb9a6735d56012a4e557fd67dd7715c16d7b/mailer.py#L15",
                ),
            },
        )


async def main():
    try:
        async with aiohttp.ClientSession() as session:
            gh = GitHubAPI(session, "sabderemane", oauth_token=os.getenv("GH_AUTH"))
            await maintenance_branch_created(gh)  
    except Exception:
        traceback.print_exc()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())