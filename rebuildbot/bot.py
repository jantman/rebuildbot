"""
rebuildbot/bot.py

The latest version of this package is available at:
<https://github.com/jantman/rebuildbot>

################################################################################
Copyright 2015 Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>

    This file is part of rebuildbot.

    rebuildbot is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    rebuildbot is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with rebuildbot.  If not, see <http://www.gnu.org/licenses/>.

The Copyright and Authors attributions contained herein may not be removed or
otherwise altered, except to add the Author attribution of a contributor to
this work. (Additional Terms pursuant to Section 7b of the AGPL v3)
################################################################################
While not legally required, I sincerely request that anyone who finds
bugs please submit them at <https://github.com/jantman/rebuildbot> or
to me via email, and that you send any contributions or improvements
either as a pull request on GitHub, or to me via email.
################################################################################

AUTHORS:
Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>
################################################################################
"""

import os
# import time
from ConfigParser import SafeConfigParser
from StringIO import StringIO
import logging

# from dateutil import parser

from .travis import Travis

logger = logging.getLogger(__name__)


class ReBuildBot(object):
    """
    Main class for ReBuildBot - this is where everything happens.
    """

    def __init__(self):
        """
        Initialize ReBuildBot and attempt to connect to all external services.
        """
        self.gh_token = self.get_github_token()
        self.github = self.connect_github()
        self.travis = Travis(self.gh_token)
        self.s3 = self.connect_s3()

    def run(self, projects=None):
        """
        Main entry point for ReBuildBot.

        Build either a specified list of projects (by GitHub repository name),
        or else all projects found by :py:meth:`~.find_projects`. Send
        notifications when done.

        projects is either None, or a list of github repository slugs
        (i.e. <user>/<repo name>). If None, all repositories will be built.
        """
        # NOTES:
        """
        TODO:
        1) we'll need find_projects_travis() and find_projects_local(), each
        returning a list of repository slugs. For the Travis ones, we want to
        kick off builds of them and append the running build_ids to a list,
        checking back and updating a result dict with the result of the build,
        the build ID, and a link to the build.
        2) For local builds, we'll do these once Travis is started, but before
        we poll travis. For each one, we'll do the git clone, get it on the
        branch we want, and then start the local build. We'll capture output
        and stderr and the exit code, and put that to an S3 bucket. Once that's
        done, we'll update a result dict with the exit code (boolean, 0 or not)
        and a link to the S3 bucket output.
        3) After each local build, we want to poll the Travis list, if it's not
        empty, and update the result dict with that information.
        4) Print debugging information throughout.
        5) Once all builds are done or have timed out, we'll build a final
        result dict of all repos, their Travis build/status/link if applicable,
        and their local build/status/link if applicable.
        6) This final result dict will be transformed into HTML, which will be
        put both in S3 and sent via email.
        """
        # repos = self.travis.get_repos()
        repo_name = 'jantman/pydnstest'
        last_build = self.travis.get_last_build(repo_name)
        last_build_url = self.travis.url_for_build(repo_name, last_build.id)
        logger.info("Last build of %s: #%s (%s) started at %s <%s> (%s)",
                    repo_name, last_build.number, last_build.id,
                    last_build.started_at, last_build_url, last_build.color)
        # last_build_dt = parser.parse(last_build.started_at)
        build_id = self.travis.run_build(repo_name)
        logger.info("New build of %s started: %s", repo_name, build_id)

    def find_projects(self):
        """
        Iterate all GitHub repositories and find any with a .rebuildbot.yml or
        a .travis.yml; remove from this set any which have had a TravisCI build
        in the last 24 hours. Return the result.
        """
        pass

    def connect_s3(self):
        pass

    def connect_github(self):
        pass

    def get_github_token(self):
        """
        Find your GitHub API token. First look in the ``GITHUB_TOKEN`` env
        variable, then look in ``~/.gitconfig``

        @rtype: string
        """
        e = os.environ.get('GITHUB_TOKEN', None)
        if e is not None:
            logger.debug("Using GITHUB_TOKEN env variable")
            return e
        # ConfigParser doesn't like leading spaces, which .gitconfig has
        with open(os.path.expanduser('~/.gitconfig'), 'r') as fh:
            config_lines = fh.readlines()
        config = SafeConfigParser()
        config.readfp(StringIO(''.join([l.lstrip() for l in config_lines])))
        token = config.get('github', 'token')
        logger.debug("Using GitHub token from ~/.gitconfig")
        return token
