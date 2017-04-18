# bedevere
[![Build Status](https://travis-ci.org/python/bedevere.svg?branch=master)](https://travis-ci.org/python/bedevere)
[![codecov](https://codecov.io/gh/python/bedevere/branch/master/graph/badge.svg)](https://codecov.io/gh/python/bedevere)

This bot is meant to help identify issues with a CPython pull request.

## What the bot identifies
### bugs.python.org issue numbers in the title
If no b.p.o issue number is found the the status fails, then the
"Details" link points to the relevant
[section of the devguide](https://cpython-devguide.readthedocs.io/pullrequest.html?highlight=bpo-#submitting).
If an issue number is found then the "Details" link points to the
issue itself, making it easier to navigate from PR to issue.

### Reason for reverting a commit
If a PR starts with the word "Revert", then the bot will check if the PR body
contains the word "Reason:".  If the reason is not found, then the "Details"
link points to the relevant
[section of the devguide](https://cpython-devguide.readthedocs.io/committing.html#reverting-a-commit).

## *Aside*: where does the name come from?
Since this bot is about identifying pull requests that need changes,
it seemed fitting to name it after Sir Bedevere who knew
[how to identify a witch](https://youtu.be/k3jt5ibfRzw).
