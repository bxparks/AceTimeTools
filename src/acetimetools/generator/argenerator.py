# Copyright 2018 Brian T. Park
#
# MIT License
"""
Generate the zone_info and zone_policies files for Arduino.
"""

import os
import logging
from typing import List

from acetimetools.datatypes.attyping import ZoneRuleRaw
from acetimetools.datatypes.attyping import ZoneEraRaw
from acetimetools.datatypes.attyping import CommentsMap
from acetimetools.datatypes.attyping import MergedCommentsMap
from acetimetools.datatypes.attyping import ZoneInfoDatabase
from acetimetools.transformer.transformer import normalize_name
from acetimetools.transformer.transformer import normalize_raw


class ArduinoGenerator:
    """Generate zone_infos and zone_policies files for Arduino/C++.
    """
    ZONE_INFOS_H_FILE_NAME = 'zone_infos.h'
    ZONE_INFOS_CPP_FILE_NAME = 'zone_infos.cpp'
    ZONE_POLICIES_H_FILE_NAME = 'zone_policies.h'
    ZONE_POLICIES_CPP_FILE_NAME = 'zone_policies.cpp'
    ZONE_REGISTRY_H_FILE_NAME = 'zone_registry.h'
    ZONE_REGISTRY_CPP_FILE_NAME = 'zone_registry.cpp'

    def __init__(
        self,
        invocation: str,
        db_namespace: str,
        compress: bool,
        generate_tiny_years: bool,
        tiny_base_year: int,
        zidb: ZoneInfoDatabase,
    ):
        # If I add a backslash (\) at the end of each line (which is needed if I
        # want to copy and paste the shell command), the C++ compiler spews out
        # warnings about "multi-line comment [-Wcomment]".
        wrapped_invocation = '\n//     --'.join(invocation.split(' --'))
        wrapped_tzfiles = '\n//   '.join(zidb['tz_files'])
        self.invocation = wrapped_invocation
        self.tz_files = wrapped_tzfiles

        if not db_namespace:
            raise Exception("db_namespace must be defined")
        self.db_namespace = db_namespace
        self.db_header_namespace = db_namespace.upper()
        self.compress = compress
        self.generate_tiny_years = generate_tiny_years
        self.tiny_base_year = tiny_base_year

        self.tz_version = zidb['tz_version']
        self.scope = zidb['scope']
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
        #
        self.original_min_year = zidb['original_min_year']
        self.original_max_year = zidb['original_max_year']
        self.generated_min_year = zidb['generated_min_year']
        self.generated_max_year = zidb['generated_max_year']
        self.lower_truncated = zidb['lower_truncated']
        self.upper_truncated = zidb['upper_truncated']
        self.start_year_accurate = zidb['start_year_accurate']
        self.until_year_accurate = zidb['until_year_accurate']
        #
        self.estimator_min_year = zidb['estimator_min_year']
        self.estimator_max_year = zidb['estimator_max_year']
        self.buf_sizes = zidb['buf_sizes']
        self.max_buf_size = zidb['max_buf_size']
        #
        self.zone_ids = zidb['zone_ids']
        self.link_ids = zidb['link_ids']
        self.formats_map = zidb['formats_map']
        self.fragments_map = zidb['fragments_map']
        self.letters_map = zidb['letters_map']
        self.compressed_names = zidb['compressed_names']
        self.memory_map8 = zidb['memory_map8']
        self.memory_map32 = zidb['memory_map32']

        self.zones_and_links = \
            list(self.zones_map.keys()) + list(self.links_map.keys())
        self.zone_and_link_ids = self.zone_ids.copy()
        self.zone_and_link_ids.update(self.link_ids)

    def generate_files(self, output_dir: str) -> None:
        # zone_policies.*
        self._write_file(output_dir, self.ZONE_POLICIES_H_FILE_NAME,
                         self.generate_policies_h())
        self._write_file(output_dir, self.ZONE_POLICIES_CPP_FILE_NAME,
                         self.generate_policies_cpp())

        # zone_infos.*
        self._write_file(output_dir, self.ZONE_INFOS_H_FILE_NAME,
                         self.generate_infos_h())
        self._write_file(output_dir, self.ZONE_INFOS_CPP_FILE_NAME,
                         self.generate_infos_cpp())

        # zone_registry.*
        self._write_file(output_dir, self.ZONE_REGISTRY_H_FILE_NAME,
                         self.generate_registry_h())
        self._write_file(output_dir, self.ZONE_REGISTRY_CPP_FILE_NAME,
                         self.generate_registry_cpp())

    def _write_file(self, output_dir: str, filename: str, content: str) -> None:
        full_filename = os.path.join(output_dir, filename)
        with open(full_filename, 'w', encoding='utf-8') as output_file:
            print(content, end='', file=output_file)
        logging.info("Created %s", full_filename)

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
// Requested Years: [{self.start_year},{self.until_year}]
// Accurate Years: [{self.start_year_accurate},{self.until_year_accurate}]
//
// Original Years:  [{self.original_min_year},{self.original_max_year}]
// Generated Years: [{self.generated_min_year},{self.generated_max_year}]
// Lower/Upper Truncated: [{self.lower_truncated},{self.upper_truncated}]
//
// Estimator Years: [{self.estimator_min_year},{self.estimator_max_year}]
// Max Buffer Size: {self.max_buf_size}
//
// Records:
//   Infos: {num_zones_and_links}
//   Eras: {self.num_eras}
//   Policies: {self.num_policies}
//   Rules: {self.num_rules}
//
// Memory (8-bits):
//   Context: {self.memory_map8['context']}
//   Rules: {self.memory_map8['rules']}
//   Policies: {self.memory_map8['policies']}
//   Eras: {self.memory_map8['eras']}
//   Zones: {self.memory_map8['zones']}
//   Links: {self.memory_map8['links']}
//   Registry: {self.memory_map8['registry']}
//   Formats: {self.memory_map8['formats']}
//   Letters: {self.memory_map8['letters']}
//   Fragments: {self.memory_map8['fragments']}
//   Names: {self.memory_map8['names']} \
(original: {self.memory_map8['names_original']})
//   TOTAL: {self.memory_map8['total']}
//
// Memory (32-bits):
//   Context: {self.memory_map32['context']}
//   Rules: {self.memory_map32['rules']}
//   Policies: {self.memory_map32['policies']}
//   Eras: {self.memory_map32['eras']}
//   Zones: {self.memory_map32['zones']}
//   Links: {self.memory_map32['links']}
//   Registry: {self.memory_map32['registry']}
//   Formats: {self.memory_map32['formats']}
//   Letters: {self.memory_map32['letters']}
//   Fragments: {self.memory_map32['fragments']}
//   Names: {self.memory_map32['names']} \
(original: {self.memory_map32['names_original']})
//   TOTAL: {self.memory_map32['total']}
//
// DO NOT EDIT

"""

    def generate_policies_h(self) -> str:
        policy_items = ''
        for name, rules in sorted(self.policies_map.items()):
            policy_normalized_name = normalize_name(name)
            policy_items += f"""\
extern const {self.scope}::ZonePolicy kZonePolicy{policy_normalized_name};
"""

        removed_policy_items = render_comments_map(self.removed_policies)
        notable_policy_items = render_comments_map(self.notable_policies)
        num_removed_policies = len(self.removed_policies)
        num_notable_policies = len(self.notable_policies)
        include_header = "infos.h"

        return self._generate_header() + f"""\
#ifndef ACE_TIME_{self.db_header_namespace}_ZONE_POLICIES_H
#define ACE_TIME_{self.db_header_namespace}_ZONE_POLICIES_H

#include <zoneinfo/{include_header}>

namespace ace_time {{
namespace {self.db_namespace} {{

//---------------------------------------------------------------------------
// Supported policies: {self.num_policies}
//---------------------------------------------------------------------------

{policy_items}

//---------------------------------------------------------------------------
// Unsupported policies: {num_removed_policies}
//---------------------------------------------------------------------------

{removed_policy_items}

//---------------------------------------------------------------------------
// Notable zone policies: {num_notable_policies}
//---------------------------------------------------------------------------

{notable_policy_items}

}}
}}

#endif
"""

    def generate_policies_cpp(self) -> str:
        policy_items = ''
        num_rules = 0
        for name, policy in sorted(self.policies_map.items()):
            rules = policy['rules']
            num_rules += len(rules)
            policy_item = self._generate_policy_item(name, rules)
            policy_items += policy_item
        num_policies = len(self.policies_map)

        return self._generate_header() + f"""\
#include <zoneinfo/compat.h>
#include "zone_policies.h"

namespace ace_time {{
namespace {self.db_namespace} {{

//---------------------------------------------------------------------------
// Policies: {num_policies}
// Rules: {num_rules}
//---------------------------------------------------------------------------

{policy_items}

}}
}}
"""

    def _generate_policy_item(
        self,
        policy_name: str,
        rules: List[ZoneRuleRaw],
    ) -> str:
        # Generate ZoneRules
        rule_items = ''
        for rule in rules:
            at_seconds = rule['at_seconds_truncated']
            if self.scope == 'complete':
                at_time_code = rule['at_time_seconds_code']
                at_time_modifier = rule['at_time_seconds_modifier']
                label = to_suffix_label(rule['at_time_suffix'])
                remaining_seconds = at_seconds % 15
                at_time_modifier_comment = \
                    f'{label} + seconds={remaining_seconds}'
                delta_minutes = rule['delta_minutes']
            else:
                at_time_code = rule['at_time_code']
                at_time_modifier = rule['at_time_modifier']
                at_time_modifier_comment = _get_time_modifier_comment(
                    time_seconds=rule['at_seconds_truncated'],
                    suffix=rule['at_time_suffix'],
                )
                delta_code = rule['delta_code_encoded']
                delta_code_comment = _get_rule_delta_code_comment(
                    rule['delta_seconds_truncated']
                )

            if self.generate_tiny_years:
                from_year = rule['from_year']
                from_year_label = f'fromYearTiny ({from_year})'
                from_year = rule['from_year_tiny']
                to_year = rule['to_year']
                to_year_label = f'toYearTiny ({to_year})'
                to_year = rule['to_year_tiny']
            else:
                from_year = rule['from_year']
                from_year_label = 'fromYear'
                to_year = rule['to_year']
                to_year_label = 'toYear'

            raw_line = normalize_raw(rule['raw_line'])
            in_month = rule['in_month']
            on_day_of_week = rule['on_day_of_week']
            on_day_of_month = rule['on_day_of_month']
            letter = rule['letter']
            letter_index = rule['letter_index']

            if self.scope == 'complete':
                item = f"""\
  // {raw_line}
  {{
    {from_year} /*{from_year_label}*/,
    {to_year} /*{to_year_label}*/,
    {in_month} /*inMonth*/,
    {on_day_of_week} /*onDayOfWeek*/,
    {on_day_of_month} /*onDayOfMonth*/,
    {at_time_modifier} /*atTimeModifier ({at_time_modifier_comment})*/,
    {at_time_code} /*atTimeCode ({at_seconds}/15)*/,
    {delta_minutes} /*deltaMinutes*/,
    {letter_index} /*letterIndex ("{letter}")*/,
  }},
"""
            else:
                item = f"""\
  // {raw_line}
  {{
    {from_year} /*{from_year_label}*/,
    {to_year} /*{to_year_label}*/,
    {in_month} /*inMonth*/,
    {on_day_of_week} /*onDayOfWeek*/,
    {on_day_of_month} /*onDayOfMonth*/,
    {at_time_code} /*atTimeCode*/,
    {at_time_modifier} /*atTimeModifier ({at_time_modifier_comment})*/,
    {delta_code} /*deltaCode ({delta_code_comment})*/,
    {letter_index} /*letterIndex ("{letter}")*/,
  }},
"""
            rule_items += item

        # Section header for a ZonePolicy
        num_rules = len(rules)
        policy_normalized_name = normalize_name(policy_name)
        progmem = 'ACE_TIME_PROGMEM'
        policy_item = f"""\
//---------------------------------------------------------------------------
// Policy name: {policy_name}
// Rules: {num_rules}
//---------------------------------------------------------------------------

static const {self.scope}::ZoneRule kZoneRules{policy_normalized_name}[] \
{progmem} = {{
{rule_items}
}};

const {self.scope}::ZonePolicy kZonePolicy{policy_normalized_name} \
{progmem} = {{
  kZoneRules{policy_normalized_name} /*rules*/,
  {num_rules} /*numRules*/,
}};

"""
        return policy_item

    def generate_infos_h(self) -> str:
        zone_items = ''
        zone_ids = ''
        buf_sizes = ''
        for zone_name, eras in sorted(self.zones_map.items()):
            zone_normalized_name = normalize_name(zone_name)

            zone_items += f"""\
extern const {self.scope}::ZoneInfo kZone{zone_normalized_name}; // {zone_name}
"""

            zone_id = self.zone_ids[zone_name]
            zone_ids += f"""\
const uint32_t kZoneId{zone_normalized_name} = 0x{zone_id:08x}; // {zone_name}
"""

            buf_size = self.buf_sizes[zone_name].number
            buf_year = self.buf_sizes[zone_name].year
            buf_sizes += f"""\
const uint8_t kZoneBufSize{zone_normalized_name} = {buf_size};  \
// {zone_name} in {buf_year}
"""

        link_items = ''
        link_ids = ''
        for link_name, zone_name in sorted(self.links_map.items()):
            link_normalized_name = normalize_name(link_name)
            link_items += f"""\
extern const {self.scope}::ZoneInfo kZone{link_normalized_name}; \
// {link_name} -> {zone_name}
"""
            link_id = self.link_ids[link_name]
            link_ids += f"""\
const uint32_t kZoneId{link_normalized_name} = 0x{link_id:08x}; // {link_name}
"""

        removed_info_items = render_comments_map(self.removed_zones)
        # notable_info_items = render_comments_map(self.notable_zones)
        notable_info_items = render_merged_comments_map(
            self.merged_notable_zones)
        removed_link_items = render_comments_map(self.removed_links)
        notable_link_items = render_comments_map(self.notable_links)

        num_removed_infos = len(self.removed_zones)
        num_notable_infos = len(self.merged_notable_zones)
        num_removed_links = len(self.removed_links)
        num_notable_links = len(self.notable_links)
        include_header = "infos.h"

        return self._generate_header() + f"""\
#ifndef ACE_TIME_{self.db_header_namespace}_ZONE_INFOS_H
#define ACE_TIME_{self.db_header_namespace}_ZONE_INFOS_H

#include <zoneinfo/{include_header}>

class __FlashStringHelper;

namespace ace_time {{
namespace {self.db_namespace} {{

//---------------------------------------------------------------------------
// ZoneContext (should not be in PROGMEM)
//---------------------------------------------------------------------------

// Version of the TZ Database which generated these files.
extern const __FlashStringHelper* const kTzDatabaseVersion;

// Metadata about the zonedb files.
extern const {self.scope}::ZoneContext kZoneContext;

//---------------------------------------------------------------------------
// Supported zones: {self.num_zones}
//---------------------------------------------------------------------------

{zone_items}

// Zone Ids

{zone_ids}

//---------------------------------------------------------------------------
// Supported links: {self.num_links}
//---------------------------------------------------------------------------

{link_items}

// Zone Ids

{link_ids}

//---------------------------------------------------------------------------
// Maximum size of the Transition buffer in ExtendedZoneProcessor for each zone
// over the given years. Used only in the AceTimeValidation/Extended*Test tests
// for ExtendedZoneProcessor.
//
// MaxBufSize: {self.max_buf_size}
//---------------------------------------------------------------------------

{buf_sizes}

//---------------------------------------------------------------------------
// Unsupported zones: {num_removed_infos}
//---------------------------------------------------------------------------

{removed_info_items}

//---------------------------------------------------------------------------
// Notable zones: {num_notable_infos}
//---------------------------------------------------------------------------

{notable_info_items}

//---------------------------------------------------------------------------
// Unsupported links: {num_removed_links}
//---------------------------------------------------------------------------

{removed_link_items}

//---------------------------------------------------------------------------
// Notable links: {num_notable_links}
//---------------------------------------------------------------------------

{notable_link_items}

}}
}}

#endif
"""

    def generate_infos_cpp(self) -> str:
        progmem = 'ACE_TIME_PROGMEM'

        # Generate the list of zone infos
        num_eras = 0
        info_items = ''
        for zone_name, info in sorted(self.zones_map.items()):
            eras = info['eras']
            info_item = self._generate_info_item(zone_name, eras)
            info_items += info_item
            num_eras += len(eras)
        assert num_eras == self.num_eras

        # Generate links references.
        link_items = ''
        for link_name, zone_name in sorted(self.links_map.items()):
            link_item = self._generate_link_item(link_name, zone_name)
            link_items += link_item

        # Generate array of fragments.
        num_fragments = len(self.fragments_map) + 1
        fragment_strings = ''
        fragment_pointers = '  nullptr, // \'\\x00\' cannot exist\n'
        for fragment, index in self.fragments_map.items():
            fragment_strings += (
                f'static const char kFragment{index}[] {progmem} = '
                f'"{fragment}";\n'
            )
            fragment_pointers += (
                f'  kFragment{index}, // \'\\x{index:02x}\' "{fragment}"\n'
            )

        # Generate array of letters.
        num_letters = len(self.letters_map)
        letter_strings = ''
        letter_pointers = ''
        for letter, index in self.letters_map.items():
            letter_strings += \
                f'static const char kLetter{index}[] {progmem} = "{letter}";\n'
            letter_pointers += f'  kLetter{index}, // "{letter}"\n'

        return self._generate_header() + f"""\
#include <zoneinfo/compat.h>
#include "zone_policies.h"
#include "zone_infos.h"

namespace ace_time {{
namespace {self.db_namespace} {{

//---------------------------------------------------------------------------
// ZoneContext
//---------------------------------------------------------------------------

static const char kVersionString[] {progmem} = "{self.tz_version}";
const __FlashStringHelper* const kTzDatabaseVersion =
    (const __FlashStringHelper*) kVersionString;

{fragment_strings}
const char* const kFragments[] {progmem} = {{
{fragment_pointers}
}};

{letter_strings}
const char* const kLetters[] {progmem} = {{
{letter_pointers}
}};

const {self.scope}::ZoneContext kZoneContext {progmem} = {{
  {self.start_year} /*startYear*/,
  {self.until_year} /*untilYear*/,
  {self.start_year_accurate} /*startYearAccurate*/,
  {self.until_year_accurate} /*untilYearAccurate*/,
  {self.tiny_base_year} /*baseYear*/,
  {self.max_buf_size} /*maxTransitions*/,
  kVersionString /*tzVersion*/,
  {num_fragments} /*numFragments*/,
  {num_letters} /*numLetters*/,
  kFragments /*fragments*/,
  kLetters /*letters*/,
}};

//---------------------------------------------------------------------------
// Zones: {self.num_zones}
// Eras: {num_eras}
//---------------------------------------------------------------------------

{info_items}

//---------------------------------------------------------------------------
// Links: {self.num_links}
//---------------------------------------------------------------------------

{link_items}
}}
}}
"""

    def _generate_info_item(
        self,
        zone_name: str,
        eras: List[ZoneEraRaw],
    ) -> str:
        era_items = ''
        for era in eras:
            era_item = self._generate_era_item(zone_name, era)
            era_items += era_item

        if self.compress:
            compressed_name = self.compressed_names[zone_name]
        else:
            compressed_name = zone_name
        rendered_name = compressed_name_to_c_string(compressed_name)

        num_eras = len(eras)
        zone_normalized_name = normalize_name(zone_name)
        zone_id = self.zone_ids[zone_name]
        progmem = 'ACE_TIME_PROGMEM'
        info_item = f"""\
//---------------------------------------------------------------------------
// Zone name: {zone_name}
// Eras: {num_eras}
//---------------------------------------------------------------------------

static const {self.scope}::ZoneEra kZoneEra{zone_normalized_name}[] \
{progmem} = {{
{era_items}
}};

static const char kZoneName{zone_normalized_name}[] {progmem} = {rendered_name};

const {self.scope}::ZoneInfo kZone{zone_normalized_name} {progmem} = {{
  kZoneName{zone_normalized_name} /*name*/,
  0x{zone_id:08x} /*zoneId*/,
  &kZoneContext /*zoneContext*/,
  {num_eras} /*numEras*/,
  kZoneEra{zone_normalized_name} /*eras*/,
  nullptr /*targetInfo*/,
}};

"""

        return info_item

    def _generate_era_item(
        self, zone_name: str, era: ZoneEraRaw
    ) -> str:
        policy_name = era['policy_name']
        if policy_name is None:
            zone_policy = 'nullptr'
        else:
            policy_normalized_name = normalize_name(policy_name)
            zone_policy = f'&kZonePolicy{policy_normalized_name}'

        offset_seconds = era['offset_seconds_truncated']
        if self.scope == 'complete':
            offset_code = era['offset_seconds_code']
            offset_remainder = era['offset_seconds_remainder']
            delta_minutes = era['delta_minutes']
        else:
            offset_code = era['offset_code']
            delta_code = era['delta_code_encoded']
            delta_code_comment = _get_era_delta_code_comment(
                offset_seconds=era['offset_seconds_truncated'],
                delta_seconds=era['era_delta_seconds_truncated'],
            )

        if self.generate_tiny_years:
            until_year = era['until_year_tiny']
            until_year_label = 'untilYearTiny'
        else:
            until_year = era['until_year']
            until_year_label = 'untilYear'
        until_month = era['until_month']
        until_day = era['until_day']

        until_seconds = era['until_seconds_truncated']
        if self.scope == 'complete':
            until_time_code = era['until_time_seconds_code']
            until_time_modifier = era['until_time_seconds_modifier']
            label = to_suffix_label(era['until_time_suffix'])
            remaining_seconds = until_seconds % 15
            until_time_modifier_comment = \
                f'{label} + seconds={remaining_seconds}'
        else:
            until_time_code = era['until_time_code']
            until_time_modifier = era['until_time_modifier']
            until_time_modifier_comment = _get_time_modifier_comment(
                time_seconds=era['until_seconds_truncated'],
                suffix=era['until_time_suffix'],
            )

        format = era['format_short']
        raw_line = normalize_raw(era['raw_line'])

        if self.scope == 'complete':
            era_item = f"""\
  // {raw_line}
  {{
    {zone_policy} /*zonePolicy*/,
    "{format}" /*format*/,
    {offset_code} /*offsetCode ({offset_seconds}/15)*/,
    {offset_remainder} /*offsetRemainder ({offset_seconds}%15)*/,
    {delta_minutes} /*deltaMinutes*/,
    {until_year} /*{until_year_label}*/,
    {until_month} /*untilMonth*/,
    {until_day} /*untilDay*/,
    {until_time_code} /*untilTimeCode ({until_seconds}/15)*/,
    {until_time_modifier} /*untilTimeModifier ({until_time_modifier_comment})*/,
  }},
"""
        else:
            era_item = f"""\
  // {raw_line}
  {{
    {zone_policy} /*zonePolicy*/,
    "{format}" /*format*/,
    {offset_code} /*offsetCode*/,
    {delta_code} /*deltaCode ({delta_code_comment})*/,
    {until_year} /*{until_year_label}*/,
    {until_month} /*untilMonth*/,
    {until_day} /*untilDay*/,
    {until_time_code} /*untilTimeCode*/,
    {until_time_modifier} /*untilTimeModifier ({until_time_modifier_comment})*/,
  }},
"""  # noqa

        return era_item

    def _generate_link_item(
        self, link_name: str, zone_name: str,
    ) -> str:
        """Return the Link item.
        """
        if self.compress:
            compressed_name = self.compressed_names[link_name]
        else:
            compressed_name = link_name
        rendered_name = compressed_name_to_c_string(compressed_name)

        link_normalized_name = normalize_name(link_name)
        link_id = self.link_ids[link_name]
        zone_normalized_name = normalize_name(zone_name)
        num_eras = len(self.zones_map[zone_name]['eras'])
        progmem = 'ACE_TIME_PROGMEM'

        return f"""\
//---------------------------------------------------------------------------
// Link name: {link_name} -> {zone_name}
//---------------------------------------------------------------------------

static const char kZoneName{link_normalized_name}[] {progmem} = \
{rendered_name};

const {self.scope}::ZoneInfo kZone{link_normalized_name} {progmem} = {{
  kZoneName{link_normalized_name} /*name*/,
  0x{link_id:08x} /*zoneId*/,
  &kZoneContext /*zoneContext*/,
  {num_eras} /*numEras*/,
  kZoneEra{zone_normalized_name} /*eras*/,
  &kZone{zone_normalized_name} /*targetInfo*/,
}};

"""

    def generate_registry_cpp(self) -> str:

        # Generate only Zones, sorted by zoneId to enable
        # ZoneRegistrar::binarySearchById().
        zone_registry_items = ''
        for zone_name in sorted(
                self.zones_map.keys(),
                key=lambda x: self.zone_ids[x],
        ):
            normalized_name = normalize_name(zone_name)
            zone_id = self.zone_ids[zone_name]
            zone_registry_items += f"""\
  &kZone{normalized_name}, // 0x{zone_id:08x}, {zone_name}
"""

        # Generate Zones and Links, sorted by zoneId.
        zone_and_link_registry_items = ''
        num_zones_and_links = len(self.zones_and_links)
        for zone_name in sorted(
            self.zones_and_links,
            key=lambda x: self.zone_and_link_ids[x],
        ):
            normalized_name = normalize_name(zone_name)
            zone_id = self.zone_and_link_ids[zone_name]
            target_name = self.links_map.get(zone_name)
            if target_name:
                desc_name = f'{zone_name} -> {target_name}'
            else:
                desc_name = zone_name

            zone_and_link_registry_items += f"""\
  &kZone{normalized_name}, // 0x{zone_id:08x}, {desc_name}
"""

        num_zones = len(self.zones_map)
        progmem = 'ACE_TIME_PROGMEM'

        return self._generate_header() + f"""\
#include <zoneinfo/compat.h>
#include "zone_infos.h"
#include "zone_registry.h"

namespace ace_time {{
namespace {self.db_namespace} {{

//---------------------------------------------------------------------------
// Zone Info registry. Sorted by zoneId.
//---------------------------------------------------------------------------
const {self.scope}::ZoneInfo* const kZoneRegistry[{num_zones}] {progmem} = {{
{zone_registry_items}
}};

//---------------------------------------------------------------------------
// Zone and Link (fat) Info registry. Sorted by zoneId. Links act like Zones.
//---------------------------------------------------------------------------
const {self.scope}::ZoneInfo* const \
kZoneAndLinkRegistry[{num_zones_and_links}] {progmem} = {{
{zone_and_link_registry_items}
}};

}}
}}
"""

    def generate_registry_h(self) -> str:
        num_zones = len(self.zones_map)
        assert num_zones == self.num_zones
        num_zones_and_links = len(self.zones_and_links)
        assert num_zones_and_links == self.num_zones + self.num_links
        include_header = "infos.h"

        return self._generate_header() + f"""\
#ifndef ACE_TIME_{self.db_header_namespace}_ZONE_REGISTRY_H
#define ACE_TIME_{self.db_header_namespace}_ZONE_REGISTRY_H

#include <zoneinfo/{include_header}>

namespace ace_time {{
namespace {self.db_namespace} {{

// Zones
const uint16_t kZoneRegistrySize = {num_zones};
extern const {self.scope}::ZoneInfo* const kZoneRegistry[{num_zones}];

// Zones and Links
const uint16_t kZoneAndLinkRegistrySize = {num_zones_and_links};
extern const {self.scope}::ZoneInfo* const \
kZoneAndLinkRegistry[{num_zones_and_links}];

}}
}}
#endif
"""


def _get_time_modifier_comment(
    time_seconds: int,
    suffix: str,
) -> str:
    """Create the comment that explains how the until_time_code or at_time_code
    was calculated.
    """
    if suffix == 'w':
        comment = 'kSuffixW'
    elif suffix == 's':
        comment = 'kSuffixS'
    else:
        comment = 'kSuffixU'
    remaining_time_minutes = time_seconds % 900 // 60
    comment += f' + minute={remaining_time_minutes}'
    return comment


def _get_era_delta_code_comment(offset_seconds: int, delta_seconds: int) -> str:
    """Create the comment that explains how the ZoneEra delta_code[_encoded] was
    calculated.
    """
    offset_minute = offset_seconds % 900 // 60
    delta_minutes = delta_seconds // 60
    return (
        f"((offsetMinute={offset_minute}) << 4) + "
        f"((deltaMinutes={delta_minutes})/15 + 4)"
    )


def _get_rule_delta_code_comment(delta_seconds: int) -> str:
    """Create the comment that explains how the ZoneRule delta_code[_encoded]
    was calculated.
    """
    delta_minutes = delta_seconds // 60
    return f"(deltaMinutes={delta_minutes})/15 + 4"


def compressed_name_to_c_string(compressed_name: str) -> str:
    """Convert a compressed name (with fragment references) to a string that
    the C++ compiler will accept. The primary reason for this function is
    because the hex escape sequence (\\xHH) in C/C++ has no length limit, so
    will happily run into the characters after the HH. So we have to break
    those references into separate strings. Example: converts ("\x01ab")
    into ("\x01" "ab").
    """
    rendered_string = ''
    in_normal_string = False
    for c in compressed_name:
        if ord(c) < 0x20:
            if in_normal_string:
                rendered_string += f'" "\\x{ord(c):02x}" '
                in_normal_string = False
            else:
                rendered_string += f'"\\x{ord(c):02x}" '
        else:
            if in_normal_string:
                rendered_string += c
            else:
                rendered_string += f'"{c}'
            in_normal_string = True
    if in_normal_string:
        rendered_string += '"'
    return rendered_string.strip()


def render_comments_map(comments: CommentsMap, indent: str = '') -> str:
    """Convert the CommentsMap into a C++ comment. Print the name and list of
    reasons one a single line, or multiple lines, like this:

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
                comment += f'//   {indent}{reason},\n'
            comment += f"// {indent}}}\n"
    return comment


def render_merged_comments_map(merged_comments: MergedCommentsMap) -> str:
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
                comment += render_comments_map(reason, '  ')
        comment += "// }\n"
    return comment


def to_suffix_label(suffix: str) -> str:
    if suffix == 'w':
        return 'kAtcSuffixW'
    elif suffix == 's':
        return 'kAtcSuffixS'
    else:
        return 'kAtcSuffixU'
    return 'UNKNOWN'
