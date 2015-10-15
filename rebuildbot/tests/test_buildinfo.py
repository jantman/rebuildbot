"""
rebuildbot/tests/test_buildinfo.py

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

import sys
import traceback
from datetime import timedelta
from rebuildbot.buildinfo import BuildInfo

if (
        sys.version_info[0] < 3 or
        sys.version_info[0] == 3 and sys.version_info[1] < 4
):
    from mock import patch, call, Mock
else:
    from unittest.mock import patch, call, Mock

pbm = 'rebuildbot.buildinfo'
pb = '%s.BuildInfo' % pbm


class TestBuildInfoInit(object):

    def test_slug(self):
        cls = BuildInfo('myslug')
        assert cls.slug == 'myslug'
        assert cls.https_clone_url is None
        assert cls.ssh_clone_url is None
        assert cls.run_travis is False
        assert cls.travis_trigger_error is None
        assert cls.travis_build_id is None
        assert cls.travis_build_result is None
        assert cls.local_build_return_code is None
        assert cls.local_build_output is None
        assert cls.local_build_exception is None
        assert cls.local_build_ex_type is None
        assert cls.local_build_traceback is None
        assert cls.local_build_finished is False
        assert cls.local_build_duration is None
        assert cls.local_build_s3_link is None
        assert cls.run_local is False
        assert cls.travis_build_result is None
        assert cls.travis_build_state is None
        assert cls.travis_build_color is None
        assert cls.travis_build_duration is None
        assert cls.travis_build_errored is None
        assert cls.travis_build_number is None
        assert cls.travis_build_url is None
        assert cls.travis_build_finished is False

    def test_local_script(self):
        cls = BuildInfo('myslug', run_local=True)
        assert cls.slug == 'myslug'
        assert cls.https_clone_url is None
        assert cls.ssh_clone_url is None
        assert cls.run_travis is False
        assert cls.travis_trigger_error is None
        assert cls.travis_build_id is None
        assert cls.travis_build_result is None
        assert cls.local_build_return_code is None
        assert cls.local_build_output is None
        assert cls.local_build_exception is None
        assert cls.local_build_ex_type is None
        assert cls.local_build_traceback is None
        assert cls.local_build_finished is False
        assert cls.local_build_duration is None
        assert cls.local_build_s3_link is None
        assert cls.run_local is True
        assert cls.travis_build_result is None
        assert cls.travis_build_state is None
        assert cls.travis_build_color is None
        assert cls.travis_build_duration is None
        assert cls.travis_build_errored is None
        assert cls.travis_build_number is None
        assert cls.travis_build_url is None
        assert cls.travis_build_finished is False

    def test_other_args(self):
        cls = BuildInfo('myslug', https_clone_url='https', ssh_clone_url='ssh')
        assert cls.slug == 'myslug'
        assert cls.https_clone_url == 'https'
        assert cls.ssh_clone_url == 'ssh'
        assert cls.run_travis is False
        assert cls.travis_trigger_error is None
        assert cls.travis_build_id is None
        assert cls.travis_build_result is None
        assert cls.local_build_return_code is None
        assert cls.local_build_output is None
        assert cls.local_build_exception is None
        assert cls.local_build_ex_type is None
        assert cls.local_build_traceback is None
        assert cls.local_build_finished is False
        assert cls.local_build_duration is None
        assert cls.local_build_s3_link is None
        assert cls.run_local is False
        assert cls.travis_build_result is None
        assert cls.travis_build_state is None
        assert cls.travis_build_color is None
        assert cls.travis_build_duration is None
        assert cls.travis_build_errored is None
        assert cls.travis_build_number is None
        assert cls.travis_build_url is None
        assert cls.travis_build_finished is False


class TestBuildInfo(object):

    def setup(self):
        self.cls = BuildInfo('me/myrepo', run_local=True,
                             https_clone_url='https_url',
                             ssh_clone_url='ssh_url')

    def test_is_done_travis_true(self):
        self.cls.travis_build_id = 1
        self.cls.travis_build_finished = True
        self.cls.run_local = False
        assert self.cls.is_done is True

    def test_is_done_local_true(self):
        self.cls.travis_build_id = 1
        self.cls.travis_build_finished = True
        self.cls.run_local = True
        self.cls.local_build_finished = True
        assert self.cls.is_done is True

    def test_is_done_local_false(self):
        self.cls.travis_build_id = 1
        self.cls.travis_build_finished = True
        self.cls.run_local = True
        assert self.cls.is_done is False

    def test_is_done_travis_false(self):
        self.cls.travis_build_id = 1
        self.cls.run_local = False
        assert self.cls.is_done is False

    def test_set_travis_trigger_error(self):
        ex = Exception("foo")
        self.cls.set_travis_trigger_error(ex)
        assert self.cls.travis_trigger_error == ex

    def test_set_travis_build_id(self):
        self.cls.set_travis_build_id(123)
        assert self.cls.travis_build_id == 123

    def test_set_travis_build_finished(self):
        bld = Mock()
        type(bld).state = 'state'
        type(bld).color = 'color'
        type(bld).duration = 123
        type(bld).errored = False
        type(bld).number = 456
        type(bld).id = 789

        with patch('%s.Travis.url_for_build' % pbm) as mock_url:
            mock_url.return_value = 'mybuildurl'
            self.cls.set_travis_build_finished(bld)
        assert self.cls.travis_build_result == bld
        assert self.cls.travis_build_state == 'state'
        assert self.cls.travis_build_color == 'color'
        assert self.cls.travis_build_duration == 123
        assert self.cls.travis_build_errored is False
        assert self.cls.travis_build_number == 456
        assert self.cls.travis_build_url == 'mybuildurl'
        assert mock_url.mock_calls == [
            call('me/myrepo', 789)
        ]

    def test_set_local_build(self):
        self.cls.set_local_build(return_code=2, output='myoutput', duration=1)
        assert self.cls.local_build_return_code == 2
        assert self.cls.local_build_output == 'myoutput'
        assert self.cls.local_build_exception is None
        assert self.cls.local_build_finished is True
        assert self.cls.local_build_duration == 1

    def test_set_local_build_exception(self):
        ex = Exception("foo")
        tb = Mock()
        ex_type = Mock()
        self.cls.set_local_build(excinfo=ex, ex_type=ex_type, traceback=tb)
        assert self.cls.local_build_return_code is None
        assert self.cls.local_build_output is None
        assert self.cls.local_build_exception == ex
        assert self.cls.local_build_ex_type == ex_type
        assert self.cls.local_build_traceback == tb
        assert self.cls.local_build_finished is True

    def test_set_dry_run(self):
        self.cls.set_dry_run()
        assert self.cls.slug == 'me/myrepo'
        assert self.cls.https_clone_url == 'https_url'
        assert self.cls.ssh_clone_url == 'ssh_url'
        assert self.cls.run_travis is False
        assert self.cls.travis_trigger_error is None
        assert self.cls.travis_build_id == -1
        assert self.cls.travis_build_result is None
        assert self.cls.local_build_return_code is None
        assert self.cls.local_build_output is None
        assert self.cls.local_build_exception is None
        assert self.cls.local_build_ex_type is None
        assert self.cls.local_build_traceback is None
        assert self.cls.local_build_finished is False
        assert self.cls.local_build_duration is None
        assert self.cls.local_build_s3_link is None
        assert self.cls.run_local is True
        assert self.cls.travis_build_result is None
        assert self.cls.travis_build_state == 'DRY RUN'
        assert self.cls.travis_build_color == 'black'
        assert self.cls.travis_build_duration == -1
        assert self.cls.travis_build_errored is False
        assert self.cls.travis_build_number == -1
        assert self.cls.travis_build_url == '#'
        assert self.cls.travis_build_finished is True

    def test_local_build_output_str(self):
        self.cls.local_build_output = 'my output'
        self.cls.local_build_return_code = 3
        self.cls.local_build_duration = timedelta(hours=1, minutes=2, seconds=3)
        res = self.cls.local_build_output_str
        assert res == "my output\n\n=> Build exited 3 in 1:02:03"

    def test_local_build_output_str_exception(self):
        # get an exception with a traceback
        try:
            raise Exception("foo")
        except Exception:
            ex_type, ex, tb = sys.exc_info()
            self.cls.local_build_exception = ex
            self.cls.local_build_ex_type = ex_type
            self.cls.local_build_traceback = tb
        res = self.cls.local_build_output_str
        assert res == "Build raised exception:\n" + ''.join(
            traceback.format_exception(ex_type, ex, tb)
        )

    def test_set_local_build_s3_link(self):
        self.cls.set_local_build_s3_link('foo')
        assert self.cls.local_build_s3_link == 'foo'
