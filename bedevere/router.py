"""Dispatch webhook events to appropriate async functions."""

ROUTES = {}


def route(event, action):
    """Route matching events to this function."""
    def register(func):
        """Register a handler for an event."""
        actions = ROUTES.setdefault(event, {})
        actions.setdefault(action, []).append(func)
        return func
    return register


async def dispatch(gh, event):
    """Call relevant handlers for the event."""
    try:
        actions = ROUTES[event.event]
        handlers = actions[event.data["action"]]
    except KeyError:
        return
    for handler in handlers:
        await handler(gh, event)
