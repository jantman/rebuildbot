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
from dateutil import parser
from datetime import timedelta, datetime
import pytz
from rebuildbot.exceptions import (PollTimeoutException, TravisTriggerError)

try:
    from urllib import quote
except ImportError:
    from urllib.parse import quote

from travispy import TravisPy
from travispy.travispy import PUBLIC

logger = logging.getLogger(__name__)

CHECK_WAIT_TIME = 10  # seconds to wait before polling for builds
POLL_NUM_TIMES = 6  # how many times to poll before raising exception


class Travis(object):
    """
    ReBuildBot wrapper around TravisPy.
    """

    def __init__(self, github_token):
        """
        Connect to TravisCI. Return a connected TravisPy instance.

        :param github_token: GitHub access token to auth to Travis with
        :type github_token: str
        :rtype: :py:class:`TravisPy`
        """
        self.travis = TravisPy.github_auth(github_token)
        self.user = self.travis.user()
        logger.debug("Authenticated to TravisCI as %s <%s> (user ID %s)",
                     self.user.login, self.user.email, self.user.id)

    def get_repos(self, date_check=True):
        """
        Return a list of all repo names for the current authenticated user. If
        ``date_check`` is True, only return repos with a last build more
        than 24 hours ago.

        This only returns repos with a slug (<user_or_org>/<repo_name>) that
        begins with the user login; it ignores organization repos or repos
        that the user is a collaborator on.

        :param date_check: whether or not to only return repos with a last
        build more than 24 hours ago.
        :type date_check: bool
        :returns: list of the user's repository slugs
        :rtype: list of strings
        """
        repos = []
        for r in self.travis.repos(member=self.user.login):
            if not r.slug.startswith(self.user.login + '/'):
                logger.debug("Ignoring repo owned by another user: %s", r.slug)
                continue
            build_in_last_day = False
            try:
                build_in_last_day = self.repo_build_in_last_day(r)
            except KeyError:
                logger.debug('Skipping repo with no builds: %s', r.slug)
                continue
            if date_check and build_in_last_day:
                logger.debug("Skipping repo with build in last day: %s", r.slug)
                continue
            repos.append(r.slug)
        logger.debug('Found %d repos: %s', len(repos), repos)
        return sorted(repos)

    def repo_build_in_last_day(self, repo):
        """
        Return True if the repo has had a build in the last day, False otherwise

        :param repo: Travis repository object
        :rtype: bool
        """
        now = datetime.now(pytz.utc)
        dt = parser.parse(repo.last_build.started_at)
        if now - dt > timedelta(hours=24):
            return False
        return True

    def run_build(self, repo_slug, branch='master'):
        """
        Trigger a Travis build of the specified repository on the specified
        branch. Wait for the build repository's latest build ID to change,
        and then return a 2-tuple of the old build id and the new one.
        If the new build has not started within the timeout interval, the
        new build ID will be None.

        :param repo_slug: repository slug (<username>/<repo_name>)
        :type repo_slug: string
        :param branch: name of the branch to build
        :type branch: string
        :raises: PollTimeoutException, TravisTriggerError
        :returns: (last build ID, new build ID)
        :rtype: tuple
        """
        repo = self.travis.repo(repo_slug)
        logger.info("Travis Repo %s (%s): pending=%s queued=%s running=%s "
                    "state=%s", repo_slug, repo.id, repo.pending, repo.queued,
                    repo.running, repo.state)
        last_build = repo.last_build
        logger.debug("Found last build as #%s (%s), state=%s (%s), "
                     "started_at=%s (<%s>)",
                     last_build.number, last_build.id,
                     last_build.state, last_build.color, last_build.started_at,
                     self.url_for_build(repo_slug, last_build.id))
        self.trigger_travis(repo_slug, branch=branch)
        try:
            new_id = self.wait_for_new_build(repo_slug, last_build.id)
        except PollTimeoutException:
            logger.warning("Could not find new build ID for %s within timeout;"
                           " will poll later." % repo_slug)
            new_id = None
        return (last_build.id, new_id)

    def wait_for_new_build(self, repo_slug, last_build_id):
        """
        Wait for a repository to show a new last build ID, indicating that the
        triggered build has started or is queued.

        This polls for the last_build ID every :py:const:`~.CHECK_WAIT_TIME`
        seconds, up to :py:const:`~.POLL_NUM_TRIES` times. If the ID has not
        changed at the end, raise a :py:class:`~.PollTimeoutException`.

        :param repo_slug: the slug for the repo to check
        :type repo_slug: string
        :param last_build_id: the ID of the last build
        :type last_build_id: int
        :raises: PollTimeoutException, TravisTriggerError
        :returns: ID of the new build
        :rtype: int
        """
        logger.info("Waiting up to %s seconds for build of %s to start",
                    (POLL_NUM_TIMES * CHECK_WAIT_TIME), repo_slug)
        for c in range(0, POLL_NUM_TIMES):
            build_id = self.get_last_build(repo_slug).id
            if build_id != last_build_id:
                logger.debug("Found new build ID: %s", build_id)
                return build_id
            logger.debug("Build has not started; waiting %ss", CHECK_WAIT_TIME)
            time.sleep(CHECK_WAIT_TIME)
        else:
            raise PollTimeoutException('last_build.id', repo_slug,
                                       CHECK_WAIT_TIME, POLL_NUM_TIMES)

    def get_last_build(self, repo_slug):
        """
        Return the TravisPy.Build object for the last build of the repo.
        """
        return self.travis.repo(repo_slug).last_build

    def trigger_travis(self, repo_slug, branch='master'):
        """
        Trigger a TravisCI build of a specific branch of a specific repo.

        The `README.rst for TravisPy <https://github.com/menegazzo/travispy>`_
        clearly says that it will only support official, non-experimental,
        non-Beta API methods. As a result, the API functionality to
        `trigger builds <http://docs.travis-ci.com/user/triggering-builds/>`_
        is not supported. This method adds that.

        :raises TravisTriggerError
        :param repo_slug: repository slug (<username>/<repo_name>)
        :type repo_slug: string
        :param branch: name of the branch to build
        :type branch: string
        """
        body = {
            'request': {
                'branch': branch,
                'message': 'triggered by https://github.com/jantman/rebuildbot'
            }
        }
        url = PUBLIC + '/repo/' + quote(repo_slug, safe='') + '/requests'
        logger.debug("Triggering build of %s %s via %s", repo_slug, branch, url)
        headers = self.travis._HEADERS
        headers['Content-Type'] = 'application/json'
        headers['Accept'] = 'application/json'
        headers['Travis-API-Version'] = '3'
        res = self.travis._session.post(url, json=body, headers=headers)
        if res.status_code >= 200 and res.status_code < 300:
            logger.info("Successfully triggered build on %s", repo_slug)
            return
        raise TravisTriggerError(repo_slug, branch, url, res.status_code,
                                 res.headers, res.text)

    @staticmethod
    def url_for_build(repo_slug, build_num):
        """
        Given a repository name and build number, return the HTML URL for the
        build.
        """
        s = 'https://travis-ci.org/%s/builds/%s' % (repo_slug, build_num)
        return s

    def get_build(self, build_id):
        """
        Return the Build object for the specified build ID.

        :param build_id: the build ID of the build to get
        :type build_id: int
        :rtype: :py:class:`travispy.entities.Build`
        """
        b = self.travis.build(build_id)
        b.check_state()
        return b
