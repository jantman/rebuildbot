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
from contextlib import nested
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
            call().parse_args([]),
        ]

    def test_parse_args_none(self):
        res = self.cls.parse_args([])
        assert res.verbose == 0
        assert res.version is False

    def test_parse_args_verbose1(self):
        res = self.cls.parse_args(['-v'])
        assert res.verbose == 1
        assert res.version is False

    def test_parse_args_verbose2(self):
        res = self.cls.parse_args(['-vv'])
        assert res.verbose == 2
        assert res.version is False

    def test_parse_args_version(self):
        res = self.cls.parse_args(['-V'])
        assert res.verbose == 0
        assert res.version is True

    def test_console_entry_point(self):
        argv = ['/tmp/rebuildbot/runner.py']
        with nested(
                patch.object(sys, 'argv', argv),
                patch('%s.ReBuildBot' % pbm),
                patch('%s.logger' % pbm),
        ) as (foo, mock_bot, mock_logger):
            self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call(),
            call().run()
        ]
        assert mock_logger.mock_calls == []

    def test_console_entry_point_version(self, capsys):
        argv = ['/tmp/rebuildbot/runner.py', '-V']
        with nested(
                patch.object(sys, 'argv', argv),
                patch('%s.ReBuildBot' % pbm),
                patch('%s.logger' % pbm),
        ) as (foo, mock_bot, mock_logger):
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
        argv = ['/tmp/rebuildbot/runner.py', '-v']
        with nested(
                patch.object(sys, 'argv', argv),
                patch('%s.ReBuildBot' % pbm),
                patch('%s.logger' % pbm),
        ) as (foo, mock_bot, mock_logger):
            self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call(),
            call().run()
        ]
        assert mock_logger.mock_calls == [
            call.setLevel(logging.INFO)
        ]

    def test_console_entry_point_verbose2(self):
        argv = ['/tmp/rebuildbot/runner.py', '-vv']
        with nested(
                patch.object(sys, 'argv', argv),
                patch('%s.ReBuildBot' % pbm),
                patch('%s.logger' % pbm),
                patch('%s.logging.Formatter' % pbm),
        ) as (foo, mock_bot, mock_logger, mock_formatter):
            mock_handler = Mock()
            type(mock_logger).handlers = [mock_handler]
            self.cls.console_entry_point()
        assert mock_bot.mock_calls == [
            call(),
            call().run()
        ]

        FORMAT = "[%(levelname)s %(filename)s:%(lineno)s - " \
                 "%(name)s.%(funcName)s() ] %(message)s"
        assert mock_formatter.mock_calls == [call(fmt=FORMAT)]
        assert mock_handler.mock_calls == [
            call.setFormatter(mock_formatter.return_value)
        ]
        assert mock_logger.mock_calls == [
            call.setLevel(logging.DEBUG)
        ]
