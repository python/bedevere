from unittest import mock

from aiohttp import web
from gidgethub import sansio

from bedevere import __main__ as main
from bedevere import config

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


def pr_opened_event(repo):
    return sansio.Event(
        {
            "action": "opened",
            "number": 1,
            "pull_request": {
                "url": f"https://api.github.com/repos/{repo}/pulls/1",
                "statuses_url": f"https://api.github.com/repos/{repo}/statuses/abc",
                "issue_url": f"https://api.github.com/repos/{repo}/issues/1",
                "title": "Fix a typo",
                "body": "",
                "user": {"login": "contributor"},
                "author_association": "NONE",
                "draft": False,
                "base": {"ref": "main"},
                "head": {"ref": "fix-typo", "label": "contributor:fix-typo"},
            },
            "repository": {"full_name": repo},
        },
        event="pull_request",
        delivery_id="1",
    )


async def test_unconfigured_repo_runs_no_cpython_features():
    # FakeGH has no API methods, so any status, label or comment call fails.
    await main.dispatch(pr_opened_event("python/devguide"), FakeGH())


async def test_configured_repo_runs_its_features_in_order():
    dispatched = []

    def spy(name):
        class SpyRouter:
            async def dispatch(self, event, gh, **kwargs):
                dispatched.append((name, kwargs["features"]))

        return SpyRouter()

    spies = {name: spy(name) for name in main.FEATURE_ROUTERS}
    with mock.patch.dict(main.FEATURE_ROUTERS, spies):
        await main.dispatch(pr_opened_event("python/cpython"), FakeGH())

    assert [name for name, _ in dispatched] == list(main.FEATURE_ROUTERS)
    assert all(features == config.ALL_FEATURES for _, features in dispatched)


async def test_event_without_repository_runs_no_features():
    event_data = {"action": "created"}
    event_data.update(app_installation_payload)
    event = sansio.Event(event_data, event="installation", delivery_id="1")
    with mock.patch.dict(main.FEATURE_ROUTERS, {}, clear=True):
        main.FEATURE_ROUTERS["policy"] = mock.AsyncMock()
        await main.dispatch(event, FakeGH())
        main.FEATURE_ROUTERS["policy"].dispatch.assert_not_called()
