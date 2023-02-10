# Copyright 2022 Brian T. Park
#
# MIT License
"""
Generate the zone_info and zone_policies files for the AceTimeC C library.
Borrowed heavily from argenerator.py.
"""

import os
import logging
from typing import Dict
from typing import List
from typing import Tuple

from acetimetools.data_types.at_types import ZoneRuleRaw
from acetimetools.data_types.at_types import ZoneEraRaw
from acetimetools.data_types.at_types import ZonesMap
from acetimetools.data_types.at_types import PoliciesMap
from acetimetools.data_types.at_types import LinksMap
from acetimetools.data_types.at_types import CommentsMap
from acetimetools.data_types.at_types import MergedCommentsMap
from acetimetools.data_types.at_types import IndexMap
from acetimetools.data_types.at_types import ZoneInfoDatabase
from acetimetools.data_types.at_types import BufSizeMap
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
        zidb: ZoneInfoDatabase,
    ):
        # If I add a backslash (\) at the end of each line (which is needed if I
        # want to copy and paste the shell command), the C++ compiler spews out
        # warnings about "multi-line comment [-Wcomment]".
        wrapped_invocation = '\n//     --'.join(invocation.split(' --'))
        wrapped_tzfiles = '\n//   '.join(zidb['tz_files'])

        # Determine zonedb C++ namespace
        scope = zidb['scope']
        if not db_namespace:
            if scope == 'basic':
                db_namespace = 'zonedb'
            elif scope == 'extended':
                db_namespace = 'zonedbx'
            else:
                raise Exception(
                    f"db_namespace cannot be determined for scope '{scope}'"
                )

        self.zone_policies_generator = ZonePoliciesGenerator(
            invocation=wrapped_invocation,
            tz_files=wrapped_tzfiles,
            db_namespace=db_namespace,
            generate_int16_years=generate_int16_years,
            tz_version=zidb['tz_version'],
            scope=zidb['scope'],
            zones_map=zidb['zones_map'],
            policies_map=zidb['policies_map'],
            removed_zones=zidb['removed_zones'],
            removed_policies=zidb['removed_policies'],
            notable_zones=zidb['notable_zones'],
            notable_policies=zidb['notable_policies'],
            letters_map=zidb['letters_map'],
        )
        self.zone_infos_generator = ZoneInfosGenerator(
            invocation=wrapped_invocation,
            tz_files=wrapped_tzfiles,
            db_namespace=db_namespace,
            compress=compress,
            generate_int16_years=generate_int16_years,
            tz_version=zidb['tz_version'],
            scope=zidb['scope'],
            start_year=zidb['start_year'],
            until_year=zidb['until_year'],
            zones_map=zidb['zones_map'],
            links_map=zidb['links_map'],
            policies_map=zidb['policies_map'],
            removed_zones=zidb['removed_zones'],
            removed_links=zidb['removed_links'],
            removed_policies=zidb['removed_policies'],
            notable_zones=zidb['notable_zones'],
            merged_notable_zones=zidb['merged_notable_zones'],
            notable_links=zidb['notable_links'],
            notable_policies=zidb['notable_policies'],
            buf_sizes=zidb['buf_sizes'],
            max_buf_size=zidb['max_buf_size'],
            zone_ids=zidb['zone_ids'],
            link_ids=zidb['link_ids'],
            formats_map=zidb['formats_map'],
            fragments_map=zidb['fragments_map'],
            letters_map=zidb['letters_map'],
            compressed_names=zidb['compressed_names'],
        )
        self.zone_registry_generator = ZoneRegistryGenerator(
            invocation=wrapped_invocation,
            tz_files=wrapped_tzfiles,
            db_namespace=db_namespace,
            tz_version=zidb['tz_version'],
            scope=zidb['scope'],
            zones_map=zidb['zones_map'],
            links_map=zidb['links_map'],
            zone_ids=zidb['zone_ids'],
            link_ids=zidb['link_ids'],
        )

    def generate_files(self, output_dir: str) -> None:
        # zone_policies.*
        self._write_file(output_dir, self.ZONE_POLICIES_H_FILE_NAME,
                         self.zone_policies_generator.generate_policies_h())
        self._write_file(output_dir, self.ZONE_POLICIES_C_FILE_NAME,
                         self.zone_policies_generator.generate_policies_c())

        # zone_infos.*
        self._write_file(output_dir, self.ZONE_INFOS_H_FILE_NAME,
                         self.zone_infos_generator.generate_infos_h())
        self._write_file(output_dir, self.ZONE_INFOS_C_FILE_NAME,
                         self.zone_infos_generator.generate_infos_c())

        # zone_registry.*
        self._write_file(output_dir, self.ZONE_REGISTRY_H_FILE_NAME,
                         self.zone_registry_generator.generate_registry_h())
        self._write_file(output_dir, self.ZONE_REGISTRY_C_FILE_NAME,
                         self.zone_registry_generator.generate_registry_c())

    def _write_file(self, output_dir: str, filename: str, content: str) -> None:
        full_filename = os.path.join(output_dir, filename)
        with open(full_filename, 'w', encoding='utf-8') as output_file:
            print(content, end='', file=output_file)
        logging.info("Created %s", full_filename)


class ZonePoliciesGenerator:

    ZONE_POLICIES_H_FILE = """\
// This file was generated by the following script:
//
//   $ {invocation}
//
// using the TZ Database files
//
//   {tz_files}
//
// from https://github.com/eggert/tz/releases/tag/{tz_version}
//
// DO NOT EDIT

#ifndef ACE_TIME_C_{dbHeaderNamespace}_ZONE_POLICIES_H
#define ACE_TIME_C_{dbHeaderNamespace}_ZONE_POLICIES_H

#include "../zone_info.h"

#ifdef __cplusplus
extern "C" {{
#endif

//---------------------------------------------------------------------------
// Supported zone policies: {numPolicies}
//---------------------------------------------------------------------------

{policyItems}

//---------------------------------------------------------------------------
// Unsupported zone policies: {numRemovedPolicies}
//---------------------------------------------------------------------------

{removedPolicyItems}

//---------------------------------------------------------------------------
// Notable zone policies: {numNotablePolicies}
//---------------------------------------------------------------------------

{notablePolicyItems}

//---------------------------------------------------------------------------

#ifdef __cplusplus
}}
#endif

#endif
"""

    ZONE_POLICIES_C_FILE = """\
// This file was generated by the following script:
//
//   $ {invocation}
//
// using the TZ Database files
//
//   {tz_files}
//
// from https://github.com/eggert/tz/releases/tag/{tz_version}
//
// Policies: {numPolicies}
// Rules: {numRules}
// Letter Size (bytes): {letterSize}
// Total Memory 8-bit (bytes): {memory8}
// Total Memory 32-bit (bytes): {memory32}
//
// DO NOT EDIT

#include "zone_policies.h"

{policyItems}
"""

    SIZEOF_ZONE_RULE_8 = 11
    SIZEOF_ZONE_RULE_32 = 12  # 11 rounded to 4-byte alignment
    SIZEOF_ZONE_POLICY_8 = 6
    SIZEOF_ZONE_POLICY_32 = 12  # 10 rounded to 4-byte alignment

    def __init__(
        self,
        invocation: str,
        tz_files: str,
        db_namespace: str,
        generate_int16_years: bool,
        tz_version: str,
        scope: str,
        zones_map: ZonesMap,
        policies_map: PoliciesMap,
        removed_zones: CommentsMap,
        removed_policies: CommentsMap,
        notable_zones: CommentsMap,
        notable_policies: CommentsMap,
        letters_map: IndexMap,
    ):
        self.invocation = invocation
        self.tz_files = tz_files
        self.db_namespace = db_namespace
        self.generate_int16_years = generate_int16_years
        self.tz_version = tz_version
        self.scope = scope
        self.zones_map = zones_map
        self.policies_map = policies_map
        self.removed_zones = removed_zones
        self.removed_policies = removed_policies
        self.notable_zones = notable_zones
        self.notable_policies = notable_policies
        self.letters_map = letters_map

        self.db_header_namespace = self.db_namespace.upper()

    def generate_policies_h(self) -> str:
        policy_items = ''
        for policy_name, rules in sorted(self.policies_map.items()):
            policy_normalized_name = normalize_name(policy_name)
            policy_items += f"""\
extern const AtcZonePolicy kAtcZonePolicy{policy_normalized_name};
"""

        removed_policy_items = render_comments_map(self.removed_policies)
        notable_policy_items = render_comments_map(self.notable_policies)

        return self.ZONE_POLICIES_H_FILE.format(
            invocation=self.invocation,
            tz_files=self.tz_files,
            tz_version=self.tz_version,
            dbNamespace=self.db_namespace,
            dbHeaderNamespace=self.db_header_namespace,
            numPolicies=len(self.policies_map),
            policyItems=policy_items,
            numRemovedPolicies=len(self.removed_policies),
            removedPolicyItems=removed_policy_items,
            numNotablePolicies=len(self.notable_policies),
            notablePolicyItems=notable_policy_items)

    def generate_policies_c(self) -> str:
        policy_items = ''
        memory8 = 0
        memory32 = 0
        num_rules = 0
        for name, rules in sorted(self.policies_map.items()):
            num_rules += len(rules)
            policy_item, policy_memory8, policy_memory32 = \
                self._generate_policy_item(name, rules)
            policy_items += policy_item
            memory8 += policy_memory8
            memory32 += policy_memory32

        num_policies = len(self.policies_map)
        letter_size = sum([
            len(letter) + 1 for letter in self.letters_map.keys()
        ])

        return self.ZONE_POLICIES_C_FILE.format(
            invocation=self.invocation,
            tz_files=self.tz_files,
            tz_version=self.tz_version,
            dbNamespace=self.db_namespace,
            dbHeaderNamespace=self.db_header_namespace,
            numPolicies=num_policies,
            numRules=num_rules,
            letterSize=letter_size,
            memory8=memory8,
            memory32=memory32,
            policyItems=policy_items)

    def _generate_policy_item(
        self,
        policy_name: str,
        rules: List[ZoneRuleRaw],
    ) -> Tuple[str, int, int]:
        # Generate kAtcZoneRules*[]
        rule_items = ''
        for rule in rules:
            at_time_code = rule['at_time_code']
            at_time_modifier = rule['at_time_modifier']
            at_time_modifier_comment = _get_time_modifier_comment(
                time_seconds=rule['at_seconds_truncated'],
                suffix=rule['at_time_suffix'],
            )
            delta_code = rule['delta_code_encoded']
            delta_code_comment = _get_rule_delta_code_comment(
                delta_seconds=rule['delta_seconds_truncated'],
                scope=self.scope,
            )
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
            rule_items += f"""\
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

        # Calculate the memory consumed by structs and arrays
        num_rules = len(rules)
        memory8 = (
            1 * self.SIZEOF_ZONE_POLICY_8
            + num_rules * self.SIZEOF_ZONE_RULE_8)
        memory32 = (
            1 * self.SIZEOF_ZONE_POLICY_32
            + num_rules * self.SIZEOF_ZONE_RULE_32)

        policy_normalized_name = normalize_name(policy_name)
        progmem = ''
        policy_item = f"""\
//---------------------------------------------------------------------------
// Policy name: {policy_name}
// Rules: {num_rules}
// Memory (8-bit): {memory8}
// Memory (32-bit): {memory32}
//---------------------------------------------------------------------------

static const AtcZoneRule kAtcZoneRules{policy_normalized_name}[] {progmem} = {{
{rule_items}
}};

const AtcZonePolicy kAtcZonePolicy{policy_normalized_name} {progmem} = {{
  kAtcZoneRules{policy_normalized_name} /*rules*/,
  {num_rules} /*num_rules*/,
}};

"""

        return (policy_item, memory8, memory32)


class ZoneInfosGenerator:
    ZONE_INFOS_H_FILE = """\
// This file was generated by the following script:
//
//   $ {invocation}
//
// using the TZ Database files
//
//   {tz_files}
//
// from https://github.com/eggert/tz/releases/tag/{tz_version}
//
// DO NOT EDIT

#ifndef ACE_TIME_C_{dbHeaderNamespace}_ZONE_INFOS_H
#define ACE_TIME_C_{dbHeaderNamespace}_ZONE_INFOS_H

#include "../zone_info.h"

#ifdef __cplusplus
extern "C" {{
#endif

//---------------------------------------------------------------------------
// ZoneContext (should not be in PROGMEM)
//---------------------------------------------------------------------------

// Version of the TZ Database which generated these files.
extern const char kAtcTzDatabaseVersion[];

// Metadata about the zonedb files.
extern const AtcZoneContext kAtcZoneContext;

//---------------------------------------------------------------------------
// Supported zones: {numInfos}
//---------------------------------------------------------------------------

{infoItems}

// Zone Ids

{zoneIds}

//---------------------------------------------------------------------------
// Supported links: {numLinks}
//---------------------------------------------------------------------------

{linkItems}

// Zone Ids

{linkIds}

//---------------------------------------------------------------------------
// Maximum size of the Transition buffer in ExtendedZoneProcessor for each zone
// over the given years. Used only in the AceTimeValidation/Extended*Test tests
// for ExtendedZoneProcessor.
//
// MaxBufSize: {maxBufSize}
//---------------------------------------------------------------------------

{bufSizes}

//---------------------------------------------------------------------------
// Unsupported zones: {numRemovedInfos}
//---------------------------------------------------------------------------

{removedInfoItems}

//---------------------------------------------------------------------------
// Notable zones: {numNotableInfos}
//---------------------------------------------------------------------------

{notableInfoItems}

//---------------------------------------------------------------------------
// Unsupported links: {numRemovedLinks}
//---------------------------------------------------------------------------

{removedLinkItems}

//---------------------------------------------------------------------------
// Notable links: {numNotableLinks}
//---------------------------------------------------------------------------

{notableLinkItems}

//---------------------------------------------------------------------------

#ifdef __cplusplus
}}
#endif

#endif
"""

    ZONE_INFOS_C_FILE = """\
// This file was generated by the following script:
//
//   $ {invocation}
//
// using the TZ Database files
//
//   {tz_files}
//
// from https://github.com/eggert/tz/releases/tag/{tz_version}
//
// Zones: {numInfos}
// Links: {numLinks}
// kAtcZoneRegistry sizes (bytes):
//   Names: {zoneStringSize} (originally {zoneStringOriginalSize})
//   Formats: {formatSize}
//   Fragments: {fragmentSize}
//   Memory (8-bit): {zoneMemory8}
//   Memory (32-bit): {zoneMemory32}
// kAtcZoneAndLinkRegistry sizes (bytes):
//   Names: {zoneAndLinkStringSize} (originally {zoneAndLinkStringOriginalSize})
//   Formats: {formatSize}
//   Fragments: {fragmentSize}
//   Memory (8-bit): {zoneAndLinkMemory8}
//   Memory (32-bit): {zoneAndLinkMemory32}
//
// DO NOT EDIT

#include "zone_policies.h"
#include "zone_infos.h"

//---------------------------------------------------------------------------
// ZoneContext (should not be in PROGMEM)
//---------------------------------------------------------------------------

const char kAtcTzDatabaseVersion[] = "{tz_version}";

const char * const kAtcFragments[] = {{
{fragments}
}};

const char* const kAtcLetters[] = {{
{letters}
}};

const AtcZoneContext kAtcZoneContext = {{
  {start_year} /*startYear*/,
  {until_year} /*untilYear*/,
  kAtcTzDatabaseVersion /*tzVersion*/,
  {numFragments} /*numFragments*/,
  {numLetters} /*numLetters*/,
  kAtcFragments /*fragments*/,
  kAtcLetters /*letters*/,
}};

//---------------------------------------------------------------------------
// Zones: {numInfos}
//---------------------------------------------------------------------------

{infoItems}

//---------------------------------------------------------------------------
// Links: {numLinks}
//---------------------------------------------------------------------------

{linkItems}
"""

    SIZEOF_ZONE_ERA_8 = 12
    SIZEOF_ZONE_ERA_32 = 16  # 16 rounded to 4-byte alignment
    SIZEOF_ZONE_INFO_8 = 13
    SIZEOF_ZONE_INFO_32 = 24  # 21 rounded to 4-byte alignment

    def __init__(
        self,
        invocation: str,
        db_namespace: str,
        compress: bool,
        generate_int16_years: bool,
        tz_version: str,
        tz_files: str,
        scope: str,
        start_year: int,
        until_year: int,
        zones_map: ZonesMap,
        links_map: LinksMap,
        policies_map: PoliciesMap,
        removed_zones: CommentsMap,
        removed_links: CommentsMap,
        removed_policies: CommentsMap,
        notable_zones: CommentsMap,
        merged_notable_zones: MergedCommentsMap,
        notable_links: CommentsMap,
        notable_policies: CommentsMap,
        buf_sizes: BufSizeMap,
        max_buf_size: int,
        zone_ids: Dict[str, int],
        link_ids: Dict[str, int],
        formats_map: IndexMap,
        fragments_map: IndexMap,
        letters_map: IndexMap,
        compressed_names: Dict[str, str],
    ):
        self.invocation = invocation
        self.db_namespace = db_namespace
        self.compress = compress
        self.generate_int16_years = generate_int16_years
        self.tz_version = tz_version
        self.tz_files = tz_files
        self.scope = scope
        self.start_year = start_year
        self.until_year = until_year
        self.zones_map = zones_map
        self.links_map = links_map
        self.policies_map = policies_map
        self.removed_zones = removed_zones
        self.removed_links = removed_links
        self.removed_policies = removed_policies
        self.notable_zones = notable_zones
        self.merged_notable_zones = merged_notable_zones
        self.notable_links = notable_links
        self.notable_policies = notable_policies
        self.buf_sizes = buf_sizes
        self.max_buf_size = max_buf_size
        self.zone_ids = zone_ids
        self.link_ids = link_ids
        self.formats_map = formats_map
        self.fragments_map = fragments_map
        self.letters_map = letters_map
        self.compressed_names = compressed_names

        self.db_header_namespace = self.db_namespace.upper()

    def generate_infos_h(self) -> str:
        info_items = ''
        info_zone_ids = ''
        info_buf_sizes = ''
        for zone_name, eras in sorted(self.zones_map.items()):
            zone_normalized_name = normalize_name(zone_name)
            info_items += f"""\
extern const AtcZoneInfo kAtcZone{zone_normalized_name}; // {zone_name}
"""

            zone_id = self.zone_ids[zone_name]
            info_zone_ids += f"""\
#define kAtcZoneId{zone_normalized_name} 0x{zone_id:08x} /* {zone_name} */
"""

            buf_size = self.buf_sizes[zone_name].number
            buf_year = self.buf_sizes[zone_name].year
            info_buf_sizes += f"""\
#define kAtcZoneBufSize{zone_normalized_name} {buf_size}  \
/* {zone_name} in {buf_year} */
"""

        link_items = ''
        link_ids = ''
        for link_name, zone_name in sorted(self.links_map.items()):
            link_normalized_name = normalize_name(link_name)
            link_items += f"""\
extern const AtcZoneInfo kAtcZone{link_normalized_name}; \
// {link_name} -> {zone_name}
"""
            link_id = self.link_ids[link_name]
            link_ids += f"""\
#define kAtcZoneId{link_normalized_name} 0x{link_id:08x} /* {link_name} */
"""

        removed_info_items = render_comments_map(self.removed_zones)
        # notable_info_items = render_comments_map(self.notable_zones)
        notable_info_items = render_merged_comments_map(
            self.merged_notable_zones)
        removed_link_items = render_comments_map(self.removed_links)
        notable_link_items = render_comments_map(self.notable_links)

        return self.ZONE_INFOS_H_FILE.format(
            invocation=self.invocation,
            tz_files=self.tz_files,
            tz_version=self.tz_version,
            scope=self.scope,
            dbNamespace=self.db_namespace,
            dbHeaderNamespace=self.db_header_namespace,
            numInfos=len(self.zones_map),
            infoItems=info_items,
            zoneIds=info_zone_ids,
            numLinks=len(self.links_map),
            linkItems=link_items,
            linkIds=link_ids,
            numRemovedInfos=len(self.removed_zones),
            removedInfoItems=removed_info_items,
            numNotableInfos=len(self.notable_zones),
            notableInfoItems=notable_info_items,
            numRemovedLinks=len(self.removed_links),
            removedLinkItems=removed_link_items,
            numNotableLinks=len(self.notable_links),
            notableLinkItems=notable_link_items,
            bufSizes=info_buf_sizes,
            maxBufSize=self.max_buf_size,
        )

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

        # Estimate size of entire ZoneInfo database, factoring in deduping
        # of strings
        num_infos = len(self.zones_map)
        num_links = len(self.links_map)
        zone_string_original_size = sum([
            len(name) + 1 for name in self.zones_map.keys()
        ])
        if self.compress:
            zone_string_size = sum([
                len(self.compressed_names[name]) + 1
                for name in self.zones_map.keys()
            ])
        else:
            zone_string_size = sum([
                len(name) + 1
                for name in self.zones_map.keys()
            ])
        link_string_original_size = sum([
            len(name) + 1 for name in self.links_map.keys()
        ])
        if self.compress:
            link_string_size = sum([
                len(self.compressed_names[name]) + 1
                for name in self.links_map.keys()
            ])
        else:
            link_string_size = sum([
                len(name) + 1
                for name in self.links_map.keys()
            ])
        format_size = sum([len(s) + 1 for s in self.formats_map.keys()])
        fragment_size = sum([len(s) + 1 for s in self.fragments_map.keys()])

        zone_memory8 = (
            zone_string_size
            + format_size
            + fragment_size
            + num_eras * self.SIZEOF_ZONE_ERA_8
            + num_infos * self.SIZEOF_ZONE_INFO_8
            + num_infos * 2  # sizeof(kAtcZoneRegistry)
            + num_fragments * 2
        )
        zone_memory32 = (
            zone_string_size
            + format_size
            + fragment_size
            + num_eras * self.SIZEOF_ZONE_ERA_32
            + num_infos * self.SIZEOF_ZONE_INFO_32
            + num_infos * 4  # sizeof(kAtcZoneRegistry)
            + num_fragments * 2
        )
        zone_and_link_memory8 = (
            zone_memory8
            + link_string_size
            + num_links * self.SIZEOF_ZONE_INFO_8
            + num_links * 2  # sizeof(kAtcZoneAndLinkRegistry)
        )
        zone_and_link_memory32 = (
            zone_memory32
            + link_string_size
            + num_links * self.SIZEOF_ZONE_INFO_32
            + num_links * 4  # sizeof(kAtcZoneAndLinkRegistry)
        )
        zone_and_link_string_original_size = (
            zone_string_original_size + link_string_original_size
        )

        return self.ZONE_INFOS_C_FILE.format(
            invocation=self.invocation,
            tz_files=self.tz_files,
            tz_version=self.tz_version,
            scope=self.scope,
            start_year=self.start_year,
            until_year=self.until_year,
            dbNamespace=self.db_namespace,
            dbHeaderNamespace=self.db_header_namespace,
            numInfos=num_infos,
            numLinks=num_links,
            numEras=num_eras,
            zoneStringSize=zone_string_size,
            zoneStringOriginalSize=zone_string_original_size,
            zoneMemory8=zone_memory8,
            zoneMemory32=zone_memory32,
            zoneAndLinkStringSize=(zone_string_size + link_string_size),
            zoneAndLinkStringOriginalSize=zone_and_link_string_original_size,
            zoneAndLinkMemory8=zone_and_link_memory8,
            zoneAndLinkMemory32=zone_and_link_memory32,
            formatSize=format_size,
            fragmentSize=fragment_size,
            infoItems=info_items,
            linkItems=link_items,
            numFragments=num_fragments,
            numLetters=num_letters,
            fragments=fragments,
            letters=letters,
        )

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

        # Calculate memory sizes
        zone_name_size = len(compressed_name) + 1
        format_size = 0
        for era in eras:
            format_size += len(era['format_short']) + 1
        num_eras = len(eras)
        data_size8 = (
            num_eras * self.SIZEOF_ZONE_ERA_8
            + self.SIZEOF_ZONE_INFO_8
        )
        data_size32 = (
            num_eras * self.SIZEOF_ZONE_ERA_32
            + self.SIZEOF_ZONE_INFO_32
        )

        string_size = zone_name_size + format_size
        original_size = len(zone_name) + 1 + format_size
        zone_normalized_name = normalize_name(zone_name)
        zone_id = self.zone_ids[zone_name]
        memory8 = data_size8 + string_size
        memory32 = data_size32 + string_size
        progmem = ''
        info_item = f"""\
//---------------------------------------------------------------------------
// Zone name: {zone_name}
// Zone Eras: {num_eras}
// Strings (bytes): {string_size} (originally {original_size})
// Memory (8-bit): {memory8}
// Memory (32-bit): {memory32}
//---------------------------------------------------------------------------

static const AtcZoneEra kAtcZoneEra{zone_normalized_name}[] {progmem} = {{
{era_items}
}};

static const char kAtcZoneName{zone_normalized_name}[] {progmem} = \
{rendered_name};

const AtcZoneInfo kAtcZone{zone_normalized_name} {progmem} = {{
  kAtcZoneName{zone_normalized_name} /*name*/,
  0x{zone_id:08x} /*zone_id*/,
  &kAtcZoneContext /*zone_context*/,
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
            zone_policy = f'&kAtcZonePolicy{normalize_name(rules_policy_name)}'

        offset_code = era['offset_code']
        delta_code = era['delta_code_encoded']
        delta_code_comment = _get_era_delta_code_comment(
            offset_seconds=era['offset_seconds_truncated'],
            delta_seconds=era['era_delta_seconds_truncated'],
            scope=self.scope,
        )
        if self.generate_int16_years:
            until_year = era['until_year']
            until_year_label = 'until_year'
        else:
            until_year = era['until_year_tiny']
            until_year_label = 'until_year_tiny'
        until_month = era['until_month']
        until_day = era['until_day']
        until_time_code = era['until_time_code']
        until_time_modifier = era['until_time_modifier']
        until_time_modifier_comment = _get_time_modifier_comment(
            time_seconds=era['until_seconds_truncated'],
            suffix=era['until_time_suffix'],
        )
        format = era['format_short']
        raw_line = normalize_raw(era['raw_line'])
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

        link_name_size = len(compressed_name) + 1
        original_link_name_size = len(link_name) + 1
        memory8 = link_name_size + self.SIZEOF_ZONE_INFO_8
        memory32 = link_name_size + self.SIZEOF_ZONE_INFO_32
        link_normalized_name = normalize_name(link_name)
        link_id = self.link_ids[link_name]
        zone_normalized_name = normalize_name(zone_name)
        num_eras = len(self.zones_map[zone_name])
        progmem = ''
        link_item = f"""\
//---------------------------------------------------------------------------
// Link name: {link_name} -> {zone_name}
// Strings (bytes): {link_name_size} (originally {original_link_name_size})
// Memory (8-bit): {memory8}
// Memory (32-bit): {memory32}
//---------------------------------------------------------------------------

static const char kAtcZoneName{link_normalized_name}[] {progmem} = \
{rendered_name};

const AtcZoneInfo kAtcZone{link_normalized_name} {progmem} = {{
  kAtcZoneName{link_normalized_name} /*name*/,
  0x{link_id:08x} /*zoneId*/,
  &kAtcZoneContext /*zoneContext*/,
  {num_eras} /*numEras*/,
  kAtcZoneEra{zone_normalized_name} /*eras*/,
  &kAtcZone{zone_normalized_name} /*targetInfo*/,
}};

"""

        return link_item


class ZoneRegistryGenerator:

    ZONE_REGISTRY_C_FILE = """\
// This file was generated by the following script:
//
//   $ {invocation}
//
// using the TZ Database files
//
//   {tz_files}
//
// from https://github.com/eggert/tz/releases/tag/{tz_version}
//
// DO NOT EDIT

#include "zone_infos.h"
#include "zone_registry.h"

//---------------------------------------------------------------------------
// Zone Info registry. Sorted by zoneId.
//---------------------------------------------------------------------------
const AtcZoneInfo * const kAtcZoneRegistry[{numZones}] {progmem} = {{
{zoneRegistryItems}
}};

//---------------------------------------------------------------------------
// Zone and Link Info registry. Sorted by zoneId. Links act like Zones.
//---------------------------------------------------------------------------
const AtcZoneInfo * const kAtcZoneAndLinkRegistry[{numZonesAndLinks}] \
{progmem} = {{
{zoneAndLinkRegistryItems}
}};
"""

    ZONE_REGISTRY_H_FILE = """\
// This file was generated by the following script:
//
//   $ {invocation}
//
// using the TZ Database files
//
//   {tz_files}
//
// from https://github.com/eggert/tz/releases/tag/{tz_version}
//
// DO NOT EDIT

#ifndef ACE_TIME_C_{dbHeaderNamespace}_ZONE_REGISTRY_H
#define ACE_TIME_C_{dbHeaderNamespace}_ZONE_REGISTRY_H

#include "../zone_info.h"

#ifdef __cplusplus
extern "C" {{
#endif

// Zones
#define kAtcZoneRegistrySize {numZones}
extern const AtcZoneInfo * const kAtcZoneRegistry[{numZones}];

// Zones and Links
#define kAtcZoneAndLinkRegistrySize {numZonesAndLinks}
extern const AtcZoneInfo * \
const kAtcZoneAndLinkRegistry[{numZonesAndLinks}];

#ifdef __cplusplus
}}
#endif

#endif
"""

    def __init__(
        self,
        invocation: str,
        tz_files: str,
        db_namespace: str,
        tz_version: str,
        scope: str,
        zones_map: ZonesMap,
        links_map: LinksMap,
        zone_ids: Dict[str, int],
        link_ids: Dict[str, int],
    ):
        self.invocation = invocation
        self.tz_files = tz_files
        self.db_namespace = db_namespace
        self.tz_version = tz_version
        self.scope = scope
        self.zones_map = zones_map
        self.links_map = links_map
        self.zone_ids = zone_ids
        self.link_ids = link_ids

        self.db_header_namespace = self.db_namespace.upper()
        self.zones_and_links = list(zones_map.keys()) + list(links_map.keys())
        self.zone_and_link_ids = zone_ids.copy()
        self.zone_and_link_ids.update(link_ids)

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
  &kAtcZone{normalized_name}, // 0x{zone_id:08x}, {zone_name}
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
  &kAtcZone{normalized_name}, // 0x{zone_id:08x}, {desc_name}
"""

        return self.ZONE_REGISTRY_C_FILE.format(
            invocation=self.invocation,
            tz_files=self.tz_files,
            tz_version=self.tz_version,
            scope=self.scope,
            dbNamespace=self.db_namespace,
            dbHeaderNamespace=self.db_header_namespace,
            numZones=len(self.zones_map),
            numZonesAndLinks=num_zones_and_links,
            numLinks=len(self.links_map),
            zoneRegistryItems=zone_registry_items,
            zoneAndLinkRegistryItems=zone_and_link_registry_items,
            progmem='',
        )

    def generate_registry_h(self) -> str:
        return self.ZONE_REGISTRY_H_FILE.format(
            invocation=self.invocation,
            tz_files=self.tz_files,
            tz_version=self.tz_version,
            scope=self.scope,
            dbNamespace=self.db_namespace,
            dbHeaderNamespace=self.db_header_namespace,
            numZones=len(self.zones_map),
            numZonesAndLinks=len(self.zones_and_links),
            numLinks=len(self.links_map),
        )


def _get_time_modifier_comment(
    time_seconds: int,
    suffix: str,
) -> str:
    """Create the comment that explains how the until_time_code or at_time_code
    was calculated.
    """
    if suffix == 'w':
        comment = 'kAtcSuffixW'
    elif suffix == 's':
        comment = 'kAtcSuffixS'
    else:
        comment = 'kAtcSuffixU'
    remaining_time_minutes = time_seconds % 900 // 60
    comment += f' + minute={remaining_time_minutes}'
    return comment


def _get_era_delta_code_comment(
    offset_seconds: int,
    delta_seconds: int,
    scope: str,
) -> str:
    """Create the comment that explains how the ZoneEra delta_code[_encoded] was
    calculated.
    """
    offset_minute = offset_seconds % 900 // 60
    delta_minutes = delta_seconds // 60
    if scope == 'extended':
        return (
            f"((offset_minute={offset_minute}) << 4) + "
            f"((delta_minutes={delta_minutes})/15 + 4)"
        )
    else:
        return f"(delta_minutes={delta_minutes})/15"


def _get_rule_delta_code_comment(
    delta_seconds: int,
    scope: str,
) -> str:
    """Create the comment that explains how the ZoneRule delta_code[_encoded]
    was calculated.
    """
    delta_minutes = delta_seconds // 60
    if scope == 'extended':
        return f"(delta_minutes={delta_minutes})/15 + 4"
    else:
        return f"(delta_minutes={delta_minutes})/15"
