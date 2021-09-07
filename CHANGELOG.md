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
* (2021-08-25)
    * Initial `git subtree split` from AceTime project.
