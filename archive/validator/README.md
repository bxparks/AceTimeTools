# Interactive Validation (validate.py)

The `validate.py` script allows us to validate the processing of the TZ Database
through the Python implementation of the AceTime `ZoneProcessor` classes. The
Python implementation is called `ZoneProcessor` (a previous naming convention
used in the C++ version which did not make it over the Python world). This
functionality was previously inside `tzcompiler.py` itself before it was
extracted out into `validate.py` to reduce the complexity of the `tzcompiler.py`
script. The data processing pipeline for the `validate.py` script looks like
this

```
         TZDB files
             |
             v
        extractor.py
             |
             v
        transformer.py
             |
             v
     inline_zone_info.py
         /        \
        /          v
       /         zone_processor.py   pytz
      v               \               /
zone_processor.py      v             v
        \             zstdgenerator.py
         \            /
          v          v
          validator.py
```
