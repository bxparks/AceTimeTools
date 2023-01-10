# AceTime Tools

[![Python Tools](https://github.com/bxparks/AceTimeTools/actions/workflows/python_tools.yml/badge.svg)](https://github.com/bxparks/AceTimeTools/actions/workflows/python_tools.yml)

These are various scripts and tools which parse the [IANA
TZ database](https://www.iana.org/time-zones) and generate zoneinfo datasets for
the [AceTime](https://github.com/bxparks/AceTime) Arduino library and the
[AceTimePython](https://github.com/bxparks/AceTimePython) library. These tools
used to be in the AceTime project itself, but was extracted into a separate repo
to support other languages and environments.

**Version**: v1.2.1 (2023-01-10)

**Changelog**: [CHANGELOG.md](CHANGELOG.md)

## Summary of Tools

Here is a quick summary of the various tools:

* `tzcompiler.sh`
    * main driver for generating the zoneinfo files in the various `zonedb*/`
      irectories.
    * thin shell wrapper around the `tzcompiler.py` script, which invokes an ETL
      data processing pipeline to perform 2 major tasks:
        * parse and read the raw IANA TZ databas files with `Zone`, `Link` and
        `Rule` entries),
        * generate the `zone_infos.{h,cpp}`, `zone_policies.{h,cpp}`,
        `zone_registry.{h,cpp}` files in the specified `zonedb*/` directory.
* `zinfo.py`
    * a command line interface to the `zone_processor.py` Python
      module using a pre-compiled zoneinfo files in
      `AceTimePython/src/acetime/zonedb/` directory.
    * (Maybe move to AceTimePython project? Though it's sometimes useful for
      debugging output of the `tzcompiler.py`)
* `copytz.sh`
    * script to copy the raw TZDB files from a local copy of the IANA TZDB repo
      (https://github.com/eggert/tz/) at a specific tag version (e.g. "2021e")
      into the current directory
    * copying the raw TZDB files allows parallel pipelines which use different
      TZDB versions

## TZ Compiler (tzcompiler.py)

The TZ Database processing pipeline for `tzcompiler.py` looks something like
this:

```
Python packages     Python files/classes/data
===============     =========================

                      TZDB files
  .------>                |
  |                       v
extractor            Extractor.parse()
  |                       |     (PoliciesMap, ZonesMap, LinksMap)
  |                       |
  +------>                v     (TransformerResult)
  |                 Transformer.transform()
  |                       |
  |                       |     (TransformerResult)
transformer               v
  |                 ArduinoTransformer.transform()
  |                       | \   (TransformerResult)
  +------>                |  \
  |                       |   v     (ZonesMap, PoliciesMap)
  |                       |  BufSizeEstimator.calculate_buf_size_map()
  |                       |                 |
  |                       |                 v    (ZonesMap, PoliciesMap)
  |                       |         ZoneInfoInliner.generate_zonedb()
  |                       |                 |    (ZoneInfoMap, ZonePolicyMap)
AceTimePython/            |                 v
zone_processor            |     BufSizeEstimator._calculate_buf_sizes_per_zone()
  |                       |           /     \
  |                       |          /       v
  |                       |         /       ZoneProcessor.get_buffer_sizes()
  |                       |        /        /
  |                       |       /        v  (BufSizeMap)
  |                       |      /  BufSizeEstimator.calculate_max_buf_size()
  |                       |     /      / (int)
  |                       |    /      /
  +------>                |   /      /
  |                       v  v      v
  |             create_zone_info_database()
data_types                |     (ZoneInfoDatabase)
  |                       v
  |                ZoneInfoDatabase
  |                 /     |     \
  +------>         /      |      \
  |               /       |       ------------------------.
  |              /        |                  \             \
generator       /         |                   \             \
  |            v          v                    v             v
  |   argenerator.py   pygenerator.py    jsongenerator.py  zonelist
  |          /            |                    |           generator.py
  `--->     /             |                    |                \
           v              v                    v                 v
zone_infos.{h,cpp}      zone_infos.py       zonedb.json      zones.txt
zone_policies.{h,cpp}   zone_policies.py                         |
zone_registry.{h,cpp}   zone_strings.py                          v
zone_strings.{h,cpp}         |                           (AceTimeValidation)
                             v
                          zinfo.py
```

## Dependencies

* Python3.7 or higher
* [IANA TZ Database](https://github.com/eggert/tz) as a sibling directory
    * `$ cd ..`
    * `$ git clone https://github.com/eggert/tz`
* [AceTimePython](https://github.com/bxparks/AceTimePython)
    * This causes a partial circular dependency.
    * AceTimeTool generates the `zonedb` files used by the AceTimePython
      classes.
    * But AceTimeTool feeds the in-memory transient versions of the `zonedb`
      files into the `zone_processor.py` module in AceTimePython to estimate the
      Transition buffer sizes, which is then included in the actual
      `src/acetime/zonedb` files written into the AceTimePython library.

## Usage

In the following:

* `$ACE_TIME` is the location of the AceTime project
* `$ACE_TIME_PYTHON` is the location of the AceTimePython project

### Generating ZoneDB Files

**AceTime**

```
$ cd $ACE_TIME/src/ace_time/zonedb
$ vi Makefile # Update the TZ_VERSION variable
$ make

$ cd $ACE_TIME/src/ace_time/zonedbx
$ vi Makefile # Update the TZ_VERSION
$ make
```

**AceTimePython**

```
$ cd $ACE_TIME_PYTHON/src/acetime/zonedb
$ vi Makefile # Update the TZ_VERSION variable
$ make
```

### Type Checking

The scripts should pass `mypy` type checking in `strict` mode:
```
$ make mypy
```

### Unit Testing

The unit tests for the AceTimeTools project itself can be run with:
```
$ make tests
```

<a name="License"></a>
## License

[MIT License](https://opensource.org/licenses/MIT)

<a name="FeedbackAndSupport"></a>
## Feedback and Support

If you have any questions, comments, or feature requests for this library,
please use the [GitHub
Discussions](https://github.com/bxparks/AceTimeTools/discussions) for this
project. If you have bug reports, please file a ticket in [GitHub
Issues](https://github.com/bxparks/AceTimeTools/issues). Feature requests should
go into Discussions first because they often have alternative solutions which
are useful to remain visible, instead of disappearing from the default view of
the Issue tracker after the ticket is closed.

Please refrain from emailing me directly unless the content is sensitive. The
problem with email is that I cannot reference the email conversation when other
people ask similar questions later.

<a name="Authors"></a>
## Authors

* Created by Brian T. Park (brian@xparks.net).
