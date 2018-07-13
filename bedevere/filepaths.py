"""Checks related to filepaths on a pull request."""
import gidgethub.routing

from . import news
from . import prtype
from . import util


router = gidgethub.routing.Router()


@router.register('pull_request', action='opened')
@router.register('pull_request', action='synchronize')
async def check_file_paths(event, gh, *args, **kwargs):
    pull_request = event.data['pull_request']
    filenames = await util.filenames_for_PR(gh, pull_request)
    await news.check_news(gh, pull_request, filenames)
    if event.data['action'] == 'opened':
        await prtype.classify_by_filepaths(gh, pull_request, filenames)

