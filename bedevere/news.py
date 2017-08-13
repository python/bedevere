"""Check for a news entry."""
import functools
import os.path
import re

import gidgethub.routing

from . import util


router = gidgethub.routing.Router()


create_status = functools.partial(util.create_status, 'bedevere/news')

DEVGUIDE_URL = 'https://cpython-devguide.readthedocs.io/committing.html#what-s-new-and-news-entries'

FILENAME_RE = re.compile(r"""Misc/NEWS.d/.+/      # Directory
                             \d{4}-\d{2}-\d{2}\.  # Date as YYY-MM-DD
                             bpo-\d+(?:,\d+)*\.   # Issue number(s)
                             .+\.                 # Nonce
                             rst                  # File extension""",
                         re.VERBOSE)


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
    async for file_data in gh.getiter(files_url):
        filename = file_data['filename']
        if FILENAME_RE.match(filename):
            status = create_status(util.StatusState.SUCCESS,
                                   description='News entry found in Misc/NEWS.d')
            break
    else:
        issue = await util.issue_for_PR(gh, pull_request)
        if util.skip("news", issue):
            description = "Trivial pull requests don't need a news entry"
            status = create_status(util.StatusState.SUCCESS,
                                   description=description)
        else:
            description = 'No news entry found in Misc/NEWS.d'
            status = create_status(util.StatusState.FAILURE,
                                   description=description,
                                   target_url=DEVGUIDE_URL)

    await gh.post(pull_request['statuses_url'], data=status)
