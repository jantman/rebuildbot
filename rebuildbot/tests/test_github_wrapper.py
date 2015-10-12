"""
rebuildbot/tests/test_github_wrapper.py

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
import datetime
from base64 import b64encode
from contextlib import nested

from github import Github
from github.AuthenticatedUser import AuthenticatedUser
from github.Repository import Repository
from github.Branch import Branch
from github.Commit import Commit
from github.GitCommit import GitCommit
from github.GitAuthor import GitAuthor
from github.GithubException import UnknownObjectException
from github.ContentFile import ContentFile

from rebuildbot.github_wrapper import GitHubWrapper

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

pbm = 'rebuildbot.github_wrapper'  # patch base path for this module
pb = 'rebuildbot.github_wrapper.GitHubWrapper'  # patch base for class


class TestGitHubWrapperInit(object):

    def test_init(self):
        with patch('%s.Github' % pbm) as mock_github:
            cls = GitHubWrapper('mytoken')
        assert mock_github.mock_calls == [call('mytoken')]
        assert cls.github == mock_github.return_value


class TestGitHubWrapper(object):

    def setup(self):
        self.mock_github = Mock(spec_set=Github)
        with patch('%s.__init__' % pb, Mock(return_value=None)):
            self.cls = GitHubWrapper()
            self.cls.github = self.mock_github
            self.cls.token = 'mytoken'

    def test_find_projects(self):

        def se_404(fname):
            raise UnknownObjectException(404, 'some data')

        content1 = b64encode("my file content")
        mock_content1 = Mock(spec_set=ContentFile)
        type(mock_content1).content = content1
        mock_repo1 = Mock(spec_set=Repository)
        type(mock_repo1).full_name = 'myuser/foo'
        mock_repo1.get_file_contents.return_value = mock_content1
        type(mock_repo1).clone_url = 'cloneurl'
        type(mock_repo1).ssh_url = 'sshurl'

        mock_repo2 = Mock(spec_set=Repository)
        type(mock_repo2).full_name = 'myuser/bar'

        mock_repo3 = Mock(spec_set=Repository)
        type(mock_repo3).full_name = 'myuser/baz'
        mock_repo3.get_file_contents.side_effect = se_404

        with nested(
                patch('%s.get_repos' % pb),
                patch('%s.repo_commit_in_last_day' % pb),
                patch('%s.logger' % pbm),
        ) as (
            mock_get_repos,
            mock_last_day,
            mock_logger,
        ):
            mock_get_repos.return_value = [
                mock_repo1, mock_repo2, mock_repo3
            ]
            mock_last_day.side_effect = [False, True, False]
            res = self.cls.find_projects()

        assert res == {
            'myuser/foo': ('my file content', 'cloneurl', 'sshurl')
        }
        assert mock_logger.mock_calls == [
            call.debug("Skipping repository '%s' - commit on master in "
                       "last day", 'myuser/bar'),
            call.debug("Skipping repository '%s' - .rebuildbot.sh not "
                       "present", 'myuser/baz'),
        ]

    def test_get_project_config(self):
        content1 = b64encode("my file content")
        mock_content1 = Mock(spec_set=ContentFile)
        type(mock_content1).content = content1
        mock_repo1 = Mock(spec_set=Repository)
        type(mock_repo1).full_name = 'myuser/foo'
        mock_repo1.get_file_contents.return_value = mock_content1
        type(mock_repo1).clone_url = 'cloneurl'
        type(mock_repo1).ssh_url = 'sshurl'

        self.cls.github.get_repo.return_value = mock_repo1
        res = self.cls.get_project_config('me/myrepo')
        assert res == ('my file content', 'cloneurl', 'sshurl')
        assert self.cls.github.mock_calls == [
            call.get_repo('me/myrepo'),
            call.get_repo().get_file_contents('.rebuildbot.sh', ref='master')
        ]
        assert mock_repo1.mock_calls == [
            call.get_file_contents('.rebuildbot.sh', ref='master')
        ]

    def test_get_project_config_404(self):

        def se_404(fname, ref='master'):
            raise UnknownObjectException(404, 'some data')

        mock_repo1 = Mock(spec_set=Repository)
        type(mock_repo1).full_name = 'myuser/foo'
        mock_repo1.get_file_contents.side_effect = se_404

        self.cls.github.get_repo.return_value = mock_repo1
        res = self.cls.get_project_config('me/myrepo')
        assert res == (None, None, None)
        assert self.cls.github.mock_calls == [
            call.get_repo('me/myrepo'),
            call.get_repo().get_file_contents('.rebuildbot.sh', ref='master')
        ]
        assert mock_repo1.mock_calls == [
            call.get_file_contents('.rebuildbot.sh', ref='master')
        ]

    def test_get_repos(self):
        mock_user = Mock(spec_set=AuthenticatedUser)
        type(mock_user).login = 'myuser'

        mock_repo1 = Mock(spec_set=Repository)
        type(mock_repo1).full_name = 'myuser/foo'
        type(mock_repo1).owner = Mock(login='myuser')
        mock_repo2 = Mock(spec_set=Repository)
        type(mock_repo2).full_name = 'someorg/foo'
        type(mock_repo2).owner = Mock(login='someorg')
        mock_repo3 = Mock(spec_set=Repository)
        type(mock_repo3).full_name = 'myuser/bar'
        type(mock_repo3).owner = Mock(login='myuser')

        mock_user.get_repos.return_value = [mock_repo1, mock_repo2, mock_repo3]
        self.cls.github.get_user.return_value = mock_user

        res = self.cls.get_repos()
        assert res == [mock_repo1, mock_repo3]

    @freeze_time('2015-01-10 12:13:14')
    def test_repo_commit_in_last_day_false(self):
        mock_repo = Mock(spec_set=Repository)
        type(mock_repo).full_name = 'myuser/foo'
        type(mock_repo).owner = Mock(login='myuser')

        mock_author = Mock(spec_set=GitAuthor)
        type(mock_author).date = datetime.datetime(2015, 1, 1, 2, 3, 4)
        mock_commit_commit = Mock(spec_set=GitCommit)
        type(mock_commit_commit).author = mock_author
        mock_commit = Mock(spec_set=Commit)
        type(mock_commit).sha = 'myCommitSHA'
        type(mock_commit).commit = mock_commit_commit
        mock_branch = Mock(spec_set=Branch)
        type(mock_branch).commit = mock_commit
        mock_repo.get_branch.return_value = mock_branch

        res = self.cls.repo_commit_in_last_day(mock_repo)
        assert res is False
        assert mock_repo.mock_calls == [call.get_branch('master')]

    @freeze_time('2015-01-10 12:13:14')
    def test_repo_commit_in_last_day_true(self):
        mock_repo = Mock(spec_set=Repository)
        type(mock_repo).full_name = 'myuser/foo'
        type(mock_repo).owner = Mock(login='myuser')

        mock_author = Mock(spec_set=GitAuthor)
        type(mock_author).date = datetime.datetime(2015, 1, 10, 10, 1, 2)
        mock_commit_commit = Mock(spec_set=GitCommit)
        type(mock_commit_commit).author = mock_author
        mock_commit = Mock(spec_set=Commit)
        type(mock_commit).sha = 'myCommitSHA'
        type(mock_commit).commit = mock_commit_commit
        mock_branch = Mock(spec_set=Branch)
        type(mock_branch).commit = mock_commit
        mock_repo.get_branch.return_value = mock_branch

        res = self.cls.repo_commit_in_last_day(mock_repo)
        assert res is True
        assert mock_repo.mock_calls == [call.get_branch('master')]
