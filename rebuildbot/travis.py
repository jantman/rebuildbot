"""
rebuildbot/travis.py

Wrapper around travispy

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

import time
import logging
import json

try:
    from urllib import quote
except ImportError:
    from urllib.parse import quote

from travispy import TravisPy
from travispy.travispy import PUBLIC

logger = logging.getLogger(__name__)

CHECK_WAIT_TIME = 10  # seconds to wait before polling for builds


class Travis(object):
    """
    ReBuildBot wrapper around TravisPy
    """

    def __init__(self, github_token):
        """
        Connect to TravisCI. Return a connected TravisPy instance.

        @rtype: :py:class:`TravisPy`
        """
        self.travis = TravisPy.github_auth(github_token)
        self.user = self.travis.user()
        logger.debug("Authenticated to TravisCI as %s <%s> (user ID %s)",
                     self.user.login, self.user.email, self.user.id)

    def get_repos(self):
        """
        Return a list of all repo names for the current user.
        """
        repos = []
        for r in self.travis.repos(member=self.user.login):
            if r.slug.startswith(self.user.login + '/'):
                repos.append(r.slug)
            else:
                logger.debug("Ignoring repo owned by another user: %s", r.slug)
        return repos

    def run_build(self, repo_name, branch='master'):
        """
        Trigger a Travis build of the specified repository on the specified
        branch. Return the build ID of the triggered build, or None on error.
        """
        self.repo_name = 'jantman/pydnstest'
        self.branch = branch
        self.repo = self.travis.repo(repo_name)
        logger.info("Travis Repo %s (%s): pending=%s queued=%s running=%s "
                    "state=%s", repo_name, self.repo.id, self.repo.pending,
                    self.repo.queued, self.repo.running, self.repo.state)
        self.last_build = self.repo.last_build
        logger.debug("Found last build as #%s (%s), state=%s, started_at=%s ",
                     self.last_build.number, self.last_build.id,
                     self.last_build.state, self.last_build.started_at)
        res = self.trigger_travis(repo_name)
        if not res:
            return None
        c = 0
        logger.info("Waiting up to %s seconds for build of %s to start",
                    (10 * CHECK_WAIT_TIME), repo_name)
        while c < 10:
            build_id = self.get_last_build(repo_name).id
            if build_id != self.last_build.id:
                logger.debug("Found new build ID: %s", build_id)
                return build_id
            logger.debug("Build has not started; waiting %ss", CHECK_WAIT_TIME)
            time.sleep(CHECK_WAIT_TIME)
            c += 1
        else:
            logger.error("ERROR: Triggered build of %s branch %s, but "
                         "last_build has not changed in %d seconds.", repo_name,
                         branch, (c * CHECK_WAIT_TIME))
            return None
        return build_id

    def get_last_build(self, repo_name):
        """
        Return the TravisPy.Build object for the last build of the repo.
        """
        return self.travis.repo(repo_name).last_build

    def trigger_travis(self, repo_name, branch='master'):
        """
        Trigger a TravisCI build of a specific branch of a specific repo.

        The `README.rst for TravisPy <https://github.com/menegazzo/travispy>`_
        clearly says that it will only support official, non-experimental,
        non-Beta API methods. As a result, the API functionality to
        `trigger builds <http://docs.travis-ci.com/user/triggering-builds/>`_
        is not supported. This method adds that.

        Return True if the API indicates success, False otherwise
        """
        body = {
            'request': {
                'branch': branch,
                'message': 'triggered by https://github.com/jantman/rebuildbot'
            }
        }
        body_json = json.dumps(body)
        logger.debug("Request body: %s", body_json)
        url = PUBLIC + '/repo/' + quote(repo_name, safe='') + '/requests'
        headers = self.travis._HEADERS
        headers['Content-Type'] = 'application/json'
        headers['Accept'] = 'application/json'
        headers['Travis-API-Version'] = '3'
        res = self.travis._session.post(url, json=body, headers=headers)
        if res.status_code >= 200 and res.status_code < 300:
            logger.info("Successfully triggered build on %s", repo_name)
            return True
        logger.error("Error: attempt to trigger build via %s got status code "
                     "%s", url, res.status_code)
        logger.debug("Response headers: %s", res.headers)
        logger.debug("Response text: %s", res.text)
        return False

    def url_for_build(self, repo_name, build_num):
        """
        Given a repository name and build number, return the HTML URL for the
        build.
        """
        s = 'https://travis-ci.org/%s/builds/%s' % (repo_name, build_num)
        return s
