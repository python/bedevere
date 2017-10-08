"""Add stale label to pull requests with label CLA not signed/awaiting changes and no activity."""
import os
from datetime import datetime
import asyncio
import aiohttp
from gidgethub import aiohttp as gh_aiohttp


from . import util

STALE_LABEL = 'stale'
PR_ACTIVE_DURATION = 30 #days

def is_pr(issue):
    return issue.get('pull_request') != None

def is_stale(issue):
    updated_at = datetime.strptime(issue['updated_at'], '%Y-%m-%dT%H:%M:%SZ')
    return (datetime.now() - updated_at).days > PR_ACTIVE_DURATION

def has_stale_label(issue):
    return STALE_LABEL in util.labels(issue) 

async def process_issue(issue, gh):
    if is_pr(issue) and is_stale(issue) and not has_stale_label(issue):
        print("Adding stale label to issue " + str(issue['number']))
        await gh.post(issue['labels_url'], data=[STALE_LABEL])

async def label_stale_prs(gh):
    async for issue in gh.getiter("/repos/python/cpython/issues?labels=CLA%20not%20signed&sort=updated&direction=asc&state=open"):
        await process_issue(issue, gh)

    async for issue in gh.getiter("/repos/python/cpython/issues?labels=awaiting%20changes&sort=updated&direction=asc&state=open"):
        await process_issue(issue, gh)


async def invoke():
    oauth_token = os.environ.get("GH_AUTH")
    async with aiohttp.ClientSession() as session:
        gh = gh_aiohttp.GitHubAPI(session, "python/bedevere", oauth_token=oauth_token)
        # Give GitHub some time to reach internal consistency.
        await asyncio.sleep(1)
        return await label_stale_prs(gh)
