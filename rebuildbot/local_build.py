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
        pass
        # NOTE: be sure to respect dry_run here; it should output everything
        #  that would be done - what would be cloned where, and the script
        #  and then update the build_info object appropriately to signal a
        #  finished local build run.
        """
        - For local builds, we'll do these once Travis is started, but before
        we poll travis. For each one, we'll do the git clone, get it on the
        branch we want, and then start the local build. We'll capture output
        and stderr and the exit code, and put that to an S3 bucket. Once that's
        done, we'll update a result dict with the exit code (boolean, 0 or not)
        and a link to the S3 bucket output.
        """
