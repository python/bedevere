import asyncio
import importlib
import os
import sys
import traceback

import aiohttp
from aiohttp import web
import cachetools
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import routing
from gidgethub import sansio

from . import backport, bpo, stage


router = routing.Router(backport.router, bpo.router, stage.router)
cache = cachetools.LRUCache(maxsize=500)


async def main(request):
    try:
        body = await request.read()
        secret = os.environ.get("GH_SECRET")
        event = sansio.Event.from_http(request.headers, body, secret=secret)
        print('GH delivery ID', event.delivery_id, file=sys.stderr)
        if event.event == "ping":
            return web.Response(status=200)
        oauth_token = os.environ.get("GH_AUTH")
        async with aiohttp.ClientSession() as session:
            gh = gh_aiohttp.GitHubAPI(session, "python/bedevere",
                                      oauth_token=oauth_token,
                                      cache=cache)
            # Give GitHub some time to reach internal consistency.
            await asyncio.sleep(1)
            await router.dispatch(event, gh)
        return web.Response(status=200)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return web.Response(status=500)


if __name__ == "__main__":  # pragma: no cover
    app = web.Application()
    app.router.add_post("/", main)
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)
    web.run_app(app, port=port)
