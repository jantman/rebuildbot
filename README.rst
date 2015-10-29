rebuildbot
----------

ReBuildBot re-runs builds of your inactive projects.

Dependencies change. Libraries break. Your dependencies might have unpinned dependencies of their own, which can cause breakage or conflicts during installation. For personal projects with slow development cycles, it might be weeks or months before a broken build or bug report uncovers the problems. ReBuildBot is a Python script that runs via cron to trigger rebuilds of your projects on TravisCI, and/or execute build commands locally in a fresh git clone of master (i.e. integration or acceptance tests). You'll receive an email with the details of the runs and links to local command output uploaded to S3.

Requirements
============

* Python 2.7, or Python >= 3.3. Sorry if this is too limited, but:
  * Python 2.6 is archaic at this point, and just too difficult to maintain compatibility with in one codebase
  * The `boto <https://github.com/boto/boto>`_ library we use to interface with S3 lacks support for Python3 < 3.3, and it doesn't appear that will change.
* Some code on GitHub, being tested by Travis.
* An AWS account, and an existing S3 bucket to put build reports in. In order for the links in the report to work, the S3 bucket must be configured for `static website hosting <http://docs.aws.amazon.com/AmazonS3/latest/dev/HowDoIWebsiteConfiguration.html>`_ with a `bucket policy to allow global anonymous read access <http://docs.aws.amazon.com/AmazonS3/latest/dev/WebsiteAccessPermissionsReqd.html>`_.

Credentials
===========

GitHub
++++++

Your GitHub user token must either be set as the ``GITHUB_TOKEN`` environment variable, or be stored in a ``token`` attribute of the ``[github]`` section of your ``~/.gitconfig`` like:

.. code-block::

   [github]
	user = jantman
	token = <your token here>

This token is used both for authenticating to the GitHub API, as well as authentication to TravisCI.

AWS
+++

ReBuildBot stores its output in an S3 bucket on AWS (which should be configured for static website hosting).
It uses the `boto <https://github.com/boto/boto>`_ library for communication with S3, so any of the various
methods of specifying your AWS credentials that Boto accepts (see the `boto credentials documentation <http://boto.readthedocs.org/en/latest/boto_config_tut.html#credentials>`_)
will work; rebuildbot never touches AWS credentials and knows nothing about them.

Getting Started
===============

1. Install rebuildbot in a virtualenv.
2. You'll probably want to do a ``rebuildbot -v --dry-run BUCKET_NAME`` to make sure it can authenticate and that it finds all of your projects.
3. Do an initial run, to make sure everything works. You may want to manually select just a few projects, as your tests might take a while to run.
4. When you're satisfied that it appears to be working, set it up to run via cron. Please do not run more than once a day.

Configuring Local Tests
=======================

In addition to triggering TravisCI builds of the master branch, ReBuildBot can also run local integration tests. This is
done via a simple ``.rebuildbot.sh`` script in the repository to test. When run, ReBuildBot will identify all of your
GitHub repositories that contain a ``.rebuildbot.sh`` in the root directory of the repository, clone the repo locally,
and then execute the ``.rebuildbot.sh`` script. All output will be captured (note, STDOUT and STDERR will be combined)
and uploaded to the specified S3 bucket, and the clone will be removed when the tests are complete (unless specified
otherwise).

A sample ``.rebuildbot.sh`` for a Puppet module with Beaker acceptance tests might look like:

.. code-block:: bash

    #!/bin/bash -x
    echo "foo"

By default, any repositories with commits on master in the last 24 hours will not have local tests run. To bypass this behavior and run tests for all repositories that have a ``.rebuildbot.sh`` present, run with ``--no-date-check``.

Security
========

Aside from needing access to your GitHub token and your AWS account, the only major security concern is ReBuildBot's
very naive method of running integration tests - it executes a bash script in the repository to be tested, as whatever
user ReBuildBot is running under. Please be aware of the implications of this; most importantly, that anyone who can
push to the master branch in your repository can execute commands on whatever machine runs ReBuildBot. Because of the
file naming convention (``.rebuildbot.sh``), it's pretty easy to search public repositories on GitHub and find out
who's running this.

As such, I'd recommend that you take one or all of the following security precautions:

1. Make sure that push access to your GitHub repository is tightly controlled. If you have the slightest reason to believe
   that someone else has obtained access to your repositories (whether via SSH, web UI login, or API token), disable ReBuildBot
   immediately.
2. If practical, have ReBuildBot run in a container or virtual machine.
3. If that isn't possible, have ReBuildBot run as an isolated, non-privileged user.

It's up to you to assess the possible risks that executing code from your own GitHub accont pose, and decide on what
security measures are adequate for you.
