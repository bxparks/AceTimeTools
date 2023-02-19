#!/usr/bin/env python3
#
# Copyright 2018 Brian T. Park
#
# MIT License.

"""
Read the raw TZ Database files at the location specified by `--input_dir`.
Generate the zonedb files in various formats for different languages selected by
the `--language` flag.

The compiler has a number of stages implemented by various helper classes:

* Extractor
    * Parse and extract the raw TZDB files into internal zoneinfo (ZoneInfo,
      ZoneEra, ZonePolicy, ZoneRule) records.
* Transformer
    * Mutate and remove zoneinfo records according to selected options and
      algorithms.
* Generator
    * Generate the various zonedb files in the format requested by the
      `--language` flag.

Informational Flags:

* --tz_version
    * Pass through flag to identify the TZDB version.

Extractor Flags:

* `--input_dir`
    * Location of the raw TZDB files.

Transformer Flags:

* --scope {basic | extended)
    * Selects one of the 2 algorithms supported by AceTime.
    * AceTimeC, AceTimePython, and AceTimeGo supports only 'extended'.
* `--generate_int16_years`
    * Output `from_year` and `to_year` as 16-bit integers instead of 8-bit
      "tiny" integers.
    * Retain records which are outside of the 8-bit integers.
* --start_year {start}
    * Truncate output so that the algorithm works for year >= start_year.
* --until_year {until}
    * Truncate output so that the algorithm works for year < until_year.
* --granularity {seconds}
    * Convenience flag that overrides the other `--xxx_granularity` flags.
* --until_at_granularity {seconds}
    * Truncate Zone.UNTIL fields to this granularity.
* --offset_granularity {seconds}
    * Truncate Zone.STDOFF field to this granularity.
* --delta_granularity {seconds}
    * Truncate Zone.DSTOFF (aka Zone.RULES) and Rule.SAVE to this granularity.
* --strict, --nostrict
    * Remove entries outside of the selected granularity.
* `--include_list {file}`
    * Filter the zones to include only those in this include list.
* --compress, --nocompress
    * Compress zone names using keyword substitution.

Generator Flags:

* `--language` flag is a comma-separated list of generator file:
    * arduino: Generate `zone_*.{h,cpp}` files for AceTime Arduino library
    * c: Generate `zone_*.{h,cpp}` files for AceTimeC C lang library
    * python: Generate `zone_*.py` files for AceTimePython Python library
    * json: Generate `zonedb.json` file.
    * zonelist: Generate a raw list of zone names in 'zones.txt' file.
* `--output_dir {dir}`
    * The directory where various files should be created.
    * If empty, it means the same as $PWD.
* ArduinoGenerator
    * --db_namespace {db_namespace}
        * Use the given identifier as the C++ namespace of the generated
          classes.
    * `--generate_int16_years`
        * Generate 16-bit year fields instead of 8-bit.
* CGenerator
    * `--generate_int16_years`
        * Generate 16-bit year fields instead of 8-bit.
    * `--generate_hires`
        * Generate one-second resolution UNTIL, AT, OFFSET (one-minute DELTA).
* GoGenerator
    * --db_namespace {db_namespace}
        * Specifies the Go `package` name.
* JsonGenerator
    * --json_file {file}
        * Name of the JSON file (e.g. `zonedb.json`, `zonedbx.json`)

Examples:

    See tzcompiler.sh
"""

import argparse
import logging
import sys
from typing import Set
from typing_extensions import Protocol

from acetimetools.data_types.at_types import TransformerResult
from acetimetools.data_types.at_types import ZoneInfoDatabase
from acetimetools.data_types.at_types import create_zone_info_database
from acetimetools.extractor.extractor import Extractor
from acetimetools.transformer.transformer import Transformer
from acetimetools.transformer.artransformer import ArduinoTransformer
from acetimetools.transformer.commenter import Commenter
from acetimetools.transformer.gotransformer import GoTransformer
from acetimetools.bufestimator.bufestimator import BufSizeEstimator
from acetimetools.generator.argenerator import ArduinoGenerator
from acetimetools.generator.cgenerator import CGenerator
from acetimetools.generator.gogenerator import GoGenerator
from acetimetools.generator.pygenerator import PythonGenerator
from acetimetools.generator.zonelistgenerator import ZoneListGenerator
from acetimetools.generator.jsongenerator import JsonGenerator


class Generator(Protocol):
    """Define an interface for Generator subclasses for mypy type checking."""
    def generate_files(self, name: str) -> None:
        ...


def generate_zonedb(
    invocation: str,
    db_namespace: str,
    compress: bool,
    generate_int16_years: bool,
    generate_hires: bool,
    language: str,
    output_dir: str,
    json_file: str,
    zidb: ZoneInfoDatabase,
) -> None:
    """Generate the zonedb/ or zonedbx/ files for Python or Arduino,
    but probably mostly for Arduino.
    """
    generator: Generator

    # Create the Python or Arduino files as requested
    if language == 'python':
        logging.info('==== Creating Python zone_*.py files')
        generator = PythonGenerator(
            invocation=invocation,
            zidb=zidb,
        )
        generator.generate_files(output_dir)

    elif language == 'arduino':
        logging.info('==== Creating Arduino zone_*.{h,cpp} files')
        generator = ArduinoGenerator(
            invocation=invocation,
            db_namespace=db_namespace,
            compress=compress,
            generate_int16_years=generate_int16_years,
            zidb=zidb,
        )
        generator.generate_files(output_dir)

    elif language == 'c':
        logging.info('==== Creating AceTimeC zone_*.{h,c} files')
        generator = CGenerator(
            invocation=invocation,
            db_namespace=db_namespace,
            compress=compress,
            generate_int16_years=generate_int16_years,
            generate_hires=generate_hires,
            zidb=zidb,
        )
        generator.generate_files(output_dir)

    elif language == 'go':
        logging.info('==== Creating AceTimeGo zone_*.go files')
        generator = GoGenerator(
            invocation=invocation,
            db_namespace=db_namespace,
            zidb=zidb,
        )
        generator.generate_files(output_dir)

    elif language == 'json':
        logging.info('==== Creating zonedb.json file')
        generator = JsonGenerator(zidb=zidb, json_file=json_file)
        generator.generate_files(output_dir)

    elif language == 'zonelist':
        logging.info('==== Creating zones.txt file')
        generator = ZoneListGenerator(
            invocation=invocation,
            zidb=zidb,
        )
        generator.generate_files(output_dir)

    else:
        raise Exception(f"Unrecognized language '{language}'")


def main() -> None:
    """
    Main driver for TZ Database compiler which parses the IANA TZ Database files
    located at the --input_dir and generates zoneinfo files and validation
    datasets for unit tests at --output_dir.

    Usage:
        tzcompiler.py [flags...]
    """
    # Configure command line flags.
    parser = argparse.ArgumentParser(description='Generate Zone Info.')

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
        required=True)
    parser.add_argument(
        '--start_year',
        help='Start year of Zone Eras (default: 2000)',
        type=int,
        default=2000)
    parser.add_argument(
        '--until_year',
        help='Until year of Zone Eras (default: 2038)',
        type=int,
        default=2038)

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

    # Make --strict the default, --nostrict optional.
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

    # Data pipeline selectors. Reduced down to a single 'zonedb' option which
    # is the default.
    parser.add_argument(
        '--action',
        help='Action to perform (zonedb)',
        default='zonedb',
    )

    # Language selector (for --action zonedb).
    parser.add_argument(
        '--language',
        help='Comma-separated list of target languages '
             '(arduino|c|python|go|json|zonelist)',
        default='',
    )

    # C++ namespace names for '--language arduino'. If not specified, it will
    # automatically be set to 'zonedb' or 'zonedbx' depending on the 'scope'.
    parser.add_argument(
        '--db_namespace',
        help='C++ namespace for the zonedb files (default: zonedb or zonedbx)',
    )

    # Whether to compress the zone and link names
    parser.add_argument(
        '--compress',
        help='Compress the zone and link names using fragments (default: True)',
        action='store_true',
        default=True,
    )
    parser.add_argument(
        '--nocompress',
        help='Disable compression of zone and link names using fragments',
        action='store_false',
        dest='compress',
    )

    # For language=json, specify the output file.
    parser.add_argument(
        '--json_file',
        help='The JSON output file (default: zonedb.json)',
        default='zonedb.json',
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

    # Target location of the generated files.
    parser.add_argument(
        '--output_dir',
        help='Location of the output directory',
        default='',
    )

    # Flag to ignore max_buf_size check. Needed on ExtendedHinnantDateTest if we
    # want to test the extended year range from 1974 to 2050, because one of the
    # zones requires a buf_size=9, but ExtendedZoneProcessor only supports 8.
    parser.add_argument(
        '--ignore_buf_size_too_large',
        help='Ignore transition buf size too large',
        action='store_true',
    )

    # Generate full int16_t years instead int8_t years which are offsets from
    # the year 2000.
    parser.add_argument(
        '--generate_int16_years',
        help='Generate int16_t years instead of int8_t years',
        action='store_true',
    )

    # Generate high resolution AT, UNTIL, OFFSET and DSTOFF fields.
    parser.add_argument(
        '--generate_hires',
        help='Generate high resolution AT, UNTIL, OFFSET, and DSTOFF',
        action='store_true',
    )

    # File name containing list of zones and links to include.
    parser.add_argument(
        '--include_list',
        help='File containing list of zones and links to include',
        default='',
    )

    # Parse the command line arguments
    args = parser.parse_args()

    # Manually parse the comma-separated --action.
    languages = set(args.language.split(','))
    allowed_languages = set([
        'arduino', 'c', 'python', 'go', 'json', 'zonelist',
    ])
    if not languages.issubset(allowed_languages):
        print(f'Invalid --language: {languages - allowed_languages}')
        sys.exit(1)

    # Configure logging. This should normally be executed after the
    # parser.parse_args() because it allows us set the logging.level using a
    # flag.
    logging.basicConfig(level=logging.INFO)

    # How the script was invoked
    invocation = ' '.join(sys.argv)

    # Read the zone list filter file.
    include_list = read_include_list(args.include_list)

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

    logging.info('======== TZ Compiler settings')
    logging.info(f'Scope: {args.scope}')
    logging.info(
        f'Start year: {args.start_year}; Until year: {args.until_year}'
    )
    logging.info(f'Strict: {args.strict}')
    logging.info(f'TZ Version: {args.tz_version}')
    logging.info(
        'Ignore too large transition buf_size: '
        f'{args.ignore_buf_size_too_large}'
    )
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
        zones_to_policies={},
        removed_zones={},
        removed_policies={},
        removed_links={},
        notable_zones={},
        merged_notable_zones={},
        notable_policies={},
        notable_links={},
        original_min_year=0,
        original_max_year=0,
        generated_min_year=0,
        generated_max_year=0,
        buf_sizes={},
        max_buf_size=0,
        zone_ids={},
        link_ids={},
        letters_per_policy={},
        letters_map={},
        formats_map={},
        fragments_map={},
        compressed_names={},
        memory_map8={},
        memory_map32={},
        go_letters_map={},
        go_formats_map={},
        go_names_map={},
        go_zone_and_link_index_map={},
        go_policy_index_size_map={},
        go_rule_count=0,
        go_info_index_size_map={},
        go_era_count=0,
    )

    # Transform the TZ zones and rules
    logging.info('======== Transforming Zones and Rules')
    transformer = Transformer(
        scope=args.scope,
        start_year=args.start_year,
        until_year=args.until_year,
        until_at_granularity=until_at_granularity,
        offset_granularity=offset_granularity,
        delta_granularity=delta_granularity,
        strict=args.strict,
        generate_int16_years=args.generate_int16_years,
        include_list=include_list,
    )
    transformer.transform(tresult)
    transformer.print_summary(tresult)

    # Generate the fields for the Arduino zoneinfo data.
    if 'arduino' in languages or 'c' in languages:
        logging.info('======== Transforming to Arduino Zones and Rules')
        arduino_transformer = ArduinoTransformer(
            args.compress, args.generate_hires)
        arduino_transformer.transform(tresult)
        arduino_transformer.print_summary(tresult)
    else:
        logging.info('======== Skipping Arduino transformations')

    # Estimate the buffer size of ExtendedZoneProcessor.TransitionStorage.
    logging.info('======== Estimating transition buffer sizes')

    estimator = BufSizeEstimator(
        start_year=args.start_year,
        until_year=args.until_year,
        ignore_buf_size_too_large=args.ignore_buf_size_too_large,
    )
    estimator.transform(tresult)
    estimator.print_summary(tresult)

    # Generate the fields for the Arduino zoneinfo data.
    logging.info('======== Updating comments')
    commenter = Commenter()
    commenter.transform(tresult)
    commenter.print_summary(tresult)

    # Generate the fields for the Arduino zoneinfo data.
    if 'go' in languages:
        logging.info('======== Transforming to Go Zones and Rules')
        go_transformer = GoTransformer()
        go_transformer.transform(tresult)
        go_transformer.print_summary(tresult)
    else:
        logging.info('======== Skipping Go lang transformations')

    # Collect TZ DB data into a single JSON-serializable object.
    zidb = create_zone_info_database(
        tz_version=args.tz_version,
        tz_files=Extractor.ZONE_FILES,
        scope=args.scope,
        start_year=args.start_year,
        until_year=args.until_year,
        until_at_granularity=until_at_granularity,
        offset_granularity=offset_granularity,
        delta_granularity=delta_granularity,
        strict=args.strict,
        compress=args.compress,
        tresult=tresult,
    )

    if args.action == 'zonedb':
        logging.info('======== Generating zonedb files')
        for language in languages:
            generate_zonedb(
                invocation=invocation,
                db_namespace=args.db_namespace,
                compress=args.compress,
                generate_int16_years=args.generate_int16_years,
                generate_hires=args.generate_hires,
                language=language,
                output_dir=args.output_dir,
                zidb=zidb,
                json_file=args.json_file,
            )
    else:
        logging.error(f"Unrecognized action '{args.action}'")
        sys.exit(1)

    logging.info('======== Finished processing TZ Data files.')


def read_include_list(filename: str) -> Set[str]:
    """Read file containing the list of zones and links to include. Empty
    list means 'include everything'.
    """
    zones: Set[str] = set()
    if not filename:
        return zones

    with open(filename) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            zones.add(line)
    return zones


if __name__ == '__main__':
    main()
