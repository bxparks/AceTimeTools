#!/usr/bin/env python3
#
# Copyright 2020 Brian T. Park
#
# MIT License.

"""
Parse the IANA TZ Database files located at the --input_dir and validate the
internal zonedb files using the Python ZoneProcessor class against pytz.
(Previous version of this was part of tzcompiler.py. Now extracted into
a separate script.)

Usage:
    validate.py [flags...]

Flags:

    The following flags are recognized and passed along into the various helper
    classes:

    Transformer:

        --scope (basic|extended)
        --start_year
        --until_year
        --granularity
        --until_at_granularity
        --offset_granularity
        --delta_granularity
        --strict, --nostrict

    TestDataGenerator:

        --validation_start_year
        --validation_until_year

    ZoneProcessor:

        --debug_processor

    Validator:

        --zone {zone_name}
        --year {year}
        --validate_dst_offset
        --debug_validator

Examples:

    See validate.sh.
"""

import argparse
import logging

from acetime.zonedb_types import ZoneInfoMap
from acetime.zonedb_types import ZonePolicyMap
from acetimetools.datatypes.attyping import TransformerResult
from acetimetools.extractor.extractor import Extractor
from acetimetools.transformer.transformer import Transformer
from acetimetools.zone_processor.zone_info_inliner import ZoneInfoInliner
from acetimetools.validator.validator import Validator


def validate(
    zone_infos: ZoneInfoMap,
    zone_policies: ZonePolicyMap,
    zone: str,
    year: int,
    start_year: int,
    until_year: int,
    validate_dst_offset: bool,
    debug_validator: bool,
    debug_processor: bool,
) -> None:

    validator = Validator(
        zone_infos=zone_infos,
        zone_policies=zone_policies,
        validate_dst_offset=validate_dst_offset,
        debug_validator=debug_validator,
        debug_processor=debug_processor,
        zone_name=zone,
        year=year,
        start_year=start_year,
        until_year=until_year,
    )

    logging.info('======== Validating test data')
    validator.validate_test_data()


def main() -> None:
    # Configure command line flags.
    parser = argparse.ArgumentParser(
        description='Validate TZ zone files with ZoneProcessor.'
    )

    # Extractor flags.
    parser.add_argument(
        '--input_dir', help='Location of the input directory', required=True)

    # Transformer flags.
    parser.add_argument(
        '--scope',
        # basic: time zones for BasicZoneProcessor
        # extended: time zones for ExtendedZoneProcessor
        choices=['basic', 'extended'],
        help='Scope of the generated zoneinfo database (basic|extended)',
        required=True,
    )
    parser.add_argument(
        '--start_year',
        help='Start year of Zone Eras (default: 2000)',
        type=int,
        default=2000,
    )
    parser.add_argument(
        '--until_year',
        help='Until year of Zone Eras (default: 2038)',
        type=int,
        default=2038,
    )

    parser.add_argument(
        '--granularity',
        help=(
            'If given, overrides the other granularity flags to '
            'truncate UNTIL, AT, STDOFF (offset), SAVE (delta) and '
            'RULES (rulesDelta) fields to this many seconds (default: None)'
        ),
        type=int,
    )
    parser.add_argument(
        '--until_at_granularity',
        help=(
            'Truncate UNTIL and AT fields to this many seconds (default: 60)'
        ),
        type=int,
    )
    parser.add_argument(
        '--offset_granularity',
        help=(
            'Truncate STDOFF (offset) fields to this many seconds'
            '(default: 900 (basic), 60 (extended))'
        ),
        type=int,
    )
    parser.add_argument(
        '--delta_granularity',
        help=(
            'Truncate SAVE (delta) and RULES (rulesDelta) field to this many'
            'seconds (default: 900)'
        ),
        type=int,
    )

    parser.add_argument(
        '--strict',
        help='Remove zones and rules not aligned at granularity time boundary',
        action='store_true',
        default=True,
    )
    parser.add_argument(
        '--nostrict',
        help='Retain zones and rules not aligned at granularity time boundary',
        action='store_false',
        dest='strict',
    )

    # Validator flags.
    parser.add_argument(
        '--zone',
        help='Name of time zone to validate (default: all zones)',
    )
    parser.add_argument(
        '--year',
        help='Year to validate (default: start_year, until_year)',
        type=int,
    )
    parser.add_argument(
        '--validate_dst_offset',
        # Not enabled by default because pytz DST seems to be buggy.
        help='Validate the DST offset as well as the total UTC offset',
        action="store_true")
    parser.add_argument(
        '--debug_validator',
        help='Enable debug output from Validator',
        action="store_true")

    # ZoneProcessor flags
    parser.add_argument(
        '--debug_processor',
        help='Enable debug output from ZoneProcessor',
        action="store_true")

    # TestDataGenerator flag.
    #
    # pytz cannot handle dates after the end of 32-bit Unix time_t type
    # (2038-01-19T03:14:07Z), see
    # https://answers.launchpad.net/pytz/+question/262216, so the
    # validation_until_year cannot be greater than 2038.
    parser.add_argument(
        '--validation_start_year',
        help='Start year of ZoneProcessor validation (default: start_year)',
        type=int,
        default=0)
    parser.add_argument(
        '--validation_until_year',
        help='Until year of ZoneProcessor validation (default: 2038)',
        type=int,
        default=0)

    # Parse the command line arguments
    args = parser.parse_args()

    # Configure logging. This should normally be executed after the
    # parser.parse_args() because it allows us set the logging.level using a
    # flag.
    logging.basicConfig(level=logging.INFO)

    # Define scope-dependent granularity if not overridden by flag
    if args.granularity:
        until_at_granularity = args.granularity
        offset_granularity = args.granularity
        delta_granularity = args.granularity
    else:
        if args.until_at_granularity:
            until_at_granularity = args.until_at_granularity
        else:
            until_at_granularity = 60

        if args.offset_granularity:
            offset_granularity = args.offset_granularity
        else:
            if args.scope == 'basic':
                offset_granularity = 900
            else:
                offset_granularity = 60

        if args.delta_granularity:
            delta_granularity = args.delta_granularity
        else:
            delta_granularity = 900

    logging.info('Granularity for UNTIL/AT: %d', until_at_granularity)
    logging.info('Granularity for STDOFF (offset): %d', offset_granularity)
    logging.info(
        'Granularity for RULES (rulesDelta) and SAVE (delta): %d',
        delta_granularity,
    )

    # Extract the TZ files
    logging.info('======== Extracting TZ Data files')
    extractor = Extractor(args.input_dir)
    extractor.parse()
    extractor.print_summary()
    policies_map, zones_map, links_map = extractor.get_data()

    # Create initial TransformerResult
    tresult = TransformerResult(
        zones_map=zones_map,
        policies_map=policies_map,
        links_map=links_map,
        removed_zones={},
        removed_policies={},
        removed_links={},
        notable_zones={},
        notable_policies={},
        notable_links={},
        zone_ids={},
        link_ids={},
        letters_map={},
        formats_map={},
        fragments_map={},
        compressed_names={},
    )

    # Transform the TZ zones and rules
    logging.info('======== Transforming Zones and Rules')
    logging.info('Extracting years [%d, %d)', args.start_year, args.until_year)
    transformer = Transformer(
        tresult=tresult,
        scope=args.scope,
        start_year=args.start_year,
        until_year=args.until_year,
        until_at_granularity=until_at_granularity,
        offset_granularity=offset_granularity,
        delta_granularity=delta_granularity,
        strict=args.strict,
    )
    transformer.transform()
    transformer.print_summary()
    tresult = transformer.get_data()

    # Generate internal versions of zone_infos and zone_policies
    # so that ZoneProcessor can be created.
    logging.info('======== Generating inlined zone_infos and zone_policies')
    zone_info_inliner = ZoneInfoInliner(tresult.zones_map, tresult.policies_map)
    zone_infos, zone_policies = zone_info_inliner.generate_zonedb()
    logging.info(
        'Inlined zone_infos=%d; zone_policies=%d',
        len(zone_infos), len(zone_policies))

    # Set the defaults for validation_start_year and validation_until_year
    # if they were not specified.
    validation_start_year = (
        args.start_year
        if args.validation_start_year == 0
        else args.validation_start_year
    )
    validation_until_year = (
        args.until_year
        if args.validation_until_year == 0
        else args.validation_until_year
    )

    validate(
        zone_infos=zone_infos,
        zone_policies=zone_policies,
        zone=args.zone,
        year=args.year,
        start_year=validation_start_year,
        until_year=validation_until_year,
        validate_dst_offset=args.validate_dst_offset,
        debug_validator=args.debug_validator,
        debug_processor=args.debug_processor,
    )

    logging.info('======== Finished processing TZ Data files.')


if __name__ == '__main__':
    main()
