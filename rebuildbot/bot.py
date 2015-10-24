"""
rebuildbot/bot.py

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
import os
import shutil
import logging
import time
from datetime import datetime
from platform import node as platform_node
from getpass import getuser

import pytz
import tzlocal

from jinja2 import Environment, PackageLoader

import boto
from boto.s3.key import Key

from travispy.errors import TravisError

from .travis import Travis
from .exceptions import GitTokenMissingError, PollTimeoutException
from .github_wrapper import GitHubWrapper
from .buildinfo import BuildInfo
from .local_build import LocalBuild
from .version import _VERSION

# python3 ConfigParser
if sys.version_info[0] < 3:
    from ConfigParser import SafeConfigParser
    from ConfigParser import (NoSectionError, NoOptionError)
    from StringIO import StringIO
else:  # nocoverage
    from configparser import ConfigParser as SafeConfigParser
    from configparser import (NoSectionError, NoOptionError)
    from io import StringIO

logger = logging.getLogger(__name__)


class ReBuildBot(object):
    """
    Main class for ReBuildBot - this is where everything happens.
    """

    def __init__(self, bucket_name, s3_prefix='rebuildbot', dry_run=False,
                 date_check=True):
        """
        Initialize ReBuildBot and attempt to connect to all external services.

        :param bucket_name: the name of the S3 bucket to write results to
        :type bucket_name: str
        :param s3_prefix: prefix to prepend to all keys in S3 bucket
        :type s3_prefix: str
        :param dry_run: log what would be done, and perform normal output/
          notifications, but do not actually run any tests
        :type dry_run: boolean
        :param date_check: whether or not to skip running local builds on repos
        with a commit to master in the last 24 hours; if True, skip those repos
        :type date_check: bool
        """
        self.s3_prefix = s3_prefix
        self.date_check = date_check
        self.gh_token = self.get_github_token()
        self.github = GitHubWrapper(self.gh_token)
        self.travis = Travis(self.gh_token)
        self.bucket = self.connect_s3(bucket_name)
        self.bucket_endpoint = None
        self.dry_run = dry_run
        """mapping of repository slugs to BuildInfo objects"""
        self.builds = {}

    def run(self, projects=None):
        """
        Main entry point for ReBuildBot.

        Build either a specified list of projects (by GitHub repository name),
        or else all projects found from Travis and GitHub.
        Send notifications when done.

        :param projects: list of project/repository full names (slugs) to build,
        if building a subset of all
        :type projects: list of strings
        """
        self.builds = self.find_projects(projects)
        self.start_travis_builds()
        # @TODO probably need a timeout here
        while self.have_work_to_do:
            self.runner_loop()
        self.handle_results()

    def runner_loop(self):
        """
        Main loop that polls Travis for build results, and runs local builds.

        Loop first polls all non-complete Travis builds for their result, and
        if the build has completed, updates the appropriate ``self.builds``
        object. After each Travis polling cycle, one local build is run to
        completion (serially).

        This logic is optimized to reduce load on the host machine by running
        local builds serially. Maybe this should be changed at some point, but
        since my use case is mainly running
        `Beaker <https://github.com/puppetlabs/beaker/>`_ tests for Puppet
        modules, which spin up VirtualBox machines, I only want one running
        at a time.
        """
        travis_updates = self.poll_travis_updates()
        ran_local = False
        for name, bi in sorted(self.builds.items()):
            if bi.run_local and bi.local_build_finished is False:
                b = LocalBuild(name, bi, dry_run=self.dry_run)
                b.run()
                ran_local = True
                break
        if not ran_local and not travis_updates:
            logger.info("No Travis builds updated and no local builds to run; "
                        "sleeping 10 seconds")
            time.sleep(10)

    @property
    def have_work_to_do(self):
        """
        Return True while we have Travis builds running or local builds left
        to run; False otherwise.

        :returns: whether there are builds running or remaining to run
        :rtype: boolean
        """
        for name, bi in self.builds.items():
            if not bi.is_done:
                return True
        return False

    def handle_results(self):
        """
        Once all builds are complete, collect the results, upload the relevant
        information to S3, and then build the final report and send it.
        """
        prefix = self.get_s3_prefix()
        self.write_local_output(prefix)
        report = self.generate_report(prefix)
        url = self.write_to_s3(prefix, 'index.html', report, ctype='text/html')
        logger.info("Full report written to: %s", url)

    def generate_report(self, prefix):
        """
        Generate the overall HTML report for this run.

        :param prefix: the prefix to write S3 files under, or local files under
        :type prefix: str
        :returns: generated report HTML
        :rytpe: str
        """
        env = Environment(
            loader=PackageLoader('rebuildbot', 'templates'),
            extensions=['jinja2.ext.loopcontrols']
        )
        template = env.get_template('report.html')

        date_s = datetime.now(pytz.utc).astimezone(tzlocal.get_localzone())
        date_s = date_s.strftime('%Y-%m-%d %H:%M:%S%z %Z')

        run_info = {
            'version': _VERSION,
            'date_s': date_s,
            'host': platform_node(),
            'user': getuser(),
            'bucket': self.bucket.name,
            'prefix': prefix,
        }
        build_infos = self.get_build_info_html_list()

        html = template.render(run_info=run_info, builds=build_infos)
        return html

    def get_build_info_html_list(self):
        """
        Return a list of 3-tuples for builds, in sorted order, each one being
        (build_name, travis_html, local_html).

        :rtype: tuple
        """
        res = []
        for name, bi in sorted(self.builds.items()):
            res.append(
                (name, bi.make_travis_html(), bi.make_local_build_html())
            )
        return res

    def get_s3_prefix(self):
        """
        Return the full prefix to use for objects in S3.

        :returns: full prefix to use for objects in S3
        :rtype: str
        """
        if self.dry_run:
            logger.warning("DRY RUN: Not uploading to S3; files will be written"
                           " locally under './s3_content/'")
            if os.path.exists('s3_content'):
                logger.info("Removing ./s3_content")
                shutil.rmtree('s3_content')
            logger.info("Creating directory ./s3_content")
            os.mkdir('s3_content')
            return 's3_content'
        dt_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        prefix = os.path.join(self.s3_prefix, dt_str)
        return prefix

    def write_to_s3(self, prefix, fname, content, ctype='text/plain'):
        """
        Write ``content`` into S3 at ``prefix``/``fname``. If ``self.dry_run``,
        write to local disk instead. Return the resulting URL, either an S3
        URL or a local 'file://' URL.

        :param prefix: the prefix to write S3 files under, or local files under
        :type prefix: str
        :param fname: the file name to create
        :type fname: str
        :param content: the content to write into the file
        :type content: str
        :returns: URL to the created file
        :rtype: str
        """
        path = os.path.join(prefix, fname)
        if self.dry_run:
            path = os.path.abspath(path)
            logger.warning("DRY RUN: Writing s3-bound content to %s", path)
            dest_dir = os.path.dirname(path)
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            with open(path, 'w') as fh:
                fh.write(content)
            return 'file://%s' % path
        # else write to S3
        logger.debug("Creating S3 key: %s", path)
        k = Key(self.bucket)
        k.key = path
        k.set_contents_from_string(content)
        k.set_metadata('Content-Type', ctype)
        url = self.url_for_s3(path)
        logger.debug("Data written to %s", url)
        return url

    def write_local_output(self, prefix):
        """
        Write output for all local builds to S3 (or local filesystem if dry_run)
        under ``prefix``.

        :param prefix: the prefix to write S3 files under, or local files under
        :type prefix: str
        :rtype: None
        """
        for proj_name, build_obj in sorted(self.builds.items()):
            content = build_obj.local_build_output_str
            logger.debug("Writing local output to S3 for %s", proj_name)
            url = self.write_to_s3(prefix, proj_name, content)
            build_obj.set_local_build_s3_link(url)

    def url_for_s3(self, path):
        """
        Given a path to a key in ``self.bucket``, return the URL to that path.

        :param path: a key path in S3
        :type path: str
        :returns: HTTP URL to path
        :rtype: str
        """
        u = 'http://%s/%s' % (self.bucket_endpoint, path)
        return u

    def find_projects(self, projects):
        """
        Find which projects to run, and create an :py:class:`~.BuildInfo` object
        for each project. Return a dict of project/repo name to BuildInfo obj.

        If ``projects`` is not None, use only those repository names. Otherwise,
        call :py:meth:`~.GitHubWrapper.get_find_projects` and
        :py:meth:`~.Travis.get_repos` to find the eligible projects.

        :param projects: list of project/repository full names (slugs) to build,
        if building a subset of all
        :type projects: list of strings
        :returns: dict of repo/project name to BuildInfo object for each repo.
        :rtype: dict
        """
        builds = {}
        if projects is None:
            logger.info("Finding candidate projects from Travis and GitHub")
            # GitHub
            for repo, tup in self.github.find_projects(
                    date_check=self.date_check).items():
                https_clone_url, ssh_clone_url = tup
                builds[repo] = BuildInfo(repo, run_local=True,
                                         https_clone_url=https_clone_url,
                                         ssh_clone_url=ssh_clone_url)
            # Travis
            for repo in self.travis.get_repos():
                if repo not in builds:
                    builds[repo] = BuildInfo(repo)
                builds[repo].run_travis = True
            return builds
        logger.info("Using explicit projects list: %s", projects)
        for project in projects:
            tup = self.github.get_project_config(project)
            https_clone_url, ssh_clone_url = tup
            run_local = True
            if https_clone_url is None and ssh_clone_url is None:
                run_local = False
            tmp_build = BuildInfo(project, run_local=run_local,
                                  https_clone_url=https_clone_url,
                                  ssh_clone_url=ssh_clone_url)
            try:
                self.travis.get_last_build(project)
                tmp_build.run_travis = True
            except TravisError:
                pass
            builds[project] = tmp_build
        return builds

    def connect_s3(self, bucket_name):
        """
        Connect to Amazon S3 via :py:func:`boto.connect_s3` and get a Bucket
        object for ``bucket_name``; return the Bucket.

        :param bucket_name: the name of the S3 bucket to write results to
        :type bucket_name: str
        :rtype: :py:class:`boto.s3.bucket.Bucket`
        """
        logger.debug("Connecting to S3")
        conn = boto.connect_s3()
        logger.debug("Getting S3 bucket %s", bucket_name)
        bucket = conn.get_bucket(bucket_name)
        logger.debug("Got bucket")
        self.bucket_endpoint = bucket.get_website_endpoint()
        return bucket

    def get_github_token(self):
        """
        Find your GitHub API token. First look in the ``GITHUB_TOKEN`` env
        variable, then look in ``~/.gitconfig``

        :rtype: string
        """
        e = os.environ.get('GITHUB_TOKEN', None)
        if e is not None:
            logger.debug("Using GITHUB_TOKEN env variable")
            return e
        # ConfigParser doesn't like leading spaces, which .gitconfig has
        with open(os.path.expanduser('~/.gitconfig'), 'r') as fh:
            config_lines = fh.readlines()
        config = SafeConfigParser()
        config.readfp(StringIO(''.join([l.lstrip() for l in config_lines])))
        try:
            token = config.get('github', 'token')
        except (NoSectionError, NoOptionError):
            raise GitTokenMissingError()
        logger.debug("Using GitHub token from ~/.gitconfig")
        return token

    def start_travis_builds(self):
        """
        Iterate all BuildInfo objects in ``self.builds``; for any with
        ``run_travis`` True, start a Travis build of the repository and update
        the BuildInfo object with the Build ID of the triggered build. If an
        error or exception is encountered while triggering the build, store it
        in the BuildInfo object and continue on.
        """
        started = 0
        errored = 0
        logger.info("Triggering Travis builds")
        for repo_slug, build_info in sorted(self.builds.items()):
            if (
                    not build_info.run_travis or
                    build_info.travis_build_finished
            ):
                continue
            if self.dry_run:
                logger.info("DRY RUN: would trigger Travis build of %s",
                            repo_slug)
                build_info.set_dry_run()
                continue
            try:
                old_id, new_id = self.travis.run_build(repo_slug)
                build_info.set_travis_build_ids(old_id, new_id)
            except Exception as ex:
                build_info.set_travis_trigger_error(ex)
                logger.exception(ex)
        logger.info("Finished triggering Travis builds; triggered %s "
                    "successfully, %s had errors being triggered", started,
                    errored)

    def poll_travis_updates(self):
        """
        For all Travis builds that have not yet completed, poll TravisCI to
        check if they've finished, and if so, update the BuildInfo object.

        Return True if anything changed, False otherwise.
        """
        have_changes = False
        logger.debug("Polling for Travis updates")
        for repo_slug, build_info in sorted(self.builds.items()):
            if self.dry_run:
                build_info.set_dry_run()
                continue
            if (
                    not build_info.run_travis or
                    build_info.travis_build_finished
            ):
                continue
            build_id = build_info.travis_build_id
            if build_id is None:
                # try to fetch a new build ID
                build_id = self.update_travis_build(build_info)
                # if we still didn't get a new build ID...
                if build_id is None:
                    logger.warning("Still have not gotten new Travis build ID "
                                   "for %s; skipping", repo_slug)
                    continue
                else:
                    have_changes = True
            t_build = self.travis.get_build(build_id)
            if t_build.finished:
                logger.debug("Build %s of %s has finished; updating",
                             build_info.travis_build_id, repo_slug)
                build_info.set_travis_build_finished(t_build)
                have_changes = True
            else:
                logger.debug("Build %s of %s still running",
                             build_info.travis_build_id, repo_slug)
        logger.debug("Completed updating Travis build status; have_changes=%s",
                     have_changes)
        return have_changes

    def update_travis_build(self, bi):
        """
        Given a BuildInfo object that we don't yet have a new build ID for,
        poll Travis to attempt to get the new Build ID. If we get one (newer
        than the last build ID), update ``bi`` with it and return it. Else,
        return None.

        :param bi: BuildInfo object to poll for
        :type bi: :py:class:`~.BuildInfo`
        :returns: new build ID or None
        :rtype: int
        """
        logger.debug("Checking for new build ID for %s (last ID %s)",
                     bi.slug, bi.travis_last_build_id)
        try:
            new = self.travis.wait_for_new_build(
                bi.slug, bi.travis_last_build_id
            )
        except PollTimeoutException:
            logger.exception("Still have not found new Build ID for %s",
                             bi.slug)
            return None
        bi.set_travis_build_ids(bi.travis_last_build_id, new)
        return new
