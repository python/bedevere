import asyncio

import gidgethub.routing
from gidgethub.abc import GitHubAPI

router = gidgethub.routing.Router()

MERGE_CONFLICT_LABEL = "merge-conflict"


@router.register("push")
async def new_commit_pushed_to_main(event, gh: GitHubAPI, *arg, **kwargs) -> None:
    """If there is a new commit pushed to main, update all open PRs merge status."""
    if event.data["ref"] != "refs/heads/main":
        return

    prs_to_add_conflict_label = []
    prs_to_remove_conflict_label = []

    after = None
    while True:
        query = """
query ($after: String) {
  repository(name: "cpython", owner: "python") {
    id
    pullRequests(first: 10, after: $after, states: OPEN) {
      nodes {
        id
        mergeable
        number
        # title
        # url
        # state
        labels(first: 100) {
          edges {
            node {
              name
            }
          }
        }
      }
      pageInfo {
        endCursor
        hasNextPage
      }
    }
  }
  rateLimit {
    remaining
  }
}
"""
        data = await gh.graphql(query, after=after)
        for pr in data["repository"]["pullRequests"]["nodes"]:
            has_conflict_label = MERGE_CONFLICT_LABEL in (
                edge["node"]["name"] for edge in pr["labels"]["edges"]
            )
            if pr["mergeable"] == "CONFLICTING":
                if not has_conflict_label:
                    prs_to_add_conflict_label.append(pr)
            else:
                if has_conflict_label:
                    prs_to_remove_conflict_label.append(pr)

        if data["rateLimit"]["remaining"] < 1000:
            break
        after = data["repository"]["pullRequests"]["pageInfo"]["endCursor"]
        if not data["repository"]["pullRequests"]["pageInfo"]["hasNextPage"]:
            break

    futs = [
        gh.post(
            f"https://api.github.com/repos/python/cpython/issues/{pr['number']}/labels",
            data={"labels": [MERGE_CONFLICT_LABEL]},
        )
        for pr in prs_to_add_conflict_label
    ] + [
        gh.delete(
            f"https://api.github.com/repos/python/cpython/issues/{pr['number']}/labels/{MERGE_CONFLICT_LABEL}",
        )
        for pr in prs_to_remove_conflict_label
    ]
    for fut in asyncio.as_completed(futs):
        await fut
