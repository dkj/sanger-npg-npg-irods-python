# -*- coding: utf-8 -*-
#
# Copyright © 2023 Genome Research Ltd. All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# @author Keith James <kdj@sanger.ac.uk>

import argparse
import sys

import sqlalchemy
import structlog
from sqlalchemy.orm import Session

from npg_irods.cli.util import add_logging_arguments, configure_logging
from npg_irods.db import DBConfig
from npg_irods.utilities import update_secondary_metadata
from npg_irods.version import version

description = """
Reads iRODS data object and/or collection paths from a file or STDIN, one per line and
updates any standard sample and/or study metadata and access permissions to reflect
the current state in the ML warehouse.

To generate a list of paths to be updated, see `locate-data-objects` in this package.

Currently this script supports:

 - Illumina sequencing data objects for data that have not been through the
   library-merge process.

 - Oxford nanopore sequencing data collections.

If any of the paths could not be updated, the exit code will be non-zero and an
error message summarising the results will be sent to STDERR.
"""

parser = argparse.ArgumentParser(
    description=description, formatter_class=argparse.RawDescriptionHelpFormatter
)
add_logging_arguments(parser)

parser.add_argument(
    "--database-config",
    "--database_config",
    "--db-config",
    "--db_config",
    help="Configuration file for database connection.",
    type=argparse.FileType("r"),
    required=True,
)
parser.add_argument(
    "-i",
    "--input",
    help="Input filename.",
    type=argparse.FileType("r"),
    default=sys.stdin,
)
parser.add_argument(
    "-o",
    "--output",
    help="Output filename.",
    type=argparse.FileType("w"),
    default=sys.stdout,
)
parser.add_argument(
    "--print-update",
    help="Print to output those paths that were updated. Defaults to True.",
    action="store_true",
)
parser.add_argument(
    "--print-fail",
    help="Print to output those paths that require updating, where the update failed. "
    "Defaults to False.",
    action="store_true",
)
parser.add_argument(
    "-c",
    "--clients",
    help="Number of baton clients to use. Defaults to 4.",
    type=int,
    default=4,
)
parser.add_argument(
    "-t",
    "--threads",
    help="Number of threads to use. Defaults to 4.",
    type=int,
    default=4,
)
parser.add_argument(
    "--version", help="Print the version and exit.", action="store_true"
)
parser.add_argument(
    "--zone",
    help="Specify a federated iRODS zone in which to find data objects and/or "
    "collections to update. This is not required if the target paths "
    "are on the local zone.",
    type=str,
)

args = parser.parse_args()
configure_logging(
    config_file=args.log_config,
    debug=args.debug,
    verbose=args.verbose,
    colour=args.colour,
    json=args.json,
)
log = structlog.get_logger("main")


def main():
    if args.version:
        print(version())
        exit(0)

    dbconfig = DBConfig.from_file(args.database_config.name, "mlwh_ro")

    engine = sqlalchemy.create_engine(dbconfig.url)
    with Session(engine) as session:
        num_processed, num_updated, num_errors = update_secondary_metadata(
            args.input,
            args.output,
            session,
            print_update=args.print_update,
            print_fail=args.print_fail,
        )

        if num_errors:
            log.error(
                "Update failed",
                num_processed=num_processed,
                num_updated=num_updated,
                num_errors=num_errors,
            )
            exit(1)

        msg = (
            "All updates were successful" if num_updated else "No updates were required"
        )
        log.info(
            msg,
            num_processed=num_processed,
            num_updated=num_updated,
            num_errors=num_errors,
        )
