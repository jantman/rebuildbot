"""
rebuildbot/exceptions.py

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


class GitTokenMissingError(Exception):

    def __init__(self):
        msg = "ReBuildBot could not find your GitHub token. You must either " \
              "set it as the GITHUB_TOKEN environment variable, or add it as " \
              "the value of a 'token' key in the 'github' section of your " \
              "~/.gitconfig file."
        super(GitTokenMissingError, self).__init__(msg)


class TravisTriggerError(Exception):
    """Raised when triggering a Travis build returns a bad response code."""

    def __init__(self, repo, branch, url, status_code, headers, text):
        self.repo = repo
        self.branch = branch
        self.url = url
        self.status_code = status_code
        self.headers = headers
        self.text = text

        msg = "Got {sc} response code when triggering build of {r} ({b}) " \
              "via <{url}>:\nHeaders:\n{h}\nResponse Body:\n{t}".format(
                  sc=status_code,
                  r=repo,
                  b=branch,
                  url=url,
                  h=headers,
                  t=text
              )
        super(TravisTriggerError, self).__init__(msg)


class PollTimeoutException(Exception):
    """
    Raised when polling the Travis API for a change times out.
    """

    def __init__(self, poll_type, repo, wait_time, num_times):
        self.poll_type = poll_type
        self.repo = repo
        self.wait_time = wait_time
        self.num_times = num_times

        msg = "Polling Travis for update to {pt} on {r} timed out after {s} " \
              "seconds".format(
                  pt=poll_type,
                  r=repo,
                  s=(wait_time * num_times)
              )
        super(PollTimeoutException, self).__init__(msg)
