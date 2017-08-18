import enum
import sys

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


async def post_status(gh, event, status):
    """Post a status in reaction to an event."""
    await gh.post(event.data["pull_request"]["statuses_url"], data=status)


def skip_label(what):
    """Generate a "skip" label name."""
    return f"skip {what}"


def labels(issue):
    return {label_data["name"] for label_data in issue["labels"]}


def skip(what, issue):
    """See if an issue has a "skip {what}" label."""
    return skip_label(what) in labels(issue)


def label_name(event_data):
    """Get the label name from a label-related webhook event."""
    return event_data["label"]["name"]


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


def no_labels(event_data):
    if "label" not in event_data:
        print("no 'label' key in payload; "
              "'unlabeled' event triggered by label deletion?",
              file=sys.stderr)
        return True
    else:
        return False
