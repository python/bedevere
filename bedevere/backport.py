import asyncio
import json
import os
import re
import traceback

import aiohttp
from gidgethub.aiohttp import GitHubAPI

from . import util

TITLE_RE = re.compile(r'\s*\[(?P<branch>\d+\.\d+)\].+\((?:GH-|#)(?P<pr>\d+)\)')

BACKPORT_LABEL = 'needs backport to {branch}'
MESSAGE_TEMPLATE = ('[GH-{pr}](https://github.com/python/cpython/pull/{pr}) is '
                    'a backport of this pull request to the '
                    '[{branch} branch](https://github.com/python/cpython/tree/{branch}).')


async def issue_for_PR(gh, pull_request):
    """Get the issue data for a pull request."""
    return await gh.getitem(pull_request["issue_url"])

async def _copy_over_labels(gh, original_issue, backport_issue):
    """Copy over relevant labels from the original PR to the backport PR."""
    label_prefixes = "skip", "type", "sprint"
    labels = list(filter(lambda x: x.startswith(label_prefixes),
                    util.labels_(original_issue)))
    if labels:
        await gh.post(backport_issue["labels_url"], data=labels)


async def _remove_backport_label(gh, original_issue, branch, backport_pr_number):
    """Remove the appropriate "backport to" label on the original PR.

    Also leave a comment on the original PR referencing the backport PR.
    """
    backport_label = BACKPORT_LABEL.format(branch=branch)
    if backport_label not in util.labels_(original_issue):
        return
    await gh.delete(original_issue['labels_url'], {'name': backport_label})
    message = MESSAGE_TEMPLATE.format(branch=branch, pr=backport_pr_number)
    await gh.post(original_issue['comments_url'], data={'body': message})

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

async def main():
    try:
        async with aiohttp.ClientSession() as session:
            gh = GitHubAPI(session, "sabderemane", oauth_token=os.getenv("GH_AUTH"))
            await manage_labels(gh)  
    except Exception:
        traceback.print_exc()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())