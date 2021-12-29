# Changelog

* Unreleased
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
