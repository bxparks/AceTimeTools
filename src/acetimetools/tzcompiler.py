#!/usr/bin/env python3
#
# Copyright 2018 Brian T. Park
#
# MIT License.

"""
Read the raw TZ Database files at the location specified by `--input_dir`.
Generate the output files (selected by `--actions`) for different languages or
librarties (selected by the `--language`)

The compiler has a number of stages implemented by various helper classes:

* Extractor
    * Parse and extract the raw TZDB files into internal zoneinfo (ZoneInfo,
      ZoneEra, ZonePolicy, ZoneRule) records.
* Transformer
    * Mutate and remove zoneinfo records according to selected options and
      algorithms.
* Generator
    * Generate the various zonedb files in the format requested by the
      `--languages` flag.

Informational Flags:

* --tz_version
    * Pass through flag to identify the TZDB version.

Workflow Flags:

* `--actions` flags is a comma-separated list of output format
    * zonedb: Generate zonedb files for the given language or library
    * json: Generate `zonedb.json` file for the given language
    * zonelist: Generate a raw list of zone names in 'zones.txt' file.

* `--languages` flag is a comma-separated list of target language or library
    * arduino: Generate `zone_*.{h,cpp}` files for AceTime Arduino library
    * c: Generate `zone_*.{h,cpp}` files for acetimec C library
    * python: Generate `zone_*.py` files for acetimepy Python library
    * go: Generate `zone_*.{go}` files for acetimego C library

Extractor Flags:

* `--input_dir`
    * Location of the raw TZDB files.

Transformer Flags:

* --start_year {start}
    * Truncate output so that the algorithm works for year >= start_year.
* --until_year {until}
    * Truncate output so that the algorithm works for year < until_year.
* --tiny_base_year {year}
    * Base year for fields encoded as 8-bit offset from the base year.
    * Setting this to 2100 allows us to represent the years in the range of
      [1974,2225] with:
        * -128 representing an error condition,
        * -127 representing -Infinity,
        * 126 representing +Infinity for the TO field, and
        * 127 representing +Infinity for the UNTIL field.
* --scope {basic | extended | complete)
    * Selects one of the 3 zonedb encoding formats
    * acetimec, acetimepy, and acetimego currently ignores this flag and
      defaults to 'complete'
    * basic
        * until_at_granularity: 60 seconds (1 minute)
        * offset_granularity: 60 seconds (1 minute)
        * delta_granularity: 900 seconds (15 minutes)
        * generate_tiny_years: True
        * time_code_format: 'low'
        * (valid for subset of timezones >= ~2000)
    * extended
        * until_at_granularity: 60 seconds (1 minute)
        * offset_granularity: 60 seconds (1 minute)
        * delta_granularity: 900 seconds (15 minutes)
        * generate_tiny_years: False (TODO: change to True?)
        * time_code_format: 'low'
        * (valid for all timezones >= ~1972)
    * complete
        * until_at_granularity: 1 second
        * offset_granularity: 1 second
        * delta_granularity: 60 seconds (1 minute)
        * generate_tiny_years: False
        * time_code_format: 'high'
        * (valid for timezones >= 1844, all TZDB)
* --until_at_granularity {seconds}
    * Truncate Zone.UNTIL fields to this granularity.
* --offset_granularity {seconds}
    * Truncate Zone.STDOFF field to this granularity.
* --delta_granularity {seconds}
    * Truncate Zone.DSTOFF (aka Zone.RULES) and Rule.SAVE to this granularity.
* --strict, --nostrict
    * Remove zones outside of the selected granularity. (default True)
* `--include_list {file}`
    * Filter the zones to include only those in this include list.
* --compress, --nocompress
    * Compress zone names using keyword substitution.
* --generate_tiny_years
    * Create zonedbs using int8 years intead of int16 years

Generator Flags:

* `--output_dir {dir}`
    * The directory where various files should be created.
    * If empty, it means the same as $PWD.
* `--scope`
    * Determines the format of the zonedb file.
* --generate_tiny_years
    * Create zonedbs using int8 years intead of int16 years
* --compress, --nocompress
    * Compress zone names using keyword substitution.
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

from acetimetools.datatypes.attyping import TransformerResult
from acetimetools.datatypes.attyping import ZoneInfoDatabase
from acetimetools.datatypes.attyping import create_zone_info_database
from acetimetools.datatypes.attyping import MIN_YEAR
from acetimetools.datatypes.attyping import MAX_UNTIL_YEAR
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
    generate_tiny_years: bool,
    tiny_base_year: int,
    languages: Set[str],
    output_dir: str,
    zidb: ZoneInfoDatabase,
) -> None:
    """Generate various zonedb files for the requested languages.
    Activated for '--actions zonedb'.
    """
    generator: Generator

    if 'python' in languages:
        logging.info('==== Creating acetimepy zone_*.py files')
        generator = PythonGenerator(
            invocation=invocation,
            zidb=zidb,
        )
        generator.generate_files(output_dir)

    if 'arduino' in languages:
        logging.info('==== Creating AceTime zone_*.{h,cpp} files')
        generator = ArduinoGenerator(
            invocation=invocation,
            db_namespace=db_namespace,
            compress=compress,
            generate_tiny_years=generate_tiny_years,
            tiny_base_year=tiny_base_year,
            zidb=zidb,
        )
        generator.generate_files(output_dir)

    if 'c' in languages:
        logging.info('==== Creating acetimec zone_*.{h,c} files')
        generator = CGenerator(
            invocation=invocation,
            db_namespace=db_namespace,
            compress=compress,
            generate_tiny_years=generate_tiny_years,
            tiny_base_year=tiny_base_year,
            zidb=zidb,
        )
        generator.generate_files(output_dir)

    if 'go' in languages:
        logging.info('==== Creating acetimego zone_*.go files')
        generator = GoGenerator(
            invocation=invocation,
            db_namespace=db_namespace,
            zidb=zidb,
        )
        generator.generate_files(output_dir)


def generate_json(
    output_dir: str,
    json_file: str,
    zidb: ZoneInfoDatabase,
) -> None:
    """Generate JSON file. Activated for '--actions json'.
    """
    logging.info('==== Creating zonedb.json file')
    generator = JsonGenerator(zidb=zidb, json_file=json_file)
    generator.generate_files(output_dir)


def generate_zonelist(
    invocation: str,
    output_dir: str,
    zidb: ZoneInfoDatabase,
) -> None:
    """Generate JSON file. Activated for '--actions zonelist'.
    """
    logging.info('==== Creating zones.txt file')
    generator = ZoneListGenerator(invocation=invocation, zidb=zidb)
    generator.generate_files(output_dir)


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

    # Target action (i.e. output) selector.
    parser.add_argument(
        '--actions',
        help='Comma-separated list of actions or targets '
             '(zonedb|json|zonelist)',
        default='zonedb',
        required=True,
    )

    # Language selector for transforming.
    parser.add_argument(
        '--languages',
        help='Comma-separated list of languages (arduino|c|python|go)',
        default='',
        required=True,
    )

    # Extractor flags.
    parser.add_argument(
        '--input_dir', help='Location of the input directory', required=True)

    # Transformer flags.

    # Size/resolution of the zoneinfo dataset.
    parser.add_argument(
        '--scope',
        # basic: BasicZoneProcessor, lores
        # extended: ExtendedZoneProcessor, midres
        # complete: ExtendedZoneProcessor, hires
        choices=['basic', 'extended', 'complete'],
        help='Scope of zoneinfo database (basic|extended|complete)',
        required=True)

    parser.add_argument(
        '--start_year',
        help='Start year of Zone Eras (default: 2000)',
        type=int,
        default=2000)
    parser.add_argument(
        '--until_year',
        help='Until year of Zone Eras (default: 2100)',
        type=int,
        default=2100)

    parser.add_argument(
        '--tiny_base_year',
        help='Base year for tiny year fields (default: 2100)',
        type=int,
        default=2100)

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

    # Defines the namespace or package of the generated zonedb files depending
    # on the --languages flag:
    #   * arduino: defines the C++ namespace
    #   * c: defines the prefix of the kAtc{db_namespace}ZoneXxx data structs
    #   * python: not used
    #   * go: defines the Go package name of the zonedb data structs
    parser.add_argument(
        '--db_namespace',
        help='Namespace or package of the zonedb files (Required)',
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

    # File name containing list of zones and links to include.
    parser.add_argument(
        '--include_list',
        help='File containing list of zones and links to include',
        default='',
    )

    # Skip buffer size estimation, to avoid circular dependency to acetimepy.
    parser.add_argument(
        '--skip_bufestimator',
        help='Skip buffer size estimator',
        action='store_true',
    )

    # Parse the command line arguments
    args = parser.parse_args()

    # Validate the comma-separated --actions flag.
    actions = set(args.actions.split(','))
    allowed_actions = set(['zonedb', 'json', 'zonelist'])
    if not actions.issubset(allowed_actions):
        print(f'Invalid --actions: {actions - allowed_actions}')
        sys.exit(1)

    # Validate the comma-separated --languages flag.
    languages = set(args.languages.split(','))
    allowed_languages = set(['arduino', 'c', 'python', 'go'])
    if not languages.issubset(allowed_languages):
        print(f'Invalid --languages: {languages - allowed_languages}')
        sys.exit(1)

    # Configure logging. This should normally be executed after the
    # parser.parse_args() because it allows us set the logging.level using a
    # flag.
    logging.basicConfig(level=logging.INFO)

    # How the script was invoked
    invocation = ' '.join(sys.argv)

    # Read the zone list filter file.
    include_list = read_include_list(args.include_list)

    # Define default parameters from the '--scope' flag.
    if args.scope == 'basic':
        if args.start_year < 1980:
            raise Exception(
                f"Invalid StartYear {args.start_year} for scope 'basic'")
        until_at_granularity = 60
        offset_granularity = 60
        delta_granularity = 900
        time_code_format = 'low'
        generate_tiny_years = True
    elif args.scope == 'extended':
        if args.start_year < 1974:
            raise Exception(
                f"Invalid StartYear {args.start_year} for scope 'extended'")
        until_at_granularity = 60
        offset_granularity = 60
        delta_granularity = 900
        time_code_format = 'low'
        generate_tiny_years = True
    elif args.scope == 'complete':
        until_at_granularity = 1
        offset_granularity = 1
        delta_granularity = 60
        time_code_format = 'high'
        generate_tiny_years = False
    else:
        raise Exception(f'Unknown scope {args.scope}')

    if args.until_at_granularity:
        until_at_granularity = args.until_at_granularity
    if args.offset_granularity:
        offset_granularity = args.offset_granularity
    if args.delta_granularity:
        delta_granularity = args.delta_granularity

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
    logging.info(f'Generate tiny years: {generate_tiny_years}')
    logging.info(f'Tiny base year: {args.tiny_base_year}')

    # Extract the TZ files
    logging.info('======== Extracting TZ Data files')
    extractor = Extractor(args.input_dir)
    extractor.parse()
    extractor.print_summary()
    policies_map, zones_map, links_map = extractor.get_data()

    # Create initial TransformerResult.
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
        lower_truncated=False,
        upper_truncated=False,
        start_year_accurate=MIN_YEAR,
        until_year_accurate=MAX_UNTIL_YEAR,
        buf_sizes={},
        max_buf_size=0,
        estimator_min_year=0,
        estimator_max_year=0,
        zone_ids={},
        link_ids={},
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
        go_info_index_size_map={},
        go_memory_map={},
    )

    # Transform the TZ zones and rules, for all languages.
    logging.info('======== Transforming Zones and Rules')
    transformer = Transformer(
        scope=args.scope,
        start_year=args.start_year,
        until_year=args.until_year,
        until_at_granularity=until_at_granularity,
        offset_granularity=offset_granularity,
        delta_granularity=delta_granularity,
        strict=args.strict,
        generate_tiny_years=generate_tiny_years,
        tiny_base_year=args.tiny_base_year,
        include_list=include_list,
    )
    transformer.transform(tresult)
    transformer.print_summary(tresult)

    # Estimate the buffer size of ExtendedZoneProcessor.TransitionStorage.
    if args.skip_bufestimator:
        logging.info('======== Skipping buffer size estimation')
    else:
        logging.info('======== Estimating transition buffer sizes')
        estimator = BufSizeEstimator(
            start_year=args.start_year,
            until_year=args.until_year,
            ignore_buf_size_too_large=args.ignore_buf_size_too_large,
        )
        estimator.transform(tresult)
        estimator.print_summary(tresult)

    # Merge comments from ZonePolicies into ZoneInfos.
    logging.info('======== Merging policy comments into zone comments')
    commenter = Commenter()
    commenter.transform(tresult)
    commenter.print_summary(tresult)

    # Transform fields for the 'arduino' (AceTime) or 'c' (acetimec) libraries.
    if 'arduino' in languages or 'c' in languages:
        logging.info('======== Transforming to Arduino/C Zones and Rules')
        arduino_transformer = ArduinoTransformer(
            args.scope,
            args.compress,
            time_code_format)
        arduino_transformer.transform(tresult)
        arduino_transformer.print_summary(tresult)
    else:
        logging.info('======== Skipping Arduino/C transformations')

    # Generate the fields for the 'go' (acetimego) library.
    if 'go' in languages:
        logging.info('======== Transforming to Go lang Zones and Rules')
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

    # Perform one or more actions.
    logging.info('======== Performing actions, generating files')
    if 'zonedb' in actions:
        generate_zonedb(
            invocation=invocation,
            db_namespace=args.db_namespace,
            compress=args.compress,
            generate_tiny_years=generate_tiny_years,
            tiny_base_year=args.tiny_base_year,
            languages=languages,
            output_dir=args.output_dir,
            zidb=zidb,
        )
    if 'json' in actions:
        generate_json(
            output_dir=args.output_dir,
            json_file=args.json_file,
            zidb=zidb,
        )
    if 'zonelist' in actions:
        generate_zonelist(
            invocation=invocation,
            output_dir=args.output_dir,
            zidb=zidb,
        )

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
