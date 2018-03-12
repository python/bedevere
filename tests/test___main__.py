from aiohttp import web
import pytest

from bedevere import __main__ as main


async def test_ping(aiohttp_client):
    app = web.Application()
    app.router.add_post("/", main.main)
    client = await aiohttp_client(app)
    headers = {"x-github-event": "ping",
               "x-github-delivery": "1234"}
    data = {"zen": "testing is good"}
    response = await client.post("/", headers=headers, json=data)
    assert response.status == 200


async def test_success(aiohttp_client):
    app = web.Application()
    app.router.add_post("/", main.main)
    client = await aiohttp_client(app)
    headers = {"x-github-event": "project",
               "x-github-delivery": "1234"}
    # Sending a payload that shouldn't trigger any networking, but no errors
    # either.
    data = {"action": "created"}
    response = await client.post("/", headers=headers, json=data)
    assert response.status == 200


async def test_failure(aiohttp_client):
    """Even in the face of an exception, the server should not crash."""
    app = web.Application()
    app.router.add_post("/", main.main)
    client = await aiohttp_client(app)
    # Missing key headers.
    response = await client.post("/", headers={})
    assert response.status == 500
