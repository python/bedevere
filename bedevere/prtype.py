"""Label a pull request based on its type."""
import enum
import pathlib

from . import util

LABEL_PREFIX = "type"


@enum.unique
class Category(enum.Enum):
    """Category of Pull Request."""
    bugfix = f"{LABEL_PREFIX}-bugfix"
    documentation = f"{LABEL_PREFIX}-documentation"
    enhancement = f"{LABEL_PREFIX}-enhancement"
    performance = f"{LABEL_PREFIX}-performance"
    security = f"{LABEL_PREFIX}-security"
    tests = f"{LABEL_PREFIX}-tests"


async def add_category(gh, issue, category):
    """Apply this type label if there aren't any type labels on the PR."""
    if any(label.startswith("type") for label in util.labels(issue)):
        return
    await gh.post(issue["labels_url"], data=[category.value])


async def classify_by_filepaths(gh, pull_request, filenames):
    """Categorize the pull request based on the files it has modified.

    If any paths are found which do not fall within a specific classification,
    then no new label is applied.

    The routing is handled by the filepaths module.
    """
    issue = await util.issue_for_PR(gh, pull_request)
    docs = tests = False
    for filename in filenames:
        if util.is_news_dir(filename):
            continue
        filepath = pathlib.PurePath(filename)
        if filepath.suffix == '.rst':
            docs = True
        elif filepath.name.startswith('test_'):
            tests = True
        else:
            return
    if tests:
        await add_category(gh, issue, Category.tests)
    elif docs:
        await add_category(gh, issue, Category.documentation)
    return
