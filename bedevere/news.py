"""Check for a news entry."""
import functools
import pathlib
import re

import gidgethub.routing

from . import util


router = gidgethub.routing.Router()


create_status = functools.partial(util.create_status, 'bedevere/news')

DEVGUIDE_URL = 'https://devguide.python.org/committing/#what-s-new-and-news-entries'

NEWS_NEXT_DIR = "Misc/NEWS.d/next/"
FILENAME_RE = re.compile(r"""# YYYY-mm-dd or YYYY-mm-dd-HH-MM-SS
                             \d{4}-\d{2}-\d{2}(?:-\d{2}-\d{2}-\d{2})?\.
                             bpo-\d+(?:,\d+)*\.       # Issue number(s)
                             [A-Za-z0-9_=-]+\.        # Nonce (URL-safe base64)
                             rst                      # File extension""",
                         re.VERBOSE)

SKIP_NEWS_LABEL = util.skip_label("news")
SKIP_LABEL_STATUS = create_status(util.StatusState.SUCCESS,
                                  description='"skip news" label found')


@router.register('pull_request', action='opened')
@router.register('pull_request', action='synchronize')
async def check_news(event, gh, *args, **kwargs):
    pr_number = event.data['number']
    pull_request = event.data['pull_request']
    # For some unknown reason there isn't any files URL in a pull request
    # payload.
    files_url = f'/repos/python/cpython/pulls/{pr_number}/files'
    # Could have collected all the filenames in an async set comprehension,
    # but doing it this way potentially minimizes the number of API calls.
    in_next_dir = file_found = False
    async for file_data in gh.getiter(files_url):
        filename = file_data['filename']
        if not filename.startswith(NEWS_NEXT_DIR):
            continue
        in_next_dir = True
        file_path = pathlib.PurePath(filename)
        if len(file_path.parts) != 5:  # Misc, NEWS.d, next, <subsection>, <entry>
            continue
        file_found = True
        if FILENAME_RE.match(file_path.name):
            status = create_status(util.StatusState.SUCCESS,
                                   description='News entry found in Misc/NEWS.d')
            break
    else:
        issue = await util.issue_for_PR(gh, pull_request)
        if util.skip("news", issue):
            status = SKIP_LABEL_STATUS
        else:
            if not in_next_dir:
                description = f'No news entry in {NEWS_NEXT_DIR} or "skip news" label found'
            elif not file_found:
                description = f"News entry not in a subdirectory of {NEWS_NEXT_DIR}"
            else:
                description = "News entry file name incorrectly formatted"
            status = create_status(util.StatusState.FAILURE,
                                   description=description,
                                   target_url=DEVGUIDE_URL)

    await gh.post(pull_request['statuses_url'], data=status)


@router.register('pull_request', action="labeled")
async def label_added(event, gh, *args, **kwargs):
    if util.label_name(event.data) == SKIP_NEWS_LABEL:
        await util.post_status(gh, event, SKIP_LABEL_STATUS)


@router.register("pull_request", action="unlabeled")
async def label_removed(event, gh, *args, **kwargs):
    if util.no_labels(event.data):
        return
    elif util.label_name(event.data) == SKIP_NEWS_LABEL:
        await check_news(event, gh)
