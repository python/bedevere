from unittest import mock

from aiohttp import web
from gidgethub import sansio

from bedevere import __main__ as main

app_installation_payload = {
    "installation": {
        "id": 123,
        "account": {"login": "mariatta"},
    }
}


async def test_health_check(aiohttp_client):
    app = web.Application()
    app.router.add_get("/health", main.health_check)
    client = await aiohttp_client(app)
    response = await client.get("/health")
    assert response.status == 200
    assert await response.text() == "OK"


async def test_ping(aiohttp_client):
    app = web.Application()
    app.router.add_post("/", main.main)
    client = await aiohttp_client(app)
    headers = {"x-github-event": "ping", "x-github-delivery": "1234"}
    data = {"zen": "testing is good"}
    response = await client.post("/", headers=headers, json=data)
    assert response.status == 200


async def test_bad_request_if_no_installation(aiohttp_client):
    app = web.Application()
    app.router.add_post("/", main.main)
    client = await aiohttp_client(app)
    headers = {"x-github-event": "project", "x-github-delivery": "1234"}
    # Sending a payload that shouldn't trigger any networking, but no errors
    # either.
    data = {"action": "created"}
    response = await client.post("/", headers=headers, json=data)
    assert response.status == 400
    assert await response.text() == "Must be installed as an App."


async def test_failure(aiohttp_client):
    """Even in the face of an exception, the server should not crash."""
    app = web.Application()
    app.router.add_post("/", main.main)
    client = await aiohttp_client(app)
    # Missing key headers.
    response = await client.post("/", headers={})
    assert response.status == 500


@mock.patch("gidgethub.apps.get_installation_access_token")
async def test_success_with_installation(get_access_token_mock, aiohttp_client):
    get_access_token_mock.return_value = {
        "token": "ghs_blablabla",
        "expires_at": "2023-06-14T19:02:50Z",
    }
    app = web.Application()
    app.router.add_post("/", main.main)
    client = await aiohttp_client(app)
    headers = {"x-github-event": "project", "x-github-delivery": "1234"}
    # Sending a payload that shouldn't trigger any networking, but no errors
    # either.
    data = {"action": "created"}
    data.update(app_installation_payload)
    response = await client.post("/", headers=headers, json=data)
    assert response.status == 200


class FakeGH:
    def __init__(self):
        pass


async def test_repo_installation_added(capfd):
    event_data = {
        "action": "created",
    }
    event_data.update(app_installation_payload)

    event = sansio.Event(event_data, event="installation", delivery_id="1")
    gh = FakeGH()
    await main.router.dispatch(event, gh)
    out, err = capfd.readouterr()
    assert (
        f"App installed by {event.data['installation']['account']['login']}, installation_id: {event.data['installation']['id']}"
        in out
    )
