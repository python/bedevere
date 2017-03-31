import asyncio

from gidgethub import sansio
import pytest

from bedevere import router


class RouterReset:

    """Reset the router cache."""

    def teardown_method(self):
        router.ROUTES = {}

    setup_method = teardown_method


class TestRoute(RouterReset):

    """Tests for bedevere.router.route()."""

    def test_nonoverlapping_events(self):
        @router.route("pull_request", "opened")
        def func1(): pass
        @router.route("issues", "opened")
        def func2(): pass
        assert "pull_request" in router.ROUTES
        actions = router.ROUTES["pull_request"]
        assert "opened" in actions
        assert actions["opened"] == [func1]
        assert "issues" in router.ROUTES
        actions = router.ROUTES["issues"]
        assert "opened" in actions
        assert actions["opened"] == [func2]

    def test_overlapping_events(self):
        @router.route("pull_request", "opened")
        def func1(): pass
        @router.route("pull_request", "closed")
        def func2(): pass
        actions = router.ROUTES["pull_request"]
        assert "opened" in actions
        assert "closed" in actions
        assert actions["opened"] == [func1]
        assert actions["closed"] == [func2]


    def test_overlapping_actions(self):
        @router.route("pull_request", "opened")
        def func1(): pass
        @router.route("pull_request", "opened")
        def func2(): pass
        handlers = router.ROUTES["pull_request"]["opened"]
        assert frozenset(handlers) == {func1, func2}

    def test_multiple_routes_on_a_single_function(self):
        @router.route("pull_request", "opened")
        @router.route("pull_request", "closed")
        def func(): pass
        actions = router.ROUTES["pull_request"]
        assert "opened" in actions
        assert "closed" in actions
        assert len(actions["opened"]) == 1
        assert actions["opened"][0] == func
        assert len(actions["closed"]) == 1
        assert actions["closed"][0] == func


class TestDispatch(RouterReset):

    """Tests for bedevere.router.dispatch()."""

    event = sansio.Event({"action": "opened"}, event="pull_request",
                         delivery_id="1")

    @pytest.mark.asyncio
    async def test_no_routes(self):
        # Should not raise any errors.
        await router.dispatch(None, self.event)

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        results = set()
        gh = object()
        @router.route("pull_request", "opened")
        async def func1(gh, event): results.add(("func1", (gh, event)))
        @router.route("pull_request", "opened")
        async def func2(gh, event): results.add(("func2", (gh, event)))
        await router.dispatch(gh, self.event)
        assert results == {("func1", (gh, self.event)),
                           ("func2", (gh, self.event)),}
