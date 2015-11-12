"""
rebuildbot/runner.py

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
import argparse
import logging

from .bot import ReBuildBot
from .version import _VERSION, _PROJECT_URL

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger()

# suppress boto internal logging below WARNING level
boto_log = logging.getLogger("boto")
boto_log.setLevel(logging.WARNING)
boto_log.propagate = True

# suppress requests internal logging below WARNING level
requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING)
requests_log.propagate = True

# suppress github internal logging below WARNING level
github_log = logging.getLogger("github")
github_log.setLevel(logging.WARNING)
github_log.propagate = True


class Runner(object):

    def parse_args(self, argv):
        """
        parse arguments/options

        :param argv: argument list to parse, usually ``sys.argv[1:]``
        :type argv: list
        :returns: parsed arguments
        :rtype: :py:class:`argparse.Namespace`
        """
        desc = 'Rebuildbot re-runs builds of your inactive projects.'
        # ###### IMPORTANT license notice ##########
        # Pursuant to Sections 5(b) and 13 of the GNU Affero General Public
        # License, version 3, this notice MUST NOT be removed, and MUST be
        # displayed to ALL USERS of this software, even if they interact with
        # it remotely over a network.
        #
        # See the "Development" section of the rebuildbot documentation
        # (docs/source/development.rst or
        # <http://rebuildbot.readthedocs.org/en/latest/development.html> )
        # for further information.
        # ###### IMPORTANT license notice ##########
        epilog = 'rebuildbot is AGPLv3-licensed Free Software. Anyone ' \
                 'using this program, even remotely over a network, is ' \
                 'entitled to a copy of the source code. Use `--version` for ' \
                 'information on the source code location.'
        p = argparse.ArgumentParser(description=desc, epilog=epilog)
        p.add_argument('-v', '--verbose', dest='verbose', action='count',
                       default=0,
                       help='verbose output. specify twice for debug-level '
                       'output.')
        p.add_argument('-V', '--version', dest='version', action='store_true',
                       default=False,
                       help='print version number and exit.')
        p.add_argument('-d', '--dry-run', dest='dry_run',
                       action='store_true', default=False,
                       help='log what would be done, and perform '
                       'normal output/notifications, but do not '
                       'actually run any tests')
        p.add_argument('-R', '--repo', dest='repos', action='append',
                       default=None, help='repository (user/repo name)'
                       'to test, instead of discovering all '
                       'possibilities. Can be specified multiple '
                       'times.')
        p.add_argument('-p', '--s3-prefix', dest='s3_prefix', type=str,
                       action='store', help='Prefix to prepend to all '
                       'keys created in S3 (default: rebuildbot)',
                       default='rebuildbot')
        p.add_argument('--no-date-check', dest='date_check',
                       action='store_false', default=True,
                       help='bypass commit date check on repos, '
                       'running local builds regardless of date of '
                       'last commit to master.')
        p.add_argument('--no-travis', dest='run_travis', default=True,
                       action='store_false',
                       help='skip running Travis builds (only run '
                       'local)')
        p.add_argument('--no-local', dest='run_local', default=True,
                       action='store_false',
                       help='skip running local builds (only run '
                       'Travis)')
        p.add_argument('BUCKET_NAME', action='store', type=str,
                       help='Name of S3 bucket to upload reports to')
        args = p.parse_args(argv)
        return args

    def console_entry_point(self):
        args = self.parse_args(sys.argv[1:])
        if args.verbose == 1:
            logger.setLevel(logging.INFO)
        elif args.verbose > 1:
            # debug-level logging hacks
            FORMAT = "[%(levelname)s %(filename)s:%(lineno)s - " \
                     "%(name)s.%(funcName)s() ] %(message)s"
            debug_formatter = logging.Formatter(fmt=FORMAT)
            logger.handlers[0].setFormatter(debug_formatter)
            logger.setLevel(logging.DEBUG)

        if args.version:
            print('rebuildbot {v} (see <{s}> for source code)'.format(
                s=_PROJECT_URL,
                v=_VERSION
            ))
            raise SystemExit(0)

        bot = ReBuildBot(args.BUCKET_NAME, s3_prefix=args.s3_prefix,
                         dry_run=args.dry_run, date_check=args.date_check,
                         run_local=args.run_local, run_travis=args.run_travis)
        bot.run(projects=args.repos)


def console_entry_point():
    r = Runner()
    r.console_entry_point()


if __name__ == "__main__":
    console_entry_point()
