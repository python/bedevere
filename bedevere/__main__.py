import asyncio
import importlib
import os
import sys
import traceback

import aiohttp
from aiohttp import web
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import sansio

from . import router
# Import modules for router registration.
importlib.import_module(".bpo", __package__)


async def main(request):
    try:
        body = await request.read()
        secret = os.environ.get("GH_SECRET")
        event = sansio.Event.from_http(request.headers, body, secret=secret)
        if event.event == "ping":
            return web.Response(status=200)
        oauth_token = os.environ.get("GH_AUTH")
        with aiohttp.ClientSession() as session:
            gh = gh_aiohttp.GitHubAPI(session, "python/bedevere",
                                      oauth_token=oauth_token)
            # Give GitHub some time to reach internal consistency.
            await asyncio.sleep(1)
            await router.dispatch(gh, event)
        return web.Response(status=200)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return web.Response(status=500)


if __name__ == "__main__":
    app = web.Application()
    app.router.add_post("/", main)
    web.run_app(app, port=os.environ.get("PORT"))
