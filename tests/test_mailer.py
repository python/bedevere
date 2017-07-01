import textwrap

import pytest

from gidgethub import sansio
from gidgethub import abc as gh_abc

from bedevere import mailer


class FakeGH:

    def __init__(self, *, getitem=None):
        self._getitem_return = getitem

    async def getitem(self, url):
        return self._getitem_return

    async def post(self, url, data):
        self.url = url
        self.data = data


@pytest.mark.asyncio
async def test_send_email():
    data = {
        "ref": "refs/heads/3.5",
        "commits": [
            {
                "id": "2d420b342509e6c2b597af82ea74c4cbb13e2abd",
                "message": "Update .gitignore\n(cherry picked from commit 9d9ed0e5cceef45fd63dc1f7b3fe6e695da16e83)",
                "timestamp": "2017-02-08T15:37:50+03:00",
                "url": "https://github.com/fayton/cpython/commit/2d420b342509e6c2b597af82ea74c4cbb13e2abd",
                "author": {"name": "cbiggles", "email": "berker.peksag+cbiggles@gmail.com", "username": "cbiggles"},
                "committer": {"name": "Berker Peksag", "email": "berker.peksag@gmail.com", "username": "berkerpeksag"},
                "added": [],
                "removed": [],
                "modified": [".gitignore"]
            }
        ],
    }
    diff = """
    diff --git a/.gitignore b/.gitignore
    index c2b4fc703f7..e0d0685fa7d 100644
    --- a/.gitignore
    +++ b/.gitignore
    @@ -93,3 +93,4 @@ htmlcov/
     Tools/msi/obj
     Tools/ssl/amd64
     Tools/ssl/win32
    +foo
    """
    event = sansio.Event(data, event="push", delivery_id="12345")
    gh = FakeGH(getitem=textwrap.dedent(diff))
    result = await mailer.send_email(event, gh)
    assert result == "Ok"
