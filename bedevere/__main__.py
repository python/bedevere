import asyncio

import os
import sys
import traceback

import aiohttp
from aiohttp import web
import cachetools
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import routing
from gidgethub import sansio
from gidgethub import actions

from . import backport, gh_issue, close_pr, filepaths, news, stage

# import sentry_sdk

router = routing.Router(backport.router, gh_issue.router, close_pr.router,
                        filepaths.router, news.router,
                        stage.router)
cache = cachetools.LRUCache(maxsize=500)

# sentry_sdk.init(os.environ.get("SENTRY_DSN"))

async def main(event_payload):
    try:
        event_name = os.environ["GITHUB_EVENT_NAME"]
        job_id = os.environ["GITHUB_JOB"]
        event = sansio.Event(event_payload, event=event_name, delivery_id=job_id)
        print(f"{event.data=}")
        print(f"{event_payload}")
        print('GH delivery ID', event.delivery_id, file=sys.stderr)

        oauth_token = os.environ.get("GITHUB_TOKEN")
        async with aiohttp.ClientSession() as session:
            gh = gh_aiohttp.GitHubAPI(session, "python/bedevere",
                                      oauth_token=oauth_token,
                                      cache=cache)
            # Give GitHub some time to reach internal consistency.
            await asyncio.sleep(1)
            await router.dispatch(event, gh, session=session)
        try:
            print('GH requests remaining:', gh.rate_limit.remaining)
        except AttributeError:
            pass

    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":  # pragma: no cover
    if os.environ.get("GITHUB_EVENT_PATH"):
        event_from = actions.event()
        asyncio.run(main(event_from))
    else:
        print(f"Environment Variable 'GITHUB_EVENT_PATH' not found.")
