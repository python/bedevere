Contributing and Maintenance Guide
==================================

Bedevere web service is deployed to Heroku, which is managed by The PSF.

Deployment
----------

There are two ways to have bedevere deployed: automatic deployment, and
manual deployment.

Automatic Deployment (currently broken)
'''''''''''''''''''''''''''''''''''''''

When the automatic deployment is enabled (on Heroku side), any merged PR
will automatically be deployed to Heroku. This process takes less than 5 minutes.

If after 10 minutes you did not see the changes reflected, please ping one
of the collaborators listed below.

To enable Automatic deployment:

- On the Heroku dashboard for bedevere, choose the "Deploy" tab.
- Scroll down to the "Automatic deploys" section
- Enter the name of the branch to be deployed (in this case: ``main``)
- Check the "Wait for CI to pass before deploy" button
- Press the "Enable automatic deploys" button.

Once done, merging a PR against the ``main`` branch will trigger a new
deployment using a webhook that is already set up in the repo settings.


.. note::

   Due to recent `security incident`_, the Heroku GitHub integration is broken.
   Automatic deployment does not currently work. Until this gets resolved,
   maintainers have to deploy bedevere to Heroku manually.


Manual Deployment
'''''''''''''''''

The app can be deployed manually to Heroku by collaborators and members of the ``bedevere`` app on Heroku.
Heroku admins can do it too.

#. Install Heroku CLI

   Details at: https://devcenter.heroku.com/articles/heroku-cli
  
#. Login to Heroku CLI on the command line and follow instructions::
      
      heroku login
   
  
#. If you haven't already, get a clone of the bedevere repo::
     
      git clone git@github.com:python/bedevere.git
  
   Or, using `GitHub CLI`_::
   
      gh repo clone python/bedevere 

#. From the ``bedevere`` directory, add the ``bedevere`` Heroku app as remote branch::
   
      heroku git:remote -a bedevere
  
 
#. From the ``bedevere`` directory, push to Heroku::
  
      git push heroku main
  
  
After a successful push, the deployment will begin.

Heroku app collaborators and members
''''''''''''''''''''''''''''''''''''

- @Mariatta
- @ambv
- @brettcannon

.. _security incident: https://status.heroku.com/incidents/2413
.. _GitHub CLI: https://cli.github.com/
