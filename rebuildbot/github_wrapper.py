"""
rebuildbot/github_wrapper.py

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

import logging
import datetime
from base64 import b64decode

from github import Github
from github.GithubException import UnknownObjectException

logger = logging.getLogger(__name__)


class GitHubWrapper(object):
    """
    ReBuildBot wrapper around PyGithub
    """

    def __init__(self, token):
        """connect to GitHub with the given token"""
        self.token = token
        logger.debug("Connecting to GitHub API")
        self.github = Github(token)
        logger.debug("Connected to GitHub API")

    def find_projects(self):
        """
        Iterate all GitHub repositories and find any with a .rebuildbot.sh;
        remove from this set any which have had a commit on master in the last
        24 hours. Return the result as a dict, where keys are the repository
        full name / slug, and values are the contents of .rebuildbot.sh in the
        repository.

        @returns: dict of repository slug strings to .rebuildbot.sh content str
        @rtype: dict
        """
        projects = {}
        for repo in self.get_repos():
            if self.repo_commit_in_last_day(repo):
                logger.debug("Skipping repository '%s' - commit on master in "
                             "last day", repo.full_name)
                continue
            try:
                config = repo.get_file_contents('.rebuildbot.sh')
            except UnknownObjectException:
                logger.debug("Skipping repository '%s' - .rebuildbot.sh not "
                             "present", repo.full_name)
                continue
            projects[repo.full_name] = b64decode(config.content)
        return projects

    def get_project_config(self, repo_full_name, branch='master'):
        """
        Given the full name to a repository, return the content of
        .rebuildbot.sh or None if not present.

        @param repo_full_name: the full name / slug for the repo
        @type repo_full_name: string
        @param branch_name: the branch name to check
        @type branch_name: string
        """
        repo = self.github.get_repo(repo_full_name)
        try:
            config = repo.get_file_contents('.rebuildbot.sh', ref=branch)
        except UnknownObjectException:
            logger.debug("Skipping repository '%s' - .rebuildbot.sh not "
                         "present", repo.full_name)
            return None
        return b64decode(config.content)

    def get_repos(self):
        """
        return a list of all GitHub repositories owned by the current user (this
        excludes repositories owned by organizations, or that the current user
        is a contributor to)

        @returns: list of :py:class:`github.github.Repository` objects
        @rtype: list of :py:class:`github.github.Repository`
        """
        repos = []
        user = self.github.get_user()
        for repo in user.get_repos():
            if repo.owner.login != user.login:
                logger.debug("Skipping repository owned by another user: %s",
                             repo.full_name)
                continue
            repos.append(repo)
        return repos

    def repo_commit_in_last_day(self, repo_obj, branch_name='master'):
        """
        Return true if the specified branch of the repo has a HEAD commit within
        the last day, False otherwise.

        @param repo_obj: the repository to inspect
        @type repo_obj: :py:class:`github.github.Repository`
        @param branch_name: the branch name to check
        @type branch_name: string
        @returns: True if the last commit is within the last day, else False
        @rtype: boolean
        """
        branch = repo_obj.get_branch(branch_name)
        # branch.commit is the HEAD commit of the branch
        dt = branch.commit.commit.author.date
        logger.debug("Repo %s - found HEAD commit of %s as %s on %s",
                     repo_obj.full_name, branch_name, branch.commit.sha,
                     dt)
        age = datetime.datetime.now() - dt
        if age > datetime.timedelta(days=1):
            return False
        return True
