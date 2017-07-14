"""Label a pull request based on what its waiting on."""

# The following is the state machine for the flow of a PR
# (written as a DOT file; you can use Graphviz or
# http://www.webgraphviz.com/ to view the graph):
"""
digraph "PR stages" {
  "New PR" [color=blue]
  "Awaiting review" [shape=box, color=orange]
  "Awaiting core review" [shape=box, color=green]
  "Awaiting changes" [shape=box, color=blue]
  "Awaiting change review" [shape=box, color=green]
  "Awaiting merge" [shape=box, color=green]

  "New PR" -> "Awaiting review" [label="PR by non-core dev", color=blue]
  "Awaiting review" -> "Awaiting core review" [label="Non-core review", color=orange]
  "Awaiting core review" -> "Awaiting changes" [label="Core dev requests changes", color=green]
  "Awaiting changes" -> "Awaiting change review" [label="PR creator addresses changes", color=blue]
  "Awaiting change review" -> "Awaiting changes" [label="Core dev requests changes", color=green]
  "Awaiting change review" -> "Awaiting merge" [label="Core dev approves PR", color=green]


  "Awaiting review" -> "Awaiting merge" [label="Core dev approves PR", color=green]
  "Awaiting review" -> "Awaiting changes" [label="Core dev requests changes", color=green]
  "Awaiting core review" -> "Awaiting merge" [label="Core dev approves PR", color=green]

  "New PR" -> "Awaiting merge" [label="PR by core dev", color=green]
}
"""

import enum

import gidgethub.routing


router = gidgethub.routing.Router()

LABEL_PREFIX = "awaiting"

@enum.unique
class Blocker(enum.Enum):
    """What is blocking a pull request from being committed."""
    review = f"{LABEL_PREFIX} review"
    merge = f"{LABEL_PREFIX} merge"


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


async def stage(gh, issue, blocked_on):
    """Remove any "awaiting" labels and apply the specified one."""
    label_name = blocked_on.value
    if any(label_name == label["name"] for label in issue["labels"]):
        return
    for label in issue["labels"]:
        stale_name = label["name"]
        if name.startswith(LABEL_PREFIX + " "):
            await gh.delete(issue["labels_url"], {"name": stale_name})
    await gh.post(issue["labels_url"], data=[label_name])


@router.register("pull_request", action="opened")
async def opened_pr(gh, event, *arg, **kwargs):
    """Decide if a new pull request requires a review.

    If a pull request comes in from a core developer, then mark it
    as "awaiting merge". Otherwise the pull request is
    "awaiting review".
    """
    username = event["pull_request"]["user"]["login"]
    issue = await gh.getitem(event["pull_request"]["issue_url"])
    if is_core_dev(username):
        await stage(gh, issue, Blocker.merge)
    else:
        await stage(gh, issue, Blocker.review)
