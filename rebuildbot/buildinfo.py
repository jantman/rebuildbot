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

from rebuildbot.travis import Travis


class BuildInfo(object):
    """
    A container object to hold the status and output of Travis and local
    rebuilds of a specific GitHub repository.
    """

    def __init__(self, repo_slug, local_script=None, https_clone_url=None,
                 ssh_clone_url=None):
        """
        Initialize a BuildInfo data container.

        :param repo_slug: the repository slug / full name
        :type repo_slug: string
        :param local_script: the contents of .rebuildbot.sh for the repo
        :type local_script: string
        :param https_clone_url: the HTTPS git clone URL for the repo
        :type https_clone_url: string
        :param ssh_clone_url: the SSH git clone URL for the repo
        :type ssh_clone_url: string
        """
        self.slug = repo_slug  # repo full name / slug
        self.local_script = local_script  # .rebuildbot.sh local build script
        self.https_clone_url = https_clone_url
        self.ssh_clone_url = ssh_clone_url
        self.run_travis = False  # whether or not to run Travis build
        self.run_local = True  # whether or not to run local build
        self.travis_trigger_error = None  # Exception when triggering travis
        self.travis_build_id = None  # Travis Build ID of the new build
        self.travis_build_result = None  # travispy.entities.build.Build

        # set by self.set_local_build()
        self.local_build_return_code = None  # local build exit code
        self.local_build_output = None  # string local build output
        self.local_build_exception = None  # exception when running local build
        self.local_build_finished = False
        self.local_build_duration = None

        # set by self.set_travis_build_finished()
        # these mirror the fields of :py:class:`travispy.entities.build.Build`
        self.travis_build_result = None
        self.travis_build_state = None
        self.travis_build_color = None
        self.travis_build_duration = None
        self.travis_build_errored = None
        self.travis_build_number = None
        self.travis_build_url = None
        self.travis_build_finished = False

        if local_script is None:
            self.run_local = False

    @property
    def is_done(self):
        """
        Return True if this build still has more work to do (Travis running, or
        local build to run) else False.

        :rtype: boolean
        """
        if (
                self.travis_build_id is not None and
                self.travis_build_finished is False
        ):
            return False
        if self.run_local and not self.local_build_finished:
            return False
        return True

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

    def set_travis_build_finished(self, build):
        """
        Update the object with a reference to a finished Travis Build.

        :param build: the finished build
        :type build: :py:class:`travispy.entities.build.Build`
        """
        self.travis_build_result = build
        self.travis_build_state = build.state
        self.travis_build_color = build.color
        self.travis_build_duration = build.duration  # int seconds
        self.travis_build_errored = build.errored
        self.travis_build_number = build.number
        self.travis_build_url = Travis.url_for_build(self.slug, build.id)
        self.travis_build_finished = True

    def set_local_build(self, return_code=None, output=None, excinfo=None,
                        duration=None):
        """
        When a local build is finished, update with its return code and
        output string.

        :param return_code: the return code of the build script
        :type return_code: int
        :param output: the string output of the build script
        :type output: string
        :param excinfo: Exception encountered during build, if any
        :type excinfo: Exception
        :param duration: duration of the build (excluding git clone)
        :type duration: datetime.datetime.timedelta
        """
        self.local_build_return_code = return_code
        self.local_build_output = output
        self.local_build_exception = excinfo
        self.local_build_finished = True
        self.local_build_duration = duration

    def set_dry_run(self):
        """
        Set all Travis data to reflect a dry-run. LocalBuild data will be set
        by the :py:class:`~.LocalBuild` class.
        """
        self.travis_build_finished = True
        self.travis_build_id = -1

        # set by self.set_travis_build_finished()
        # these mirror the fields of :py:class:`travispy.entities.build.Build`
        self.travis_build_result = None
        self.travis_build_state = 'DRY RUN'
        self.travis_build_color = 'black'
        self.travis_build_duration = -1
        self.travis_build_errored = False
        self.travis_build_number = -1
        self.travis_build_url = '#'

    def make_html_info(self):
        pass
