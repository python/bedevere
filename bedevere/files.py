"""Checks related to files on a pull request."""
import gidgethub.routing

from .news import check_news
from .prtype import classify_by_files
from . import util


router = gidgethub.routing.Router()


@router.register('pull_request', action='opened')
@router.register('pull_request', action='synchronize')
async def retrieve_files(event, gh, *args, **kwargs):
    pull_request = event.data['pull_request']
    filenames = await util.filenames_for_PR(gh, pull_request)
    await check_news(gh, pull_request, filenames)
    if event.data['action'] == 'opened':
        await classify_by_files(gh, pull_request, filenames)

