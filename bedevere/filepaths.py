"""Checks related to filepaths on a pull request."""
import gidgethub.routing

from . import news
from . import prtype
from . import util


router = gidgethub.routing.Router()


@router.register('pull_request', action='opened')
@router.register('pull_request', action='synchronize')
@router.register('pull_request', action='reopened')
async def check_file_paths(event, gh, *args, **kwargs):
    pull_request = event.data['pull_request']
    files = await util.files_for_PR(gh, pull_request)
    filenames = [file['file_name'] for file in files]
    if event.data['action'] == 'opened':
        labels = await prtype.classify_by_filepaths(gh, pull_request, filenames)
        if prtype.Labels.skip_news not in labels:
            await news.check_news(gh, pull_request, files)
    else:
        await news.check_news(gh, pull_request, files)
