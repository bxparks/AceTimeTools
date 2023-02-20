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

from acetimetools.data_types.at_types import IndexMap
from acetimetools.data_types.at_types import IndexSizeMap
from acetimetools.data_types.at_types import LinksMap
from acetimetools.data_types.at_types import MemoryMap
from acetimetools.data_types.at_types import OffsetMap
from acetimetools.data_types.at_types import PoliciesMap
from acetimetools.data_types.at_types import TransformerResult
from acetimetools.data_types.at_types import ZonesMap
from acetimetools.transformer.artransformer import _to_suffix_code


class GoTransformer:
    """Process TransformerResult and generate the go_format_index_map and
    go_letters_index_map needed by gogenerator.py.
    """
    def __init__(self) -> None:
        pass

    def transform(self, tresult: TransformerResult) -> None:
        letters_map = _collect_letter_strings(tresult.policies_map)
        if letters_map['~'][1] > 255:
            raise Exception("Total letter strings exceeds uint8 max of 255")

        formats_map = _collect_format_strings(tresult.zones_map)
        if formats_map['~'][1] > 65535:
            raise Exception("Total format strings exceeds uint16 max of 65535")

        zone_and_link_names = (
            list(tresult.zones_map.keys())
            + list(tresult.links_map.keys())
        )
        names_map = _collect_name_strings(zone_and_link_names)
        if names_map['~'][1] > 65535:
            raise Exception("Total name strings exceeds uint16 max of 65535")

        zone_and_link_ids = tresult.zone_ids.copy()
        zone_and_link_ids.update(tresult.link_ids)
        zone_and_link_index_map = _generate_zone_and_link_index_map(
            zone_and_link_names, zone_and_link_ids)

        policy_index_size_map, rule_count = _generate_policy_index_size_map(
            tresult.policies_map)
        if rule_count > 65535:
            raise Exception("Rule count exceeds uint16 max of 65536")
        if len(policy_index_size_map) > 255:
            raise Exception("Policy count exceeds uint8 max of 255")

        info_index_size_map, era_count = _generate_info_index_size_map(
            tresult.zones_map)
        if era_count > 65535:
            raise Exception("Era count exceeds uint16 max of 65536")
        if len(info_index_size_map) > 65535:
            raise Exception("Info count exceeds uint16 max of 65535")

        _generate_zone_era_time_codes(tresult.zones_map)
        _generate_zone_rule_time_codes(tresult.policies_map)

        memory_map = _generate_memory_map(
            tresult.zones_map,
            tresult.links_map,
            tresult.policies_map,
            names_map,
            formats_map,
            letters_map,
        )

        tresult.go_zone_and_link_index_map = zone_and_link_index_map
        tresult.go_policy_index_size_map = policy_index_size_map
        tresult.go_rule_count = rule_count
        tresult.go_info_index_size_map = info_index_size_map
        tresult.go_era_count = era_count
        tresult.go_names_map = names_map
        tresult.go_formats_map = formats_map
        tresult.go_letters_map = letters_map
        tresult.go_memory_map = memory_map

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
    all_letters.add('')  # TODO: delete? letter '-' is normalized to ''
    for policy_name, rules in policies_map.items():
        for rule in rules:
            all_letters.add(rule['letter'])

    # Create a map of letter to byte_offset.
    index = 0
    offset = 0
    letters_map: OffsetMap = OrderedDict()
    for letter in sorted(all_letters):
        letters_map[letter] = (index, offset)
        index += 1
        offset += len(letter)
    letters_map["~"] = (index, offset)  # final sentinel marker

    return letters_map


def _collect_format_strings(zones_map: ZonesMap) -> OffsetMap:
    """Collect the 'formats' field and return a map of *byte* offsets.
    The final entry is a sential "~" which should not exist in the TZDB.
    """
    formats: Set[str] = set()
    formats.add('')  # TODO: delete?
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

    return formats_map


def _collect_name_strings(zone_and_link_names: Iterable[str]) -> OffsetMap:

    # Don't include the empty string.
    names: Set[str] = set()
    names.update(zone_and_link_names)

    # Create a map of name to byte offset
    index = 0
    offset = 0
    names_map: OffsetMap = OrderedDict()
    for name in sorted(names):
        names_map[name] = (index, offset)
        index += 1
        offset += len(name)
    names_map["~"] = (index, offset)  # final sentinel marker

    return names_map


def _generate_zone_and_link_index_map(
    zone_and_link_names: List[str],
    zone_and_link_ids: Dict[str, int],
) -> IndexMap:
    """ Create a combined IndexMap of zones and links, sorted by zoneId to
    allow binary searchon zoneId.
    """
    zone_and_link_index_map: IndexMap = {}
    index = 0
    for name in sorted(
        zone_and_link_names,
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


def _generate_zone_era_time_codes(zones_map: ZonesMap) -> None:
    for name, eras in sorted(zones_map.items()):
        for era in eras:
            # OffsetSeconds
            offset_seconds = era['offset_seconds_truncated']
            era['go_offset_seconds_code'] = offset_seconds // 15
            era['go_offset_seconds_remainder'] = offset_seconds % 15

            # DeltaMinutes
            delta_seconds = era['era_delta_seconds_truncated']
            era['go_era_delta_minutes'] = delta_seconds // 60
            if delta_seconds % 60 != 0:
                raise Exception(
                    f"ERROR: Zone {name} should have delta_seconds "
                    "in units of one minute"
                )

            # UntilSeconds
            until_seconds = era['until_seconds_truncated']
            era['go_until_seconds_code'] = until_seconds // 15
            era['go_until_seconds_remainder'] = until_seconds % 15
            era['go_until_seconds_suffix_value'] = _to_suffix_code(
                era['until_time_suffix'])
            era['go_until_seconds_modifier'] = (
                era['go_until_seconds_suffix_value']
                + era['go_until_seconds_remainder']
            )


def _generate_zone_rule_time_codes(policies_map: PoliciesMap) -> None:
    for name, rules in policies_map.items():
        for rule in rules:
            # DeltaMinutes
            delta_seconds = rule['delta_seconds_truncated']
            if delta_seconds % 60 != 0:
                raise Exception(
                    f"ERROR: Policy {name} should have delta_seconds "
                    "in units of one minute"
                )
            rule['go_delta_minutes'] = delta_seconds // 60

            # AtSeconds
            at_seconds = rule['at_seconds_truncated']
            rule['go_at_seconds_code'] = at_seconds // 15
            rule['go_at_seconds_remainder'] = at_seconds % 15
            rule['go_at_seconds_suffix_value'] = _to_suffix_code(
                rule['at_time_suffix'])
            rule['go_at_seconds_modifier'] = (
                rule['go_at_seconds_suffix_value']
                + rule['go_at_seconds_remainder']
            )


def _generate_memory_map(
    zones_map: ZonesMap,
    links_map: LinksMap,
    policies_map: PoliciesMap,
    names_map: OffsetMap,
    formats_map: OffsetMap,
    letters_map: OffsetMap,
) -> MemoryMap:

    num_rules = sum([len(rules) for _, rules in policies_map.items()])
    num_policies = len(policies_map)
    num_eras = sum([len(eras) for _, eras in zones_map.items()])
    num_zones = len(zones_map)
    num_links = len(links_map)

    rule_chunk_size = 12
    rule_size = num_rules * rule_chunk_size

    policy_chunk_size = 4
    policy_size = num_policies * policy_chunk_size

    era_chunk_size = 14
    era_size = num_eras * era_chunk_size

    info_chunk_size = 12
    zone_size = num_zones * info_chunk_size
    link_size = num_links * info_chunk_size

    registry_size = 0
    fragment_size = 0

    name_size = sum([len(name) for name, _ in names_map.items()])
    name_size += 2 * len(names_map)  # NameOffsets[] array

    format_size = sum([len(format) for format, _ in formats_map.items()])
    format_size += 2 * len(formats_map)  # FormatOffsets[] array

    letter_size = sum([len(letter) for letter, _ in letters_map.items()])
    letter_size += 1 * len(letters_map)  # LetterOffsets[] array

    total_size = (
        rule_size
        + policy_size
        + era_size
        + zone_size
        + link_size
        + registry_size
        + name_size
        + format_size
        + letter_size
    )

    return {
        'rules': rule_size,
        'policies': policy_size,
        'eras': era_size,
        'zones': zone_size,
        'links': link_size,
        'registry': registry_size,
        'names': name_size,
        'names_original': name_size,
        'fragments': fragment_size,
        'formats': format_size,
        'letters': letter_size,
        'total': total_size,
    }
