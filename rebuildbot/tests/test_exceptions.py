"""
rebuildbot/tests/test_exceptions.py

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

from rebuildbot.exceptions import (GitTokenMissingError, TravisTriggerError,
                                   PollTimeoutException)


class TestGitTokenMissingError(object):

    def test_exception(self):
        ex = GitTokenMissingError()
        msg = "ReBuildBot could not find your GitHub token. You must either " \
              "set it as the GITHUB_TOKEN environment variable, or add it as " \
              "the value of a 'token' key in the 'github' section of your " \
              "~/.gitconfig file."
        assert ex.message == msg


class TestTravisTriggerError(object):

    def test_error(self):
        ex = TravisTriggerError('myrepo', 'mybranch', 'myurl', 'SC',
                                'myheaders', 'mytext')
        assert ex.repo == 'myrepo'
        assert ex.branch == 'mybranch'
        assert ex.url == 'myurl'
        assert ex.status_code == 'SC'
        assert ex.headers == 'myheaders'
        assert ex.text == 'mytext'
        assert ex.message == "Got SC response code when triggering build of " \
            "myrepo (mybranch) via <myurl>:\nHeaders:\nmyheaders\nResponse " \
            "Body:\nmytext"


class TestPollTimeoutException(object):

    def test_exception(self):
        ex = PollTimeoutException('mytype', 'myrepo', 3, 2)
        assert ex.poll_type == 'mytype'
        assert ex.repo == 'myrepo'
        assert ex.wait_time == 3
        assert ex.num_times == 2
        assert ex.message == "Polling Travis for update to mytype on myrepo " \
            "timed out after 6 seconds"
