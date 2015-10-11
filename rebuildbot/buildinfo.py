"""
rebuildbot/buildinfo.py

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


class BuildInfo(object):
    """
    A container object to hold the status and output of Travis and local
    rebuilds of a specific GitHub repository.
    """

    def __init__(self, repo_slug, local_script=None):
        """
        Initialize a BuildInfo data container.

        @param repo_slug: the repository slug / full name
        @type repo_slug: string
        @param local_script: the contents of .rebuildbot.sh for the repo
        @type local_script: string
        """
        self.slug = repo_slug  # repo full name / slug
        self.local_script = local_script  # .rebuildbot.sh local build script
        self.run_travis = False  # whether or not to run Travis build
        self.run_local = True  # whether or not to run local build
        self.travis_trigger_error = None  # Exception when triggering travis
        self.travis_build_id = None  # Travis Build ID of the new build

        if local_script is None:
            self.run_local = False

    def set_travis_trigger_error(self, e):
        """
        If an exception is encountered triggering the Travis build, store the
        exception.

        :param e: Exception encountered when triggering Travis build
        :type e: Exception
        """
        self.travis_trigger_error = e

    def set_travis_build_id(self, build_id):
        """
        Store the ID of the triggered Travis build.

        :param build_id: the ID of the triggered Travis build
        :type build_id: int
        """
        self.travis_build_id = build_id