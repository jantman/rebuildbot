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
import logging
from contextlib import nested
from rebuildbot.bot import ReBuildBot
from rebuildbot.travis import Travis

# https://code.google.com/p/mock/issues/detail?id=249
# py>=3.4 should use unittest.mock not the mock package on pypi
if (
        sys.version_info[0] < 3 or
        sys.version_info[0] == 3 and sys.version_info[1] < 4
):
    from mock import patch, call, Mock
else:
    from unittest.mock import patch, call, Mock

pbm = 'rebuildbot.bot'  # patch base path for this module
pb = 'rebuildbot.bot.ReBuildBot'  # patch base for class


class TestReBuildBotInit(object):

    def test_init(self):
        with nested(
                patch('%s.get_github_token' % pb),
                patch('%s.connect_github' % pb),
                patch('%s.Travis' % pbm),
                patch('%s.connect_s3' % pb),
        ) as (
            mock_get_gh_token,
            mock_connect_gh,
            mock_travis,
            mock_connect_s3,
        ):
            mock_get_gh_token.return_value = 'myGHtoken'
            cls = ReBuildBot()
        assert mock_get_gh_token.mock_calls == [call()]
        assert mock_connect_gh.mock_calls == [call()]
        assert mock_travis.mock_calls == [call('myGHtoken')]
        assert mock_connect_s3.mock_calls == [call()]
        assert cls.gh_token == 'myGHtoken'
        assert cls.github == mock_connect_gh.return_value
        assert cls.travis == mock_travis.return_value
        assert cls.s3 == mock_connect_s3.return_value


class TestReBuildBot(object):

    def setup(self):
        self.mock_github = Mock()
        self.mock_travis = Mock(spec_set=Travis)
        self.mock_s3 = Mock()

        with patch('%s.__init__' % pb, Mock(return_value=None)):
            self.cls = ReBuildBot()
            self.cls.gh_token = 'myGHtoken'
            self.cls.github = self.mock_github
            self.cls.travis = self.mock_travis
            self.cls.s3 = self.mock_s3
