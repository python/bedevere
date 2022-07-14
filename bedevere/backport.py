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


TITLE_RE = re.compile(r'\s*\[(?P<branch>\d+\.\d+)\].+\((?:GH-|#)(?P<pr>\d+)\)')
MAINTENANCE_BRANCH_TITLE_RE = re.compile(r'\s*\[(?P<branch>\d+\.\d+)\].+')
MAINTENANCE_BRANCH_RE = re.compile(r'\s*(?P<branch>\d+\.\d+)')
BACKPORT_LABEL = 'needs backport to {branch}'
MESSAGE_TEMPLATE = ('[GH-{pr}](https://github.com/python/cpython/pull/{pr}) is '
                    'a backport of this pull request to the '
                    '[{branch} branch](https://github.com/python/cpython/tree/{branch}).')

BACKPORT_TITLE_DEVGUIDE_URL = "https://devguide.python.org/committing/#backport-pr-title"

async def issue_for_PR(gh, pull_request):
    """Get the issue data for a pull request."""
    return await gh.getitem(pull_request["issue_url"])

async def _copy_over_labels(gh, original_issue, backport_issue):
    """Copy over relevant labels from the original PR to the backport PR."""
    label_prefixes = "skip", "type", "sprint"
    labels = list(filter(lambda x: x.startswith(label_prefixes),
                    util.labels(original_issue)))
    if labels:
        response = await gh.post(backport_issue["labels_url"], data=labels)
        return response
    return "no labels"



async def _remove_backport_label(gh, original_issue, branch, backport_pr_number):
    """Remove the appropriate "backport to" label on the original PR.

    Also leave a comment on the original PR referencing the backport PR.
    """
    backport_label = BACKPORT_LABEL.format(branch=branch)
    if backport_label not in util.labels(original_issue):
        return
    await gh.delete(original_issue['labels_url'], {'name': backport_label})
    message = MESSAGE_TEMPLATE.format(branch=branch, pr=backport_pr_number)
    response = await gh.post(original_issue['comments_url'], data={'body': message})
    return response

async def manage_labels(gh, *args, **kwargs):
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
    if event.get("action") == "edited" and "title" not in event.get("changes"):
        return
    pull_request = event["pull_request"]
    title = util.normalize_title(pull_request['title'],
                                pull_request['body'])
    title_match = TITLE_RE.match(title)
    if title_match is None:
        return
    branch = title_match.group('branch')
    original_pr_number = title_match.group('pr')
    
    original_issue = await gh.getitem(event['repository']['issues_url'],
                                    {'number': original_pr_number})
    await _remove_backport_label(gh, original_issue, branch,
                                event["number"])

    backport_issue = await issue_for_PR(gh, pull_request)
    await _copy_over_labels(gh, original_issue, backport_issue)

async def validate_maintenance_branch_pr(gh, *args, **kwargs):
    """Check the PR title for maintenance branch pull requests.

    If the PR was made against maintenance branch, and the title does not
    match the maintenance branch PR pattern, then post a failure status.

    The maintenance branch PR has to start with `[X.Y]`
    """
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
    if event.get("action") == "edited" and "title" not in event.get("changes"):
        return
    pull_request = event["pull_request"]
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
        branch_name = event["pull_request"]["head"]["ref"]

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
            await validate_maintenance_branch_pr(gh)
            await manage_labels(gh)  
    except Exception:
        traceback.print_exc()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
