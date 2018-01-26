"""Leave follow up comments if best practises were not followed."""
from gidgethub import routing

router = routing.Router()

REPLACE_GH_NUMBER_MESSAGE = "@{committer}: Please replace `#` with `GH-` in the commit message next time. Thanks!"


@router.register("pull_request", action="closed")
async def remind_replace_gh_number(event, gh, *args, **kwargs):
    """Remind core dev to replace # with GH-."""
    if event.data["pull_request"]["merged"]:
        pr_number = event.data["pull_request"]["number"]
        commit_hash = event.data["pull_request"]["merge_commit_sha"]
        commit = await gh.getitem(
            event.data["repository"]["commits_url"],
            {"sha": commit_hash})
        commit_message = commit["commit"]["message"]
        committer = event.data["pull_request"]["merged_by"]["login"]
        if f"(#{pr_number})" in commit_message:
            await gh.post(event.data["pull_request"]["comments_url"],
                          data={'body': REPLACE_GH_NUMBER_MESSAGE.format(committer=committer)})
