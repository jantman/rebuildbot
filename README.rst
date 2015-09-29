rebuildbot
----------

Rebuildbot re-runs builds of your inactive projects.

Dependencies change. Libraries break. For personal projects with slow development cycles, it might be weeks or months before a broken build or bug report uncovers the problems. ReBuildBot is a Python script that runs via cron, triggers rebuilds of your projects on TravisCI, and optionally executes some commands in a fresh git clone of master (i.e. integration or acceptance tests). You'll receive an email with the details of the runs and links to local command output uploaded to S3.

Credentials
===========

Your GitHub user token must either be set as the ``GITHUB_TOKEN`` environment variable, or be stored in a ``token`` attribute of the ``[github]`` section of your ``~/.gitconfig`` like:

.. code-block::

   [github]
	user = jantman
	token = <your token here>
