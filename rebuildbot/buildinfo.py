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

import traceback
from datetime import timedelta

from rebuildbot.travis import Travis


class BuildInfo(object):
    """
    A container object to hold the status and output of Travis and local
    rebuilds of a specific GitHub repository.
    """

    def __init__(self, repo_slug, run_local=False, https_clone_url=None,
                 ssh_clone_url=None):
        """
        Initialize a BuildInfo data container.

        :param repo_slug: the repository slug / full name
        :type repo_slug: string
        :param run_local: whether or not to run local build
        :type local_script: boolean
        :param https_clone_url: the HTTPS git clone URL for the repo
        :type https_clone_url: string
        :param ssh_clone_url: the SSH git clone URL for the repo
        :type ssh_clone_url: string
        """
        self.slug = repo_slug  # repo full name / slug
        self.https_clone_url = https_clone_url
        self.ssh_clone_url = ssh_clone_url
        self.run_travis = False  # whether or not to run Travis build
        self.run_local = run_local  # whether or not to run local build
        self.travis_trigger_error = None  # Exception when triggering travis
        self.travis_build_id = None  # Travis Build ID of the new build
        self.travis_last_build_id = None
        self.travis_build_result = None  # travispy.entities.build.Build

        # set by self.set_local_build()
        self.local_build_return_code = None  # local build exit code
        self.local_build_output = None  # string local build output
        self.local_build_exception = None  # exception when running local build
        self.local_build_ex_type = None
        self.local_build_traceback = None
        self.local_build_finished = False
        self.local_build_start = None
        self.local_build_end = None
        self.local_build_duration = None
        self.local_build_s3_link = None
        self.local_build_repo_str = None

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

    def set_travis_build_ids(self, last_id, new_id):
        """
        Store the IDs of the previous and triggered Travis builds.

        :param last_id: the ID of the last build before triggering
        :type last_id: int
        :param new_id: the ID of the triggered Travis build
        :type new_id: int
        """
        self.travis_last_build_id = last_id
        self.travis_build_id = new_id

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
                        ex_type=None, traceback=None, start_dt=None,
                        end_dt=None, repo_str=None):
        """
        When a local build is finished, update with its return code and
        output string.

        :param return_code: the return code of the build script
        :type return_code: int
        :param output: the string output of the build script
        :type output: string
        :param excinfo: Exception encountered during build, if any
        :type excinfo: Exception
        :param traceback: the traceback associated with this exception
        :type traceback: traceback
        :param ex_type: the exception type
        :type ex_type: type
        :param start_dt: DateTime of build start
        :type start_dt: datetime.datetime
        :param end_dt: DateTime of build end
        :type end_dt: datetime.datetime
        :param repo_str: string describing the state of the cloned repo
        :type repo_str: str
        """
        self.local_build_return_code = return_code
        self.local_build_output = output
        self.local_build_exception = excinfo
        self.local_build_ex_type = ex_type
        self.local_build_traceback = traceback
        self.local_build_finished = True
        self.local_build_start = start_dt
        self.local_build_end = end_dt
        self.local_build_repo_str = repo_str
        if start_dt is not None and end_dt is not None:
            self.local_build_duration = end_dt - start_dt

    def set_local_build_s3_link(self, link):
        """
        Set the link to where the local build output was uploaded to S3.

        :param link: the HTTP link to the S3 object
        :type link: str
        """
        self.local_build_s3_link = link

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

    @property
    def local_build_output_str(self):
        """
        Return the string local build output. This is made up of
        ``local_build_output`` plus the return code, or the traceback of the
        exception if one was raised while running the build

        :rtype: str
        """
        if self.local_build_exception is not None:
            return "Build raised exception:\n" + ''.join(
                traceback.format_exception(
                    self.local_build_ex_type, self.local_build_exception,
                    self.local_build_traceback
                ))
        start_str = ''
        end_str = ''
        time_str = ''
        repo_str = ''
        if self.local_build_repo_str is not None:
            repo_str = self.local_build_repo_str
        if self.local_build_start is not None:
            start_str = "=> Build of {s} {r} starts at {d}\n".format(
                s=self.slug,
                d=self.local_build_start.strftime('%Y-%m-%d %H:%M:%S'),
                r=repo_str
            )
        else:
            start_str = "=> Build of {s} {r}\n".format(
                s=self.slug,
                r=repo_str
            )
        if self.local_build_end is not None:
            end_str = "=> Build ends at {d}\n".format(
                d=self.local_build_end.strftime('%Y-%m-%d %H:%M:%S')
            )
        if self.local_build_duration is not None:
            time_str = " in %s" % self.local_build_duration
        return "{s}{o}\n\n{e}==> Build exited {r}{t}".format(
            o=self.local_build_output,
            r=self.local_build_return_code,
            t=time_str,
            s=start_str,
            e=end_str
        )

    def make_travis_html(self):
        """
        Return an HTML string describing the Travis build outcome.

        :rtype: str
        """
        s = '<span class="icon {icon}">&nbsp;</span>'.format(
            icon=self.travis_build_icon
        )
        s += '<a href="{url}">#{num}</a> ran in {d}'.format(
            url=self.travis_build_url,
            num=self.travis_build_number,
            d=timedelta(seconds=self.travis_build_duration)
        )
        return s

    @property
    def travis_build_icon(self):
        """
        Return a build icon CSS class name for the Travis build.

        :rtype: str
        """
        if self.travis_build_state in ['canceled', 'errored']:
            return 'errored'
        if self.travis_build_state == 'failed':
            return 'failed'
        if self.travis_build_state == 'passed':
            return 'passed'
        return ''

    @property
    def local_build_icon(self):
        """
        Return a build icon CSS class name for the local build.

        :rtype: str
        """
        if self.local_build_exception is not None:
            return 'errored'
        if self.local_build_return_code == 0:
            return 'passed'
        return 'failed'

    def make_local_build_html(self):
        """
        Return an HTML string describing the local build outcome.

        :rtype: str
        """
        if not self.run_local:
            return '&nbsp;'
        s = '<span class="icon {icon}">&nbsp;</span>'.format(
            icon=self.local_build_icon
        )
        s += '<a href="{url}">Local Build</a> ran in {d}'.format(
            url=self.local_build_s3_link,
            d=self.local_build_duration
        )
        return s
