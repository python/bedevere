"""Label a pull request based on what its waiting on."""

# The following is the state machine for the flow of a PR
# (written as a DOT file; you can use Graphviz or
# http://www.webgraphviz.com/ to view the graph):
"""
digraph "PR stages" {
  "New PR" [color=orange]
  "Awaiting review" [shape=box, color=blue]
  "Awaiting core review" [shape=box, color=green]
  "Awaiting changes" [shape=box, color=blue]
  "Awaiting change review" [shape=box, color=green]
  "Awaiting merge" [shape=box, color=green]

  "New PR" -> "Awaiting review" [label="New PR", color=orange]
  "Awaiting review" -> "Awaiting core review" [label="New review", color=blue]
  "Awaiting core review" -> "Awaiting core review" [label="New review", color=blue]
  "Awaiting core review" -> "Awaiting changes" [label="New review requests changes", color=green]
  "Awaiting changes" -> "Awaiting change review" [label="(comment)", color=orange]
  "Awaiting change review" -> "Awaiting changes" [label="New review requests changes", color=green]
  "Awaiting change review" -> "Awaiting merge" [label="New review approves", color=green]

  "Awaiting review" -> "Awaiting merge" [label="New review approves", color=green]
  "Awaiting review" -> "Awaiting changes" [label="New review requests changes", color=green]
  "Awaiting core review" -> "Awaiting merge" [label="New review approves", color=green]

  "New PR" -> "Awaiting merge" [label="New PR", color=green]
}
"""

# XXX TODO
# "Awaiting changes" -> "Awaiting change review" [label="PR creator addresses changes", color=blue]

import datetime
import enum
import operator

import gidgethub.routing


router = gidgethub.routing.Router()

LABEL_PREFIX = "awaiting"

@enum.unique
class Blocker(enum.Enum):
    """What is blocking a pull request from being committed."""
    review = f"{LABEL_PREFIX} review"
    core_review = f"{LABEL_PREFIX} core review"
    changes = f"{LABEL_PREFIX} changes"
    merge = f"{LABEL_PREFIX} merge"


async def stage(gh, pull_request, blocked_on):
    """Remove any "awaiting" labels and apply the specified one."""
    issue = await gh.getitem(pull_request["issue_url"])
    label_name = blocked_on.value
    if any(label_name == label["name"] for label in issue["labels"]):
        return
    # There's no reason to expect there to be multiple "awaiting" labels on a
    # single pull request, but just in case there are we might as well clean
    # up the situation when we come across it.
    for label in issue["labels"]:
        stale_name = label["name"]
        if stale_name.startswith(LABEL_PREFIX + " "):
            await gh.delete(issue["labels_url"], {"name": stale_name})
    await gh.post(issue["labels_url"], data=[label_name])


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


@router.register("pull_request", action="opened")
async def opened_pr(event, gh, *arg, **kwargs):
    """Decide if a new pull request requires a review.

    If a pull request comes in from a core developer, then mark it
    as "awaiting merge". Otherwise the pull request is
    "awaiting review".
    """
    pull_request = event.data["pull_request"]
    username = pull_request["user"]["login"]
    if await is_core_dev(gh, username):
        await stage(gh, pull_request, Blocker.merge)
    else:
        await stage(gh, pull_request, Blocker.review)


async def has_core_dev_approval(gh, reviews):
    """Figure out what the last core developer review was.

    A true value is returned if the last review from a core developer
    was approval. A false value is returned if the last core developer
    review requested changes. And if no reviews from a core developer
    were made, None is returned.
    """
    # Get the latest reviews for everyone upfront to minimize API calls to find
    # out who is a core developer.
    latest_reviews = {}
    for review in reviews:
        positive_review = review["state"].lower()
        if positive_review == "approved":
            positive_review = True
        elif positive_review == "changes_requested":
            positive_review = False
        else:
            continue
        username = review["user"]["login"]
        when = datetime.strptime(review["submitted_at"], "%Y-%m-%dT%H:%M:%SZ")
        if username in latest_reviews:
            _, other_when = latest_reviews[username]
            if other_when > when:
                continue
        latest_reviews[username] = result, when
    flattened_reviews = ((username, when, review)
                         for username, (when, review) in latest_reviews.items())
    sorted_reviews = sorted(flattened_reviews, key=operator.itemgetter(1),
                             reversed=True)
    for username, _, positive_review in sorted_reviews:
        if await is_core_dev(gh, username):
            return positive_review
    else:
        return None


async def reviewed_by_core_dev(gh, pull_request):
    """Check if a pull request has received a review by a core developer."""
    # GitHub doesn't provide the URL to the reviews for a PR.
    async for review in gh.getiter(pull_request["url"] + "/reviews"):
        if await is_core_dev(gh, review["user"]["login"]):
            return True
    else:
        return False


@router.register("pull_request_review", action="submitted")
async def new_review(event, gh, *args, **kwargs):
    """Update the stage based on the latest review."""
    pull_request = event.data["pull_request"]
    review = event.data["review"]
    reviewer = review["user"]["login"]
    if not await is_core_dev(gh, reviewer):
        if await reviewed_by_core_dev(gh, pull_request):
            # No need to update the stage.
            return
        else:
            await stage(gh, pull_request, Blocker.core_review)
    else:
        state = review["state"].lower()
        if state == "approved":
            await stage(gh, pull_request, Blocker.merge)
        elif state == "changes_requested":
            await stage(gh, pull_request, Blocker.changes)
