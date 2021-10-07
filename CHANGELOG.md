# Changelog

* Unreleased
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
        * `AceTimePython/zonedbpy/*` files requires
          `AceTimeTools/pygenerator.py` to generate its zoneinfo files, which
          is consumed by `AceTimePython/acetz.py`.
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
