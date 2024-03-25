import asyncio
import importlib
import os
import sys
import traceback

import aiohttp
import cachetools
import sentry_sdk
from aiohttp import web
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import apps, routing, sansio

from . import backport, close_pr, filepaths, gh_issue, news, stage

router = routing.Router(
    backport.router,
    gh_issue.router,
    close_pr.router,
    filepaths.router,
    news.router,
    stage.router,
)
cache = cachetools.LRUCache(maxsize=500)

sentry_sdk.init(os.environ.get("SENTRY_DSN"))


async def main(request):
    try:
        body = await request.read()
        secret = os.environ.get("GH_SECRET")
        event = sansio.Event.from_http(request.headers, body, secret=secret)
        print("GH delivery ID", event.delivery_id, file=sys.stderr)
        if event.event == "ping":
            return web.Response(status=200)

        async with aiohttp.ClientSession() as session:
            gh = gh_aiohttp.GitHubAPI(session, "python/bedevere", cache=cache)
            if not event.data.get("installation"):
                return web.Response(text="Must be installed as an App.", status=400)
            installation_id = event.data["installation"]["id"]
            installation_access_token = await apps.get_installation_access_token(
                gh,
                installation_id=installation_id,
                app_id=os.environ.get("GH_APP_ID"),
                private_key=os.environ.get("GH_PRIVATE_KEY"),
            )
            gh.oauth_token = installation_access_token["token"]

            # Give GitHub some time to reach internal consistency.
            await asyncio.sleep(1)
            await router.dispatch(event, gh, session=session)
        try:
            print("GH requests remaining:", gh.rate_limit.remaining)
        except AttributeError:
            pass
        return web.Response(status=200)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return web.Response(status=500)


@router.register("installation", action="created")
async def repo_installation_added(event, gh, *args, **kwargs):
    print(
        f"App installed by {event.data['installation']['account']['login']}, installation_id: {event.data['installation']['id']}"
    )


if __name__ == "__main__":  # pragma: no cover
    app = web.Application()
    app.router.add_post("/", main)
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)
    web.run_app(app, port=port)
