# Copyright 2023 Brian T. Park
#
# MIT License
"""
Generate the 'zone_infos.py' and 'zone_policies.py' files for Go lang.
"""

import logging
import os
from typing import Iterable
from typing import List
from typing import Tuple

from acetimetools.data_types.at_types import ZoneEraRaw
from acetimetools.data_types.at_types import ZoneRuleRaw
from acetimetools.data_types.at_types import ZonesMap
from acetimetools.data_types.at_types import PoliciesMap
from acetimetools.data_types.at_types import CommentsMap
from acetimetools.data_types.at_types import MergedCommentsMap
from acetimetools.data_types.at_types import ZoneInfoDatabase
from acetimetools.data_types.at_types import IndexSizeMap
from acetimetools.transformer.transformer import normalize_name
from acetimetools.transformer.transformer import normalize_raw
from acetimetools.generator.byteutils import convert_to_go_string
from acetimetools.generator.byteutils import write_i8
from acetimetools.generator.byteutils import write_i16
from acetimetools.generator.byteutils import write_u8
from acetimetools.generator.byteutils import write_u16
from acetimetools.generator.byteutils import write_u32


class GoGenerator:
    """Generate Go lang files (zone_infos.go, zone_policies.go) which are
    used by the ZoneProcessor class.
    """

    ZONE_INFOS_FILE_NAME = 'zone_infos.go'
    ZONE_POLICIES_FILE_NAME = 'zone_policies.go'
    ZONE_REGISTRY_FILE_NAME = 'zone_registry.go'
    ZONE_INFOS_TEST_FILE_NAME = 'zone_infos_test.go'
    ZONE_POLICIES_TEST_FILE_NAME = 'zone_policies_test.go'
    ZONE_REGISTRY_TEST_FILE_NAME = 'zone_registry_test.go'
    READER_TEST_FILE_NAME = 'reader_test.go'

    def __init__(
        self,
        invocation: str,
        db_namespace: str,
        zidb: ZoneInfoDatabase,
    ):
        wrapped_invocation = '\n//     --'.join(invocation.split(' --'))
        wrapped_tzfiles = '\n//   '.join(zidb['tz_files'])
        self.invocation = wrapped_invocation
        self.tz_files = wrapped_tzfiles
        self.db_namespace = db_namespace
        self.tz_version = zidb['tz_version']
        self.start_year = zidb['start_year']
        self.until_year = zidb['until_year']
        self.num_zones = zidb['num_zones']
        self.num_links = zidb['num_links']
        self.num_policies = zidb['num_policies']
        self.num_eras = zidb['num_eras']
        self.num_rules = zidb['num_rules']
        self.zones_map = zidb['zones_map']
        self.links_map = zidb['links_map']
        self.policies_map = zidb['policies_map']
        self.removed_zones = zidb['removed_zones']
        self.removed_links = zidb['removed_links']
        self.removed_policies = zidb['removed_policies']
        self.notable_zones = zidb['notable_zones']
        self.merged_notable_zones = zidb['merged_notable_zones']
        self.notable_links = zidb['notable_links']
        self.notable_policies = zidb['notable_policies']
        self.original_min_year = zidb['original_min_year']
        self.original_max_year = zidb['original_max_year']
        self.generated_min_year = zidb['generated_min_year']
        self.generated_max_year = zidb['generated_max_year']
        self.estimator_min_year = zidb['estimator_min_year']
        self.estimator_max_year = zidb['estimator_max_year']
        self.max_buf_size = zidb['max_buf_size']
        self.zone_ids = zidb['zone_ids']
        self.link_ids = zidb['link_ids']
        self.letters_map = zidb['go_letters_map']
        self.formats_map = zidb['go_formats_map']
        self.names_map = zidb['go_names_map']
        self.zone_and_link_index_map = zidb['go_zone_and_link_index_map']
        self.policy_index_size_map = zidb['go_policy_index_size_map']
        self.info_index_size_map = zidb['go_info_index_size_map']
        self.memory_map = zidb['go_memory_map']

        self.zones_and_links = (
            list(self.zones_map.keys())
            + list(self.links_map.keys())
        )
        self.zone_and_link_ids = self.zone_ids.copy()
        self.zone_and_link_ids.update(self.link_ids)

    def generate_files(self, output_dir: str) -> None:
        self._write_file(output_dir, self.ZONE_POLICIES_FILE_NAME,
                         self._generate_policies())
        self._write_file(output_dir, self.ZONE_POLICIES_TEST_FILE_NAME,
                         self._generate_policies_test())

        self._write_file(output_dir, self.ZONE_INFOS_FILE_NAME,
                         self._generate_infos())
        self._write_file(output_dir, self.ZONE_INFOS_TEST_FILE_NAME,
                         self._generate_infos_test())

        self._write_file(output_dir, self.ZONE_REGISTRY_FILE_NAME,
                         self._generate_registry())
        self._write_file(output_dir, self.ZONE_REGISTRY_TEST_FILE_NAME,
                         self._generate_registry_test())

        self._write_file(output_dir, self.READER_TEST_FILE_NAME,
                         self._generate_reader_test())

    def _write_file(self, output_dir: str, filename: str, content: str) -> None:
        full_filename = os.path.join(output_dir, filename)
        with open(full_filename, 'w', encoding='utf-8') as output_file:
            print(content, end='', file=output_file)
        logging.info("Created %s", full_filename)

    # ------------------------------------------------------------------------
    # File Header
    # ------------------------------------------------------------------------
    def _generate_header(self) -> str:
        num_zones_and_links = self.num_zones + self.num_links
        num_removed_zones = len(self.removed_zones)
        num_removed_links = len(self.removed_links)
        num_removed_zones_and_links = num_removed_zones + num_removed_links

        return f"""\
// This file was generated by the following script:
//
//   $ {self.invocation}
//
// using the TZ Database files
//
//   {self.tz_files}
//
// from https://github.com/eggert/tz/releases/tag/{self.tz_version}
//
// Supported Zones: {num_zones_and_links} \
({self.num_zones} zones, {self.num_links} links)
// Unsupported Zones: {num_removed_zones_and_links} \
({num_removed_zones} zones, {num_removed_links} links)
//
// Original Years:  [{self.original_min_year},{self.original_max_year}]
// Generated Years: [{self.generated_min_year},{self.generated_max_year}]
// Estimator Years: [{self.estimator_min_year},{self.estimator_max_year}]
// Max Buffer Size: {self.max_buf_size}
//
// Records:
//   Infos: {num_zones_and_links}
//   Eras: {self.num_eras}
//   Policies: {self.num_policies}
//   Rules: {self.num_rules}
//
// Memory:
//   Rules: {self.memory_map['rules']}
//   Policies: {self.memory_map['policies']}
//   Eras: {self.memory_map['eras']}
//   Zones: {self.memory_map['zones']}
//   Links: {self.memory_map['links']}
//   Registry: {self.memory_map['registry']}
//   Formats: {self.memory_map['formats']}
//   Letters: {self.memory_map['letters']}
//   Fragments: {self.memory_map['fragments']}
//   Names: {self.memory_map['names']}
//   TOTAL: {self.memory_map['total']}
//
// DO NOT EDIT

"""

    # ------------------------------------------------------------------------
    # Zone Policies
    # ------------------------------------------------------------------------

    def _generate_policies(self) -> str:
        zone_rules_data, chunk_size, count = self._generate_rules_data(
            self.policies_map)
        zone_rules_data_string = convert_to_go_string(
            zone_rules_data, chunk_size, '\t')
        zone_rule_chunk_size = chunk_size
        zone_rule_count = count

        zone_policies_data, chunk_size, count = self._generate_policies_data(
            self.policy_index_size_map)
        zone_policies_data_string = convert_to_go_string(
            zone_policies_data, chunk_size, '\t')
        zone_policy_chunk_size = chunk_size
        zone_policy_count = count

        removed_policy_items = _render_comments_map(self.removed_policies)
        notable_policy_items = _render_comments_map(self.notable_policies)

        letter_data = '" +\n\t"'.join(self.letters_map.keys())
        letter_offsets = _render_offsets(
            [x[1] for x in self.letters_map.values()]
        )

        return self._generate_header() + f"""\
package {self.db_namespace}

// ---------------------------------------------------------------------------
// String constants.
// ---------------------------------------------------------------------------

// All ZoneRule.Letter entries concatenated together.
const LetterData = "{letter_data}"

// Byte offset into LetterData for each index. The actual Letter string
// at index `i` given by the `ZoneRule.Letter` field is
// `LetterData[LetterOffsets[i]:LetterOffsets[i+1]]`.
var LetterOffsets = []uint8{{
{letter_offsets}
}}

// ---------------------------------------------------------------------------
// ZoneRulesData is the encoded version of ZoneRuleRecords in
// {GoGenerator.ZONE_POLICIES_TEST_FILE_NAME}. It contains an array of
// ZoneRuleRecord encoded as string.
//
// Supported zone policies: {len(self.policies_map)}
// numRules: {self.num_rules}
// ---------------------------------------------------------------------------

const ZoneRuleCount = {zone_rule_count}

const ZoneRuleChunkSize = {zone_rule_chunk_size}

// ZoneRulesData contains the ZoneRuleRecords data as a hex encoded string.
const ZoneRulesData = {zone_rules_data_string}

// ---------------------------------------------------------------------------
// ZonePoliciesData is the encoded version of ZonePolicyRecords in
// {GoGenerator.ZONE_POLICIES_TEST_FILE_NAME}. It contains an array of
// ZonePolicyRecord which is a pair of (index, count) into the ZoneRuleRecords
// array.
//
// Supported zone policies: {len(self.policies_map)}
// ---------------------------------------------------------------------------

const ZonePolicyCount = {zone_policy_count}

const ZonePolicyChunkSize = {zone_policy_chunk_size}

// ZonePoliciesData contains the ZonePolicyRecords data as a hex encoded string.
const ZonePoliciesData = {zone_policies_data_string}

// ---------------------------------------------------------------------------
// Unsupported zone policies: {len(self.removed_policies)}
// ---------------------------------------------------------------------------

{removed_policy_items}

// ---------------------------------------------------------------------------
// Notable zone policies: {len(self.notable_policies)}
// ---------------------------------------------------------------------------

{notable_policy_items}
"""

    def _generate_policies_test(self) -> str:
        zone_rules_string = self._generate_rules_string(self.policies_map)
        zone_policies_string = self._generate_policies_string(
            self.policy_index_size_map)

        return self._generate_header() + f"""\
package {self.db_namespace}

import (
\t"github.com/bxparks/AceTimeGo/zoneinfo"
)
// ---------------------------------------------------------------------------
// ZoneRuleRecords is a concatenated array of zoneinfo.ZoneInfoRecord objects
// from all ZonePolicyRecords.
//
// Supported zone policies: {len(self.policies_map)}
// numRules: {self.num_rules}
// ---------------------------------------------------------------------------

var ZoneRuleRecords = []zoneinfo.ZoneRuleRecord{{
{zone_rules_string}
}}

// ---------------------------------------------------------------------------
// ZonePolicyRecords contain indexes into the ZoneRuleRecords.
// Supported zone policies: {len(self.policies_map)}
// ---------------------------------------------------------------------------

var ZonePolicyRecords = []zoneinfo.ZonePolicyRecord{{
{zone_policies_string}
}}

"""

    def _generate_rules_string(self, policies_map: PoliciesMap) -> str:
        zone_rules_string = ''
        rule_index = 0
        for policy_name, rules in sorted(policies_map.items()):
            zone_rules_string += self._generate_rule_items_string(
                policy_name, rule_index, rules)
            rule_index += len(rules)
            zone_rules_string += '\n'
        return zone_rules_string

    def _generate_rule_items_string(
        self,
        policy_name: str,
        rule_index: int,
        rules: List[ZoneRuleRaw]
    ) -> str:
        rule_items_string = f"""\
\t// ---------------------------------------------------------------------------
\t// PolicyName: {policy_name}
\t// RuleIndex: {rule_index}
\t// RuleCount: {len(rules)}
\t// ---------------------------------------------------------------------------

"""
        for rule in rules:
            raw_line = normalize_raw(rule['raw_line'])
            from_year = rule['from_year']
            to_year = rule['to_year']
            in_month = rule['in_month']
            on_day_of_week = rule['on_day_of_week']
            on_day_of_month = rule['on_day_of_month']

            letter = rule['letter']
            entry = self.letters_map[letter]
            letter_index = entry[0]  # entry[1] is the byte offset
            letter_comment = f'"{letter}"'

            # Explain how 'delta_code' was calculated.
            delta_minutes = rule['go_delta_minutes']

            at_seconds = rule['at_seconds_truncated']
            at_seconds_code = rule['go_at_seconds_code']
            at_seconds_remainder = rule['go_at_seconds_remainder']
            at_seconds_modifier = rule['go_at_seconds_modifier']
            at_seconds_modifier_comment = _get_time_modifier_comment(
                remainder_seconds=at_seconds_remainder,
                suffix=rule['at_time_suffix'],
            )

            rule_items_string += f"""\
\t// {raw_line}
\t{{
\t\tFromYear: {from_year},
\t\tToYear: {to_year},
\t\tInMonth: {in_month},
\t\tOnDayOfWeek: {on_day_of_week},
\t\tOnDayOfMonth: {on_day_of_month},
\t\tAtSecondsCode: {at_seconds_code}, // {at_seconds} / 15
\t\tAtSecondsModifier: {at_seconds_modifier}, // {at_seconds_modifier_comment}
\t\tDeltaMinutes: {delta_minutes},
\t\tLetterIndex: {letter_index}, // {letter_comment}
\t}},
"""
        return rule_items_string

    def _generate_rules_data(
        self, policies_map: PoliciesMap
    ) -> Tuple[bytearray, int, int]:
        """Return the bytearray encoding of the ZoneRuleRecords, and the size of
        each encoded ZoneRule.
        """

        chunk_size = 12
        data = bytearray()
        count = 0
        for policy_name, rules in sorted(policies_map.items()):
            count += len(rules)
            for rule in rules:
                self._generate_rule_data(data, rule)
        return data, chunk_size, count

    def _generate_rule_data(self, data: bytearray, rule: ZoneRuleRaw) -> None:
        # Find the index for the 'letter' field.
        letter = rule['letter']
        if letter == '-':
            letter = ''
        entry = self.letters_map[letter]
        letter_index = entry[0]  # entry[1] is the byte offset

        # chunk_size = 12 bytes
        # WARNING: If this is changed, the chunk_size must be updated.
        write_i16(data, rule['from_year'])
        write_i16(data, rule['to_year'])
        write_u8(data, rule['in_month'])
        write_u8(data, rule['on_day_of_week'])
        write_i8(data, rule['on_day_of_month'])
        write_u8(data, rule['go_at_seconds_modifier'])
        write_u16(data, rule['go_at_seconds_code'])
        write_i8(data, rule['go_delta_minutes'])
        write_u8(data, letter_index)

    def _generate_policies_string(
        self, policy_index_size_map: IndexSizeMap
    ) -> str:
        zone_policies_string = ''
        for policy_name, indexes in policy_index_size_map.items():
            index = indexes[0]
            rule_index = indexes[1]
            rule_count = indexes[2]
            if policy_name == "":
                policy_name = "(None)"
            zone_policies_string += f"""\
\t{{RuleIndex: {rule_index}, RuleCount: {rule_count}}}, \
// {index}: PolicyName: {policy_name}
"""
        return zone_policies_string

    def _generate_policies_data(
        self, policy_index_size_map: IndexSizeMap
    ) -> Tuple[bytearray, int, int]:
        """Return the bytearray encoding of the ZonePolicyRecords, and the size
        of each encoded ZonePolicy.
        """
        chunk_size = 4
        data = bytearray()
        for policy_name, indexes in policy_index_size_map.items():
            rule_index = indexes[1]
            rule_count = indexes[2]
            # WARNING: If this is changed, the chunk_size must be updated.
            write_u16(data, rule_index)
            write_u16(data, rule_count)
        return data, chunk_size, len(policy_index_size_map)

    # ------------------------------------------------------------------------
    # Zone Infos
    # ------------------------------------------------------------------------

    def _generate_infos(self) -> str:
        zone_eras_data, chunk_size, count = self._generate_eras_data(
            self.zones_map)
        zone_eras_data_string = convert_to_go_string(
            zone_eras_data, chunk_size, '\t')
        zone_era_chunk_size = chunk_size
        zone_era_count = count

        zone_infos_data, chunk_size, count = self._generate_infos_data()
        zone_infos_data_string = convert_to_go_string(
            zone_infos_data, chunk_size, '\t')
        zone_info_chunk_size = chunk_size
        zone_info_count = count

        removed_info_items = _render_comments_map(self.removed_zones)
        # notable_info_items = _render_comments_map(self.notable_zones)
        notable_info_items = _render_merged_comments_map(
            self.merged_notable_zones)
        removed_link_items = _render_comments_map(self.removed_links)
        notable_link_items = _render_comments_map(self.notable_links)

        format_data = '" +\n\t"'.join(self.formats_map.keys())
        format_offsets = _render_offsets(
            [x[1] for x in self.formats_map.values()]
        )

        name_data = '" +\n\t"'.join(self.names_map.keys())
        name_offsets = _render_offsets(
            [x[1] for x in self.names_map.values()]
        )

        num_zones = len(self.zones_map)
        num_links = len(self.links_map)
        num_zones_and_links = len(self.zones_and_links)
        num_removed_zones = len(self.removed_zones)
        num_removed_links = len(self.removed_links)

        return self._generate_header() + f"""\
package {self.db_namespace}

// ---------------------------------------------------------------------------
// String constants.
// ---------------------------------------------------------------------------

// All ZoneEra.Format entries concatenated together.
const FormatData = "{format_data}"

// All ZoneInfo.Name entries concatenated togther.
const NameData = "{name_data}"

// Byte offset into FormatData for each index. The actual Format string
// at index `i` given by the `ZoneEra.Format` field is
// `FormatData[FormatOffsets[i]:FormatOffsets[i+1]]`.
var FormatOffsets = []uint16{{
{format_offsets}
}}

// Byte offset into NameData for each index. The actual Letter string
// at index `i` given by the `ZoneRule.Name` field is
// `NameData[NameOffsets[i]:NameOffsets[i+1]]`.
var NameOffsets = []uint16{{
{name_offsets}
}}

// ---------------------------------------------------------------------------
// ZoneErasData is the encoded version of ZoneEraRecords.
//
// Supported zones: {num_zones}
// numEras: {self.num_eras}
// ---------------------------------------------------------------------------

const ZoneEraCount = {zone_era_count}

const ZoneEraChunkSize = {zone_era_chunk_size}

// ZoneErasData contains the ZoneEraRecords data as a hex encoded string.
const ZoneErasData = {zone_eras_data_string}

// ---------------------------------------------------------------------------
// ZoneInfoRecords is an array of zoneinfo.ZoneInfoRecord items concatenated
// together.
//
// Total: {num_zones_and_links} ({num_zones} zones, {num_links} links)
// ---------------------------------------------------------------------------

const ZoneInfoCount = {zone_info_count}

const ZoneInfoChunkSize = {zone_info_chunk_size}

// ZoneInfosData contains the ZoneInfoRecords data as a hex encoded string.
const ZoneInfosData = {zone_infos_data_string}

// ---------------------------------------------------------------------------
// Unsupported zones: {num_removed_zones}
// ---------------------------------------------------------------------------

{removed_info_items}

// ---------------------------------------------------------------------------
// Notable zones: {len(self.notable_zones)}
// ---------------------------------------------------------------------------

{notable_info_items}

// ---------------------------------------------------------------------------
// Unsuported links: {num_removed_links}
// ---------------------------------------------------------------------------

{removed_link_items}

// ---------------------------------------------------------------------------
// Notable links: {len(self.notable_links)}
// ---------------------------------------------------------------------------

{notable_link_items}
"""

    def _generate_infos_test(self) -> str:
        zone_eras_string = self._generate_eras_string(self.zones_map)
        zone_infos_string = self._generate_infos_string()
        num_zones = len(self.zones_map)
        num_links = len(self.links_map)
        num_zones_and_links = len(self.zones_and_links)

        return self._generate_header() + f"""\
package {self.db_namespace}

import (
\t"github.com/bxparks/AceTimeGo/zoneinfo"
)

// ---------------------------------------------------------------------------
// ZoneEraRecords is an array of ZoneEraRecord items concatenated together
// across all zones.
//
// Supported zones: {num_zones}
// numEras: {self.num_eras}
// ---------------------------------------------------------------------------

var ZoneEraRecords = []zoneinfo.ZoneEraRecord{{
{zone_eras_string}
}}

// ---------------------------------------------------------------------------
// ZoneInfoRecords is an array of ZoneInfoRecord items concatenated together
// across all zones.
//
// Total: {num_zones_and_links} ({num_zones} zones, {num_links} links)
// ---------------------------------------------------------------------------

var ZoneInfoRecords = []zoneinfo.ZoneInfoRecord{{
{zone_infos_string}
}}
"""

    def _generate_eras_string(self, zones_map: ZonesMap) -> str:
        zone_eras_string = ''
        era_index = 0
        for zone_name, eras in sorted(self.zones_map.items()):
            zone_eras_string += self._generate_era_items_string(
                zone_name, era_index, eras, self.policy_index_size_map)
            era_index += len(eras)
        return zone_eras_string

    def _generate_era_items_string(
        self,
        zone_name: str,
        era_index: int,
        eras: List[ZoneEraRaw],
        policy_index_size_map: IndexSizeMap,
    ) -> str:
        era_items_string = f"""\
\t// ---------------------------------------------------------------------------
\t// ZoneName: {zone_name}
\t// EraIndex: {era_index}
\t// EraCount: {len(eras)}
\t// ---------------------------------------------------------------------------

"""
        for era in eras:
            raw_line = normalize_raw(era['raw_line'])

            # Find the index for the 'format' field.
            format_short = era['format_short']
            format_comment = f'"{format_short}"'
            entry = self.formats_map[format_short]
            format_index = entry[0]  # (index, offset)

            policy_name = era['rules']
            if policy_name in ['-', ':']:
                policy_name = ""
            policy_index = policy_index_size_map[policy_name][0]
            if policy_name == "":
                policy_name = "(none)"

            offset_seconds = era['offset_seconds_truncated']
            offset_seconds_code = era['go_offset_seconds_code']
            offset_seconds_remainder = era['go_offset_seconds_remainder']

            until_seconds = era['until_seconds_truncated']
            until_seconds_code = era['go_until_seconds_code']
            until_seconds_modifier = era['go_until_seconds_modifier']
            until_seconds_modifier_comment = _get_time_modifier_comment(
                remainder_seconds=era['go_until_seconds_remainder'],
                suffix=era['until_time_suffix'],
            )
            until_year = era['until_year']
            until_month = era['until_month']
            until_day = era['until_day']

            delta_minutes = era['go_era_delta_minutes']

            era_items_string += f"""\
\t// {raw_line}
\t{{
\t\tPolicyIndex: {policy_index}, // PolicyName: {policy_name}
\t\tFormatIndex: {format_index}, // {format_comment}
\t\tDeltaMinutes: {delta_minutes},
\t\tOffsetSecondsCode: {offset_seconds_code}, // {offset_seconds} / 15
\t\tOffsetSecondsRemainder: {offset_seconds_remainder},
\t\tUntilYear: {until_year},
\t\tUntilMonth: {until_month},
\t\tUntilDay: {until_day},
\t\tUntilSecondsCode: {until_seconds_code}, // {until_seconds} / 15
\t\tUntilSecondsModifier: {until_seconds_modifier}, \
// {until_seconds_modifier_comment}
\t}},
"""
            era_items_string += '\n'

        return era_items_string

    def _generate_eras_data(
        self, zones_map: ZonesMap
    ) -> Tuple[bytearray, int, int]:
        count = 0
        chunk_size = 14
        data = bytearray()
        for zone_name, eras in sorted(self.zones_map.items()):
            count += len(eras)
            for era in eras:
                self._generate_era_data(data, era)
        return data, chunk_size, count

    def _generate_era_data(self, data: bytearray, era: ZoneEraRaw) -> None:
        policy_name = era['rules']
        if policy_name in ['-', ':']:
            policy_name = ""
        policy_index = self.policy_index_size_map[policy_name][0]

        # Find the index for the 'format' field.
        format_short = era['format_short']
        entry = self.formats_map[format_short]
        format_index = entry[0]  # (index, offset)

        offset_seconds_code = era['go_offset_seconds_code']
        offset_seconds_remainder = era['go_offset_seconds_remainder']
        delta_minutes = era['go_era_delta_minutes']
        until_year = era['until_year']
        until_month = era['until_month']
        until_day = era['until_day']
        until_seconds_code = era['go_until_seconds_code']
        until_seconds_modifier = era['go_until_seconds_modifier']

        # chunk size = 14 bytes
        # WARNING: If this is changed, the chunk_size must be updated.
        write_u16(data, format_index)
        write_u8(data, policy_index)
        write_u8(data, offset_seconds_remainder)
        write_i16(data, offset_seconds_code)
        write_i16(data, until_year)
        write_i8(data, delta_minutes)
        write_u8(data, until_month)
        write_u8(data, until_day)
        write_u8(data, until_seconds_modifier)
        write_u16(data, until_seconds_code)

    def _generate_infos_string(self) -> str:
        zone_infos_string = ''
        combined_index = 0
        # Loop over all zones and links, sorted by zoneId/linkId.
        for name in self.zone_and_link_index_map:
            target_name = self.links_map.get(name)
            if target_name is None:  # Zone
                desc_name = f'Zone {name}'
                zone_id = self.zone_ids[name]
                indexes = self.info_index_size_map[name]
                era_index = indexes[1]
                era_count = indexes[2]
                era_count_desc = ''
                target_index = 0
                target_desc = ''
            else:  # Link
                desc_name = f'Link {name} -> {target_name}'
                zone_id = self.link_ids[name]
                era_index = 0
                era_count = 0
                era_count_desc = ' // IsLink=true'
                target_index = self.zone_and_link_index_map[target_name]
                target_desc = f' // {target_name}'
            name_index = self.names_map[name][0]

            zone_infos_string += f"""\
\t// {combined_index}: {desc_name}
\t{{
\t\tZoneID: 0x{zone_id:08x},
\t\tNameIndex: {name_index}, // "{name}"
\t\tEraIndex: {era_index},
\t\tEraCount: {era_count},{era_count_desc}
\t\tTargetIndex: {target_index},{target_desc}
\t}},
"""
            combined_index += 1
        return zone_infos_string

    def _generate_infos_data(self) -> Tuple[bytearray, int, int]:
        chunk_size = 12
        data = bytearray()
        # Loop over all zones and links, sorted by zoneId/linkId.
        for name in self.zone_and_link_index_map:
            target_name = self.links_map.get(name)
            if target_name is None:  # Zone
                zone_id = self.zone_ids[name]
                indexes = self.info_index_size_map[name]
                era_index = indexes[1]
                era_count = indexes[2]
                target_index = 0
            else:  # Link
                zone_id = self.link_ids[name]
                era_index = 0
                era_count = 0
                target_index = self.zone_and_link_index_map[target_name]
            name_index = self.names_map[name][0]

            # chunk_size = 12
            # WARNING: If this is changed, the chunk_size must be updated.
            write_u32(data, zone_id)
            write_u16(data, name_index)
            write_u16(data, era_index)
            write_u16(data, era_count)
            write_u16(data, target_index)
        return data, chunk_size, len(self.zone_and_link_index_map)

    # ------------------------------------------------------------------------
    # Zone Registry
    # ------------------------------------------------------------------------

    def _generate_registry(self) -> str:
        zone_and_link_ids_string = self._generate_zone_and_link_ids()

        num_zones = len(self.zones_map)
        num_links = len(self.links_map)
        num_zones_and_links = len(self.zones_and_links)

        return self._generate_header() + f"""\
package {self.db_namespace}

import (
\t"github.com/bxparks/AceTimeGo/zoneinfo"
)

// ---------------------------------------------------------------------------
// Zone Context
// ---------------------------------------------------------------------------

const TzDatabaseVersion string = "{self.tz_version}"

// DataContext contains references to various XxxData objects and strings. These
// are the binary encoded versions of the various XxxRecord objects. This object
// is passed to the ZoneManager.
//
// The encoding to a binary string is performed because the Go language is able
// to treat strings as constants, and the TinyGo compiler can place them in
// flash memory, saving tremendous amounts of random memory.
var DataContext = zoneinfo.ZoneDataContext{{
\tTzDatabaseVersion: TzDatabaseVersion,
\tStartYear: {self.start_year},
\tUntilYear: {self.until_year},
\tMaxTransitions: {self.max_buf_size},
\tLetterData: LetterData,
\tLetterOffsets: LetterOffsets,
\tFormatData: FormatData,
\tFormatOffsets: FormatOffsets,
\tNameData: NameData,
\tNameOffsets: NameOffsets,
\tZoneRuleChunkSize: ZoneRuleChunkSize,
\tZonePolicyChunkSize: ZonePolicyChunkSize,
\tZoneEraChunkSize: ZoneEraChunkSize,
\tZoneInfoChunkSize: ZoneInfoChunkSize,
\tZoneRuleCount: ZoneRuleCount,
\tZonePolicyCount: ZonePolicyCount,
\tZoneEraCount: ZoneEraCount,
\tZoneInfoCount: ZoneInfoCount,
\tZoneRulesData: ZoneRulesData,
\tZonePoliciesData: ZonePoliciesData,
\tZoneErasData: ZoneErasData,
\tZoneInfosData: ZoneInfosData,
}}

// ---------------------------------------------------------------------------
// Zone IDs. Unique stable uint32 identifier for each zone which can be given to
// ZoneManager.NewTimeZoneFromID(). Useful for microcontroller environments
// where saving variable length strings is more difficult than a fixed width
// integer.
//
// Total: {num_zones_and_links} ({num_zones} zones, {num_links} links)
// ---------------------------------------------------------------------------

const (
{zone_and_link_ids_string}
)
"""

    def _generate_registry_test(self) -> str:
        zone_and_link_indexes_string = self._generate_zone_and_link_indexes()

        num_zones = len(self.zones_map)
        num_links = len(self.links_map)
        num_zones_and_links = len(self.zones_and_links)

        return self._generate_header() + f"""\
package {self.db_namespace}

import (
\t"github.com/bxparks/AceTimeGo/zoneinfo"
)

// ---------------------------------------------------------------------------
// Zone Context
// ---------------------------------------------------------------------------

// RecordContext contains references to the various arrays of ZoneRuleRecord,
// ZonePolicyRecord, ZoneEraRecord, and ZoneInfoRecord objects, as well as the
// strings used by those objects.
//
// The `acetime` package uses the encoded XxxData objects, not the XxxRecord
// objects referenced here. These XxxRecord objects are used only for testing
// purposes, to verify that the XxxData objects were properly generated, and can
// be read back and reconstructed to be identical to the XxxRecord objects.
var RecordContext = zoneinfo.ZoneRecordContext{{
\tTzDatabaseVersion: TzDatabaseVersion,
\tStartYear: {self.start_year},
\tUntilYear: {self.until_year},
\tMaxTransitions: {self.max_buf_size},
\tLetterData: LetterData,
\tLetterOffsets: LetterOffsets,
\tFormatData: FormatData,
\tFormatOffsets: FormatOffsets,
\tNameData: NameData,
\tNameOffsets: NameOffsets,
\tZoneRuleRecords: ZoneRuleRecords,
\tZonePolicyRecords: ZonePolicyRecords,
\tZoneEraRecords: ZoneEraRecords,
\tZoneInfoRecords: ZoneInfoRecords,
}}

// ---------------------------------------------------------------------------
// Zone Indexes. Index into the ZoneInfoRecords array. Intended for unit tests
// which need direct access to the zoneinfo.ZoneInfo struct.
//
// Total: {num_zones_and_links} ({num_zones} zones, {num_links} links)
// ---------------------------------------------------------------------------

const (
{zone_and_link_indexes_string}
)
"""

    def _generate_zone_and_link_ids(self) -> str:
        """Generate a list of constants of the form ZoneID{zoneName},
        sorted by name.
        """
        s = ''
        for name in sorted(self.zones_and_links):
            zone_id = self.zone_and_link_ids.get(name)
            if zone_id is None:
                raise Exception(f'Zone or Link "{name}" not found')
            normalized_name = normalize_name(name)
            s += f"""\
\tZoneID{normalized_name} uint32 = 0x{zone_id:08x} // {name}
"""
        return s

    def _generate_zone_and_link_indexes(self) -> str:
        """Generate a list of constants of the form ZoneInfoIndex{zoneName},
        sorted by name. These are the indexes into the ZoneInfoRecords array and
        are intended for unit testing and debugging.
        """
        s = ''
        for name, index in sorted(self.zone_and_link_index_map.items()):
            zone_id = self.zone_and_link_ids.get(name)
            if zone_id is None:
                raise Exception(f'Zone or Link "{name}" not found')
            normalized_name = normalize_name(name)
            s += f"""\
\tZoneInfoIndex{normalized_name} uint16 = {index} // {name}
"""
        return s

    def _generate_reader_test(self) -> str:
        return self._generate_header() + f"""\
package {self.db_namespace}

import (
\t"github.com/bxparks/AceTimeGo/internal"
\t"testing"
)

// Verify that ZoneInfosData is identical to ZoneInfoRecords.
func TestZoneInfoReader(t *testing.T) {{
\tinternal.VerifyZoneInfoReader(t, &DataContext, &RecordContext)
}}

// Verify that ZoneErasData is identical to ZoneEraRecords.
func TestZoneEraReader(t *testing.T) {{
\tinternal.VerifyZoneEraReader(t, &DataContext, &RecordContext)
}}

// Verify that ZonePoliciesData is identical to ZonePolicyRecords.
func TestZonePolicyReader(t *testing.T) {{
\tinternal.VerifyZonePolicyReader(t, &DataContext, &RecordContext)
}}

// Verify that ZoneRulesData is identical to ZoneRuleRecords.
func TestZoneRuleReader(t *testing.T) {{
\tinternal.VerifyZoneRuleReader(t, &DataContext, &RecordContext)
}}
"""


def _render_comments_map(comments: CommentsMap, indent: str = '') -> str:
    """Convert the CommentsMap into a Python comment. Print the name and list
    of reasons one a single line, or multiple lines, like this:

    // Name1 {reason}
    //
    // Name2 {
    //   reason1,
    //   reason2,
    // }
    """
    comment = ''
    for name, reasons in sorted(comments.items()):
        if len(reasons) <= 1:
            comment += f"// {indent}{name} {{{next(iter(reasons))}}}\n"
        else:
            comment += f"// {indent}{name} {{\n"
            for reason in reasons:
                comment += f'// {indent}  {reason},\n'
            comment += f"// {indent}}}\n"
    return comment


def _render_merged_comments_map(merged_comments: MergedCommentsMap) -> str:
    """Converts MergedCommentsMap for zones into a C++ comment. Includes the
    comments for zones, as well as any comments in the referenced policies.

    // Name1 {reason}
    //
    // Name2 {
    //   reason1,
    //   reason2,
    // }
    //
    // Name3 {
    //   reason1,
    //   reason2,
    //   Policy1 {reason11}
    //   Policy2 {
    //     reason21,
    //     reason22,
    //   }
    // }
    """
    comment = ''
    for name, reasons in sorted(merged_comments.items()):
        if len(reasons) == 0:
            continue

        # If only a single comment, and the comment is a simple string,
        # render it in a single line.
        reason = next(iter(reasons))
        if len(reasons) == 1 and isinstance(reason, str):
            comment += f"// {name} {{{reason}}}\n"
            continue

        # Otherwise, render the comments using multiple lines deliminted by ( )
        comment += f"// {name} {{\n"
        for reason in reasons:
            if isinstance(reason, str):
                comment += f'//   {reason},\n'
            else:
                comment += _render_comments_map(reason, '  ')
        comment += "// }\n"
    return comment


def _get_time_modifier_comment(
    remainder_seconds: int,
    suffix: str,
) -> str:
    """Create the comment that explains how the until_seconds_modifier or
    at_seconds_modifier was calculated.
    """
    if suffix == 'w':
        suffixStr = 'SuffixW'
    elif suffix == 's':
        suffixStr = 'SuffixS'
    else:
        suffixStr = 'SuffixU'
    return f'{suffixStr} + remainder={remainder_seconds}'


def _render_offsets(offsets: Iterable[int], prefix: str = '\t') -> str:
    """Return a comma-separated list integers as a string suitable for Golang,
    with a newline added every 10 elements for readability. The logic to
    correctly handle trailing commas, spaces, and newlines properly was trickier
    than I thought it would be.
    """
    items_per_line = 10
    count = 0
    s = ''
    for n in offsets:
        if count == 0:
            s += f'{prefix}{n}'
        elif count % items_per_line == 0:
            s += f',\n{prefix}{n}'
        else:
            s += f', {n}'
        count += 1

    # Add terminating delimiters
    if count == 0:
        pass
    else:
        s += ','
    return s
