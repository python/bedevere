"""Label a pull request based on what its waiting on."""

# The following is the state machine for the flow of a PR
# (written as a DOT file; you can use Graphviz or
# http://www.webgraphviz.com/ to view the graph):
"""
digraph "PR stages" {
  /* Colours represent who can make a state change or who is currently
     blocking the PR from moving forward.

     Blue: Anyone
     Orange: PR creator
     Green: Core developer
     Purple: Triager Actions
  */

  "New PR" [color=orange]
  "Awaiting review" [shape=box, color=blue]
  "Awaiting core review" [shape=box, color=green]
  "Awaiting changes" [shape=box, color=orange]
  "Awaiting change review" [shape=box, color=green]
  "Awaiting merge" [shape=box, color=green]

  "New PR" -> "Awaiting review" [label="New PR by a contributor", color=orange]
  "Awaiting review" -> "Awaiting core review" [label="New review by another contributor", color=blue]
  "Awaiting core review" -> "Awaiting core review" [label="New review by another contributor", color=blue]
  "Awaiting core review" -> "Awaiting changes" [label="New core review requests changes", color=green]
  "Awaiting changes" -> "Awaiting change review" [label="Changes are done by contributor\nBedevere requests review from core-dev", color=orange]
  "Awaiting change review" -> "Awaiting changes" [label="New core review requests changes", color=green]
  "Awaiting change review" -> "Awaiting merge" [label="New core review approves", color=green]

  "Awaiting review" -> "Awaiting merge" [label="New core review approves", color=green]
  "Awaiting review" -> "Awaiting changes" [label="New core review requests changes", color=green]
  "Awaiting core review" -> "Awaiting merge" [label="New core review approves", color=green]

  "New PR" -> "Awaiting core review" [label="New PR by core devs", color=green]
}
"""

import datetime
import enum
import operator
import random

import gidgethub.routing

from . import util


router = gidgethub.routing.Router()

BORING_TRIGGER_PHRASE = "I have made the requested changes; please review again"
FUN_TRIGGER_PHRASE = "I didn't expect the Spanish Inquisition"
TRIGGERS = frozenset([BORING_TRIGGER_PHRASE, FUN_TRIGGER_PHRASE])

TAG_NAME = "changes-requested"

CHANGES_REQUESTED_MESSAGE = f"""\
<!-- {TAG_NAME} -->
A Python core developer has requested some changes be made to your \
pull request before we can consider merging it. If you could please \
address their requests along with any other requests in other \
reviews from core developers that would be appreciated.

Once you have made the requested changes, please leave a comment \
on this pull request containing the phrase `{BORING_TRIGGER_PHRASE}`. \
I will then notify any core developers who have left a review that \
you're ready for them to take another look at this pull request.
<!-- /{TAG_NAME} -->

{{easter_egg}}
"""

CORE_DEV_CHANGES_REQUESTED_MESSAGE = f"""\
<!-- {TAG_NAME} -->
When you're done making the requested changes, leave the comment: `{BORING_TRIGGER_PHRASE}`.
<!-- /{TAG_NAME} -->

{{easter_egg}}
"""

EASTER_EGG_1 = """\
And if you don't make the requested changes, \
you will be poked with soft cushions!
"""

EASTER_EGG_2 = """\
And if you don't make the requested changes, \
you will be put in the comfy chair!
"""

ACK = """\
{greeting}

{core_devs}: please review the changes made to this pull request.
"""
BORING_THANKS = "Thanks for making the requested changes!"
FUN_THANKS = "Nobody expects the Spanish Inquisition!"


LABEL_PREFIX = "awaiting"

@enum.unique
class Blocker(enum.Enum):
    """What is blocking a pull request from being committed."""
    review = f"{LABEL_PREFIX} review"
    core_review = f"{LABEL_PREFIX} core review"
    changes = f"{LABEL_PREFIX} changes"
    change_review = f"{LABEL_PREFIX} change review"
    merge = f"{LABEL_PREFIX} merge"


async def _remove_stage_labels(gh, issue):
    """Remove all "awaiting" labels."""
    # There's no reason to expect there to be multiple "awaiting" labels on a
    # single pull request, but just in case there are we might as well clean
    # up the situation when we come across it.
    for label in issue["labels"]:
        stale_name = label["name"]
        if stale_name.startswith(LABEL_PREFIX + " "):
            await gh.delete(issue["labels_url"], {"name": stale_name})


async def stage(gh, issue, blocked_on):
    """Remove any "awaiting" labels and apply the specified one."""
    label_name = blocked_on.value
    if any(label_name == label["name"] for label in issue["labels"]):
        return
    await _remove_stage_labels(gh, issue)
    await gh.post(issue["labels_url"], data=[label_name])


@router.register("pull_request", action="opened")
async def opened_pr(event, gh, *arg, **kwargs):
    """Decide if a new pull request requires a review.

    If a pull request comes in from a core developer, then mark it
    as "awaiting core review". Otherwise the pull request is
    "awaiting review".
    """
    pull_request = event.data["pull_request"]
    issue = await util.issue_for_PR(gh, pull_request)
    username = util.user_login(pull_request)
    if await util.is_core_dev(gh, username):
        await stage(gh, issue, Blocker.core_review)
    else:
        await stage(gh, issue, Blocker.review)


async def core_dev_reviewers(gh, pull_request_url):
    """Find the reviewers who are core developers."""
    # Unfortunately the reviews URL is not contained in a pull request's data.
    async for review in gh.getiter(pull_request_url + "/reviews"):
        reviewer = util.user_login(review)
        # Ignoring "comment" reviews.
        actual_review = review["state"].lower() in {"approved", "changes_requested"}
        if actual_review and await util.is_core_dev(gh, reviewer):
            yield reviewer


@router.register("pull_request_review", action="submitted")
async def new_review(event, gh, *args, **kwargs):
    """Update the stage based on the latest review."""
    pull_request = event.data["pull_request"]
    review = event.data["review"]
    reviewer = util.user_login(review)
    state = review["state"].lower()
    if state == "commented":
        # Don't care about comment reviews.
        return
    elif not await util.is_core_dev(gh, reviewer):
        # Poor-man's asynchronous any().
        async for _ in core_dev_reviewers(gh, pull_request["url"]):
            # No need to update the stage as a core developer has already
            # reviewed this PR.
            return
        else:
            # Waiting for a core developer to leave a review.
            await stage(gh, await util.issue_for_PR(gh, pull_request),
                        Blocker.core_review)
    else:
        if state == "approved":
            await stage(gh, await util.issue_for_PR(gh, pull_request), Blocker.merge)
        elif state == "changes_requested":
            issue = await util.issue_for_PR(gh, pull_request)
            if Blocker.changes.value in util.labels(issue):
                # Contributor already knows what to do for this round of reviews.
                return
            easter_egg = ""
            if random.random() < 0.1:  # pragma: no cover
                easter_egg = random.choice([EASTER_EGG_1, EASTER_EGG_2])
            comment = CHANGES_REQUESTED_MESSAGE.format(easter_egg=easter_egg)
            pr_author = util.user_login(pull_request)
            if await util.is_core_dev(gh, pr_author):
                comment = CORE_DEV_CHANGES_REQUESTED_MESSAGE.format(
                    easter_egg=easter_egg)
            await stage(gh, issue, Blocker.changes)
            await gh.post(pull_request["comments_url"], data={"body": comment})
        else: # pragma: no cover
            raise ValueError(f"unexpected review state: {state!r}")


@router.register("issue_comment", action="created")
async def new_comment(event, gh, *args, **kwargs):
    issue = event.data["issue"]
    comment = event.data["comment"]
    comment_body = comment["body"].lower()
    if util.user_login(issue) != util.user_login(comment):
        # Only care about the PR creator leaving a comment.
        return
    elif not any(trigger.lower() in comment_body for trigger in TRIGGERS):
        # PR creator didn't request another review.
        return
    else:
        await stage(gh, issue, Blocker.change_review)
        pr_url = issue["pull_request"]["url"]
        # Using a set comprehension to remove duplicates.
        core_devs = ", ".join({"@" + core_dev
                             async for core_dev in core_dev_reviewers(gh, pr_url)})
        if FUN_TRIGGER_PHRASE.lower() in comment_body:
            thanks = FUN_THANKS
        else:
            thanks = BORING_THANKS
        comment = ACK.format(greeting=thanks, core_devs=core_devs)
        await gh.post(issue["comments_url"], data={"body": comment})
        # Re-request reviews from core developers based on the new state of the PR.
        reviewers_url = f'{pr_url}/requested_reviewers'
        reviewers = [core_dev async for core_dev in core_dev_reviewers(gh, pr_url)]
        await gh.post(reviewers_url, data={"reviewers": reviewers})


@router.register("pull_request", action="closed")
async def closed_pr(event, gh, *args, **kwargs):
    """Remove all `awaiting ... ` labels when a PR is merged."""
    if event.data["pull_request"]["merged"]:
        issue = await util.issue_for_PR(gh, event.data["pull_request"])
        await _remove_stage_labels(gh, issue)
