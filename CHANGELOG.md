# Changelog

* Unreleased
* v1.6.0 (2023-03-09)
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
* v1.5.0 (2023-02-13)
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
* v1.4.3 (2023-02-04)
    * `argenerator.py`, `cgenerator.py`:
        * Simplify encoding of `Rule.LETTER` as an index into
          `ZoneContext.letters`.
* v1.4.2 (2023-02-02)
    * `tzcompiler.sh`:
        * Incorporate `copytz.sh` functionality directly to avoid dependency on
          another shell script.
        * If `--tag` is not given, then copy the TZDB repo instead of doing a
          `git clone`.
        * Add `trap` statement to perform auto-cleanup of the `tzfiles/`
          temporary directory.
        * Add `--tzrepo` to specify the location of the TZDB repo explicitly.
* v1.4.1 (2023-01-29)
    * `argenerator.py`
        * Remove LinkRegistry.
        * Add `targetInfo` to `ZoneInfo` to unify fat and symbolic Links.
    * `cgenerator.py`
        * Remove LinkRegistry.
        * Add `targetInfo` to `ZoneInfo` to unify fat and symbolic Links.
* v1.4.0 (2023-01-29)
    * Support the AceTimeGo library through `gotransfomer.py` and
      `gogenerator.py`.
    * Simplify calling API of various `XxxTransformer` classes.
* v1.3.0 (2023-01-17)
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
* v1.2.1 (2023-01-10)
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
* v1.2.0 (2022-12-04)
    * If there are duplicate normalized zone names or link names, throw an
      exception to make it a fatal condition.
        * Allows detection and fixing of this problem, instead of silently
          dropping zones or links.
    * Detect Link to Link and throw exception.
    * Include notable policy comments into `zone_infos.h` and `zone_infos.py`.
* v1.1.4 (2022-11-02)
    * Add `--generate_int16_year` flag to generate year fields with `int16_t`
      type instead of `int8_t`.
    * Print the 3 notable zones whose UTC offset is not on the :00 or :30 mark.
* v1.1.3 (2022-10-22)
    * Use `ZoneProcessor.is_terminal_year()` to allow `bufestimator.py` to
      finish early when `until_year` is very large, e.g. 10000.
* v1.1.2 (2022-10-07)
    * Simplify `copytz.sh` by using `git clone` against the local repo to
      extract the files at a specific tag, instead of using `git checkout`.
        * Eliminates the need for `flock(1)` which is not supported on MacOS.
* v1.1.1 (2022-03-22)
    * Update docstring. No code changes.
    * This is a maintenance release to match the AceTime v1.11.3 release.
* v1.1.0 (2022-02-14)
    * Identify zones and policies whose DST shifts are not 0:00 or 1:00.
    * Simplify rendering of `CommentsMap` to support multiple comment lines.
    * Set the `eras` field of Link entries to the target `ZoneInfo` instead
      the `ZoneEras`, converting hard links to symbolic links.
        * Update `argenerator.py` for AceTime.
        * Update `pygenerator.py` for AceTimePython.
* v1.0.0 (2022-01-10)
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
* v0.2 (2021-12-02)
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
* v0.1 (2021-10-06)
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
