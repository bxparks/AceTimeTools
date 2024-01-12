# Changelog

* Unreleased
* 1.8.2 (2024-01-12)
    * move `stdoff.py` to `tzplus` project
* 1.8.1 (2023-06-27)
    * `argenerator.py`
        * Change type of `kTzDatabaseVersion` string from `const char*` to
          `const __FlashStringHelper*`, since it is stored in `PROGMEM` now.
    * `valtyping.py `
        * Add `scope` parameter to characterize the intended size and validity
          of the validation data.
* 1.8.0 (2023-06-23)
    * Support high-res `zonedbc` data files for AceTime library
        * Use `--scope complete`.
        * Simplify granularity flags, using `--scope` to determine the various
        granularity parameters.
        * Remove `--generate_hires` flag
    * `tzcompiler.py`
        * Refactor `--actions` and `--languages` flags
        * `--actions` is now a comma-separate list: `zonedb`, `json`, `zonelist`
        * `--languages` can be: `arduino`, `c`, `go`, `python`
        * Allows `zonedb.json` to be generate properly for different languages.
    * `letters_per_policy`
        * Remove, no longer used.
        * `letterIndex` always refers to the global `letters` map.
    * tiny years (i.e. low res mode for basic zonedb)
        * Remove `--generate_int16_years` flag.
        * Rename internal `generate_int16_years` parameter with
          `generate_tiny_years`.
        * Replace `EPOCH_YEAR_FOR_TINY` constant with `--tiny_base_year flag`
        * Change `--scope basic` to use lowres zoneinfo data structures, using
          tiny year fields.
        * Handle -Infinity and +Infinity consistently.
    * `argenerator.py`
        * Move `ZoneContext`, `letters[]` and `fragments[]` into PROGMEM.
    * Rename `data_types` to `datatypes` for readability
        * Rename `at_types.py` to `attyping.py`
        * Rename `validation_types.py` to `valtyping.py`
    * Add truncation flags and accuracy years
        * `lower_truncated`: if any era or rule was truncated before the
          requested `start_year`
        * `upper_truncated`: if any era or rul was truncated on or after the
          requested `until_year`
        * `start_year_accurate`: start year of accurate transitions
        * `until_year_accurate`: until year of accurate transitions
* 1.7.0 (2023-05-22)
    * Rename `AceTimePython` library to `acetimepy`.
    * Rename `AceTimeGo` library to `acetimego`.
    * Rename `AceTimeC` library to `acetimec`.
    * Move `zinfo.py` to `acetimepy` library.
    * `pygenerator.py`
        * Always generate `eras` for Links, turning Links into "hard links".
        * Simplifies code that handles links in the `acetimepy` project,
          and matches the handling of links in the AceTime project.
    * `validation_types.py`
        * Split `test_data` array into `transitions` and `samples`.
    * `copytz.sh`, `tzcompiler.sh`
        * Remove unused `backzone`, and obsolete `systemv` which no longer
          exists in the original TZDB.
* 1.6.3 (2023-03-26)
    * Extract RULES (in `era['rules']`) into separate fields.
        * Copy the policy name (RULE name) string into `era['policy_name']` if
          it's a reference to a policy.
        * Set to `None` if RULES is '-' or 'hh:mm'.
        * Fixed offsets already go into `era['era_delta_seconds']`.
        * Makes it much easier to distinguish the 3 different types of RULES.
    * Always flag negative DST offsets
        * Negative DST can occur through the RULES field in the ZONE records,
          or the SAVE field in the RULE records.
        * Update comment generation to generate notable comments in both cases.
        * Search for 'negative' in the comments of the zonedb files.
    * Move various 'notable' comments from `artransformer.py` to
      `transformer.py`.
        * Notable Xxx comments are now included in all AceTimeXxx libraries,
          instead of just the `AceTime` library.
* 1.6.2 (2023-03-24)
    * Add 'Records' section in the file header of zonedb generated files.
        * Contains the number of records for Info, Era, Policy, and Rule
          tables.
* 1.6.1 (2023-03-10)
    * `transformer.py`
        * Filter out ZoneRules using a coarse-grained comparison to
          `[start_year, until_year), instead of loop through every ZoneEra item,
          and doing a mark and sweep on the referenced ZoneRule.
            * This picks up a few extra ZoneRule records in some older
              ZonePolicies, but makes the code far simpler and easier to
              maintain.
    * `gogenerator.py`
        * Separate out the `XxxRecord` objects into `zone_infos_test.go`,
          `zone_policies_test.go`, `zone_registry_test.go`.
        * Auto-generate `reader_test.go` directly into the `zonedb*/` directory
          and use the `zone_test.go` files.
* 1.6.0 (2023-03-09)
    * `cgenerator.py`
        * Use `--db_namespace` flag to define the prefix of various `zonedb`
          data structures.
        * Consolidate memory stat collection for AceTime and AceTimeC.
        * Support `generate_hires` flag for 1-minute resolutions.
    * `bufestimator.py`
        * Convert into a Transformer class.
        * Add `max_transitions` field to the `ZoneContext` of various zonedb.
    * `gogenerator.py`
        * Print memory stats in the header of generated files.
    * `pygenerator.py`
        * Change `ZoneEra.zone_policy` to `Optional[ZonePolicy].
        * Set this field to `None` (intead of a str ':' or '-') when the
          corresponding `Zone.RULES` field is `hh:mm` or '-'.
    * Change various internal sentinel values.
        * Change `INVALID_YEAR` to -32768 from -1
        * Change `MAX_UNTIL_YEAR` to 32767 from 10000
        * Rename `MAX_YEAR` to `MAX_TO_YEAR`.
        * Change `MAX_TO_YEAR` from 9999 to 32766.
    * Add `--skip_bufestimator`
        * Allows generation of zonedb files without dependence on the
          AceTimePython project.
        * Useful when `AceTimePython/zone_processor.py` code becomes temporarily
          broken during development.
    * Always generate anchor rules
        * After truncating the zonedb to `[start,until)`, always generate anchor
          rules at year -32767.
        * Allows zone processor algorithms (AceTime, AceTimeC, AceTimeGo) to
          work over all years `[0,10000)`, even after truncation.
* 1.5.0 (2023-02-13)
    * Rename `rules_delta_seconds` to `era_delta_seconds` for better
      self-documentation.
        * This field is determined by the `RULES` column in the Zone entry when
          it contains `hh:mm` form instead of a symbolic pointer to a Rule.
        * This determines the DST offset of the given ZoneEra.
    * `gotransformer.py`, `gogenerator.py`
        * Support 1-second resolution instead of 1-minute resolution for
          Zone.STDOFF, Zone.UNTIL, and Rule.AT fields.
        * Support 1-minute resolution for Zone.DSTOFF (aka Zone.RULES) and
          Rule.SAVE fields.
        * Generate zonedb using signed integers variants (`write_i8()`,
          `write_i16()`, `write_i32()`) with proper range checking.
    * `artransformer.py`, `argenerator.py`
        * Unify data encoding of `ZoneInfo.deltaCode` and `ZoneRule.deltaCode`
          for "basic" zonedb files.
    * Calculate min and max years for original and generated zonedb entries.
* 1.4.3 (2023-02-04)
    * `argenerator.py`, `cgenerator.py`:
        * Simplify encoding of `Rule.LETTER` as an index into
          `ZoneContext.letters`.
* 1.4.2 (2023-02-02)
    * `tzcompiler.sh`:
        * Incorporate `copytz.sh` functionality directly to avoid dependency on
          another shell script.
        * If `--tag` is not given, then copy the TZDB repo instead of doing a
          `git clone`.
        * Add `trap` statement to perform auto-cleanup of the `tzfiles/`
          temporary directory.
        * Add `--tzrepo` to specify the location of the TZDB repo explicitly.
* 1.4.1 (2023-01-29)
    * `argenerator.py`
        * Remove LinkRegistry.
        * Add `targetInfo` to `ZoneInfo` to unify fat and symbolic Links.
    * `cgenerator.py`
        * Remove LinkRegistry.
        * Add `targetInfo` to `ZoneInfo` to unify fat and symbolic Links.
* 1.4.0 (2023-01-29)
    * Support the AceTimeGo library through `gotransfomer.py` and
      `gogenerator.py`.
    * Simplify calling API of various `XxxTransformer` classes.
* 1.3.0 (2023-01-17)
    * `copytz.sh`
        * Remove all files other than the raw TZDB files from the TZ DB git repo
          after performing a 'git clone'.
        * Prevents spurious C files from being picked up by EpoxyDuino, and
          causing compiler errors.
    * `tzcompiler.py`
        * Add `--include_list {file}` flag which points to a list of zones and
          links to include in the zonedb output.
        * Used to generate `testing/zonedb/` and `testing/zonedbx` databases
          which are used by unit tests.
* 1.2.1 (2023-01-10)
    * `cgenerator.py`
        * Rename `kAtcPolicyXxx` to `kAtcZonePolicyXxx` for consistency.
        * Include notable policy comments into `zone_infos.h` and
          `zone_infos.py`.
    * `argenerator.py`
        * Rename `kPolicyXxx` to `kZonePolicyXxx` for consistency.
    * `tzcompiler.sh`
        * Use 'git clone --branch tag' instead of 'git checkout tag'.
        * Eliminates modification of the target git repo.
        * Allows concurrent execution of `tzcompiler.sh`.
* 1.2.0 (2022-12-04)
    * If there are duplicate normalized zone names or link names, throw an
      exception to make it a fatal condition.
        * Allows detection and fixing of this problem, instead of silently
          dropping zones or links.
    * Detect Link to Link and throw exception.
    * Include notable policy comments into `zone_infos.h` and `zone_infos.py`.
* 1.1.4 (2022-11-02)
    * Add `--generate_int16_year` flag to generate year fields with `int16_t`
      type instead of `int8_t`.
    * Print the 3 notable zones whose UTC offset is not on the :00 or :30 mark.
* 1.1.3 (2022-10-22)
    * Use `ZoneProcessor.is_terminal_year()` to allow `bufestimator.py` to
      finish early when `until_year` is very large, e.g. 10000.
* 1.1.2 (2022-10-07)
    * Simplify `copytz.sh` by using `git clone` against the local repo to
      extract the files at a specific tag, instead of using `git checkout`.
        * Eliminates the need for `flock(1)` which is not supported on MacOS.
* 1.1.1 (2022-03-22)
    * Update docstring. No code changes.
    * This is a maintenance release to match the AceTime 1.11.3 release.
* 1.1.0 (2022-02-14)
    * Identify zones and policies whose DST shifts are not 0:00 or 1:00.
    * Simplify rendering of `CommentsMap` to support multiple comment lines.
    * Set the `eras` field of Link entries to the target `ZoneInfo` instead
      the `ZoneEras`, converting hard links to symbolic links.
        * Update `argenerator.py` for AceTime.
        * Update `pygenerator.py` for AceTimePython.
* 1.0.0 (2022-01-10)
    * Move `compare_xxx` scripts to `AceTimeValidation` repo.
    * Move `acetimetools/generate_validation.py` to `AceTimeValidation` repo.
    * Deprecate and archive `acetimetools/validator` to `archive/`.
    * Update `pygenerator.py`
        * Fix formatting to make flake8 happier
        * Add typing information to the `zone_{infos,policies,registry}.py`
          modules to make mypy happier.
        * Change `acetime.zonedbpy` package to `acetime.zonedb`.
        * Add zone context info to `zone_infos.py` (`TZDB_VERSION`,
          `START_YEAR`, `UNTIL_YEAR`).
* 0.2 (2021-12-02)
    * Validate that the zoneId and linkId cannot be 0x00, because 0x00
      is used as an error return code in certain parts of the AceTime C++ code.
    * Remove obsolete `sys.path` hack from `compare_acetz`, `compare_dateutil`,
      and `compare_pytz`. No longer needed after extracting `acetz` class into
      the separate AceTimePython project which is installed through `pip`.
    * Update GitHub workflows from Ubuntu 18.04 to 20.04, and add Python 3.9 and
      3.10 to the test matrix.
    * Update various `compare_{xxx}` binaries so that test samples are generated
      on the *second* of each month instead of the first. This prevents Jan 1,
      2000 from mapping to a negative epochSeconds, which converts to a UTC date
      in 1999, which can cause the estimated `max_buf_size` from
      `BufSizeEstimator` to be different than the actual maximum buf size
      observed by `ExtendedZoneProcessor`.
    * Add `max_buf_size` to the generated `zonedb*/zone_infos.h` files.
    * Add `compare_zoneinfo` which generates validation data using the Python
      3.9 zoneinfo package.
* 0.1 (2021-10-06)
    * Extract `zone_processor.py` and `acetz.py` to new
      [AceTimePython](https://github.com/bxparks/AceTimePython) library.
        * Rename `zone_specifier.py` to `zone_processor.py` to match the
          `ExtendedZoneProcessor` in C++ code.
        * Update `zone_processor.py` to match the exact algorithm used by
          `ExtendedZoneProcessor`, including the `TransitionStorage` buffer size
          calculation.
        * Remove `__slots__` in `zone_processor.py` and make it compatible
          with mypy type checking.
    * Circular dependency between projects:
        * `AceTimePython/src/acetime/zonedb/*` files require
          `AceTimeTools/pygenerator.py` to generate its zoneinfo files, which
          is consumed by `AceTimePython/src/acetime/acetz.py`.
        * `AceTimeTools/{zinfo.py,bufestimator.py,compare_acetz} requires
          `AceTimePython/zone_processor.py`
    * `pygenerator.py`
        * Rename `zone_registry.ZONE_INFO_MAP` to `ZONE_REGISTRY`.
        * Add `ZONE_AND_LINK_REGISTRY` that contains both zones and links.
        * Add `LINK` entries as aliases to `ZONE` entries.
            * Links in this implementation are "fat" links.
            * They are identical to zones, preserving their zone names.
            * In fact, the runtime cannot distinguish between a Zone and a Link.
    * `compare_acetz`
        * Use new `ZoneManager` class from `AceTimePython` library.
* (2021-08-25)
    * Initial `git subtree split` from AceTime project.
