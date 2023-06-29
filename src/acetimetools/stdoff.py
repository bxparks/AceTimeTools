#!/usr/bin/env python3
#
# Copyright 2018 Brian T. Park
#
# MIT License.

"""
Read the raw TZ Database files at the location specified by `--input_dir`.
Print a list of (zone, stdoff(int), stdoff(string)) in a file named `stdoff.txt`
in the `--output_dir`.

Example:
$ stdoff.py --input_dir ../tzfile --output_dir . --tz_version 2023c
"""

import argparse
import logging
import sys
import datetime

from acetimetools.extractor.extractor import Extractor
from acetimetools.generator.stdoffgenerator import StdoffGenerator


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate Zone Info.')

    # Extractor flags.
    parser.add_argument(
        '--input_dir', help='Location of the input directory', required=True)

    # Target location of the generated files.
    parser.add_argument(
        '--output_dir',
        help='Location of the output directory',
        default='',
    )
    # The tz_version does not affect any data processing. Its value is
    # copied into the various generated files and usually placed in the
    # comments section to describe the source of the data that generated the
    # various files.
    parser.add_argument(
        '--tz_version',
        help='Version string of the TZ files',
        required=True,
    )

    # Parse the command line arguments
    args = parser.parse_args()

    # Configure logging. This should normally be executed after the
    # parser.parse_args() because it allows us set the logging.level using a
    # flag.
    logging.basicConfig(level=logging.INFO)

    # How the script was invoked
    invocation = ' '.join(sys.argv)

    # Extract the TZ files
    logging.info('======== Extracting TZ Data files')
    extractor = Extractor(args.input_dir)
    extractor.parse()
    extractor.print_summary()
    policies_map, zones_map, links_map = extractor.get_data()

    # Generate the stdoff list.
    logging.info('==== Creating stdoff.txt file')
    now = datetime.datetime.now()
    generator = StdoffGenerator(
        invocation=invocation,
        tz_version=args.tz_version,
        year=now.year,
        zones_map=zones_map,
        links_map=links_map,
    )
    generator.generate_files(args.output_dir)


if __name__ == '__main__':
    main()
