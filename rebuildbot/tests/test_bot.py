"""
rebuildbot/tests/test_bot.py

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
import pytest
import pytz
import re
from textwrap import dedent

from boto.s3.connection import S3Connection
from boto.s3.bucket import Bucket
from boto.s3.key import Key

from rebuildbot.bot import ReBuildBot
from rebuildbot.travis import Travis
from rebuildbot.exceptions import (GitTokenMissingError, PollTimeoutException,
                                   TravisTriggerError)
from rebuildbot.github_wrapper import GitHubWrapper
from rebuildbot.buildinfo import BuildInfo
from rebuildbot.version import _VERSION

from travispy.errors import TravisError

from freezegun import freeze_time

# https://code.google.com/p/mock/issues/detail?id=249
# py>=3.4 should use unittest.mock not the mock package on pypi
if (
        sys.version_info[0] < 3 or
        sys.version_info[0] == 3 and sys.version_info[1] < 4
):
    from mock import patch, call, Mock, mock_open, PropertyMock, DEFAULT
else:
    from unittest.mock import (
        patch, call, Mock, mock_open, PropertyMock, DEFAULT
    )

pbm = 'rebuildbot.bot'  # patch base path for this module
pb = 'rebuildbot.bot.ReBuildBot'  # patch base for class


class TestReBuildBotInit(object):

    def test_init(self):
        with \
             patch('%s.get_github_token' % pb) as mock_get_gh_token, \
             patch('%s.GitHubWrapper' % pbm) as mock_gh, \
             patch('%s.Travis' % pbm) as mock_travis, \
             patch('%s.connect_s3' % pb) as mock_connect_s3:
            mock_get_gh_token.return_value = 'myGHtoken'
            cls = ReBuildBot('mybucket')
        assert mock_get_gh_token.mock_calls == [call()]
        assert mock_gh.mock_calls == [call('myGHtoken')]
        assert mock_travis.mock_calls == [call('myGHtoken')]
        assert mock_connect_s3.mock_calls == [call('mybucket')]
        assert cls.gh_token == 'myGHtoken'
        assert cls.github == mock_gh.return_value
        assert cls.travis == mock_travis.return_value
        assert cls.bucket == mock_connect_s3.return_value
        assert cls.dry_run is False
        assert cls.builds == {}
        assert cls.s3_prefix == 'rebuildbot'
        assert cls.date_check is True

    def test_init_dry_run(self):
        with \
             patch('%s.get_github_token' % pb) as mock_get_gh_token, \
             patch('%s.GitHubWrapper' % pbm) as mock_gh, \
             patch('%s.Travis' % pbm) as mock_travis, \
             patch('%s.connect_s3' % pb) as mock_connect_s3:
            mock_get_gh_token.return_value = 'myGHtoken'
            cls = ReBuildBot('mybucket', s3_prefix='foo', dry_run=True,
                             date_check=False)
        assert mock_get_gh_token.mock_calls == [call()]
        assert mock_gh.mock_calls == [call('myGHtoken')]
        assert mock_travis.mock_calls == [call('myGHtoken')]
        assert mock_connect_s3.mock_calls == [call('mybucket')]
        assert cls.gh_token == 'myGHtoken'
        assert cls.github == mock_gh.return_value
        assert cls.travis == mock_travis.return_value
        assert cls.bucket == mock_connect_s3.return_value
        assert cls.dry_run is True
        assert cls.builds == {}
        assert cls.s3_prefix == 'foo'
        assert cls.date_check is False


class TestReBuildBot(object):

    def setup(self):
        self.mock_github = Mock(spec_set=GitHubWrapper)
        self.mock_travis = Mock(spec_set=Travis)
        self.mock_bucket = Mock(spec_set=Bucket)
        type(self.mock_bucket).name = 'bktname'
        self.endpoint = 'bktname.s3-website-us-west-2.amazonaws.com'
        self.mock_bucket.get_website_endpoint.return_value = self.endpoint

        with patch('%s.__init__' % pb, Mock(return_value=None)):
            self.cls = ReBuildBot('bktname')
            self.cls.gh_token = 'myGHtoken'
            self.cls.github = self.mock_github
            self.cls.travis = self.mock_travis
            self.cls.bucket = self.mock_bucket
            self.cls.bucket_endpoint = self.endpoint
            self.cls.builds = {}
            self.cls.dry_run = False
            self.cls.s3_prefix = 's3/prefix'

    def test_get_github_token_env(self):
        new_env = {
            'foo': 'bar',
            'HOME': '/my/home',
            'GITHUB_TOKEN': 'mytoken_env',
        }
        gitconfig_content = ''

        mocked_open = mock_open(read_data=gitconfig_content)
        if sys.version_info[0] == 3:
            mock_open_target = 'builtins.open'
        else:
            mock_open_target = '__builtin__.open'

        with patch.dict('%s.os.environ' % pbm, new_env):
            with patch(mock_open_target, mocked_open, create=True):
                res = self.cls.get_github_token()
        assert res == 'mytoken_env'
        assert mocked_open.mock_calls == []

    def test_get_github_token_gitconfig(self):
        new_env = {
            'foo': 'bar',
            'HOME': '/my/home',
        }
        gitconfig_content = dedent("""
        ################################################################
        [user]
                name = My Name
                email = me@example.com
        [push]
                default = simple
        [github]
                user = ghUsername
                token = myGitConfigToken

        """)

        mocked_open = mock_open(read_data=gitconfig_content)
        if sys.version_info[0] == 3:
            mock_open_target = 'builtins.open'
        else:
            mock_open_target = '__builtin__.open'

        with patch.dict('%s.os.environ' % pbm, new_env):
            with patch(mock_open_target, mocked_open, create=True):
                res = self.cls.get_github_token()
        assert res == 'myGitConfigToken'
        assert mocked_open.mock_calls == [
            call('/my/home/.gitconfig', 'r'),
            call().__enter__(),
            call().readlines(),
            call().__exit__(None, None, None)
        ]

    def test_get_github_token_no_section(self):
        new_env = {
            'foo': 'bar',
            'HOME': '/my/home',
        }
        gitconfig_content = dedent("""
        ################################################################
        [user]
                name = My Name
                email = me@example.com
        [push]
                default = simple
        """)

        mocked_open = mock_open(read_data=gitconfig_content)
        if sys.version_info[0] == 3:
            mock_open_target = 'builtins.open'
        else:
            mock_open_target = '__builtin__.open'

        with patch.dict('%s.os.environ' % pbm, new_env):
            with patch(mock_open_target, mocked_open, create=True):
                with pytest.raises(GitTokenMissingError):
                    self.cls.get_github_token()
        assert mocked_open.mock_calls == [
            call('/my/home/.gitconfig', 'r'),
            call().__enter__(),
            call().readlines(),
            call().__exit__(None, None, None)
        ]

    def test_get_github_token_no_key(self):
        new_env = {
            'foo': 'bar',
            'HOME': '/my/home',
        }
        gitconfig_content = dedent("""
        ################################################################
        [user]
                name = My Name
                email = me@example.com
        [push]
                default = simple
        [github]
                user = ghUsername
        """)

        mocked_open = mock_open(read_data=gitconfig_content)
        if sys.version_info[0] == 3:
            mock_open_target = 'builtins.open'
        else:
            mock_open_target = '__builtin__.open'

        with patch.dict('%s.os.environ' % pbm, new_env):
            with patch(mock_open_target, mocked_open, create=True):
                with pytest.raises(GitTokenMissingError):
                    self.cls.get_github_token()
        assert mocked_open.mock_calls == [
            call('/my/home/.gitconfig', 'r'),
            call().__enter__(),
            call().readlines(),
            call().__exit__(None, None, None)
        ]

    def test_find_projects_automatic(self):
        self.cls.date_check = 'foo'
        self.cls.github.find_projects.return_value = {
            'a/p1': ('clone_a_p1', 'ssh_a_p1'),
            'a/p2': ('clone_a_p2', 'ssh_a_p2'),
        }
        self.cls.travis.get_repos.return_value = [
            'a/p1',
            'a/p3',
        ]
        res = self.cls.find_projects(None)
        assert self.cls.github.mock_calls == [
            call.find_projects(date_check='foo')
        ]
        assert self.cls.travis.mock_calls == [call.get_repos()]
        assert len(res) == 3
        assert res['a/p1'].slug == 'a/p1'
        assert res['a/p1'].run_travis is True
        assert res['a/p1'].run_local is True
        assert res['a/p1'].https_clone_url == 'clone_a_p1'
        assert res['a/p1'].ssh_clone_url == 'ssh_a_p1'
        assert res['a/p2'].slug == 'a/p2'
        assert res['a/p2'].run_travis is False
        assert res['a/p2'].run_local is True
        assert res['a/p2'].https_clone_url == 'clone_a_p2'
        assert res['a/p2'].ssh_clone_url == 'ssh_a_p2'
        assert res['a/p3'].slug == 'a/p3'
        assert res['a/p3'].run_travis is True
        assert res['a/p3'].run_local is False
        assert res['a/p3'].https_clone_url is None
        assert res['a/p3'].ssh_clone_url is None

    def test_find_projects_list(self):

        def se_last_build(proj_name):
            if proj_name in ['a/p1', 'a/p3']:
                return True
            raise TravisError({
                'status_code': 404,
                'error': 'some error',
                'message': {'message': 'foo'}
            })

        def se_config(projname):
            if projname == 'a/p1':
                return ('clone_a_p1', 'ssh_a_p1')
            if projname == 'a/p2':
                return ('clone_a_p2', 'ssh_a_p2')
            return (None, None)

        self.cls.github.get_project_config.side_effect = se_config
        self.cls.travis.get_last_build.side_effect = se_last_build

        res = self.cls.find_projects(['a/p1', 'a/p2', 'a/p3'])
        assert self.cls.github.mock_calls == [
            call.get_project_config('a/p1'),
            call.get_project_config('a/p2'),
            call.get_project_config('a/p3'),
        ]
        assert self.cls.travis.mock_calls == [
            call.get_last_build('a/p1'),
            call.get_last_build('a/p2'),
            call.get_last_build('a/p3'),
        ]
        assert len(res) == 3
        assert res['a/p1'].slug == 'a/p1'
        assert res['a/p1'].run_travis is True
        assert res['a/p1'].run_local is True
        assert res['a/p1'].https_clone_url == 'clone_a_p1'
        assert res['a/p1'].ssh_clone_url == 'ssh_a_p1'
        assert res['a/p2'].slug == 'a/p2'
        assert res['a/p2'].run_travis is False
        assert res['a/p2'].run_local is True
        assert res['a/p2'].https_clone_url == 'clone_a_p2'
        assert res['a/p2'].ssh_clone_url == 'ssh_a_p2'
        assert res['a/p3'].slug == 'a/p3'
        assert res['a/p3'].run_travis is True
        assert res['a/p3'].run_local is False
        assert res['a/p3'].https_clone_url is None
        assert res['a/p3'].ssh_clone_url is None

    def test_connect_s3(self):
        mock_conn = Mock(spec_set=S3Connection)
        mock_bucket = Mock(spec_set=Bucket)
        url = 'bktname.s3-website-us-west-2.amazonaws.com'
        mock_bucket.get_website_endpoint.return_value = url
        mock_conn.get_bucket.return_value = mock_bucket

        with patch('%s.boto.connect_s3' % pbm) as mock_s3:
            mock_s3.return_value = mock_conn
            res = self.cls.connect_s3('bktname')
        assert res == mock_bucket
        assert mock_s3.mock_calls == [
            call(),
            call().get_bucket('bktname'),
            call().get_bucket().get_website_endpoint()
        ]
        assert self.cls.bucket_endpoint == url

    def test_run(self):
        with \
             patch('%s.find_projects' % pb) as mock_find, \
             patch('%s.start_travis_builds' % pb) as mock_start_travis, \
             patch('%s.have_work_to_do' % pb, new_callable=PropertyMock) \
             as mock_have_work, \
             patch('%s.runner_loop' % pb) as mock_runner_loop, \
             patch('%s.handle_results' % pb) as mock_handle_results:
            mock_have_work.side_effect = [True, True, False]
            self.cls.run()
        assert mock_find.mock_calls == [call(None)]
        assert self.cls.builds == mock_find.return_value
        assert mock_start_travis.mock_calls == [call()]
        assert mock_have_work.mock_calls == [call(), call(), call()]
        assert mock_runner_loop.mock_calls == [call(), call()]
        assert mock_handle_results.mock_calls == [call()]

    def test_run_with_projects(self):
        with \
             patch('%s.find_projects' % pb) as mock_find, \
             patch('%s.start_travis_builds' % pb) as mock_start_travis, \
             patch('%s.have_work_to_do' % pb, new_callable=PropertyMock) \
             as mock_have_work, \
             patch('%s.runner_loop' % pb) as mock_runner_loop, \
             patch('%s.handle_results' % pb) as mock_handle_results:
            mock_have_work.return_value = False
            self.cls.run(['foo/bar', 'baz/blam'])
        assert mock_find.mock_calls == [call(['foo/bar', 'baz/blam'])]
        assert self.cls.builds == mock_find.return_value
        assert mock_start_travis.mock_calls == [call()]
        assert mock_have_work.mock_calls == [call()]
        assert mock_runner_loop.mock_calls == []
        assert mock_handle_results.mock_calls == [call()]

    def test_start_travis_builds(self):

        exc_blam = PollTimeoutException('poll_type', 'repo', 2, 3)

        exc_blarg = TravisTriggerError('repo', 'branch', 'url', 'status_code',
                                       'headers', 'text')

        def se_run_travis(repo_slug, branch='master'):
            if repo_slug == 'foo/bar':
                return (1, 2)
            if repo_slug == 'foo/blam':
                raise exc_blam
            if repo_slug == 'foo/blarg':
                raise exc_blarg
            if repo_slug == 'foo/other':
                return (1, None)

        bi_bar = BuildInfo('foo/bar', None)
        bi_bar.run_travis = True
        bi_baz = BuildInfo('foo/baz', None)
        bi_blam = BuildInfo('foo/blam', None)
        bi_blam.run_travis = True
        bi_blarg = BuildInfo('foo/blarg', None)
        bi_blarg.run_travis = True
        bi_foo = BuildInfo('foo/foo', None)
        bi_foo.run_travis = False
        bi_quux = BuildInfo('foo/quux', None)
        bi_quux.run_travis = True
        bi_quux.travis_build_finished = True
        bi_other = BuildInfo('foo/other', None)
        bi_other.run_travis = True

        self.cls.builds = {
            'foo/bar': bi_bar,
            'foo/baz': bi_baz,
            'foo/blam': bi_blam,
            'foo/blarg': bi_blarg,
            'foo/foo': bi_foo,
            'foo/quux': bi_quux,
            'foo/other': bi_other,
        }
        self.cls.travis.run_build.side_effect = se_run_travis
        self.cls.start_travis_builds()
        assert self.cls.travis.run_build.mock_calls == [
            call('foo/bar'),
            call('foo/blam'),
            call('foo/blarg'),
            call('foo/other'),
        ]
        assert self.cls.builds['foo/bar'].travis_build_id == 2
        assert self.cls.builds['foo/bar'].travis_last_build_id == 1
        assert self.cls.builds['foo/blam'].travis_build_id is None
        assert self.cls.builds['foo/blam'].travis_trigger_error == exc_blam
        assert self.cls.builds['foo/blarg'].travis_build_id is None
        assert self.cls.builds['foo/blarg'].travis_trigger_error == exc_blarg
        assert self.cls.builds['foo/other'].travis_build_id is None
        assert self.cls.builds['foo/other'].travis_last_build_id == 1

    def test_start_travis_builds_dry_run(self):
        self.cls.dry_run = True

        bi_bar = Mock(spec_set=BuildInfo)
        type(bi_bar).run_travis = PropertyMock(return_value=True)
        type(bi_bar).travis_build_finished = PropertyMock(return_value=False)
        bi_baz = Mock(spec_set=BuildInfo)
        type(bi_baz).run_travis = PropertyMock(return_value=False)
        type(bi_baz).travis_build_finished = PropertyMock(return_value=False)

        self.cls.builds = {
            'foo/bar': bi_bar,
            'foo/baz': bi_baz,
        }
        self.cls.start_travis_builds()
        assert self.cls.travis.run_build.mock_calls == []
        assert bi_bar.mock_calls == [call.set_dry_run()]
        assert bi_baz.mock_calls == []

    def test_have_work_true(self):
        bi_1 = Mock(spec_set=BuildInfo)
        type(bi_1).is_done = PropertyMock(return_value=True)
        bi_2 = Mock(spec_set=BuildInfo)
        type(bi_2).is_done = PropertyMock(return_value=False)

        self.cls.builds = {'foo/1': bi_1, 'foo/2': bi_2}
        assert self.cls.have_work_to_do is True

    def test_have_work_false(self):
        bi_1 = Mock(spec_set=BuildInfo)
        type(bi_1).is_done = PropertyMock(return_value=True)
        bi_2 = Mock(spec_set=BuildInfo)
        type(bi_2).is_done = PropertyMock(return_value=True)

        self.cls.builds = {'foo/1': bi_1, 'foo/2': bi_2}
        assert self.cls.have_work_to_do is False

    def test_runner_loop(self):
        build1 = Mock(spec_set=BuildInfo)
        type(build1).run_local = PropertyMock(return_value=False)
        type(build1).local_build_finished = PropertyMock(return_value=False)
        build2 = Mock(spec_set=BuildInfo)
        type(build2).run_local = PropertyMock(return_value=True)
        type(build2).local_build_finished = PropertyMock(return_value=True)
        build3 = Mock(spec_set=BuildInfo)
        type(build3).run_local = PropertyMock(return_value=True)
        type(build3).local_build_finished = PropertyMock(return_value=False)
        build4 = Mock(spec_set=BuildInfo)
        type(build4).run_local = PropertyMock(return_value=True)
        type(build4).local_build_finished = PropertyMock(return_value=False)

        self.cls.builds = {
            'me/foo': build1,
            'me/bar': build2,
            'me/baz': build3,
            'me/blam': build4,
        }
        with patch('%s.poll_travis_updates' % pb) as mock_poll_travis, \
                patch('%s.time.sleep' % pbm) as mock_sleep, \
                patch('%s.LocalBuild' % pbm) as mock_local_build:
            mock_poll_travis.return_value = True
            self.cls.runner_loop()
        assert mock_poll_travis.mock_calls == [call()]
        assert mock_local_build.mock_calls == [
            call('me/baz', build3, dry_run=False),
            call().run()
        ]
        assert mock_sleep.mock_calls == []

    def test_runner_loop_dry_run(self):
        self.cls.dry_run = True

        build1 = Mock(spec_set=BuildInfo)
        type(build1).run_local = PropertyMock(return_value=True)
        type(build1).local_build_finished = PropertyMock(return_value=False)

        self.cls.builds = {
            'me/foo': build1,
        }
        with patch('%s.poll_travis_updates' % pb) as mock_poll_travis, \
                patch('%s.time.sleep' % pbm) as mock_sleep, \
                patch('%s.LocalBuild' % pbm) as mock_local_build:
            mock_poll_travis.return_value = True
            self.cls.runner_loop()
        assert mock_poll_travis.mock_calls == [call()]
        assert mock_local_build.mock_calls == [
            call('me/foo', build1, dry_run=True),
            call().run()
        ]
        assert mock_sleep.mock_calls == []

    def test_runner_loop_no_local(self):
        build1 = Mock(spec_set=BuildInfo)
        type(build1).run_local = PropertyMock(return_value=True)
        type(build1).local_build_finished = PropertyMock(return_value=True)

        self.cls.builds = {
            'me/foo': build1,
        }
        with patch('%s.poll_travis_updates' % pb) as mock_poll_travis, \
                patch('%s.time.sleep' % pbm) as mock_sleep, \
                patch('%s.LocalBuild' % pbm) as mock_local_build:
            mock_poll_travis.return_value = False
            self.cls.runner_loop()
        assert mock_poll_travis.mock_calls == [call()]
        assert mock_local_build.mock_calls == []
        assert mock_sleep.mock_calls == [call(10)]

    def test_poll_travis_updates(self):
        build1 = Mock(spec_set=BuildInfo)
        type(build1).run_travis = PropertyMock(return_value=False)
        type(build1).travis_build_finished = False
        type(build1).travis_build_id = -1

        build2 = Mock(spec_set=BuildInfo)
        type(build2).run_travis = PropertyMock(return_value=True)
        type(build2).travis_build_finished = True
        type(build2).travis_build_id = -1

        build3 = Mock(spec_set=BuildInfo)
        type(build3).run_travis = PropertyMock(return_value=True)
        type(build3).travis_build_finished = False
        type(build3).travis_build_id = 123

        build4 = Mock(spec_set=BuildInfo)
        type(build4).run_travis = PropertyMock(return_value=True)
        type(build4).travis_build_finished = False
        type(build4).travis_build_id = 456

        build5 = Mock(spec_set=BuildInfo)
        type(build5).run_travis = PropertyMock(return_value=True)
        type(build5).travis_build_finished = False
        type(build5).travis_build_id = None

        build6 = Mock(spec_set=BuildInfo)
        type(build6).run_travis = PropertyMock(return_value=True)
        type(build6).travis_build_finished = False
        type(build6).travis_build_id = None

        mock_travis_build3 = Mock()
        type(mock_travis_build3).finished = PropertyMock(return_value=True)
        mock_travis_build4 = Mock()
        type(mock_travis_build4).finished = PropertyMock(return_value=False)
        mock_travis_build5 = Mock()
        type(mock_travis_build5).finished = PropertyMock(return_value=False)

        def se_get_build(build_id):
            if build_id == 123:
                return mock_travis_build3
            if build_id == 456:
                return mock_travis_build4
            if build_id == 789:
                return mock_travis_build5
            return Mock()

        def se_update(build):
            if build == build5:
                return 789
            return None

        self.cls.travis.get_build.side_effect = se_get_build

        self.cls.builds = {
            'a/1': build1,
            'a/2': build2,
            'a/3': build3,
            'a/4': build4,
            'a/5': build5,
            'a/6': build6,
        }

        with patch('%s.update_travis_build' % pb) as mock_update:
            mock_update.side_effect = se_update
            res = self.cls.poll_travis_updates()

        assert res is True
        assert self.cls.travis.mock_calls == [
            call.get_build(123),
            call.get_build(456),
            call.get_build(789),
        ]
        assert build1.mock_calls == []
        assert build2.mock_calls == []
        assert build3.mock_calls == [
            call.set_travis_build_finished(mock_travis_build3)
        ]
        assert build4.mock_calls == []
        assert build5.mock_calls == []
        assert build6.mock_calls == []
        assert mock_update.mock_calls == [
            call(build5),
            call(build6),
        ]

    def test_poll_travis_updates_dry_run(self):
        self.cls.dry_run = True

        build1 = Mock(spec_set=BuildInfo)
        build2 = Mock(spec_set=BuildInfo)

        self.cls.builds = {
            'a/1': build1,
            'a/2': build2,
        }

        self.cls.poll_travis_updates()

        assert self.cls.travis.mock_calls == []
        assert build1.mock_calls == [call.set_dry_run()]
        assert build2.mock_calls == [call.set_dry_run()]

    @freeze_time('2015-01-10 12:13:14')
    def test_get_s3_prefix(self):
        with patch('%s.os.path.exists' % pbm) as mock_exists:
            with patch('%s.shutil.rmtree' % pbm) as mock_rmtree:
                with patch('%s.os.mkdir' % pbm) as mock_mkdir:
                    res = self.cls.get_s3_prefix()
        assert mock_exists.mock_calls == []
        assert mock_rmtree.mock_calls == []
        assert mock_mkdir.mock_calls == []
        assert res == 's3/prefix/2015-01-10_12-13-14'

    @freeze_time('2015-01-10 12:13:14')
    def test_get_s3_prefix_dry_run(self):
        self.cls.dry_run = True
        with patch('%s.os.path.exists' % pbm) as mock_exists:
            mock_exists.return_value = True
            with patch('%s.shutil.rmtree' % pbm) as mock_rmtree:
                with patch('%s.os.mkdir' % pbm) as mock_mkdir:
                    res = self.cls.get_s3_prefix()
        assert mock_exists.mock_calls == [call('s3_content')]
        assert mock_rmtree.mock_calls == [call('s3_content')]
        assert mock_mkdir.mock_calls == [call('s3_content')]
        assert res == 's3_content'

    @freeze_time('2015-01-10 12:13:14')
    def test_get_s3_prefix_dry_run_no_exist(self):
        self.cls.dry_run = True
        with patch('%s.os.path.exists' % pbm) as mock_exists:
            mock_exists.return_value = False
            with patch('%s.shutil.rmtree' % pbm) as mock_rmtree:
                with patch('%s.os.mkdir' % pbm) as mock_mkdir:
                    res = self.cls.get_s3_prefix()
        assert mock_exists.mock_calls == [call('s3_content')]
        assert mock_rmtree.mock_calls == []
        assert mock_mkdir.mock_calls == [call('s3_content')]
        assert res == 's3_content'

    def test_url_for_s3(self):
        res = self.cls.url_for_s3('my/path')
        assert res == 'http://%s/my/path' % self.endpoint

    def test_write_to_s3(self):
        with \
             patch('%s.open' % pbm, mock_open(), create=True) as m_open, \
             patch('%s.Key' % pbm, spec_set=Key) as mock_key, \
             patch('%s.url_for_s3' % pb) as mock_url, \
             patch('%s.os.path.abspath' % pbm) as mock_abspath:
            mock_url.return_value = 'myurl'
            mock_abspath.return_value = '/basedir/foo/bar/myfname'
            res = self.cls.write_to_s3('foo/bar', 'myfname', 'mycontent')
        assert m_open.mock_calls == []
        assert mock_key.mock_calls == [
            call(self.mock_bucket),
            call().set_contents_from_string('mycontent')
        ]
        assert mock_abspath.mock_calls == []
        assert mock_url.mock_calls == [call('foo/bar/myfname')]
        assert res == 'myurl'

    def test_write_to_s3_dry_run(self):
        with \
             patch('%s.open' % pbm, mock_open(), create=True) as m_open, \
             patch('%s.Key' % pbm, spec_set=Key) as mock_key, \
             patch('%s.url_for_s3' % pb) as mock_url, \
             patch('%s.os.path.exists' % pbm) as mock_exists, \
             patch('%s.os.makedirs' % pbm) as mock_makedirs, \
             patch('%s.os.path.abspath' % pbm) as mock_abspath:
            mock_url.return_value = 'myurl'
            mock_abspath.return_value = '/basedir/foo/bar/myfname'
            mock_exists.return_value = False
            self.cls.dry_run = True
            res = self.cls.write_to_s3('foo/bar', 'myfname', 'mycontent')
        assert m_open.mock_calls == [
            call('/basedir/foo/bar/myfname', 'w'),
            call().__enter__(),
            call().write('mycontent'),
            call().__exit__(None, None, None)
        ]
        assert mock_key.mock_calls == []
        assert mock_abspath.mock_calls == [
            call('foo/bar/myfname')
        ]
        assert mock_url.mock_calls == []
        assert mock_exists.mock_calls == [call('/basedir/foo/bar')]
        assert mock_makedirs.mock_calls == [call('/basedir/foo/bar')]
        assert res == 'file:///basedir/foo/bar/myfname'

    def test_write_to_s3_dry_run_exists(self):
        with \
             patch('%s.open' % pbm, mock_open(), create=True) as m_open, \
             patch('%s.Key' % pbm, spec_set=Key) as mock_key, \
             patch('%s.url_for_s3' % pb) as mock_url, \
             patch('%s.os.path.exists' % pbm) as mock_exists, \
             patch('%s.os.makedirs' % pbm) as mock_makedirs, \
             patch('%s.os.path.abspath' % pbm) as mock_abspath:
            mock_url.return_value = 'myurl'
            mock_abspath.return_value = '/basedir/foo/bar/myfname'
            mock_exists.return_value = True
            self.cls.dry_run = True
            res = self.cls.write_to_s3('foo/bar', 'myfname', 'mycontent')
        assert m_open.mock_calls == [
            call('/basedir/foo/bar/myfname', 'w'),
            call().__enter__(),
            call().write('mycontent'),
            call().__exit__(None, None, None)
        ]
        assert mock_key.mock_calls == []
        assert mock_abspath.mock_calls == [
            call('foo/bar/myfname')
        ]
        assert mock_url.mock_calls == []
        assert mock_exists.mock_calls == [call('/basedir/foo/bar')]
        assert mock_makedirs.mock_calls == []
        assert res == 'file:///basedir/foo/bar/myfname'

    def test_handle_results(self):
        with patch.multiple(
                pb,
                get_s3_prefix=DEFAULT,
                write_local_output=DEFAULT,
                generate_report=DEFAULT,
                write_to_s3=DEFAULT,
        ) as mocks:
            mocks['get_s3_prefix'].return_value = 's3/prefix'
            mocks['generate_report'].return_value = 'myreport'
            mocks['write_to_s3'].return_value = 'myurl'
            self.cls.handle_results()
        assert mocks['get_s3_prefix'].mock_calls == [call()]
        assert mocks['write_local_output'].mock_calls == [call('s3/prefix')]
        assert mocks['generate_report'].mock_calls == [call('s3/prefix')]
        assert mocks['write_to_s3'].mock_calls == [
            call('s3/prefix', 'index.html', 'myreport')
        ]

    def test_write_local_output(self):
        build1 = Mock(spec_set=BuildInfo)
        type(build1).local_build_output_str = PropertyMock(return_value='a1out')
        build2 = Mock(spec_set=BuildInfo)
        type(build2).local_build_output_str = PropertyMock(return_value='a2out')

        self.cls.builds = {
            'a/1': build1,
            'a/2': build2,
        }

        def se_write(prefix, fname, content):
            return 'url:%s:%s' % (prefix, fname)

        with patch('%s.write_to_s3' % pb) as mock_write:
            mock_write.side_effect = se_write
            self.cls.write_local_output('my/prefix')
        assert mock_write.mock_calls == [
            call('my/prefix', 'a/1', 'a1out'),
            call('my/prefix', 'a/2', 'a2out'),
        ]
        assert build1.mock_calls == [
            call.set_local_build_s3_link('url:my/prefix:a/1')
        ]
        assert build2.mock_calls == [
            call.set_local_build_s3_link('url:my/prefix:a/2')
        ]

    @freeze_time('2015-01-10 12:13:14')  # UTC
    def test_generate_report(self):
        with \
             patch('%s.get_build_info_html_list' % pb) as mock_get_html, \
             patch('%s.Environment' % pbm) as mock_env, \
             patch('%s.PackageLoader' % pbm) as mock_loader, \
             patch('%s.platform_node' % pbm) as mock_node, \
             patch('%s.getuser' % pbm) as mock_user, \
             patch('%s.tzlocal.get_localzone' % pbm) as mock_localzone:
            mock_get_html.return_value = [('name', 'travis', 'local')]
            mock_node.return_value = 'my.node.name'
            mock_user.return_value = 'myuser'
            mock_template = Mock()
            mock_template.render.return_value = 'rendered'
            mock_env.return_value.get_template.return_value = mock_template
            mock_localzone.return_value = pytz.timezone('US/Eastern')
            res = self.cls.generate_report('my/prefix')

        expected_run_info = {
            'version': _VERSION,
            'date_s': '2015-01-10 07:13:14-0500 EST',
            'host': 'my.node.name',
            'user': 'myuser',
            'prefix': 'my/prefix',
            'bucket': 'bktname'
        }

        assert mock_env.mock_calls == [
            call(
                loader=mock_loader.return_value,
                extensions=['jinja2.ext.loopcontrols']
            ),
            call().get_template('report.html'),
            call().get_template().render(
                run_info=expected_run_info, builds=[('name', 'travis', 'local')]
            )
        ]
        assert mock_loader.mock_calls == [call('rebuildbot', 'templates')]
        assert res == 'rendered'

    @freeze_time('2015-01-10 12:13:14')  # UTC
    def test_template(self):
        with \
             patch('%s.get_build_info_html_list' % pb) as mock_get_html, \
             patch('%s.platform_node' % pbm) as mock_node, \
             patch('%s.getuser' % pbm) as mock_user, \
             patch('%s.tzlocal.get_localzone' % pbm) as mock_localzone:
            mock_get_html.return_value = [
                ('u1/name1', 'travis1', 'local1'),
                ('u1/name2', 'travis2', 'local2')
            ]
            mock_node.return_value = 'my.node.name'
            mock_user.return_value = 'myuser'
            mock_localzone.return_value = pytz.timezone('US/Eastern')
            res = self.cls.generate_report('my/prefix')

        assert res.startswith('<html>') is True
        assert '<title>ReBuildBot Report - 2015-01-10 07:13:14-0500 EST on ' \
            'my.node.name' in res, "Not found in content:\n%s" % res
        footer = '<p>Generated by <a href="https://github.com/jantman/rebuild' \
                 'bot">ReBuildBot</a> v%s on %s as %s at %s. S3 content ' \
                 "uploaded to bucket '%s' under prefix %s.</p>" % (
                     _VERSION,
                     'my.node.name',
                     'myuser',
                     '2015-01-10 07:13:14-0500 EST',
                     'bktname',
                     'my/prefix'
                 )
        assert footer in res, "Not found in content:\n%s" % res
        table_re = re.compile(
            r"<table>\s+"
            "<tr><th>Project</th><th>Travis</th><th>Local</th></tr>\s+"
            "<tr><td>u1/name1</td><td>travis1</td><td>local1</td></tr>\s+"
            "<tr><td>u1/name2</td><td>travis2</td><td>local2</td></tr>\s+"
            "</table>",
            flags=re.S
        )
        assert table_re.search(res) is not None, "Content:\n%s\n" \
            "Not found in content:\n%s" % (table_re.pattern, res)

    def test_get_build_info_html_list(self):
        build1 = Mock(spec_set=BuildInfo)
        build1.make_travis_html.return_value = 'travis1'
        build1.make_local_build_html.return_value = 'local1'
        build2 = Mock(spec_set=BuildInfo)
        build2.make_travis_html.return_value = 'travis2'
        build2.make_local_build_html.return_value = 'local2'
        build3 = Mock(spec_set=BuildInfo)
        build3.make_travis_html.return_value = 'travis3'
        build3.make_local_build_html.return_value = 'local3'
        build4 = Mock(spec_set=BuildInfo)
        build4.make_travis_html.return_value = 'travis4'
        build4.make_local_build_html.return_value = 'local4'

        self.cls.builds = {
            'a/1': build1,
            'a/2': build2,
            'a/z': build3,
            'b/a': build4,
        }

        res = self.cls.get_build_info_html_list()
        assert res == [
            ('a/1', 'travis1', 'local1'),
            ('a/2', 'travis2', 'local2'),
            ('a/z', 'travis3', 'local3'),
            ('b/a', 'travis4', 'local4'),
        ]

        for bld in [build1, build2, build3, build4]:
            assert bld.mock_calls == [
                call.make_travis_html(),
                call.make_local_build_html()
            ]

    def test_update_travis_build(self):
        b = Mock(spec_set=BuildInfo)
        type(b).slug = 'my/slug'
        type(b).travis_last_build_id = 1

        self.mock_travis.wait_for_new_build.return_value = 2
        res = self.cls.update_travis_build(b)
        assert b.mock_calls == [call.set_travis_build_ids(1, 2)]
        assert self.mock_travis.mock_calls == [
            call.wait_for_new_build('my/slug', 1)
        ]
        assert res == 2

    def test_update_travis_build_timeout(self):
        b = Mock(spec_set=BuildInfo)
        type(b).slug = 'my/slug'
        type(b).travis_last_build_id = 1

        def se_travis(slug, bid):
            raise PollTimeoutException('mytype', 'myrepo', 3, 2)

        self.mock_travis.wait_for_new_build.side_effect = se_travis
        res = self.cls.update_travis_build(b)
        assert b.mock_calls == []
        assert self.mock_travis.mock_calls == [
            call.wait_for_new_build('my/slug', 1)
        ]
        assert res is None
