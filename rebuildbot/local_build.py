"""
rebuildbot/local_build.py

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

import os
import sys
import datetime
import logging
import subprocess
import locale
from tempfile import mkdtemp
from shutil import rmtree

from git import Repo

logger = logging.getLogger()


class LocalBuild(object):
    """
    Class to handle running a local build and updating the BuildInfo object
    with the results.
    """

    def __init__(self, repo_name, build_info, dry_run=False):
        """
        :param repo_name: full name / slug of the repository to build
        :type repo_name: string
        :param build_info: the BuildInfo object for this build
        :type build_info: :py:class:`~.BuildInfo`
        :param dry_run: if True, do not actually clone or run the build
        :type dry_run: bool
        """
        self.repo_name = repo_name
        self.build_info = build_info
        self.dry_run = dry_run

    def run(self):
        """
        Run the local build and update `self.build_info` with the result. If
        `self.dry_run` is True, log everything that would be done and then
        update the object.
        """
        logger.info('Starting local build of %s', self.repo_name)
        try:
            repo_path, repo_str = self.clone_repo()
        except Exception as ex:
            logger.exception("Exception while cloning %s", self.repo_name)
            ex_type, ex, tb = sys.exc_info()
            self.build_info.set_local_build(excinfo=ex, return_code=-1,
                                            ex_type=ex_type, traceback=tb)
            return
        try:
            start = self.get_time()
            output = self.run_build(repo_path)
            return_code = 0
            logger.debug("Local build completed.")
        except subprocess.CalledProcessError as ex:
            logger.exception("Subprocess exception while running local build "
                             "of %s", self.repo_name)
            ex_type, ex, tb = sys.exc_info()
            self.build_info.set_local_build(
                excinfo=ex,
                output=ex.output,
                return_code=ex.returncode,
                ex_type=ex_type,
                traceback=tb,
                start_dt=start,
                end_dt=self.get_time(),
                repo_str=repo_str
            )
            logger.debug("shutil.rmtree(%s)", repo_path)
            rmtree(repo_path)
            return
        except Exception as ex:
            logger.exception("Unexpected exception while running local build "
                             "of %s", self.repo_name)
            ex_type, ex, tb = sys.exc_info()
            self.build_info.set_local_build(excinfo=ex, ex_type=ex_type,
                                            traceback=tb, start_dt=start,
                                            end_dt=self.get_time(),
                                            repo_str=repo_str)
            logger.debug("shutil.rmtree(%s)", repo_path)
            rmtree(repo_path)
            return
        self.build_info.set_local_build(return_code=return_code, output=output,
                                        start_dt=start, end_dt=self.get_time(),
                                        repo_str=repo_str)
        logger.debug("shutil.rmtree(%s)", repo_path)
        rmtree(repo_path)

    def get_time(self):
        """
        Helper to make testing easier - return datetime.datetime.now()
        """
        return datetime.datetime.now()

    def clone_repo(self, branch='master'):
        """
        Clone the repository. Return a 2-tuple of (path on disk, string
        describing the state of the repo)
        """
        path = self.path_for_repo()
        logger.debug("Cloning %s branch %s into: %s", self.repo_name, branch,
                     path)
        if self.dry_run:
            logger.info("DRY RUN - not actually cloning %s into %s",
                        self.repo_name, path)
            return (path, '(DRY RUN)')
        excinfo = None
        for url in [
                self.build_info.ssh_clone_url,
                self.build_info.https_clone_url
        ]:
            try:
                logger.debug("Cloning %s into %s", url, path)
                repo = Repo.clone_from(
                    url,
                    path,
                    branch=branch
                )
                logger.debug("Cloned %s to %s", url, path)
                br_name = repo.head.ref.name
                sha = repo.head.ref.commit.hexsha
                repo_str = '<%s> %s (%s)' % (url, br_name, sha)
                return (path, repo_str)
            except Exception as ex:
                excinfo = ex
        raise excinfo

    def run_build(self, repo_path):
        """
        Helper method to actually run the build.

        :param repo_path: the absolute path to the repository clone
        :type repo_path: string
        :raises: exception
        :returns: string combined STDOUT/STDERR
        :rtype: string
        :raises: subprocess.CalledProcessError
        """
        if self.dry_run:
            return "DRY RUN"
        oldpwd = os.getcwd()
        logger.debug("os.chdir(%s)", repo_path)
        os.chdir(repo_path)
        try:
            script_path = os.path.join(repo_path, '.rebuildbot.sh')
            logger.info("Running: %s" % script_path)
            res = subprocess.check_output(
                ['./.rebuildbot.sh'],
                stderr=subprocess.STDOUT
            )
            if sys.version_info >= (3, 0):
                res = res.decode(locale.getdefaultlocale()[1])
            logger.debug("os.chdir(%s)", oldpwd)
            os.chdir(oldpwd)
        except Exception as ex:
            logger.debug("os.chdir(%s)", oldpwd)
            os.chdir(oldpwd)
            # any CalledProcessError is handled in self.run()
            raise ex
        return res

    def path_for_repo(self):
        """
        Determine where to clone the repo to.

        :returns: absolute path to clone the repo at
        :rtype: string
        """
        path = mkdtemp(prefix='rebuildbot_')
        return path
