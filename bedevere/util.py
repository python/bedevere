import enum

import gidgethub


@enum.unique
class StatusState(enum.Enum):
    SUCCESS = 'success'
    ERROR = 'error'
    FAILURE = 'failure'


def create_status(context, state, *, description=None, target_url=None):
    """Create the data for a status.

    The argument order is such that you can use functools.partial() to set the
    context to avoid repeatedly specifying it throughout a module.
    """
    status = {
        'context': context,
        'state': state.value,
    }
    if description is not None:
        status['description'] = description
    if target_url is not None:
        status['target_url'] = target_url

    return status


def skip(what, issue):
    """See if an issue has a "skip {what}" label."""
    return any(label_data['name'] == f'skip {what}' for label_data in issue['labels'])


def user_login(item):
    return item["user"]["login"]


async def issue_for_PR(gh, pull_request):
    """Get the issue data for a pull request."""
    return await gh.getitem(pull_request["issue_url"])


async def is_core_dev(gh, username):
    """Check if the user is a CPython core developer."""
    org_teams = "/orgs/python/teams"
    team_name = "python core"
    async for team in gh.getiter(org_teams):
        if team["name"].lower() == team_name:
            break
    else:
        raise ValueError(f"{team_name!r} not found at {org_teams!r}")
    # The 'teams' object only provides a URL to a deprecated endpoint,
    # so manually construct the URL to the non-deprecated team membership
    # endpoint.
    membership_url = f"/teams/{team['id']}/memberships/{username}"
    try:
        await gh.getitem(membership_url)
    except gidgethub.BadRequest as exc:
        if exc.status_code == 404:
            return False
        raise
    else:
        return True


def normalize_title(title, body):
    """Normalize the title if it spills over into the PR's body."""
    if not (title.endswith('…') and body.startswith('…')):
        return title
    else:
        # Being paranoid in case \r\n is used.
        return title[:-1] + body[1:].partition('\r\n')[0]
