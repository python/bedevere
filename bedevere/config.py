"""Which bedevere features run on each repository."""

import sys

ALL_FEATURES = frozenset(
    {"backport", "close_pr", "filepaths", "gh_issue", "news", "policy", "stage"}
)
DEFAULT_FEATURES = frozenset({"policy"})
DEFAULT_OWNER = "python"

# Keys are lowercase "owner/name". Unlisted repos owned by DEFAULT_OWNER get
# DEFAULT_FEATURES, and unlisted repos owned by anyone else get no features.
REPO_FEATURES = {
    "python/cpython": ALL_FEATURES,
}

_logged_unknown_repos = set()


def features_for(repo_full_name):
    """Return the features enabled for a repository.

    Repositories without an entry are logged the first time they are seen.
    """
    repo = repo_full_name.lower()
    try:
        return REPO_FEATURES[repo]
    except KeyError:
        owner = repo.partition("/")[0]
        features = DEFAULT_FEATURES if owner == DEFAULT_OWNER else frozenset()
        if repo not in _logged_unknown_repos:
            _logged_unknown_repos.add(repo)
            print(
                f"{repo_full_name} has no feature config, running only: "
                f"{', '.join(sorted(features)) or 'nothing'}",
                file=sys.stderr,
            )
        return features
