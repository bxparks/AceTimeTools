# Copyright 2023 Brian T. Park
#
# MIT License
"""
Generate the 'format' OffsetMap, and the 'letters' OffsetMap for the AceTimeGo
library.
"""

from typing import Dict
from typing import Iterable
from typing import List
from typing import Set
from typing import Tuple
import logging
from collections import OrderedDict

from acetimetools.data_types.at_types import ZonesMap
from acetimetools.data_types.at_types import PoliciesMap
from acetimetools.data_types.at_types import TransformerResult
from acetimetools.data_types.at_types import OffsetMap
from acetimetools.data_types.at_types import IndexMap
from acetimetools.data_types.at_types import IndexSizeMap


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

        zones_and_links = (
            list(tresult.zones_map.keys())
            + list(tresult.links_map.keys())
        )
        zone_and_link_ids = tresult.zone_ids.copy()
        zone_and_link_ids.update(tresult.link_ids)
        zone_and_link_index_map = _generate_zone_and_link_index_map(
            zones_and_links, zone_and_link_ids)

        policy_index_size_map, rule_count = _generate_policy_index_size_map(
            tresult.policies_map)

        info_index_size_map, era_count = _generate_info_index_size_map(
            tresult.zones_map)

        tresult.go_letters_map = letters_map
        tresult.go_formats_map = formats_map
        tresult.go_names_map = names_map
        tresult.go_zone_and_link_index_map = zone_and_link_index_map
        tresult.go_policy_index_size_map = policy_index_size_map
        tresult.go_rule_count = rule_count
        tresult.go_info_index_size_map = info_index_size_map
        tresult.go_era_count = era_count

    def print_summary(self, tresult: TransformerResult) -> None:
        logging.info(
            "Summary: "
            f"{len(tresult.go_info_index_size_map)} Zones"
            f"; {len(tresult.go_policy_index_size_map)} Policies"
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


def _generate_zone_and_link_index_map(
    zones_and_links: List[str],
    zone_and_link_ids: Dict[str, int],
) -> IndexMap:
    """ Create a combined IndexMap of zones and links, sorted by zoneId to
    allow binary searchon zoneId.
    """
    zone_and_link_index_map: IndexMap = {}
    index = 0
    for name in sorted(
        zones_and_links,
        key=lambda x: zone_and_link_ids[x],
    ):
        zone_and_link_index_map[name] = index
        index += 1
    return zone_and_link_index_map


def _generate_policy_index_size_map(
    policies_map: PoliciesMap
) -> Tuple[IndexSizeMap, int]:
    """Return the {policy -> (index, offset, size)}, and the total number of
    rules.
    """

    policy_index = 0
    rules_index = 0
    index_map: IndexSizeMap = {}

    index_map[""] = (0, 0, 0)  # add sentinel for "Null Policy"
    policy_index += 1

    for policy_name, rules in sorted(policies_map.items()):
        index_map[policy_name] = (policy_index, rules_index, len(rules))
        rules_index += len(rules)
        policy_index += 1
    return index_map, rules_index


def _generate_info_index_size_map(
    zones_map: ZonesMap
) -> Tuple[IndexSizeMap, int]:
    """Create a map of {zone_name -> (info_index, era_index, era_size)}, along
    with the total number of eras.
    """

    info_index = 0
    eras_index = 0
    index_map: IndexSizeMap = {}
    for zone_name, eras in sorted(zones_map.items()):
        index_map[zone_name] = (info_index, eras_index, len(eras))
        eras_index += len(eras)
        info_index += 1
    return index_map, eras_index
