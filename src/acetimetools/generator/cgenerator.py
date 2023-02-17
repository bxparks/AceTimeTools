# Copyright 2022 Brian T. Park
#
# MIT License
"""
Generate the zone_info and zone_policies files for the AceTimeC C library.
Borrowed heavily from argenerator.py.
"""

import os
import logging
from typing import List

from acetimetools.data_types.at_types import ZoneRuleRaw
from acetimetools.data_types.at_types import ZoneEraRaw
from acetimetools.data_types.at_types import ZoneInfoDatabase
from acetimetools.transformer.transformer import normalize_name
from acetimetools.transformer.transformer import normalize_raw
from acetimetools.generator.argenerator import compressed_name_to_c_string
from acetimetools.generator.argenerator import render_comments_map
from acetimetools.generator.argenerator import render_merged_comments_map


class CGenerator:
    """Generate zone_infos and zone_policies files for AceTimeC C lang library.
    """
    ZONE_INFOS_H_FILE_NAME = 'zone_infos.h'
    ZONE_INFOS_C_FILE_NAME = 'zone_infos.c'
    ZONE_POLICIES_H_FILE_NAME = 'zone_policies.h'
    ZONE_POLICIES_C_FILE_NAME = 'zone_policies.c'
    ZONE_REGISTRY_H_FILE_NAME = 'zone_registry.h'
    ZONE_REGISTRY_C_FILE_NAME = 'zone_registry.c'

    def __init__(
        self,
        invocation: str,
        db_namespace: str,
        compress: bool,
        generate_int16_years: bool,
        generate_hires: bool,
        zidb: ZoneInfoDatabase,
    ):
        # If I add a backslash (\) at the end of each line (which is needed if I
        # want to copy and paste the shell command), the C++ compiler spews out
        # warnings about "multi-line comment [-Wcomment]".
        wrapped_invocation = '\n//     --'.join(invocation.split(' --'))
        wrapped_tzfiles = '\n//   '.join(zidb['tz_files'])

        # C does not namespaces, so use db_namespace as a prefix for all
        # external identifiers. Normally, this will be "Atc", but for testing,
        # it can be "AtcTesting".
        if not db_namespace:
            raise Exception("db_namespace must be defined")

        self.invocation = wrapped_invocation
        self.tz_files = wrapped_tzfiles
        self.db_namespace = db_namespace
        self.db_header_namespace = db_namespace.upper()
        self.compress = compress
        self.generate_int16_years = generate_int16_years
        self.generate_hires = generate_hires

        self.tz_version = zidb['tz_version']
        self.scope = zidb['scope']
        self.start_year = zidb['start_year']
        self.until_year = zidb['until_year']
        self.zones_map = zidb['zones_map']
        self.links_map = zidb['links_map']
        self.policies_map = zidb['policies_map']
        self.removed_zones = zidb['removed_zones']
        self.removed_links = zidb['removed_links']
        self.removed_policies = zidb['removed_policies']
        self.merged_notable_zones = zidb['merged_notable_zones']
        self.notable_zones = zidb['notable_zones']
        self.notable_links = zidb['notable_links']
        self.notable_policies = zidb['notable_policies']
        self.original_min_year = zidb['original_min_year']
        self.original_max_year = zidb['original_max_year']
        self.generated_min_year = zidb['generated_min_year']
        self.generated_max_year = zidb['generated_max_year']
        self.buf_sizes = zidb['buf_sizes']
        self.max_buf_size = zidb['max_buf_size']
        self.zone_ids = zidb['zone_ids']
        self.link_ids = zidb['link_ids']
        self.formats_map = zidb['formats_map']
        self.fragments_map = zidb['fragments_map']
        self.letters_map = zidb['letters_map']
        self.compressed_names = zidb['compressed_names']
        self.memory_map8 = zidb['memory_map8']
        self.memory_map32 = zidb['memory_map32']

        self.zones_and_links = (
            list(self.zones_map.keys()) + list(self.links_map.keys())
        )
        self.zone_and_link_ids = self.zone_ids.copy()
        self.zone_and_link_ids.update(self.link_ids)

    def generate_files(self, output_dir: str) -> None:
        # zone_policies.*
        self._write_file(output_dir, self.ZONE_POLICIES_H_FILE_NAME,
                         self.generate_policies_h())
        self._write_file(output_dir, self.ZONE_POLICIES_C_FILE_NAME,
                         self.generate_policies_c())

        # zone_infos.*
        self._write_file(output_dir, self.ZONE_INFOS_H_FILE_NAME,
                         self.generate_infos_h())
        self._write_file(output_dir, self.ZONE_INFOS_C_FILE_NAME,
                         self.generate_infos_c())

        # zone_registry.*
        self._write_file(output_dir, self.ZONE_REGISTRY_H_FILE_NAME,
                         self.generate_registry_h())
        self._write_file(output_dir, self.ZONE_REGISTRY_C_FILE_NAME,
                         self.generate_registry_c())

    def _write_file(self, output_dir: str, filename: str, content: str) -> None:
        full_filename = os.path.join(output_dir, filename)
        with open(full_filename, 'w', encoding='utf-8') as output_file:
            print(content, end='', file=output_file)
        logging.info("Created %s", full_filename)

    def generate_header(self) -> str:
        num_zones = len(self.zones_map)
        num_links = len(self.links_map)
        num_zones_and_links = len(self.zones_and_links)
        num_removed_zones = len(self.removed_zones)
        num_removed_links = len(self.removed_links)
        num_removed_zones_and_links = num_removed_zones + num_removed_links

        rules8 = self.memory_map8['rules']
        policies8 = self.memory_map8['policies']
        eras8 = self.memory_map8['eras']
        infos8 = self.memory_map8['infos']
        links8 = self.memory_map8['links']
        registry8 = self.memory_map8['registry']
        names8 = self.memory_map8['names']
        names_original8 = self.memory_map8['names_original']
        fragments8 = self.memory_map8['fragments']
        formats8 = self.memory_map8['formats']
        letters8 = self.memory_map8['letters']
        total8 = self.memory_map8['total']

        rules32 = self.memory_map32['rules']
        policies32 = self.memory_map32['policies']
        eras32 = self.memory_map32['eras']
        infos32 = self.memory_map32['infos']
        links32 = self.memory_map32['links']
        registry32 = self.memory_map32['registry']
        names32 = self.memory_map32['names']
        names_original32 = self.memory_map32['names_original']
        fragments32 = self.memory_map32['fragments']
        formats32 = self.memory_map32['formats']
        letters32 = self.memory_map32['letters']
        total32 = self.memory_map32['total']

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
// Supported Zones: {num_zones_and_links} ({num_zones} zones, {num_links} links)
// Unsupported Zones: {num_removed_zones_and_links} \
({num_removed_zones} zones, {num_removed_links} links)
// Original Years: [{self.original_min_year},{self.original_max_year}]
// Generated Years: [{self.generated_min_year},{self.generated_max_year}]
//
// Memory (8-bits):
//   Rules: {rules8}
//   Policies: {policies8}
//   Eras: {eras8}
//   Infos: {infos8}
//   Links: {links8}
//   Registry: {registry8}
//   Formats: {formats8}
//   Letters: {letters8}
//   Fragments: {fragments8}
//   Name: {names8} (original: {names_original8})
//   TOTAL: {total8}
//
// Memory (32-bits):
//   Rules: {rules32}
//   Policies: {policies32}
//   Eras: {eras32}
//   Infos: {infos32}
//   Links: {links32}
//   Registry: {registry32}
//   Formats: {formats32}
//   Letters: {letters32}
//   Fragments: {fragments32}
//   Name: {names32} (original: {names_original32})
//   TOTAL: {total32}
//
// DO NOT EDIT

"""

    def generate_policies_h(self) -> str:
        policy_items = ''
        for policy_name, rules in sorted(self.policies_map.items()):
            policy_normalized_name = normalize_name(policy_name)
            policy_items += f"""\
extern const AtcZonePolicy \
k{self.db_namespace}ZonePolicy{policy_normalized_name};
"""

        removed_policy_items = render_comments_map(self.removed_policies)
        notable_policy_items = render_comments_map(self.notable_policies)
        num_policies = len(self.policies_map)
        num_rules = sum([len(rules) for _, rules in self.policies_map.items()])
        num_removed_policies = len(self.removed_policies)
        num_notable_policies = len(self.notable_policies)

        return self.generate_header() + f"""\
#ifndef ACE_TIME_C_ZONEDB_{self.db_header_namespace}_ZONE_POLICIES_H
#define ACE_TIME_C_ZONEDB_{self.db_header_namespace}_ZONE_POLICIES_H

#include "../zoneinfo/zone_info.h"

#ifdef __cplusplus
extern "C" {{
#endif

//---------------------------------------------------------------------------
// Supported policies: {num_policies}
// Supported rules: {num_rules}
//---------------------------------------------------------------------------

{policy_items}

//---------------------------------------------------------------------------
// Unsupported zone policies: {num_removed_policies}
//---------------------------------------------------------------------------

{removed_policy_items}

//---------------------------------------------------------------------------
// Notable zone policies: {num_notable_policies}
//---------------------------------------------------------------------------

{notable_policy_items}

//---------------------------------------------------------------------------

#ifdef __cplusplus
}}
#endif

#endif
"""

    def generate_policies_c(self) -> str:
        policy_items = ''
        num_rules = 0
        for name, rules in sorted(self.policies_map.items()):
            num_rules += len(rules)
            policy_item = self._generate_policy_item(name, rules)
            policy_items += policy_item

        num_policies = len(self.policies_map)

        return self.generate_header() + f"""\
#include "zone_policies.h"

//---------------------------------------------------------------------------
// Policies: {num_policies}
// Rules: {num_rules}
//---------------------------------------------------------------------------

{policy_items}
"""

    def _generate_policy_item(
        self,
        policy_name: str,
        rules: List[ZoneRuleRaw],
    ) -> str:
        # Generate kAtcZoneRules*[]
        rule_items = ''
        for rule in rules:
            at_seconds = rule['at_seconds_truncated']
            if self.generate_hires:
                at_time_code = rule['at_time_seconds_code']
                at_time_modifier = rule['at_time_seconds_modifier']
                label = _to_suffix_label(rule['at_time_suffix'])
                remaining_seconds = at_seconds % 15
                at_time_modifier_comment = \
                    f'{label} + seconds={remaining_seconds}'
                delta_minutes = rule['delta_minutes']
            else:
                at_time_code = rule['at_time_code']
                at_time_modifier = rule['at_time_modifier']
                label = _to_suffix_label(rule['at_time_suffix'])
                remaining_minutes = at_seconds % 900 // 60
                at_time_modifier_comment = \
                    f'{label} + minute={remaining_minutes}'
                delta_code = rule['delta_code_encoded']
                delta_minutes = rule['delta_minutes']
                delta_code_comment = f"(delta_minutes={delta_minutes})/15 + 4"

            if self.generate_int16_years:
                from_year = rule['from_year']
                from_year_label = 'from_year'
                to_year = rule['to_year']
                to_year_label = 'to_year'
            else:
                from_year = rule['from_year_tiny']
                from_year_label = 'from_year_tiny'
                to_year = rule['to_year_tiny']
                to_year_label = 'to_year_tiny'

            raw_line = normalize_raw(rule['raw_line'])
            in_month = rule['in_month']
            on_day_of_week = rule['on_day_of_week']
            on_day_of_month = rule['on_day_of_month']
            letter = rule['letter']
            letter_index = rule['letter_index']

            if self.generate_hires:
                item = f"""\
  // {raw_line}
  {{
    {from_year} /*{from_year_label}*/,
    {to_year} /*{to_year_label}*/,
    {in_month} /*in_month*/,
    {on_day_of_week} /*on_day_of_week*/,
    {on_day_of_month} /*on_day_of_month*/,
    {at_time_modifier} /*at_time_modifier ({at_time_modifier_comment})*/,
    {at_time_code} /*at_time_code ({at_seconds}/15)*/,
    {delta_minutes} /*delta_minutes*/,
    {letter_index} /*letterIndex ("{letter}")*/,
  }},
"""
            else:
                item = f"""\
  // {raw_line}
  {{
    {from_year} /*{from_year_label}*/,
    {to_year} /*{to_year_label}*/,
    {in_month} /*in_month*/,
    {on_day_of_week} /*on_day_of_week*/,
    {on_day_of_month} /*on_day_of_month*/,
    {at_time_code} /*at_time_code*/,
    {at_time_modifier} /*at_time_modifier ({at_time_modifier_comment})*/,
    {delta_code} /*delta_code ({delta_code_comment})*/,
    {letter_index} /*letterIndex ("{letter}")*/,
  }},
"""
            rule_items += item

        # Section header for a ZonePolicy
        num_rules = len(rules)
        policy_normalized_name = normalize_name(policy_name)
        progmem = ''
        policy_item = f"""\
//---------------------------------------------------------------------------
// Policy name: {policy_name}
// Rules: {num_rules}
//---------------------------------------------------------------------------

static const AtcZoneRule kAtcZoneRules{policy_normalized_name}[] {progmem} = {{
{rule_items}
}};

const AtcZonePolicy k{self.db_namespace}ZonePolicy{policy_normalized_name} \
{progmem} = {{
  kAtcZoneRules{policy_normalized_name} /*rules*/,
  {num_rules} /*num_rules*/,
}};

"""

        return policy_item

    SIZEOF_ZONE_ERA_8 = 12
    SIZEOF_ZONE_ERA_32 = 16  # 16 rounded to 4-byte alignment
    SIZEOF_ZONE_INFO_8 = 13
    SIZEOF_ZONE_INFO_32 = 24  # 21 rounded to 4-byte alignment

    def generate_infos_h(self) -> str:
        zone_items = ''
        zone_ids = ''
        zone_buf_sizes = ''
        for zone_name, eras in sorted(self.zones_map.items()):
            zone_normalized_name = normalize_name(zone_name)
            zone_items += f"""\
extern const AtcZoneInfo k{self.db_namespace}Zone{zone_normalized_name}; \
// {zone_name}
"""

            zone_id = self.zone_ids[zone_name]
            zone_ids += f"""\
#define k{self.db_namespace}ZoneId{zone_normalized_name} 0x{zone_id:08x} \
/* {zone_name} */
"""

            buf_size = self.buf_sizes[zone_name].number
            buf_year = self.buf_sizes[zone_name].year
            zone_buf_sizes += f"""\
#define k{self.db_namespace}ZoneBufSize{zone_normalized_name} {buf_size}  \
/* {zone_name} in {buf_year} */
"""

        link_items = ''
        link_ids = ''
        for link_name, zone_name in sorted(self.links_map.items()):
            link_normalized_name = normalize_name(link_name)
            link_items += f"""\
extern const AtcZoneInfo k{self.db_namespace}Zone{link_normalized_name}; \
// {link_name} -> {zone_name}
"""
            link_id = self.link_ids[link_name]
            link_ids += f"""\
#define k{self.db_namespace}ZoneId{link_normalized_name} 0x{link_id:08x} \
/* {link_name} */
"""

        removed_info_items = render_comments_map(self.removed_zones)
        # notable_info_items = render_comments_map(self.notable_zones)
        notable_info_items = render_merged_comments_map(
            self.merged_notable_zones)
        removed_link_items = render_comments_map(self.removed_links)
        notable_link_items = render_comments_map(self.notable_links)

        num_infos = len(self.zones_map)
        num_links = len(self.links_map)
        num_eras = sum([len(eras) for _, eras in self.zones_map.items()])
        num_removed_infos = len(self.removed_zones)
        num_notable_infos = len(self.notable_zones)
        num_removed_links = len(self.removed_links)
        num_notable_links = len(self.notable_links)

        return self.generate_header() + f"""\
#ifndef ACE_TIME_C_ZONEDB_{self.db_header_namespace}_ZONE_INFOS_H
#define ACE_TIME_C_ZONEDB_{self.db_header_namespace}_ZONE_INFOS_H

#include "../zoneinfo/zone_info.h"

#ifdef __cplusplus
extern "C" {{
#endif

//---------------------------------------------------------------------------
// ZoneContext (should not be in PROGMEM)
//---------------------------------------------------------------------------

// Metadata about the zonedb files.
extern const AtcZoneContext k{self.db_namespace}ZoneContext;

//---------------------------------------------------------------------------
// Supported zones: {num_infos}
// Supported eras: {num_eras}
//---------------------------------------------------------------------------

{zone_items}

// Zone Ids

{zone_ids}

//---------------------------------------------------------------------------
// Supported links: {num_links}
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

{zone_buf_sizes}

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

//---------------------------------------------------------------------------

#ifdef __cplusplus
}}
#endif

#endif
"""

    def generate_infos_c(self) -> str:
        # Generate the list of zone infos
        num_eras = 0
        info_items = ''
        for zone_name, eras in sorted(self.zones_map.items()):
            info_item = self._generate_info_item(zone_name, eras)
            info_items += info_item
            num_eras += len(eras)

        # Generate links references.
        link_items = ''
        for link_name, zone_name in sorted(self.links_map.items()):
            link_item = self._generate_link_item(link_name, zone_name)
            link_items += link_item

        # Generate fragments.
        num_fragments = len(self.fragments_map) + 1
        fragments = '/*\\x00*/ NULL,\n'
        for fragment, index in self.fragments_map.items():
            fragments += f'/*\\x{index:02x}*/ "{fragment}",\n'

        # Generate array of letters.
        num_letters = len(self.letters_map)
        letters = ''
        for letter, index in self.letters_map.items():
            letters += f'/*{index}*/ "{letter}",\n'

        num_infos = len(self.zones_map)
        num_links = len(self.links_map)

        return self.generate_header() + f"""\
#include "zone_policies.h"
#include "zone_infos.h"

//---------------------------------------------------------------------------
// ZoneContext (should not be in PROGMEM)
//---------------------------------------------------------------------------

static const char kAtcTzDatabaseVersion[] = "{self.tz_version}";

static const char * const kAtcFragments[] = {{
{fragments}
}};

static const char* const kAtcLetters[] = {{
{letters}
}};

const AtcZoneContext k{self.db_namespace}ZoneContext = {{
  {self.start_year} /*startYear*/,
  {self.until_year} /*untilYear*/,
  kAtcTzDatabaseVersion /*tzVersion*/,
  {num_fragments} /*numFragments*/,
  {num_letters} /*numLetters*/,
  kAtcFragments /*fragments*/,
  kAtcLetters /*letters*/,
}};

//---------------------------------------------------------------------------
// Zones: {num_infos}
// Eras: {num_eras}
//---------------------------------------------------------------------------

{info_items}

//---------------------------------------------------------------------------
// Links: {num_links}
//---------------------------------------------------------------------------

{link_items}
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
        progmem = ''
        info_item = f"""\
//---------------------------------------------------------------------------
// Zone name: {zone_name}
// Zone Eras: {num_eras}
//---------------------------------------------------------------------------

static const AtcZoneEra kAtcZoneEra{zone_normalized_name}[] {progmem} = {{
{era_items}
}};

static const char kAtcZoneName{zone_normalized_name}[] {progmem} = \
{rendered_name};

const AtcZoneInfo k{self.db_namespace}Zone{zone_normalized_name} {progmem} = {{
  kAtcZoneName{zone_normalized_name} /*name*/,
  0x{zone_id:08x} /*zone_id*/,
  &k{self.db_namespace}ZoneContext /*zone_context*/,
  {num_eras} /*num_eras*/,
  kAtcZoneEra{zone_normalized_name} /*eras*/,
  NULL /*targetInfo*/,
}};

"""

        return info_item

    def _generate_era_item(
        self, zone_name: str, era: ZoneEraRaw
    ) -> str:
        rules_policy_name = era['rules']
        if rules_policy_name == '-' or rules_policy_name == ':':
            zone_policy = 'NULL'
        else:
            zone_policy = f"""\
&k{self.db_namespace}ZonePolicy{normalize_name(rules_policy_name)}"""

        offset_seconds = era['offset_seconds_truncated']
        if self.generate_hires:
            offset_code = era['offset_seconds_code']
            offset_remainder = era['offset_seconds_remainder']
            delta_minutes = era['delta_minutes']
        else:
            offset_code = era['offset_code']
            delta_code = era['delta_code_encoded']
            offset_minute = era['offset_minute']
            delta_minutes = era['delta_minutes']
            delta_code_comment = (
                f"((offset_minute={offset_minute}) << 4) + "
                f"((delta_minutes={delta_minutes})/15 + 4)"
            )

        if self.generate_int16_years:
            until_year = era['until_year']
            until_year_label = 'until_year'
        else:
            until_year = era['until_year_tiny']
            until_year_label = 'until_year_tiny'
        until_month = era['until_month']
        until_day = era['until_day']

        until_seconds = era['until_seconds_truncated']
        if self.generate_hires:
            until_time_code = era['until_time_seconds_code']
            until_time_modifier = era['until_time_seconds_modifier']
            label = _to_suffix_label(era['until_time_suffix'])
            remaining_seconds = until_seconds % 15
            until_time_modifier_comment = \
                f'{label} + seconds={remaining_seconds}'
        else:
            until_time_code = era['until_time_code']
            until_time_modifier = era['until_time_modifier']
            label = _to_suffix_label(era['until_time_suffix'])
            remaining_minutes = until_seconds % 900 // 60
            until_time_modifier_comment = \
                f'{label} + minute={remaining_minutes}'

        format = era['format_short']
        raw_line = normalize_raw(era['raw_line'])

        if self.generate_hires:
            era_item = f"""\
  // {raw_line}
  {{
    {zone_policy} /*zone_policy*/,
    "{format}" /*format*/,
    {offset_code} /*offset_code ({offset_seconds}/15)*/,
    {offset_remainder} /*offset_remainder ({offset_seconds}%15)*/,
    {delta_minutes} /*delta_minutes*/,
    {until_year} /*{until_year_label}*/,
    {until_month} /*until_month*/,
    {until_day} /*until_day*/,
    {until_time_code} /*until_time_code ({until_seconds}/15)*/,
    {until_time_modifier} /*until_time_modifier \
({until_time_modifier_comment})*/,
  }},
"""
        else:
            era_item = f"""\
  // {raw_line}
  {{
    {zone_policy} /*zone_policy*/,
    "{format}" /*format*/,
    {offset_code} /*offset_code*/,
    {delta_code} /*delta_code ({delta_code_comment})*/,
    {until_year} /*{until_year_label}*/,
    {until_month} /*until_month*/,
    {until_day} /*until_day*/,
    {until_time_code} /*until_time_code*/,
    {until_time_modifier} /*until_time_modifier \
({until_time_modifier_comment})*/,
  }},
"""

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
        num_eras = len(self.zones_map[zone_name])
        progmem = ''

        return f"""\
//---------------------------------------------------------------------------
// Link name: {link_name} -> {zone_name}
//---------------------------------------------------------------------------

static const char kAtcZoneName{link_normalized_name}[] {progmem} = \
{rendered_name};

const AtcZoneInfo k{self.db_namespace}Zone{link_normalized_name} {progmem} = {{
  kAtcZoneName{link_normalized_name} /*name*/,
  0x{link_id:08x} /*zoneId*/,
  &k{self.db_namespace}ZoneContext /*zoneContext*/,
  {num_eras} /*numEras*/,
  kAtcZoneEra{zone_normalized_name} /*eras*/,
  &k{self.db_namespace}Zone{zone_normalized_name} /*targetInfo*/,
}};

"""

    def generate_registry_c(self) -> str:

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
  &k{self.db_namespace}Zone{normalized_name}, // 0x{zone_id:08x}, {zone_name}
"""

        # Generate Zones and Links, sorted by zoneId.
        zone_and_link_registry_items = ''
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
  &k{self.db_namespace}Zone{normalized_name}, // 0x{zone_id:08x}, {desc_name}
"""

        num_zones = len(self.zones_map)
        num_zones_and_links = len(self.zones_and_links)
        progmem = ''

        return self.generate_header() + f"""\
#include "zone_infos.h"
#include "zone_registry.h"

//---------------------------------------------------------------------------
// Zone Info registry. Sorted by zoneId.
//---------------------------------------------------------------------------
const AtcZoneInfo * const k{self.db_namespace}ZoneRegistry[{num_zones}] \
{progmem} = {{
{zone_registry_items}
}};

//---------------------------------------------------------------------------
// Zone and Link Info registry. Sorted by zoneId. Links act like Zones.
//---------------------------------------------------------------------------
const AtcZoneInfo * const \
k{self.db_namespace}ZoneAndLinkRegistry[{num_zones_and_links}] \
{progmem} = {{
{zone_and_link_registry_items}
}};
"""

    def generate_registry_h(self) -> str:
        num_zones = len(self.zones_map)
        num_zones_and_links = len(self.zones_and_links)

        return self.generate_header() + f"""\
#ifndef ACE_TIME_C_ZONEDB_{self.db_header_namespace}_ZONE_REGISTRY_H
#define ACE_TIME_C_ZONEDB_{self.db_header_namespace}_ZONE_REGISTRY_H

#include "../zoneinfo/zone_info.h"

#ifdef __cplusplus
extern "C" {{
#endif

// Zones
#define k{self.db_namespace}ZoneRegistrySize {num_zones}
extern const AtcZoneInfo * const k{self.db_namespace}ZoneRegistry[{num_zones}];

// Zones and Links
#define k{self.db_namespace}ZoneAndLinkRegistrySize {num_zones_and_links}
extern const AtcZoneInfo * \
const k{self.db_namespace}ZoneAndLinkRegistry[{num_zones_and_links}];

#ifdef __cplusplus
}}
#endif

#endif
"""


def _to_suffix_label(suffix: str) -> str:
    if suffix == 'w':
        return 'kAtcSuffixW'
    elif suffix == 's':
        return 'kAtcSuffixS'
    else:
        return 'kAtcSuffixU'
    return 'UNKNOWN'
