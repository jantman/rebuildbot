"""
rebuildbot/tests/test_local_build.py

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
import subprocess
import pytest
from rebuildbot.local_build import LocalBuild
from rebuildbot.buildinfo import BuildInfo
from datetime import datetime

from freezegun import freeze_time
from freezegun.api import FakeDatetime

# https://code.google.com/p/mock/issues/detail?id=249
# py>=3.4 should use unittest.mock not the mock package on pypi
if (
        sys.version_info[0] < 3 or
        sys.version_info[0] == 3 and sys.version_info[1] < 4
):
    from mock import Mock, patch, call
else:
    from unittest.mock import Mock, patch, call

pbm = 'rebuildbot.local_build'
pb = '%s.LocalBuild' % pbm


class TestLocalBuildInit(object):

    def test_init(self):
        bi = Mock(spec_set=BuildInfo)
        b = LocalBuild('me/repo', bi)
        assert b.repo_name == 'me/repo'
        assert b.build_info == bi
        assert b.dry_run is False

    def test_init_dry_run(self):
        bi = Mock(spec_set=BuildInfo)
        b = LocalBuild('me/repo', bi, dry_run=True)
        assert b.repo_name == 'me/repo'
        assert b.build_info == bi
        assert b.dry_run is True


class TestLocalBuild(object):

    def setup(self):
        self.bi = Mock(spec_set=BuildInfo)
        self.cls = LocalBuild('my/repo', self.bi)

    def test_run_ok(self):
        with patch('%s.clone_repo' % pb) as mock_clone, \
                patch('%s.run_build' % pb) as mock_run, \
                patch('%s.rmtree' % pbm) as mock_rmtree, \
                patch('%s.get_time' % pb) as mock_time:
            mock_clone.return_value = ('/my/clone/path', 'repostr')
            mock_run.return_value = 'my output'
            mock_time.side_effect = [
                datetime(2015, 1, 1, 1, 0, 0),
                datetime(2015, 1, 1, 2, 0, 0),
            ]
            self.cls.run()
        assert mock_clone.mock_calls == [call()]
        assert mock_run.mock_calls == [call('/my/clone/path')]
        assert self.bi.mock_calls == [
            call.set_local_build(return_code=0, output='my output',
                                 start_dt=datetime(2015, 1, 1, 1, 0, 0),
                                 end_dt=datetime(2015, 1, 1, 2, 0, 0),
                                 repo_str='repostr')
        ]
        assert mock_rmtree.mock_calls == [call('/my/clone/path')]

    def make_exc_info(self, is_called_proc_error=False):
        """generate an exception traceback"""
        try:
            if is_called_proc_error:
                raise subprocess.CalledProcessError(4, 'mycmd', 'my out')
            else:
                raise Exception("foo")
        except:
            ex_type, ex, tb = sys.exc_info()
        return (ex_type, ex, tb)

    def test_run_clone_exception(self):
        ex_t, ex, tb = self.make_exc_info()

        def clone_se():
            raise ex

        with patch('%s.clone_repo' % pb) as mock_clone, \
                patch('%s.run_build' % pb) as mock_run, \
                patch('%s.rmtree' % pbm) as mock_rmtree, \
                patch('%s.sys.exc_info' % pbm) as mock_excinfo, \
                patch('%s.get_time' % pb) as mock_time:
            mock_clone.side_effect = clone_se
            mock_run.return_value = 'my output'
            mock_time.side_effect = [
                datetime(2015, 1, 1, 1, 0, 0),
                datetime(2015, 1, 1, 2, 0, 0),
            ]
            mock_excinfo.return_value = ex_t, ex, tb
            self.cls.run()
        assert mock_clone.mock_calls == [call()]
        assert mock_run.mock_calls == []
        assert self.bi.mock_calls == [
            call.set_local_build(return_code=-1, excinfo=ex,
                                 ex_type=ex_t, traceback=tb)
        ]
        assert mock_rmtree.mock_calls == []

    def test_run_subprocess_error(self):
        ex_t, ex, tb = self.make_exc_info(True)

        def se_ex(foo):
            raise ex

        with patch('%s.clone_repo' % pb) as mock_clone, \
                patch('%s.run_build' % pb) as mock_run, \
                patch('%s.rmtree' % pbm) as mock_rmtree, \
                patch('%s.sys.exc_info' % pbm) as mock_excinfo, \
                patch('%s.get_time' % pb) as mock_time:
            mock_clone.return_value = ('/my/clone/path', 'repostr')
            mock_run.side_effect = se_ex
            mock_time.side_effect = [
                datetime(2015, 1, 1, 1, 0, 0),
                datetime(2015, 1, 1, 2, 0, 0),
            ]
            mock_excinfo.return_value = ex_t, ex, tb
            self.cls.run()
        assert mock_clone.mock_calls == [call()]
        assert mock_run.mock_calls == [call('/my/clone/path')]
        assert self.bi.mock_calls == [
            call.set_local_build(excinfo=ex, output='my out', return_code=4,
                                 ex_type=ex_t, traceback=tb,
                                 start_dt=datetime(2015, 1, 1, 1, 0, 0),
                                 end_dt=datetime(2015, 1, 1, 2, 0, 0),
                                 repo_str='repostr')
        ]
        assert mock_rmtree.mock_calls == [call('/my/clone/path')]

    def test_run_other_exception(self):
        ex_t, ex, tb = self.make_exc_info()

        def se_ex(foo):
            raise ex

        with patch('%s.clone_repo' % pb) as mock_clone, \
                patch('%s.run_build' % pb) as mock_run, \
                patch('%s.rmtree' % pbm) as mock_rmtree, \
                patch('%s.sys.exc_info' % pbm) as mock_excinfo, \
                patch('%s.get_time' % pb) as mock_time:
            mock_clone.return_value = ('/my/clone/path', 'repostr')
            mock_run.side_effect = se_ex
            mock_time.side_effect = [
                datetime(2015, 1, 1, 1, 0, 0),
                datetime(2015, 1, 1, 2, 0, 0),
            ]
            mock_excinfo.return_value = ex_t, ex, tb
            self.cls.run()
        assert mock_clone.mock_calls == [call()]
        assert mock_run.mock_calls == [call('/my/clone/path')]
        assert self.bi.mock_calls == [
            call.set_local_build(excinfo=ex, ex_type=ex_t, traceback=tb,
                                 start_dt=datetime(2015, 1, 1, 1, 0, 0),
                                 end_dt=datetime(2015, 1, 1, 2, 0, 0),
                                 repo_str='repostr')
        ]
        assert mock_rmtree.mock_calls == [call('/my/clone/path')]

    @freeze_time('2015-01-10 12:13:14')
    def test_get_time(self):
        res = self.cls.get_time()
        assert res == FakeDatetime(2015, 1, 10, 12, 13, 14)

    def test_clone_repo(self):
        type(self.bi).ssh_clone_url = 'ssh_url'
        type(self.bi).https_clone_url = 'https_url'

        mock_repo = Mock(name='mock_repo')
        mock_repo.head.ref.name = 'rname'
        mock_repo.head.ref.commit.hexsha = 'mysha'

        with patch('%s.path_for_repo' % pb) as mock_path, \
                patch('%s.Repo.clone_from' % pbm) as mock_clone:
            mock_path.return_value = '/repo/path'
            mock_clone.return_value = mock_repo
            res = self.cls.clone_repo()
        assert mock_path.mock_calls == [call()]
        assert mock_clone.mock_calls[0] == call(
            'ssh_url', '/repo/path', branch='master'
        )
        assert res == ('/repo/path', '<ssh_url> rname (mysha)')

    def test_clone_repo_ssh_fail(self):
        type(self.bi).ssh_clone_url = 'ssh_url'
        type(self.bi).https_clone_url = 'https_url'
        ex = Exception('foo')

        mock_repo = Mock(name='mock_repo')
        mock_repo.head.ref.name = 'rname'
        mock_repo.head.ref.commit.hexsha = 'mysha'

        def se_clone(url, path, branch=None):
            if url == 'ssh_url':
                raise ex
            return mock_repo

        with patch('%s.path_for_repo' % pb) as mock_path, \
                patch('%s.Repo.clone_from' % pbm) as mock_clone:
            mock_path.return_value = '/repo/path'
            mock_clone.side_effect = se_clone
            res = self.cls.clone_repo(branch='mybranch')
        assert mock_path.mock_calls == [call()]
        assert mock_clone.mock_calls[0] == call.clone_from(
            'ssh_url', '/repo/path', branch='mybranch'
        )
        assert mock_clone.mock_calls[1] == call.clone_from(
            'https_url', '/repo/path', branch='mybranch'
        )
        assert res == ('/repo/path', '<https_url> rname (mysha)')

    def test_clone_repo_all_fail(self):
        type(self.bi).ssh_clone_url = 'ssh_url'
        type(self.bi).https_clone_url = 'https_url'
        ex1 = Exception('foo')
        ex2 = Exception('bar')

        def se_clone(url, path, branch=None):
            if url == 'ssh_url':
                raise ex1
            raise ex2

        with patch('%s.path_for_repo' % pb) as mock_path, \
                patch('%s.Repo' % pbm) as mock_repo:
            mock_path.return_value = '/repo/path'
            mock_repo.clone_from.side_effect = se_clone
            with pytest.raises(Exception) as excinfo:
                self.cls.clone_repo(branch='mybranch')
        assert mock_path.mock_calls == [call()]
        assert mock_repo.mock_calls == [
            call.clone_from('ssh_url', '/repo/path', branch='mybranch'),
            call.clone_from('https_url', '/repo/path', branch='mybranch'),
        ]
        assert excinfo.value == ex2

    def test_clone_repo_dry_run(self):
        type(self.bi).ssh_clone_url = 'ssh_url'
        type(self.bi).https_clone_url = 'https_url'
        self.cls.dry_run = True
        ex = Exception('foo')

        def se_clone(url, path, branch=None):
            if url == 'ssh_url':
                raise ex
            return True

        with patch('%s.path_for_repo' % pb) as mock_path, \
                patch('%s.Repo' % pbm) as mock_repo, \
                patch('%s.logger' % pbm) as mock_logger:
            mock_path.return_value = '/repo/path'
            mock_repo.clone_from.side_effect = se_clone
            res = self.cls.clone_repo()
        assert mock_path.mock_calls == [call()]
        assert mock_repo.mock_calls == []
        assert mock_logger.mock_calls == [
            call.debug("Cloning %s branch %s into: %s", 'my/repo', 'master',
                       '/repo/path'),
            call.info("DRY RUN - not actually cloning %s into %s", 'my/repo',
                      '/repo/path')
        ]
        assert res == ('/repo/path', '(DRY RUN)')

    def test_path_for_repo(self):
        with patch('%s.mkdtemp' % pbm) as mock_mkdtemp:
            mock_mkdtemp.return_value = '/tmpdir'
            res = self.cls.path_for_repo()
        assert res == '/tmpdir'
        assert mock_mkdtemp.mock_calls == [call(prefix='rebuildbot_')]

    @pytest.mark.skipif(
        (
                sys.version_info[0] != 2 or
                (sys.version_info[0] == 2 and sys.version_info[1] != 7)
        ),
        reason='not running py27 test on %d.%d.%d' % (
                sys.version_info[0],
                sys.version_info[1],
                sys.version_info[2]
        ))
    def test_run_build_success_py27(self):
        with patch('%s.os.getcwd' % pbm) as mock_getcwd, \
                patch('%s.os.chdir' % pbm) as mock_chdir, \
                patch('%s.subprocess' % pbm, autospec=True) as mock_subprocess:
            mock_getcwd.return_value = '/my/pwd'
            res = self.cls.run_build('/repo/path')
        assert mock_getcwd.mock_calls == [call()]
        assert mock_chdir.mock_calls == [
            call('/repo/path'),
            call('/my/pwd')
        ]
        assert mock_subprocess.mock_calls == [
            call.check_output(
                ['./.rebuildbot.sh'],
                stderr=mock_subprocess.STDOUT
            )
        ]
        assert res == mock_subprocess.check_output.return_value

    @pytest.mark.skipif(
        (
                sys.version_info[0] != 2 or
                (sys.version_info[0] == 2 and sys.version_info[1] != 7)
        ),
        reason='not running py27 test on %d.%d.%d' % (
                sys.version_info[0],
                sys.version_info[1],
                sys.version_info[2]
        ))
    def test_run_build_exception_py27(self):
        ex = Exception('foo')

        def se_exc(foo, stderr=None):
            raise ex

        with patch('%s.os.getcwd' % pbm) as mock_getcwd, \
                patch('%s.os.chdir' % pbm) as mock_chdir, \
                patch('%s.subprocess' % pbm, autospec=True) as mock_subprocess:
            mock_getcwd.return_value = '/my/pwd'
            mock_subprocess.check_output.side_effect = se_exc
            with pytest.raises(Exception) as excinfo:
                self.cls.run_build('/repo/path')
        assert mock_getcwd.mock_calls == [call()]
        assert mock_chdir.mock_calls == [
            call('/repo/path'),
            call('/my/pwd')
        ]
        assert mock_subprocess.mock_calls == [
            call.check_output(
                ['./.rebuildbot.sh'],
                stderr=mock_subprocess.STDOUT
            )
        ]
        assert excinfo.value == ex

    @pytest.mark.skipif(
        (
                sys.version_info[0] != 2 or
                (sys.version_info[0] == 2 and sys.version_info[1] != 7)
        ),
        reason='not running py27 test on %d.%d.%d' % (
                sys.version_info[0],
                sys.version_info[1],
                sys.version_info[2]
        ))
    def test_run_build_dry_run_py27(self):
        self.cls.dry_run = True

        with patch('%s.os.getcwd' % pbm) as mock_getcwd, \
                patch('%s.os.chdir' % pbm) as mock_chdir, \
                patch('%s.subprocess' % pbm, autospec=True) as mock_subprocess:
            mock_getcwd.return_value = '/my/pwd'
            res = self.cls.run_build('/repo/path')
        assert mock_getcwd.mock_calls == []
        assert mock_chdir.mock_calls == []
        assert mock_subprocess.mock_calls == []
        assert res == 'DRY RUN'

    @pytest.mark.skipif(sys.version_info[0] < 3,
                        reason='not running py3 test on %d.%d.%d' % (
                            sys.version_info[0],
                            sys.version_info[1],
                            sys.version_info[2]
                        ))
    def test_run_build_success_py3(self):
        mock_res = Mock()
        with patch('%s.os.getcwd' % pbm) as mock_getcwd, \
                patch('%s.os.chdir' % pbm) as mock_chdir, \
                patch('%s.subprocess' % pbm, autospec=True) as mock_subprocess,\
                patch('%s.locale' % pbm, autospec=True) as mock_locale:
            mock_getcwd.return_value = '/my/pwd'
            mock_locale.getdefaultlocale.return_value = ['foo', 'bar']
            mock_locale.return_value = ['foo', 'bar']
            mock_subprocess.check_output.return_value = mock_res
            res = self.cls.run_build('/repo/path')
        assert mock_getcwd.mock_calls == [call()]
        assert mock_chdir.mock_calls == [
            call('/repo/path'),
            call('/my/pwd')
        ]
        assert mock_subprocess.mock_calls == [
            call.check_output(
                ['./.rebuildbot.sh'],
                stderr=mock_subprocess.STDOUT
            ),
            call.check_output().decode('bar')
        ]
        assert res == mock_res.decode.return_value
        assert mock_res.mock_calls == [
            call.decode('bar')
        ]

    @pytest.mark.skipif(sys.version_info[0] < 3,
                        reason='not running py3 test on %d.%d.%d' % (
                            sys.version_info[0],
                            sys.version_info[1],
                            sys.version_info[2]
                        ))
    def test_run_build_exception_py3(self):
        ex = Exception('foo')

        def se_exc(foo, stderr=None):
            raise ex

        with patch('%s.os.getcwd' % pbm) as mock_getcwd, \
                patch('%s.os.chdir' % pbm) as mock_chdir, \
                patch('%s.subprocess' % pbm, autospec=True) as mock_subprocess,\
                patch('%s.locale' % pbm) as mock_locale:
            mock_getcwd.return_value = '/my/pwd'
            mock_locale.getdefaultlocale.return_value = ['foo', 'bar']
            mock_subprocess.check_output.side_effect = se_exc
            with pytest.raises(Exception) as excinfo:
                self.cls.run_build('/repo/path')
        assert mock_getcwd.mock_calls == [call()]
        assert mock_chdir.mock_calls == [
            call('/repo/path'),
            call('/my/pwd')
        ]
        assert mock_subprocess.mock_calls == [
            call.check_output(
                ['./.rebuildbot.sh'],
                stderr=mock_subprocess.STDOUT
            )
        ]
        assert excinfo.value == ex

    @pytest.mark.skipif(sys.version_info[0] < 3,
                        reason='not running py3 test on %d.%d.%d' % (
                            sys.version_info[0],
                            sys.version_info[1],
                            sys.version_info[2]
                        ))
    def test_run_build_dry_run_py3(self):
        self.cls.dry_run = True

        with patch('%s.os.getcwd' % pbm) as mock_getcwd, \
                patch('%s.os.chdir' % pbm) as mock_chdir, \
                patch('%s.subprocess' % pbm, autospec=True) as mock_subprocess,\
                patch('%s.locale' % pbm) as mock_locale:
            mock_getcwd.return_value = '/my/pwd'
            mock_locale.getdefaultlocale.return_value = ['foo', 'bar']
            res = self.cls.run_build('/repo/path')
        assert mock_getcwd.mock_calls == []
        assert mock_chdir.mock_calls == []
        assert mock_subprocess.mock_calls == []
        assert res == 'DRY RUN'
