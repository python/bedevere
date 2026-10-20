Contributing and Maintenance Guide
==================================

Bedevere web service is deployed to `cabotage`_, the container platform
managed by The PSF. The application lives at
https://cabotage.us-east-2.psfhosted.computer/projects/python/bedevere/applications/bedevere
and is only visible to members of the ``python`` organization on cabotage.

How bedevere runs on cabotage
-----------------------------

- cabotage builds the container image from the ``Dockerfile`` in this repo.
- The processes to run come from the ``Procfile`` (the ``CMD`` in the
  ``Dockerfile`` is ignored). bedevere has a single ``web`` process.
- The ``web`` process must listen on the unix socket
  ``/var/run/cabotage/cabotage.sock``; a TLS sidecar forwards public traffic
  to it. ``bedevere/__main__.py`` binds to that socket when the
  ``/var/run/cabotage`` directory exists, and falls back to the ``PORT``
  environment variable otherwise, so the same code runs locally and on
  cabotage.
- The container runs as the unprivileged ``nobody`` user with a read-only
  home directory. Do not write to disk at runtime.
- ``GET /health`` returns ``200 OK``. It is the path cabotage's health probes
  request (set under *Settings*, *Health path*).

Configuration
-------------

Configuration variables are set in the cabotage UI under
the *Config* menu, *Variables*. Secrets are stored encrypted and cannot be read back
once set. bedevere needs:

- ``GH_APP_ID``: the GitHub App ID.
- ``GH_PRIVATE_KEY``: the GitHub App private key (secret).
- ``GH_SECRET``: the webhook secret configured on the GitHub App (secret).
- ``SENTRY_DSN``: where errors are reported.

A change to a variable only takes effect once a new release is created and
deployed.

Deployment
----------

There are two ways to have bedevere deployed: automatic deployment, and
manual deployment.

Automatic Deployment
''''''''''''''''''''

The cabotage application is connected to the ``python/bedevere`` repository
through the cabotage GitHub App and auto-deploys the ``main`` branch. Any PR
merged into ``main`` is built, released and deployed automatically. This
process takes a few minutes.

If after 10 minutes you did not see the changes reflected, check the
*Deploys* tab of the application for a failed build or deployment, or ping
one of the collaborators listed below.

Manual Deployment
'''''''''''''''''

The app can be deployed manually from the cabotage UI by members of the
``python`` organization on cabotage. A deployment is three steps, each with
its own button on the application page:

#. **Build Image**: builds a container image from the configured repository
   and branch.

#. **Create a release**: bundles the image with the current configuration
   variables into a release. This is also the step to run after changing a
   configuration variable.

#. **Deploy**: pushes the release live. cabotage waits for ``/health`` to
   answer before it considers the deployment complete.

After the first deployment of a new or renamed process, its replica count is
zero. Scale the ``web`` process to 1 from the application page.

Logs for the running process, and a shell inside the container, are both
available from the application page.

Maintainers
'''''''''''

- @Mariatta
- @ambv
- @brettcannon

Access to the cabotage application is granted by the PSF infrastructure team.

.. _cabotage: https://github.com/cabotage/cabotage-app
