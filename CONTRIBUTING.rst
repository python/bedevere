Contributing and Maintenance Guide
==================================

Deploying bedevere
------------------

Bedevere web service is deployed to Heroku, which is managed by The PSF.

Changes are supposed to be deployed to Heroku immediately after the PR gets merged,
however, due to recent `security incident`_,
the Heroku GitHub integration is broken.

Until this gets resolved, maintainers have to deploy bedevere to Heroku manually.

Who can deploy to Heroku
~~~~~~~~~~~~~~~~~~~~~~~~

People listed as Collaborator/Member on the ``bedevere`` Heroku app can deploy to Heroku.
Additionally, Heroku admins can also do it.

Collaborators/members:

- @Mariatta
- @ambv
- @brettcannon

How to deploy manually to Heroku
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Install Heroku CLI

   Details at: https://devcenter.heroku.com/articles/heroku-cli
  
#. Login to Heroku CLI on the command line and follow instructions

   ::
      
      heroku login
   
  
#. If you haven't already, get a clone of the bedevere repo

   ::
     
      git clone git@github.com:python/bedevere.git
  
   Or, using `GitHub CLI`_
   
   ::
   
      gh repo clone python/bedevere 

#. From the ``bedevere`` directory, add the ``bedevere`` Heroku app as remote branch

   ::
   
      heroku git:remote -a bedevere
  
 
#. From the ``bedevere`` directory, push to Heroku

   ::
  
      git push heroku main
  
  
Afther a successful push, the deployment will begin.

.. _security incident: https://status.heroku.com/incidents/2413
.. _GitHub CLI: https://cli.github.com/
