"""
rebuildbot/tests/test_runner.py

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
import logging
from rebuildbot.runner import (Runner, console_entry_point)
from rebuildbot.version import (_VERSION, _PROJECT_URL)

# https://code.google.com/p/mock/issues/detail?id=249
# py>=3.4 should use unittest.mock not the mock package on pypi
if (
        sys.version_info[0] < 3 or
        sys.version_info[0] == 3 and sys.version_info[1] < 4
):
    from mock import patch, call, Mock
else:
    from unittest.mock import patch, call, Mock

pbm = 'rebuildbot.runner'  # patch base path for this module
pb = 'rebuildbot.runner.Runner'  # patch base for class


class TestConsoleEntryPoint(object):

    def test_console_entry_point(self):
        with patch(pb) as mock_runner:
            console_entry_point()
        assert mock_runner.mock_calls == [
            call(),
            call().console_entry_point()
        ]


class TestRunner(object):

    def setup(self):
        self.cls = Runner()

    def test_parse_args(self):
        desc = 'Rebuildbot re-runs builds of your inactive projects.'
        epi = 'rebuildbot is AGPLv3-licensed Free Software. Anyone ' \
              'using this program, even remotely over a network, is ' \
              'entitled to a copy of the source code. Use `--version` for ' \
              'information on the source code location.'
        with patch('%s.argparse.ArgumentParser' % pbm) as mock_parser:
            self.cls.parse_args([])
        assert mock_parser.mock_calls == [
            call(description=desc, epilog=epi),
            call().add_argument('-v', '--verbose', dest='verbose',
                                action='count', default=0,
                                help='verbose output. specify twice for '
                                'debug-level output.'),
            call().add_argument('-V', '--version', dest='version',
                                action='store_true', default=False,
                                help='print version number and exit.'),
            call().add_argument('-d', '--dry-run', dest='dry_run',
                                action='store_true', default=False,
                                help='log what would be done, and perform '
                                'normal output/notifications, but do not '
                                'actually run any tests'),
            call().add_argument('-R', '--repo', dest='repos', action='append',
                                default=None, help='repository (user/repo name)'
                                'to test, instead of discovering all '
                                'possibilities. Can be specified multiple '
                                'times.'),
            call().add_argument('-p', '--s3-prefix', dest='s3_prefix', type=str,
                                action='store', help='Prefix to prepend to all '
                                'keys created in S3 (default: rebuildbot)',
                                default='rebuildbot'),
            call().add_argument('--no-date-check', dest='date_check',
                                action='store_false', default=True,
                                help='bypass commit date check on repos, '
                                'running local builds regardless of date of '
                                'last commit to master.'),
            call().add_argument('--no-travis', dest='run_travis', default=True,
                                action='store_false',
                                help='skip running Travis builds (only run '
                                'local)'),
            call().add_argument('--no-local', dest='run_local', default=True,
                                action='store_false',
                                help='skip running local builds (only run '
                                'Travis)'),
            call().add_argument('-i', '--ignore', dest='ignore_repos',
                                default=[], action='append',
                                help='repository slugs (USER/REPO) to '
                                     'completely ignore'),
            call().add_argument('BUCKET_NAME', action='store', type=str,
                                help='Name of S3 bucket to upload reports to'),
            call().parse_args([]),
        ]

    def test_parse_args_verbose1(self):
        res = self.cls.parse_args(['-v', 'bktname'])
        assert res.verbose == 1
        assert res.date_check is True

    def test_parse_args_date_check(self):
        res = self.cls.parse_args(['--no-date-check', 'bktname'])
        assert res.date_check is False

    def test_parse_args_verbose2(self):
        res = self.cls.parse_args(['-vv', 'bktname'])
        assert res.verbose == 2

    def test_parse_args_version(self):
        res = self.cls.parse_args(['-V', 'bktname'])
        assert res.version is True

    def test_parse_args_dry_run(self):
        res = self.cls.parse_args(['-d', 'bktname'])
        assert res.dry_run is True

    def test_parse_args_no_ignore(self):
        res = self.cls.parse_args(['bktname'])
        assert res.ignore_repos == []

    def test_parse_args_ignore(self):
        res = self.cls.parse_args(['-i', 'foo', '--ignore=bar', 'bktname'])
        assert res.ignore_repos == ['foo', 'bar']

    def test_parse_args_no_repos(self):
        res = self.cls.parse_args(['-d', 'bktname'])
        assert res.repos is None

    def test_parse_args_s3_prefix(self):
        res = self.cls.parse_args(['--s3-prefix=foo', 'bktname'])
        assert res.s3_prefix == 'foo'
        assert res.BUCKET_NAME == 'bktname'

    def test_parse_args_one_repo(self):
        res = self.cls.parse_args(['-R', 'foo/bar', 'bktname'])
        assert res.repos == ['foo/bar']

    def test_parse_args_multiple_repos(self):
        res = self.cls.parse_args(
            ['-R', 'foo/bar', '-R', 'baz/blam', 'bktname']
        )
        assert res.repos == ['foo/bar', 'baz/blam']

    def test_parse_args_no_travis(self):
        res = self.cls.parse_args(['--no-travis', 'bktname'])
        assert res.run_travis is False
        assert res.run_local is True

    def test_parse_args_no_local(self):
        res = self.cls.parse_args(['--no-local', 'bktname'])
        assert res.run_travis is True
        assert res.run_local is False

    def test_console_entry_point(self):
        argv = ['/tmp/rebuildbot/runner.py', 'bktname']
        with patch.object(sys, 'argv', argv):
            with patch('%s.ReBuildBot' % pbm) as mock_bot, \
                 patch('%s.logger' % pbm) as mock_logger, \
                 patch('%s.log_capture_string' % pbm) as mock_lcs:
                self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call('bktname', s3_prefix='rebuildbot', dry_run=False,
                 date_check=True, run_travis=True, run_local=True,
                 log_buffer=mock_lcs, ignore_repos=[]),
            call().run(projects=None)
        ]
        assert mock_logger.mock_calls == []

    def test_console_entry_point_no_date_check(self):
        argv = ['/tmp/rebuildbot/runner.py', '--no-date-check', 'bktname']
        with patch.object(sys, 'argv', argv):
            with patch('%s.ReBuildBot' % pbm) as mock_bot, \
                 patch('%s.logger' % pbm) as mock_logger, \
                 patch('%s.log_capture_string' % pbm) as mock_lcs:
                self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call('bktname', s3_prefix='rebuildbot', dry_run=False,
                 date_check=False, run_travis=True, run_local=True,
                 log_buffer=mock_lcs, ignore_repos=[]),
            call().run(projects=None)
        ]
        assert mock_logger.mock_calls == []

    def test_console_entry_point_prefix(self):
        argv = ['/tmp/rebuildbot/runner.py', '-p', 'my/prefix', 'bktname']
        with patch.object(sys, 'argv', argv):
            with patch('%s.ReBuildBot' % pbm) as mock_bot, \
                 patch('%s.logger' % pbm) as mock_logger, \
                 patch('%s.log_capture_string' % pbm) as mock_lcs:
                self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call('bktname', s3_prefix='my/prefix', dry_run=False,
                 date_check=True, run_travis=True, run_local=True,
                 log_buffer=mock_lcs, ignore_repos=[]),
            call().run(projects=None)
        ]
        assert mock_logger.mock_calls == []

    def test_console_entry_point_projects(self):
        argv = ['/tmp/rebuildbot/runner.py', '-R', 'foo/bar', '-R', 'baz/blam',
                'bktname']
        with patch.object(sys, 'argv', argv):
            with patch('%s.ReBuildBot' % pbm) as mock_bot, \
                 patch('%s.logger' % pbm) as mock_logger, \
                 patch('%s.log_capture_string' % pbm) as mock_lcs:
                self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call('bktname', s3_prefix='rebuildbot', dry_run=False,
                 date_check=True, run_travis=True, run_local=True,
                 log_buffer=mock_lcs, ignore_repos=[]),
            call().run(projects=['foo/bar', 'baz/blam'])
        ]
        assert mock_logger.mock_calls == []

    def test_console_entry_point_dry_run(self):
        argv = ['/tmp/rebuildbot/runner.py', '--dry-run', 'bktname']
        with patch.object(sys, 'argv', argv):
            with patch('%s.ReBuildBot' % pbm) as mock_bot, \
                 patch('%s.logger' % pbm) as mock_logger, \
                 patch('%s.log_capture_string' % pbm) as mock_lcs:
                self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call('bktname', s3_prefix='rebuildbot', dry_run=True,
                 date_check=True, run_travis=True, run_local=True,
                 log_buffer=mock_lcs, ignore_repos=[]),
            call().run(projects=None)
        ]
        assert mock_logger.mock_calls == []

    def test_console_entry_point_version(self, capsys):
        argv = ['/tmp/rebuildbot/runner.py', '-V', 'bktname']
        with patch.object(sys, 'argv', argv):
            with patch('%s.ReBuildBot' % pbm) as mock_bot, \
                 patch('%s.logger' % pbm) as mock_logger, \
                 patch('%s.log_capture_string' % pbm):
                with pytest.raises(SystemExit) as excinfo:
                    self.cls.console_entry_point()
        assert excinfo.value.code == 0
        assert mock_bot.mock_calls == []
        assert mock_logger.mock_calls == []
        out, err = capsys.readouterr()
        assert err == ''
        assert out == 'rebuildbot ' + _VERSION + ' (see <' + _PROJECT_URL + \
            '> for source code)' + "\n"

    def test_console_entry_point_verbose1(self):
        argv = ['/tmp/rebuildbot/runner.py', '-v', 'bktname']
        with patch.object(sys, 'argv', argv):
            with patch('%s.ReBuildBot' % pbm) as mock_bot, \
                 patch('%s.logger' % pbm) as mock_logger, \
                 patch('%s.capture_handler' % pbm) as mock_cap_handler, \
                 patch('%s.log_capture_string' % pbm) as mock_lcs:
                self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call('bktname', s3_prefix='rebuildbot', dry_run=False,
                 date_check=True, run_travis=True, run_local=True,
                 log_buffer=mock_lcs, ignore_repos=[]),
            call().run(projects=None)
        ]
        assert mock_logger.mock_calls == [
            call.setLevel(logging.INFO)
        ]
        assert mock_cap_handler.mock_calls == [
            call.setLevel(logging.INFO)
        ]

    def test_console_entry_point_verbose2(self):
        argv = ['/tmp/rebuildbot/runner.py', '-vv', 'bktname']
        with patch.object(sys, 'argv', argv):
            with patch('%s.ReBuildBot' % pbm) as mock_bot, \
                 patch('%s.logger' % pbm) as mock_logger, \
                 patch('%s.logging.Formatter' % pbm) as mock_formatter, \
                 patch('%s.capture_handler' % pbm) as mock_cap_handler, \
                 patch('%s.log_capture_string' % pbm) as mock_lcs:
                mock_handler = Mock()
                mock_handler2 = Mock()
                type(mock_logger).handlers = [mock_handler, mock_handler2]
                self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call('bktname', s3_prefix='rebuildbot', dry_run=False,
                 date_check=True, run_travis=True, run_local=True,
                 log_buffer=mock_lcs, ignore_repos=[]),
            call().run(projects=None)
        ]

        FORMAT = "[%(levelname)s %(filename)s:%(lineno)s - " \
                 "%(name)s.%(funcName)s() ] %(message)s"
        assert mock_formatter.mock_calls == [call(fmt=FORMAT)]
        assert mock_handler.mock_calls == [
            call.setFormatter(mock_formatter.return_value)
        ]
        assert mock_handler2.mock_calls == [
            call.setFormatter(mock_formatter.return_value)
        ]
        assert mock_logger.mock_calls == [
            call.setLevel(logging.DEBUG)
        ]
        assert mock_cap_handler.mock_calls == [
            call.setLevel(logging.DEBUG)
        ]

    def test_console_entry_point_no_travis(self):
        argv = ['/tmp/rebuildbot/runner.py', '--no-travis', 'bktname']
        with patch.object(sys, 'argv', argv):
            with patch('%s.ReBuildBot' % pbm) as mock_bot, \
                 patch('%s.logger' % pbm) as mock_logger, \
                 patch('%s.log_capture_string' % pbm) as mock_lcs:
                self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call('bktname', s3_prefix='rebuildbot', dry_run=False,
                 date_check=True, run_travis=False, run_local=True,
                 log_buffer=mock_lcs, ignore_repos=[]),
            call().run(projects=None)
        ]
        assert mock_logger.mock_calls == []

    def test_console_entry_point_no_local(self):
        argv = ['/tmp/rebuildbot/runner.py', '--no-local', 'bktname']
        with patch.object(sys, 'argv', argv):
            with patch('%s.ReBuildBot' % pbm) as mock_bot, \
                 patch('%s.logger' % pbm) as mock_logger, \
                 patch('%s.log_capture_string' % pbm) as mock_lcs:
                self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call('bktname', s3_prefix='rebuildbot', dry_run=False,
                 date_check=True, run_travis=True, run_local=False,
                 log_buffer=mock_lcs, ignore_repos=[]),
            call().run(projects=None)
        ]
        assert mock_logger.mock_calls == []

    def test_console_entry_point_ignore_repos(self):
        argv = [
            '/tmp/rebuildbot/runner.py',
            '-i', 'foo/bar',
            '--ignore=foo/baz',
            'bktname'
        ]
        with patch.object(sys, 'argv', argv):
            with patch('%s.ReBuildBot' % pbm) as mock_bot, \
                 patch('%s.logger' % pbm) as mock_logger, \
                 patch('%s.log_capture_string' % pbm) as mock_lcs:
                self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call('bktname', s3_prefix='rebuildbot', dry_run=False,
                 date_check=True, run_travis=True, run_local=True,
                 log_buffer=mock_lcs,
                 ignore_repos=['foo/bar', 'foo/baz']),
            call().run(projects=None)
        ]
        assert mock_logger.mock_calls == []
