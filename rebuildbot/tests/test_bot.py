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
from textwrap import dedent

from boto.s3.connection import S3Connection

from rebuildbot.bot import ReBuildBot
from rebuildbot.travis import Travis
from rebuildbot.exceptions import (GitTokenMissingError, PollTimeoutException,
                                   TravisTriggerError)
from rebuildbot.github_wrapper import GitHubWrapper
from rebuildbot.buildinfo import BuildInfo

from travispy.errors import TravisError

# https://code.google.com/p/mock/issues/detail?id=249
# py>=3.4 should use unittest.mock not the mock package on pypi
if (
        sys.version_info[0] < 3 or
        sys.version_info[0] == 3 and sys.version_info[1] < 4
):
    from mock import patch, call, Mock, mock_open, PropertyMock
else:
    from unittest.mock import patch, call, Mock, mock_open, PropertyMock

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
            cls = ReBuildBot()
        assert mock_get_gh_token.mock_calls == [call()]
        assert mock_gh.mock_calls == [call('myGHtoken')]
        assert mock_travis.mock_calls == [call('myGHtoken')]
        assert mock_connect_s3.mock_calls == [call()]
        assert cls.gh_token == 'myGHtoken'
        assert cls.github == mock_gh.return_value
        assert cls.travis == mock_travis.return_value
        assert cls.s3 == mock_connect_s3.return_value
        assert cls.dry_run is False
        assert cls.builds == {}

    def test_init_dry_run(self):
        with \
             patch('%s.get_github_token' % pb) as mock_get_gh_token, \
             patch('%s.GitHubWrapper' % pbm) as mock_gh, \
             patch('%s.Travis' % pbm) as mock_travis, \
             patch('%s.connect_s3' % pb) as mock_connect_s3:
            mock_get_gh_token.return_value = 'myGHtoken'
            cls = ReBuildBot(dry_run=True)
        assert mock_get_gh_token.mock_calls == [call()]
        assert mock_gh.mock_calls == [call('myGHtoken')]
        assert mock_travis.mock_calls == [call('myGHtoken')]
        assert mock_connect_s3.mock_calls == [call()]
        assert cls.gh_token == 'myGHtoken'
        assert cls.github == mock_gh.return_value
        assert cls.travis == mock_travis.return_value
        assert cls.s3 == mock_connect_s3.return_value
        assert cls.dry_run is True
        assert cls.builds == {}


class TestReBuildBot(object):

    def setup(self):
        self.mock_github = Mock(spec_set=GitHubWrapper)
        self.mock_travis = Mock(spec_set=Travis)
        self.mock_s3 = Mock()

        with patch('%s.__init__' % pb, Mock(return_value=None)):
            self.cls = ReBuildBot()
            self.cls.gh_token = 'myGHtoken'
            self.cls.github = self.mock_github
            self.cls.travis = self.mock_travis
            self.cls.s3 = self.mock_s3
            self.cls.builds = {}
            self.cls.dry_run = False

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
        self.cls.github.find_projects.return_value = {
            'a/p1': ('clone_a_p1', 'ssh_a_p1'),
            'a/p2': ('clone_a_p2', 'ssh_a_p2'),
        }
        self.cls.travis.get_repos.return_value = [
            'a/p1',
            'a/p3',
        ]
        res = self.cls.find_projects(None)
        assert self.cls.github.mock_calls == [call.find_projects()]
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
        with patch('%s.boto.connect_s3' % pbm) as mock_s3:
            mock_s3.return_value = mock_conn
            res = self.cls.connect_s3()
        assert res == mock_conn
        assert mock_s3.mock_calls == [call()]

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
                return 1
            if repo_slug == 'foo/blam':
                raise exc_blam
            if repo_slug == 'foo/blarg':
                raise exc_blarg

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

        self.cls.builds = {
            'foo/bar': bi_bar,
            'foo/baz': bi_baz,
            'foo/blam': bi_blam,
            'foo/blarg': bi_blarg,
            'foo/foo': bi_foo,
            'foo/quux': bi_quux,
        }
        self.cls.travis.run_build.side_effect = se_run_travis
        self.cls.start_travis_builds()
        assert self.cls.travis.run_build.mock_calls == [
            call('foo/bar'),
            call('foo/blam'),
            call('foo/blarg'),
        ]
        assert self.cls.builds['foo/bar'].travis_build_id == 1
        assert self.cls.builds['foo/blam'].travis_build_id is None
        assert self.cls.builds['foo/blam'].travis_trigger_error == exc_blam
        assert self.cls.builds['foo/blarg'].travis_build_id is None
        assert self.cls.builds['foo/blarg'].travis_trigger_error == exc_blarg

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
                patch('%s.LocalBuild' % pbm) as mock_local_build:
            self.cls.runner_loop()
        assert mock_poll_travis.mock_calls == [call()]
        assert mock_local_build.mock_calls == [
            call('me/baz', build3, dry_run=False),
            call().run()
        ]

    def test_runner_loop_dry_run(self):
        self.cls.dry_run = True

        build1 = Mock(spec_set=BuildInfo)
        type(build1).run_local = PropertyMock(return_value=True)
        type(build1).local_build_finished = PropertyMock(return_value=False)

        self.cls.builds = {
            'me/foo': build1,
        }
        with patch('%s.poll_travis_updates' % pb) as mock_poll_travis, \
                patch('%s.LocalBuild' % pbm) as mock_local_build:
            self.cls.runner_loop()
        assert mock_poll_travis.mock_calls == [call()]
        assert mock_local_build.mock_calls == [
            call('me/foo', build1, dry_run=True),
            call().run()
        ]

    def test_runner_loop_no_local(self):
        build1 = Mock(spec_set=BuildInfo)
        type(build1).run_local = PropertyMock(return_value=True)
        type(build1).local_build_finished = PropertyMock(return_value=True)

        self.cls.builds = {
            'me/foo': build1,
        }
        with patch('%s.poll_travis_updates' % pb) as mock_poll_travis, \
                patch('%s.LocalBuild' % pbm) as mock_local_build:
            self.cls.runner_loop()
        assert mock_poll_travis.mock_calls == [call()]
        assert mock_local_build.mock_calls == []

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

        mock_travis_build3 = Mock()
        type(mock_travis_build3).finished = PropertyMock(return_value=True)
        mock_travis_build4 = Mock()
        type(mock_travis_build4).finished = PropertyMock(return_value=False)

        def se_get_build(build_id):
            if build_id == 123:
                return mock_travis_build3
            if build_id == 456:
                return mock_travis_build4
            return Mock()

        self.cls.travis.get_build.side_effect = se_get_build

        self.cls.builds = {
            'a/1': build1,
            'a/2': build2,
            'a/3': build3,
            'a/4': build4,
        }

        self.cls.poll_travis_updates()

        assert self.cls.travis.mock_calls == [
            call.get_build(123),
            call.get_build(456),
        ]
        assert build1.mock_calls == []
        assert build2.mock_calls == []
        assert build3.mock_calls == [
            call.set_travis_build_finished(mock_travis_build3)
        ]
        assert build4.mock_calls == []

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
