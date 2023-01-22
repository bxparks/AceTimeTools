# Copyright 2023 Brian T. Park
#
# MIT License
"""
Generate the 'format' IndexMap, and the 'letters' IndexMap for the AceTimeGo
library.
"""

from typing import Set
import logging
from collections import OrderedDict

from acetimetools.data_types.at_types import ZonesMap
from acetimetools.data_types.at_types import PoliciesMap
from acetimetools.data_types.at_types import TransformerResult
from acetimetools.data_types.at_types import IndexMap


class GoTransformer:
    """Process TransformerResult and generate the go_format_index_map and
    go_letters_index_map needed by gogenerator.py.
    """
    def __init__(self) -> None:
        pass

    def transform(self, tresult: TransformerResult) -> None:
        letters_map = _collect_letter_strings(tresult.policies_map)
        formats_map = _collect_format_strings(tresult.zones_map)

        tresult.go_letters_map = letters_map
        tresult.go_formats_map = formats_map

    def print_summary(self, tresult: TransformerResult) -> None:
        logging.info(
            "Summary"
            f": {len(tresult.go_letters_map)} Letters"
            f"; {len(tresult.go_formats_map)} Formats"
        )


def _collect_letter_strings(policies_map: PoliciesMap) -> IndexMap:
    """Collect all LETTER entries into the IndexMap that contains the *byte*
    offset into each letter. This will be used by the AceTimeGo library. The
    final entry is a sentinel "~" (the last ASCII character) which should not
    exist in the TZDB.
    """
    all_letters: Set[str] = set()
    for policy_name, rules in policies_map.items():
        for rule in rules:
            letter = rule['letter']
            all_letters.add(letter)

    # Create a map of letter to byte_offset.
    offset = 0
    letters_map: IndexMap = OrderedDict()
    for letter in sorted(all_letters):
        letters_map[letter] = offset
        offset += len(letter)
    letters_map["~"] = offset  # final sentinel marker

    return letters_map


def _collect_format_strings(zones_map: ZonesMap) -> IndexMap:
    """Collect the 'formats' field and return a map of *byte* offsets.
    The final entry is a sential "~" which should not exist in the TZDB.
    """
    short_formats: Set[str] = set()
    for zone_name, eras in zones_map.items():
        for era in eras:
            format = era['format']
            short_format = format.replace('%s', '%')
            short_formats.add(short_format)

    # Create a map of format to byte offset
    offset = 0
    short_formats_map: IndexMap = OrderedDict()
    for short_format in sorted(short_formats):
        short_formats_map[short_format] = offset
        offset += len(short_format)
    short_formats_map["~"] = offset  # final sentinel marker

    return short_formats_map
