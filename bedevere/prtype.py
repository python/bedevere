"""Label a pull request based on its type."""
import enum
import pathlib

from . import util

TYPE_LABEL_PREFIX = "type"


@enum.unique
class Labels(enum.Enum):
    """Labels that can be applied to a Pull Request."""

    type_bug = f"{TYPE_LABEL_PREFIX}-bug"
    docs = "docs"
    type_feature = f"{TYPE_LABEL_PREFIX}-feature"
    performance = "performance"
    type_security = f"{TYPE_LABEL_PREFIX}-security"
    tests = "tests"
    skip_news = "skip news"


async def add_labels(gh, issue, labels):
    """Add the specified labels to the PR."""
    current_labels = util.labels(issue)
    label_names = [c.value for c in labels if c.value not in current_labels]
    if label_names:
        await gh.post(issue["labels_url"], data=label_names)


async def classify_by_filepaths(gh, pull_request, filenames):
    """Categorize the pull request based on the files it has modified.

    If any paths are found which do not fall within a specific classification,
    then no new label is applied.

    The routing is handled by the filepaths module.
    """
    pr_labels = []
    issue = await util.issue_for_PR(gh, pull_request)
    news = docs = tests = False
    for filename in filenames:
        if util.is_news_dir(filename):
            news = True
        filepath = pathlib.PurePath(filename)
        if filepath.suffix == '.rst':
            docs = True
        elif filepath.name.startswith('test_'):
            tests = True
        else:
            return pr_labels
    if tests:
        pr_labels = [Labels.tests]
    elif docs:
        if news:
            pr_labels = [Labels.docs]
        else:
            pr_labels = [Labels.docs, Labels.skip_news]
    await add_labels(gh, issue, pr_labels)
    return pr_labels
