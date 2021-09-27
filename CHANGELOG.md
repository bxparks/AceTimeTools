# Changelog

* Unreleased
    * Rename `zone_specifier.py` to `zone_processor.py` to match the
      `ExtendedZoneProcessor` in C++ code.
    * Update `ZoneProcessor` to match the exact algorithm used by
      `ExtendedZoneProcessor`, including the `TransitionStorage` buffer size
      calculation.
        * Allows `AceTimeValidation/ExtendedHinnantDateTest` to test for
          match match between observed buffer size (from
          `ExtendedZoneProcessor`) and the expected buffer size (from
          `zone_processor.py`).
    * Add `LINK` entries as aliases to `ZONE` entries.
        * Links in this implementation are "fat" links.
        * They are identical to zones, preserving their zone names.
        * In fact, the runtime cannot distinguish between a Zone and a Link.
* (2021-08-25)
    * Initial `git subtree split` from AceTime project.
