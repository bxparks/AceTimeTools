#!/usr/bin/env python3
#
# Copyright 2018 Brian T. Park
#
# MIT License
"""
The command line interface for ZoneProcessor class and zonedb files for
debugging. Previous version of this was embedded directly inside
zone_processor.py. See the examples below.

TODO: The output format should provide an easy, human-readable list of
transitions so that we can verify that the AceTime scripts are extracting and
processing the TZDB information correctly. A --debug flag can print more
detailed information about the internal implementation to help debugging.

Examples:

    # America/Los_Angeles for 2018-03-10T02:00:00
    $ ./zinfo.py --zone America/Los_Angeles --date 2019-03-10T01:59
    UTC-08:00+00:00 (PST)

    $ ./zinfo.py --zone America/Los_Angeles --date 2019-03-10T02:00
    Invalid time

    $ ./zinfo.py --zone America/Los_Angeles --date 2019-03-10T03:00
    UTC-08:00+01:00 (PDT)

    $ ./zinfo.py --zone America/Los_Angeles --date 2019-11-03T01:00
    UTC-08:00+01:00 (PDT)

    $ ./zinfo.py --zone America/Los_Angeles --date 2019-11-03T01:59
    UTC-08:00+01:00 (PDT)

    $ ./zinfo.py --zone America/Los_Angeles --date 2019-11-03T02:00
    UTC-08:00+00:00 (PST)

    # America/Indiana/Petersburg for the year 2006.
    $ ./zinfo.py --zone America/Indiana/Petersburg --year 2006

    # America/Indiana/Indianapolis for the year 2006.
    $ ./zinfo.py --zone America/Indiana/Indianapolis --year 2006

    # Australia/Darwin for the year 2006.
    $ ./zinfo.py --zone Australia/Darwin --year 2006

    # America/Darwin for the year 2006.
    $ ./zinfo.py --zone America/Adak --year 2000 --debug
"""

import sys
import argparse
import logging
from typing import cast
from datetime import datetime

from acetime.typing import ZoneInfo
from acetime.zonedb import zone_registry
from acetime.common import to_utc_string
from acetime.zone_processor import ZoneProcessor


def main() -> None:
    # Configure command line flags.
    parser = argparse.ArgumentParser(description='Zone Agent.')
    parser.add_argument(
        '--transition',
        help='Print the transition instead of timezone info',
        action='store_true')
    parser.add_argument(
        '--debug', help='Print debugging info', action='store_true')
    parser.add_argument('--zone', help='Name of time zone', required=True)
    parser.add_argument('--year', help='Year of interest', type=int)
    parser.add_argument('--date', help='DateTime of interest')
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Find the zone.
    zone_info = cast(ZoneInfo, zone_registry.ZONE_REGISTRY.get(args.zone))
    if not zone_info:
        logging.error("Zone '%s' not found", args.zone)
        sys.exit(1)

    # Create the ZoneProcessor for zone
    zone_processor = ZoneProcessor(
        zone_info=zone_info,
        debug=args.debug,
    )

    if args.year:
        zone_processor.init_for_year(args.year)
        if args.debug:
            logging.info('==== Final matches and transitions')
        zone_processor.print_matches_and_transitions()
    elif args.date:
        dt: datetime = datetime.strptime(args.date, "%Y-%m-%dT%H:%M")
        if args.transition:
            transition = zone_processor.get_transition_for_datetime(dt)
            if transition:
                logging.info(transition)
            else:
                logging.error('Transition not found')
        else:
            offset_info = zone_processor.get_timezone_info_for_datetime(dt)
            if not offset_info:
                logging.info('Invalid time')
            else:
                logging.info(
                    '%s (%s)',
                    to_utc_string(
                        offset_info.utc_offset,
                        offset_info.dst_offset,
                    ),
                    offset_info.abbrev,
                )
    else:
        print("One of --year or --date must be provided")
        sys.exit(1)


if __name__ == '__main__':
    main()
