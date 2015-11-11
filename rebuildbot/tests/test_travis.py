"""
rebuildbot/tests/test_travis.py

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
from requests import Response

from rebuildbot.travis import (Travis, CHECK_WAIT_TIME, POLL_NUM_TIMES)
from rebuildbot.exceptions import (PollTimeoutException, TravisTriggerError)

from travispy import TravisPy
from travispy.entities.repo import Repo
from travispy.entities.user import User
from travispy.entities.build import Build

from freezegun import freeze_time

# https://code.google.com/p/mock/issues/detail?id=249
# py>=3.4 should use unittest.mock not the mock package on pypi
if (
        sys.version_info[0] < 3 or
        sys.version_info[0] == 3 and sys.version_info[1] < 4
):
    from mock import patch, call, Mock
else:
    from unittest.mock import patch, call, Mock

pbm = 'rebuildbot.travis'  # patch base path for this module
pb = 'rebuildbot.travis.Travis'  # patch base for class


class TestTravisInit(object):
    """Test the rebuildbot.travis.Travis constructor"""

    def test_init(self):
        with patch('%s.TravisPy.github_auth' % pbm) as mock_travispy:
            mock_user = Mock()
            type(mock_user).login = 'mylogin'
            type(mock_user).email = 'myemail'
            type(mock_user).id = 'mockid'
            mock_travispy.return_value.user.return_value = mock_user
            cls = Travis('mytoken')
            assert mock_travispy.mock_calls == [
                call('mytoken'),
                call().user()
            ]
            assert cls.travis == mock_travispy.return_value


class TestTravis(object):
    """Test rebuildbot.travis.Travis non-constructor methods, with mocked
    constructor"""

    def setup(self):
        self.mock_travis = Mock(spec_set=TravisPy)
        self.mock_user = Mock(spec_set=User)
        type(self.mock_user).login = 'mylogin'
        type(self.mock_user).email = 'myemail'
        type(self.mock_user).id = 'myid'

        with patch('%s.__init__' % pb, Mock(return_value=None)):
            self.cls = Travis('mytoken')
            self.cls.travis = self.mock_travis
            self.cls.user = self.mock_user

    def test_get_repos(self):

        def se_build(r):
            if r.slug == 'mylogin/foo':
                return False
            return True

        r1 = Mock(spec_set=Repo)
        type(r1).slug = 'mylogin/foo'
        r2 = Mock(spec_set=Repo)
        type(r2).slug = 'otherlogin/foo'
        r3 = Mock(spec_set=Repo)
        type(r3).slug = 'mylogin/bar'
        self.mock_travis.repos.return_value = [r1, r2, r3]
        with patch('%s.repo_build_in_last_day' % pb) as mock_build:
            mock_build.side_effect = se_build
            res = self.cls.get_repos()
        assert res == ['mylogin/foo']
        assert self.mock_travis.mock_calls == [
            call.repos(member='mylogin')
        ]
        assert mock_build.mock_calls == [
            call(r1),
            call(r3)
        ]

    def test_get_repos_date_check_false(self):
        r1 = Mock(spec_set=Repo)
        type(r1).slug = 'mylogin/foo'
        r2 = Mock(spec_set=Repo)
        type(r2).slug = 'otherlogin/foo'
        r3 = Mock(spec_set=Repo)
        type(r3).slug = 'mylogin/bar'
        self.mock_travis.repos.return_value = [r1, r2, r3]
        with patch('%s.repo_build_in_last_day' % pb) as mock_build:
            mock_build.return_value = True
            res = self.cls.get_repos(date_check=False)
        assert res == ['mylogin/bar', 'mylogin/foo']
        assert self.mock_travis.mock_calls == [
            call.repos(member='mylogin')
        ]
        assert mock_build.mock_calls == []

    @freeze_time('2015-01-10 01:00:00')
    def test_repo_build_in_last_day_true(self):
        mock_repo = Mock(spec_set=Repo)
        mock_repo.last_build.started_at = '2015-01-10T00:45:00Z'
        assert self.cls.repo_build_in_last_day(mock_repo) is True

    @freeze_time('2015-01-10 01:00:00')
    def test_repo_build_in_last_day_false(self):
        mock_repo = Mock(spec_set=Repo)
        mock_repo.last_build.started_at = '2015-01-02T12:45:12Z'
        assert self.cls.repo_build_in_last_day(mock_repo) is False

    def test_run_build(self):
        mock_repo = Mock(spec_set=Repo)
        mock_build = Mock(spec_set=Build)
        type(mock_build).id = 1
        type(mock_repo).last_build = mock_build
        self.mock_travis.repo.return_value = mock_repo

        with patch('%s.wait_for_new_build' % pb) as mock_wait:
            mock_wait.return_value = 2
            with patch('%s.trigger_travis' % pb) as mock_trigger:
                res = self.cls.run_build('mylogin/reponame')
        assert res == (1, 2)
        assert self.mock_travis.mock_calls == [
            call.repo('mylogin/reponame')
        ]
        assert mock_trigger.mock_calls == [
            call('mylogin/reponame', branch='master')
        ]
        assert mock_wait.mock_calls == [call('mylogin/reponame', 1)]

    def test_run_build_branch(self):
        mock_repo = Mock(spec_set=Repo)
        mock_build = Mock(spec_set=Build)
        type(mock_build).id = 1
        type(mock_repo).last_build = mock_build
        self.mock_travis.repo.return_value = mock_repo

        with patch('%s.wait_for_new_build' % pb) as mock_wait:
            mock_wait.return_value = 2
            with patch('%s.trigger_travis' % pb) as mock_trigger:
                res = self.cls.run_build('mylogin/reponame', branch='foo')
        assert res == (1, 2)
        assert self.mock_travis.mock_calls == [
            call.repo('mylogin/reponame')
        ]
        assert mock_trigger.mock_calls == [
            call('mylogin/reponame', branch='foo')
        ]
        assert mock_wait.mock_calls == [call('mylogin/reponame', 1)]

    def test_run_build_timeout(self):
        mock_repo = Mock(spec_set=Repo)
        mock_build = Mock(spec_set=Build)
        type(mock_build).id = 1
        type(mock_repo).last_build = mock_build
        self.mock_travis.repo.return_value = mock_repo

        def wait_se(slug, old_id):
            raise PollTimeoutException('t', 'r', 1, 2)

        with patch('%s.wait_for_new_build' % pb) as mock_wait:
            mock_wait.side_effect = wait_se
            with patch('%s.trigger_travis' % pb) as mock_trigger:
                res = self.cls.run_build('mylogin/reponame')
        assert res == (1, None)
        assert self.mock_travis.mock_calls == [
            call.repo('mylogin/reponame')
        ]
        assert mock_trigger.mock_calls == [
            call('mylogin/reponame', branch='master')
        ]
        assert mock_wait.mock_calls == [call('mylogin/reponame', 1)]

    def test_wait_for_new_build_ok(self):
        mock_build = Mock(spec_set=Build)
        type(mock_build).id = 2

        with patch('%s.get_last_build' % pb) as mock_last_build:
            with patch('%s.time.sleep' % pbm) as mock_sleep:
                mock_last_build.return_value = mock_build
                res = self.cls.wait_for_new_build('mylogin/reponame', 1)
        assert res == 2
        assert mock_sleep.mock_calls == []
        assert mock_last_build.mock_calls == [call('mylogin/reponame')]

    def test_wait_for_new_build_ok_after_2(self):
        builds = []
        for x in range(0, 2):
            mock_build = Mock(spec_set=Build)
            type(mock_build).id = 1
            builds.append(mock_build)
        mock_build = Mock(spec_set=Build)
        type(mock_build).id = 2
        builds.append(mock_build)

        with patch('%s.get_last_build' % pb) as mock_last_build:
            with patch('%s.time.sleep' % pbm) as mock_sleep:
                mock_last_build.side_effect = builds
                res = self.cls.wait_for_new_build('mylogin/reponame', 1)
        assert res == 2
        assert mock_sleep.mock_calls == [
            call(CHECK_WAIT_TIME),
            call(CHECK_WAIT_TIME)
        ]
        assert mock_last_build.mock_calls == [
            call('mylogin/reponame'),
            call('mylogin/reponame'),
            call('mylogin/reponame')
        ]

    def test_wait_for_new_build_timeout(self):
        mock_build = Mock(spec_set=Build)
        type(mock_build).id = 1

        with patch('%s.get_last_build' % pb) as mock_last_build:
            with patch('%s.time.sleep' % pbm) as mock_sleep:
                mock_last_build.return_value = mock_build
                with pytest.raises(PollTimeoutException) as excinfo:
                    self.cls.wait_for_new_build('mylogin/reponame', 1)

        sleep_calls = []
        last_build_calls = []
        for x in range(0, POLL_NUM_TIMES):
            sleep_calls.append(call(CHECK_WAIT_TIME))
            last_build_calls.append(call('mylogin/reponame'))

        assert mock_sleep.mock_calls == sleep_calls
        assert mock_last_build.mock_calls == last_build_calls

        assert excinfo.value.poll_type == 'last_build.id'
        assert excinfo.value.repo == 'mylogin/reponame'
        assert excinfo.value.wait_time == CHECK_WAIT_TIME
        assert excinfo.value.num_times == POLL_NUM_TIMES

    def test_get_last_build(self):
        mock_build = Mock(spec_set=Build)
        mock_repo = Mock(spec_set=Repo)
        type(mock_repo).last_build = mock_build
        self.mock_travis.repo.return_value = mock_repo
        res = self.cls.get_last_build('a/b')
        assert res == mock_build
        assert self.mock_travis.mock_calls == [call.repo('a/b')]

    def test_trigger_travis_ok(self):
        mock_response = Mock(spec_set=Response)
        type(mock_response).status_code = 202
        type(mock_response).headers = {'response': 'headers'}
        type(mock_response).text = 'response_text'

        mock_session = Mock()
        mock_session.post.return_value = mock_response
        type(self.mock_travis)._session = mock_session

        self.mock_travis._HEADERS = {'foo': 'bar'}
        self.cls.trigger_travis('a/b')

        expected_url = 'http://api.travis-ci.org/repo/a%2Fb/requests'
        expected_json = {
            'request': {
                'branch': 'master',
                'message': 'triggered by https://github.com/jantman/rebuildbot',
            }
        }
        expected_headers = {
            'foo': 'bar',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Travis-API-Version': '3',
        }
        assert self.mock_travis._session.post.mock_calls == [
            call(expected_url, json=expected_json, headers=expected_headers)
        ]

    def test_trigger_travis_ok_branch(self):
        mock_response = Mock(spec_set=Response)
        type(mock_response).status_code = 202
        type(mock_response).headers = {'response': 'headers'}
        type(mock_response).text = 'response_text'

        mock_session = Mock()
        mock_session.post.return_value = mock_response
        type(self.mock_travis)._session = mock_session

        self.mock_travis._HEADERS = {'foo': 'bar'}
        self.cls.trigger_travis('a/b', branch='mybranch')

        expected_url = 'http://api.travis-ci.org/repo/a%2Fb/requests'
        expected_json = {
            'request': {
                'branch': 'mybranch',
                'message': 'triggered by https://github.com/jantman/rebuildbot',
            }
        }
        expected_headers = {
            'foo': 'bar',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Travis-API-Version': '3',
        }
        assert self.mock_travis._session.post.mock_calls == [
            call(expected_url, json=expected_json, headers=expected_headers)
        ]

    def test_trigger_travis_404(self):
        mock_response = Mock(spec_set=Response)
        type(mock_response).status_code = 404
        type(mock_response).headers = {'response': 'headers'}
        type(mock_response).text = 'response_text'

        mock_session = Mock()
        mock_session.post.return_value = mock_response
        type(self.mock_travis)._session = mock_session

        expected_url = 'http://api.travis-ci.org/repo/a%2Fb/requests'

        self.mock_travis._HEADERS = {'foo': 'bar'}
        with pytest.raises(TravisTriggerError) as excinfo:
            self.cls.trigger_travis('a/b')
        assert excinfo.value.repo == 'a/b'
        assert excinfo.value.branch == 'master'
        assert excinfo.value.url == expected_url
        assert excinfo.value.status_code == 404
        assert excinfo.value.headers == {'response': 'headers'}
        assert excinfo.value.text == 'response_text'

        expected_json = {
            'request': {
                'branch': 'master',
                'message': 'triggered by https://github.com/jantman/rebuildbot',
            }
        }
        expected_headers = {
            'foo': 'bar',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Travis-API-Version': '3',
        }
        assert self.mock_travis._session.post.mock_calls == [
            call(expected_url, json=expected_json, headers=expected_headers)
        ]

    def test_url_for_build(self):
        res = self.cls.url_for_build('a/b', 123)
        assert res == 'https://travis-ci.org/a/b/builds/123'

    def test_get_build(self):
        m = Mock()
        self.mock_travis.build.return_value = m
        res = self.cls.get_build(123)
        assert res == m
        assert self.mock_travis.mock_calls == [
            call.build(123),
            call.build().check_state()
        ]
