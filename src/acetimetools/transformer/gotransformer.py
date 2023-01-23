# Copyright 2023 Brian T. Park
#
# MIT License
"""
Generate the 'format' OffsetMap, and the 'letters' OffsetMap for the AceTimeGo
library.
"""

from typing import Iterable
from typing import Set
import logging
from collections import OrderedDict

from acetimetools.data_types.at_types import ZonesMap
from acetimetools.data_types.at_types import PoliciesMap
from acetimetools.data_types.at_types import TransformerResult
from acetimetools.data_types.at_types import OffsetMap


class GoTransformer:
    """Process TransformerResult and generate the go_format_index_map and
    go_letters_index_map needed by gogenerator.py.
    """
    def __init__(self) -> None:
        pass

    def transform(self, tresult: TransformerResult) -> None:
        letters_map = _collect_letter_strings(tresult.policies_map)
        formats_map = _collect_format_strings(tresult.zones_map)
        names_map = _collect_name_strings(
            tresult.zones_map.keys(),
            tresult.links_map.keys(),
        )

        tresult.go_letters_map = letters_map
        tresult.go_formats_map = formats_map
        tresult.go_names_map = names_map

    def print_summary(self, tresult: TransformerResult) -> None:
        logging.info(
            "Summary"
            f": {len(tresult.go_letters_map)} Letters"
            f"; {len(tresult.go_formats_map)} Formats"
            f"; {len(tresult.go_names_map)} Names"
        )


def _collect_letter_strings(policies_map: PoliciesMap) -> OffsetMap:
    """Collect all LETTER entries into the OffsetMap that contains the *byte*
    offset into each letter. This will be used by the AceTimeGo library. The
    final entry is a sentinel "~" (the last ASCII character) which should not
    exist in the TZDB.
    """
    all_letters: Set[str] = set()
    all_letters.add('')  # always include the empty string
    for policy_name, rules in policies_map.items():
        for rule in rules:
            letter = rule['letter']
            if letter == '-':  # replace '-' with just an empty string
                letter = ''
            all_letters.add(letter)

    # Create a map of letter to byte_offset.
    index = 0
    offset = 0
    letters_map: OffsetMap = OrderedDict()
    for letter in sorted(all_letters):
        letters_map[letter] = (index, offset)
        index += 1
        offset += len(letter)
    letters_map["~"] = (index, offset)  # final sentinel marker

    # Check that the letters_buffer fits using a uint8 type.
    if offset >= 256:
        raise Exception(f"Total size of LETTERS ({offset}) is >= 256")

    return letters_map


def _collect_format_strings(zones_map: ZonesMap) -> OffsetMap:
    """Collect the 'formats' field and return a map of *byte* offsets.
    The final entry is a sential "~" which should not exist in the TZDB.
    """
    formats: Set[str] = set()
    formats.add('')  # always include the empty string
    for zone_name, eras in zones_map.items():
        for era in eras:
            format = era['format']
            format = format.replace('%s', '%')
            formats.add(format)

    # Create a map of format to byte offset
    index = 0
    offset = 0
    formats_map: OffsetMap = OrderedDict()
    for format in sorted(formats):
        formats_map[format] = (index, offset)
        index += 1
        offset += len(format)
    formats_map["~"] = (index, offset)  # final sentinel marker

    # Check that the formats_buffer fits using a uint16 type.
    if offset >= 65536:
        raise Exception(f"Total size of FORMATS ({offset}) is >= 65536")

    return formats_map


def _collect_name_strings(
    zone_names: Iterable[str],
    link_names: Iterable[str],
) -> OffsetMap:

    names: Set[str] = set()
    names.add('')  # always include the empty string
    names.update(zone_names)
    names.update(link_names)

    # Create a map of name to byte offset
    index = 0
    offset = 0
    names_map: OffsetMap = OrderedDict()
    for name in sorted(names):
        names_map[name] = (index, offset)
        index += 1
        offset += len(name)
    names_map["~"] = (index, offset)  # final sentinel marker

    # Check that the names_buffer fits using a uint16 type.
    if offset >= 65536:
        raise Exception(f"Total size of Names ({offset}) is >= 65536")

    return names_map
