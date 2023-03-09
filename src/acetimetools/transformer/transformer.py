# Copyright 2018 Brian T. Park
#
# MIT License.

import logging
import re
import datetime
from collections import OrderedDict
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple
from typing_extensions import TypedDict

from acetimetools.data_types.at_types import ZoneRuleRaw
from acetimetools.data_types.at_types import ZoneEraRaw
from acetimetools.data_types.at_types import ZonesMap
from acetimetools.data_types.at_types import PoliciesMap
from acetimetools.data_types.at_types import LinksMap
from acetimetools.data_types.at_types import CommentsMap
from acetimetools.data_types.at_types import TransformerResult
from acetimetools.data_types.at_types import add_comment
from acetimetools.data_types.at_types import merge_comments
from acetimetools.data_types.at_types import EPOCH_YEAR_FOR_TINY
from acetimetools.data_types.at_types import INVALID_YEAR
from acetimetools.data_types.at_types import MAX_UNTIL_YEAR
from acetimetools.data_types.at_types import MIN_YEAR
from acetimetools.data_types.at_types import MIN_YEAR_TINY
from acetimetools.data_types.at_types import MAX_TO_YEAR
from acetimetools.data_types.at_types import MAX_TO_YEAR_TINY

INVALID_SECONDS = 999999  # 277h46m69s

# Map of policyName -> zoneName[] used internally by Transformer to track the
# Zones which references the given policyName.
PoliciesToZones = Dict[str, List[str]]


class Transformer:
    """
    Cleanses and transforms the Zone, Rule and Link entries for processing by
    various AceTime algorithms. The TransformerResult will be further
    transformed by the transformer.ArduinoTransformer class to massage it into
    an at_types.ZoneInfoDatabase data structure. The ZoneInfoDatabase is then
    used to generate the AceTime C++ files, the AceTimePython files, and the
    zonedb*.json JSON files.

    The Transformer was intended to be agnostic to a specific implementation of
    the AceTime algorithms. The ArduinoTransformer was intended to transform the
    abstract data structures into a specific data structure that is suitable to
    be consumed by the AceTime library. It turned out to be easier for the
    AceTimePython library to reuse the same data structure as AceTime, so the
    ArduinoTransformer is used for the AceTimePython library as well.
    """
    def __init__(
        self,
        scope: str,
        start_year: int,
        until_year: int,
        until_at_granularity: int,
        offset_granularity: int,
        delta_granularity: int,
        strict: bool,
        generate_int16_years: bool,
        include_list: Set[str],
    ):
        """
        Args:
            scope: scope of database (basic, or extended)
            start_year: include only years on or after start_year
            until_year: include only years valid before until_year
            until_at_granularity: truncate UNTIL, AT to this many seconds
            offset_granularity: truncate STDOFF (offset) to this many seconds
            delta_granularity: truncate SAVE (delta_seconds), RULES
                (era_delta_seconds) to this many seconds
            strict: throw out Zones or Rules which are not exactly on the time
                boundary defined by granularity
            generate_int16_years: generate 'year' fields for an int16_t type,
                instead of the older int8_t type
            include_list: include list of zones and links, empty means 'all'
        """
        self.scope = scope
        self.start_year = start_year
        self.until_year = until_year
        self.until_at_granularity = until_at_granularity
        self.offset_granularity = offset_granularity
        self.delta_granularity = delta_granularity
        self.strict = strict
        self.generate_int16_years = generate_int16_years
        self.include_list = include_list

        self.all_removed_zones: CommentsMap = {}
        self.all_removed_policies: CommentsMap = {}
        self.all_removed_links: CommentsMap = {}
        self.all_notable_zones: CommentsMap = {}
        self.all_notable_policies: CommentsMap = {}
        self.all_notable_links: CommentsMap = {}

    def transform(self, tresult: TransformerResult) -> None:
        """
        Transforms the given tresult in-situ through a series of filters.
        """
        self.tresult = tresult
        zones_map = tresult.zones_map
        policies_map = tresult.policies_map
        links_map = tresult.links_map

        logging.info(
            'Processing years [%d, %d)',
            self.start_year,
            self.until_year,
        )
        logging.info(
            'Found %d zones, %d policies, %d links',
            len(zones_map),
            len(policies_map),
            len(links_map),
        )

        # Part 1: Some sanity checks, gathering, and include filtering.
        if not self.generate_int16_years:
            if not is_year_tiny(self.start_year):
                raise Exception(f"Start year {self.start_year} not tiny")
            if not is_year_tiny(self.until_year):
                raise Exception(f"Until year {self.until_year} not tiny")
        _detect_links_to_links(links_map)
        _detect_hash_collisions(zones_map=zones_map, links_map=links_map)
        original_min_year, original_max_year = \
            _detect_tzdb_years(zones_map, policies_map)
        links_map = self._filter_include_links(links_map, self.include_list)
        zones_map = self._filter_include_zones(zones_map, self.include_list)

        # Part 2: Transform the zones_map.
        zones_map = self._remove_zone_eras_too_old(zones_map)
        zones_map = self._remove_zone_eras_too_new(zones_map)
        zones_map = self._extend_zone_eras_until(zones_map)
        zones_map = self._remove_zones_without_eras(zones_map)
        if self.scope == 'basic':
            zones_map = self._remove_zone_with_non_simple_until_year(zones_map)
        zones_map = self._create_zones_with_until_day(zones_map)
        zones_map = self._create_zones_with_expanded_until_time(zones_map)
        zones_map = self._remove_zones_invalid_until_time_suffix(zones_map)
        zones_map = self._create_zones_with_expanded_offset_string(zones_map)
        zones_map = self._remove_zones_with_invalid_rules_format_combo(
            zones_map)
        zones_map = self._create_zones_with_rules_expansion(zones_map)
        zones_map = self._remove_zones_with_non_monotonic_until(zones_map)
        zones_map = self._create_short_format_strings(zones_map)
        if not self.generate_int16_years:
            zones_map = self._create_tiny_until_years(zones_map)

        # Part 3: Transformations requiring both zones_map and policies_map.
        policies_map = self._remove_unused_policies(zones_map, policies_map)
        zones_map, policies_map = self._mark_rules_used_by_zones(
            zones_map, policies_map)
        policies_to_zones = _create_policies_to_zones(zones_map, policies_map)

        # Part 4: Transform the policies_map
        policies_map = self._remove_rules_unused(policies_map)
        if not self.generate_int16_years:
            policies_map = self._remove_rules_out_of_bounds(policies_map)
        if self.scope == 'basic':
            policies_map = self._remove_rules_multiple_transitions_in_month(
                policies_map)
        policies_map = self._create_rules_with_expanded_at_time(
            policies_map, policies_to_zones)
        policies_map = self._remove_rules_invalid_at_time_suffix(policies_map)
        policies_map = self._create_rules_with_expanded_delta_offset(
            policies_map)
        policies_map = self._create_rules_with_on_day_expansion(policies_map)
        policies_map = self._create_rules_with_anchor_transition(policies_map)
        policies_map = self._normalize_letters(policies_map)
        if self.scope == 'basic':
            policies_map = self._remove_rules_with_border_transitions(
                policies_map)
        if self.scope == 'basic':
            policies_map = self._remove_rules_long_dst_letter(policies_map)
        if not self.generate_int16_years:
            policies_map = self._create_tiny_from_to_years(policies_map)

        # Part 5: Remove unused zones and links.
        zones_map = self._remove_zones_without_rules(zones_map, policies_map)
        links_map = self._remove_links_to_missing_zones(links_map, zones_map)

        # Part 6: Detect zones and links whose normalized names conflict.
        zones_map, links_map = self._detect_zones_and_links_with_similar_names(
            zones_map, links_map)

        # Part 7: Replace the original maps with the transformed ones.
        tresult.policies_map = policies_map
        tresult.zones_map = zones_map
        tresult.links_map = links_map

        # Part 8: Add additional results
        tresult.zone_ids = self._generate_zone_ids(zones_map)
        tresult.link_ids = self._generate_link_ids(links_map)
        tresult.removed_zones = self.all_removed_zones
        tresult.removed_policies = self.all_removed_policies
        tresult.removed_links = self.all_removed_links
        tresult.notable_zones = self.all_notable_zones
        tresult.notable_policies = self.all_notable_policies
        tresult.notable_links = self.all_notable_links
        tresult.merged_notable_zones = self.tresult.merged_notable_zones
        tresult.original_min_year = original_min_year
        tresult.original_max_year = original_max_year
        tresult.generated_min_year, tresult.generated_max_year = \
            _detect_tzdb_years(zones_map, policies_map)

    def print_summary(self, tresult: TransformerResult) -> None:
        logging.info(
            f"Summary: Zones: generated={len(tresult.zones_map)}"
            f"; removed={len(tresult.removed_zones)}"
            f"; noted={len(tresult.notable_zones)}")

        logging.info(
            f"Summary: Policies: generated={len(tresult.policies_map)}"
            f"; removed={len(tresult.removed_policies)}"
            f"; noted={len(tresult.notable_policies)}")

        logging.info(
            f"Summary: Links: generated={len(tresult.links_map)}"
            f"; removed={len(tresult.removed_links)}"
            f"; noted={len(tresult.notable_links)}")

    def _print_comments_map(
        self,
        label: str,
        comments: CommentsMap,
        max_comments: int = 5,
    ) -> None:
        """Helper routine that prints the 'Removed' or 'Noted' Zone rules or
        Zone eras along with the reason why it was removed or noted. Print up to
        a maximum of max_comments zones or eras.
        """
        if len(comments) == 0:
            return

        # Print summary line, e.g.:
        # "Removed 0 rule policies with from_year or to_year out of bounds"
        logging.info(label, len(comments))

        # Print all lines if len() <= max_comments. Otherwise, print top half of
        # max_comments and bottom half of max_comments.
        sorted_comments = sorted(comments.items())
        num_items = len(sorted_comments)
        if num_items <= max_comments:
            for name, reasons in sorted_comments:
                logging.info(f'- {name} ({reasons})')
        else:
            index = 0
            ellipses_printed = False
            limit = (max_comments - 1) // 2
            for name, reasons in sorted_comments:
                if ((index >= 0 and index < limit)
                        or (index >= num_items - limit and index < num_items)):
                    logging.info(f'- {name} ({reasons})')
                else:
                    if not ellipses_printed:
                        logging.info('- [...]')
                        ellipses_printed = True
                index += 1

    # --------------------------------------------------------------------
    # Part 1: Some sanity checks, gathering, and include filtering.
    # --------------------------------------------------------------------

    def _filter_include_links(
        self,
        links_map: LinksMap,
        include_list: Set[str]
    ) -> LinksMap:
        """Remove links missing from include list."""
        if not include_list:
            return links_map

        results: LinksMap = {}
        removed_links: CommentsMap = {}
        for link_name, zone_name in links_map.items():
            if link_name in include_list:
                results[link_name] = zone_name
            else:
                add_comment(
                    removed_links, link_name,
                    "Link missing from include list"
                )

        self._print_comments_map(
            'Removed %s links missing from include list', removed_links,
        )
        merge_comments(self.all_removed_links, removed_links)
        return results

    def _filter_include_zones(
        self,
        zones_map: ZonesMap,
        include_list: Set[str]
    ) -> ZonesMap:
        """Remove zones missing from include list."""
        if not include_list:
            return zones_map

        results: ZonesMap = {}
        removed_zones: CommentsMap = {}
        for name, eras in zones_map.items():
            if name in include_list:
                results[name] = eras
            else:
                add_comment(
                    removed_zones, name,
                    "Zone missing from include list"
                )

        self._print_comments_map(
            'Removed %s zone infos missing from include list', removed_zones,
        )
        merge_comments(self.all_removed_zones, removed_zones)
        return results

    # --------------------------------------------------------------------
    # Part 2: Transform the zones_map.
    # --------------------------------------------------------------------

    def _remove_zone_eras_too_old(self, zones_map: ZonesMap) -> ZonesMap:
        """Remove zone eras which are too old, i.e. before (self.start_year-1).
        If the start_year is 2000, ZoneProcessor.init_for_year() could be called
        with 1999, so we use `start_year-1`.
        """
        results: ZonesMap = {}
        notable_zones: CommentsMap = {}
        removed_zones: CommentsMap = {}
        count = 0
        for name, eras in zones_map.items():
            keep_eras: List[ZoneEraRaw] = []
            for era in eras:
                if era['until_year'] >= self.start_year - 1:
                    keep_eras.append(era)

            removed_count = len(eras) - len(keep_eras)
            count += removed_count

            if removed_count == 0:
                results[name] = eras
            elif removed_count < len(eras):
                results[name] = keep_eras
                add_comment(
                    notable_zones, name,
                    f'Removed {removed_count} zone eras before '
                    f'year {self.start_year}'
                )
            else:
                add_comment(
                    removed_zones, name,
                    f'All eras are too old, < year {self.start_year}'
                )

        self._print_comments_map(
            'Removed %s zone infos with eras too old', removed_zones,
        )
        self._print_comments_map(
            'Noted %s zone infos with eras too old', notable_zones,
        )
        merge_comments(self.all_removed_zones, removed_zones)
        merge_comments(self.all_notable_zones, notable_zones)
        return results

    def _remove_zone_eras_too_new(self, zones_map: ZonesMap) -> ZonesMap:
        """Remove zone eras which are too new, i.e. after self.until_year.
        We need at least one year after the last valid year (i.e. until_year),
        so we need zone eras valid to at least until_year.

        TODO: If a zone era is removed because it is too far in the future, it
        is no longer guaranteed that the last zone era ends with MAX_UNTIL_YEAR.
        If the ZoneProcessor code is called with a year greater than
        self.until_year, it may cause a loop to crash. I think this means that
        we should not run this transformation.
        """
        results: ZonesMap = {}
        notable_zones: CommentsMap = {}
        removed_zones: CommentsMap = {}
        count = 0
        for name, eras in zones_map.items():
            keep_eras: List[ZoneEraRaw] = []
            start_year = MIN_YEAR
            for era in eras:
                if start_year <= self.until_year + 1:
                    keep_eras.append(era)
                # the next era's start year is this era's until_year
                start_year = era['until_year']

            removed_count = len(eras) - len(keep_eras)
            count += removed_count

            if removed_count == 0:
                results[name] = eras
            elif removed_count < len(eras):
                results[name] = keep_eras
                add_comment(
                    notable_zones, name,
                    f'Removed {removed_count} zone eras after '
                    f'year {self.until_year}'
                )
            else:
                add_comment(
                    removed_zones, name,
                    f'All eras are too new, > year {self.until_year}'
                )

        self._print_comments_map(
            'Removed %s zone infos with eras too new', removed_zones,
        )
        self._print_comments_map(
            'Noted %s zone infos with eras too new', notable_zones,
        )
        merge_comments(self.all_removed_zones, removed_zones)
        merge_comments(self.all_notable_zones, notable_zones)
        return results

    def _extend_zone_eras_until(self, zones_map: ZonesMap) -> ZonesMap:
        """Extend the UNTIL field of last zone era to +Infinity if it is not
        already +Infinity. This happens if zone eras too far in the future were
        removed by _remove_zone_eras_too_new().
        """
        for name, eras in zones_map.items():
            last_era = eras[-1]
            if last_era['until_year'] != MAX_UNTIL_YEAR:
                last_era['until_year'] = MAX_UNTIL_YEAR
                last_era['raw_line'] = 'Extended: ' + last_era['raw_line']
                # Don't bother adding an entry in notable_zones, because there
                # would already be a note about removing eras "too new".

        return zones_map

    def _remove_zones_without_eras(self, zones_map: ZonesMap) -> ZonesMap:
        """Remove zones without any eras, which can happen if the start_year and
        until_year are too narrow. This prevents the C++ code from crashing.
        """
        results: ZonesMap = {}
        removed_zones: CommentsMap = {}
        for name, eras in zones_map.items():
            if eras:
                results[name] = eras
            else:
                add_comment(removed_zones, name, "no ZoneEra found")

        self._print_comments_map(
            'Removed %s zone infos without ZoneEras', removed_zones,
        )
        merge_comments(self.all_removed_zones, removed_zones)
        return results

    def _remove_zone_with_non_simple_until_year(
        self, zones_map: ZonesMap,
    ) -> ZonesMap:
        """Remove zones which have month, day or time in the UNTIL field.
        These are not supported by BasicZoneProcessor.
        """
        results: ZonesMap = {}
        removed_zones: CommentsMap = {}
        for name, eras in zones_map.items():
            valid = True
            for era in eras:
                if not era['until_year_only']:
                    valid = False
                    add_comment(
                        removed_zones, name, "UNTIL contains month/day/time")
                    break
            if valid:
                results[name] = eras

        self._print_comments_map(
            'Removed %s zone infos with UNTIL containing month/day/time',
            removed_zones,
        )
        merge_comments(self.all_removed_zones, removed_zones)
        return results

    def _create_zones_with_until_day(self, zones_map: ZonesMap) -> ZonesMap:
        """Convert zone.until_day from 'lastSun' or 'Sun>=1' to a precise day,
        which is possible because the year and month are already known. For
        example:
            * Zone Asia/Tbilisi 2005 3 lastSun 2:00
            * Zone America/Grand_Turk 2015 Nov Sun>=1 2:00
        """
        results: ZonesMap = {}
        removed_zones: CommentsMap = {}
        notable_zones: CommentsMap = {}
        for name, eras in zones_map.items():
            valid = True
            for era in eras:
                until_day_string = era['until_day_string']

                # Parse the conditional expression in until_day_string. We can
                # resolve the 'lastSun', 'Sun>=X' and 'Fri<=X' to a specific day
                # of month because we know the year.
                (on_day_of_week, on_day_of_month) = \
                    _parse_on_day_string(until_day_string)
                if (on_day_of_week, on_day_of_month) == (0, 0):
                    valid = False
                    add_comment(
                        removed_zones, name,
                        f"invalid until_day '{until_day_string}'")
                    break

                month, day = calc_day_of_month(
                    era['until_year'], era['until_month'], on_day_of_week,
                    on_day_of_month)
                if month == 0:
                    valid = False
                    add_comment(
                        removed_zones, name,
                        f"Shift to previous year unsupported for "
                        f"{until_day_string}")
                    break
                if month == 13:
                    valid = False
                    add_comment(
                        removed_zones, name,
                        f"Shift to following year unsupported for "
                        f"{until_day_string}")

                if era['until_month'] != month:
                    add_comment(
                        notable_zones, name,
                        f"until_month shifted from '{era['until_month']}' to "
                        f"'{month}' due to {until_day_string}")
                era['until_month'], era['until_day'] = month, day

            if valid:
                results[name] = eras

        self._print_comments_map(
            'Removed %s zone infos with invalid UNTIL day', removed_zones
        )
        self._print_comments_map(
            'Noted %s zone infos with notable UNTIL day', notable_zones
        )
        merge_comments(self.all_removed_zones, removed_zones)
        merge_comments(self.all_notable_zones, notable_zones)
        return results

    def _create_zones_with_expanded_until_time(
        self, zones_map: ZonesMap,
    ) -> ZonesMap:
        """ Create 'until_seconds' and 'until_seconds_truncated' from
        'until_time'.
        """
        results: ZonesMap = {}
        removed_zones: CommentsMap = {}
        notable_zones: CommentsMap = {}
        for name, eras in zones_map.items():
            valid = True
            for era in eras:
                until_time = era['until_time']
                until_seconds = time_string_to_seconds(until_time)
                if until_seconds == INVALID_SECONDS:
                    valid = False
                    add_comment(
                        removed_zones, name,
                        f"invalid UNTIL time '{until_time}'")
                    break
                if until_seconds < 0:
                    valid = False
                    add_comment(
                        removed_zones, name,
                        f"negative UNTIL time '{until_time}'")
                    break

                until_seconds_truncated = truncate_to_granularity(
                    until_seconds, self.until_at_granularity)
                if until_seconds != until_seconds_truncated:
                    if self.strict:
                        valid = False
                        add_comment(
                            removed_zones, name,
                            f"UNTIL time '{until_time}' must be multiples "
                            f"of '{self.until_at_granularity}' seconds")
                        break
                    else:
                        hm = seconds_to_hm_string(until_seconds_truncated)
                        add_comment(
                            notable_zones, name,
                            f"UNTIL time '{until_time}' truncated to '{hm}'")
                else:
                    if until_seconds % 60 != 0:
                        add_comment(
                            notable_zones, name,
                            f"UNTIL time '{until_time}' not multiple of 1-min")

                era['until_seconds'] = until_seconds
                era['until_seconds_truncated'] = until_seconds_truncated
            if valid:
                results[name] = eras

        self._print_comments_map(
            'Removed %s zone infos with invalid UNTIL time', removed_zones,
        )
        self._print_comments_map(
            'Noted %s zone infos with notable UNTIL time', notable_zones,
        )
        merge_comments(self.all_removed_zones, removed_zones)
        merge_comments(self.all_notable_zones, notable_zones)
        return results

    def _remove_zones_invalid_until_time_suffix(
        self, zones_map: ZonesMap,
    ) -> ZonesMap:
        """Remove zones whose UNTIL time contains an unsupported suffix.
        """
        # Define the supported time suffices. Basic supports only 'w', while
        # Extended supports all suffixes. The 'g' and 'z' is the same as 'u' and
        # does not currently appear in any TZ file, so let's catch it because it
        # could indicate a bug
        if self.scope == 'basic':
            supported_suffices = ['w']
        else:
            supported_suffices = ['w', 's', 'u']

        results: ZonesMap = {}
        removed_zones: CommentsMap = {}
        for name, eras in zones_map.items():
            valid = True
            for era in eras:
                suffix = era['until_time_suffix']
                suffix = suffix if suffix else 'w'
                era['until_time_suffix'] = suffix
                if suffix not in supported_suffices:
                    valid = False
                    add_comment(
                        removed_zones, name,
                        f"unsupported UNTIL time suffix '{suffix}'")
                    break
            if valid:
                results[name] = eras

        self._print_comments_map(
            'Removed %s zone infos with unsupported UNTIL time suffix',
            removed_zones,
        )
        merge_comments(self.all_removed_zones, removed_zones)
        return results

    def _create_zones_with_expanded_offset_string(
        self, zones_map: ZonesMap,
    ) -> ZonesMap:
        """ Create expanded offset 'offset_seconds' from zone.offset_string.
        """
        results: ZonesMap = {}
        removed_zones: CommentsMap = {}
        notable_zones: CommentsMap = {}
        for name, eras in zones_map.items():
            valid = True
            for era in eras:
                offset_string = era['offset_string']
                offset_seconds = time_string_to_seconds(offset_string)
                if offset_seconds == INVALID_SECONDS:
                    valid = False
                    add_comment(
                        removed_zones, name,
                        f"invalid STDOFF '{offset_string}'")
                    break

                # Truncate offset to requested granularity.
                offset_seconds_truncated = truncate_to_granularity(
                    offset_seconds, self.offset_granularity)
                if offset_seconds != offset_seconds_truncated:
                    if self.strict:
                        valid = False
                        add_comment(
                            removed_zones, name,
                            f"STDOFF '{offset_string}' must be multiples of "
                            f"'{self.offset_granularity}' seconds")
                        break
                    else:
                        hm = seconds_to_hm_string(offset_seconds_truncated)
                        add_comment(
                            notable_zones, name,
                            f"STDOFF '{offset_string}' truncated to '{hm}'")

                # Check that offset seconds can fit in a timeCode field
                # implemented as a signed byte in multiples of 15-minutes.
                offset_code = div_to_zero(offset_seconds_truncated, 900)
                if offset_code < -127 or offset_code > 127:
                    valid = False
                    add_comment(
                        removed_zones, name,
                        f"STDOFF '{offset_string}' too large for 8-bits")
                    break

                era['offset_seconds'] = offset_seconds
                era['offset_seconds_truncated'] = offset_seconds_truncated

            if valid:
                results[name] = eras

        self._print_comments_map(
            'Removed %s zone infos with invalid STDOFF field', removed_zones,
        )
        self._print_comments_map(
            'Noted %s zone infos with notable STDOFF field', notable_zones,
        )
        merge_comments(self.all_removed_zones, removed_zones)
        merge_comments(self.all_notable_zones, notable_zones)
        return results

    def _remove_zones_with_invalid_rules_format_combo(
        self, zones_map: ZonesMap
    ) -> ZonesMap:
        """Check for valid FORMAT field.

        First, it should always exist.

        If the RULES is fixed (i.e. contains '-' or a 'hh:mm' offset, then
        FORMAT can contain only the '/' . It cannot contain a '%' because there
        would be no RULE entry with a LETTER that can replace the '%'.

        If the RULES is a reference to a named RULE, then it seems reasonable to
        always expect a '%' or a '/' but we cannot make this strict. There are
        cases where the FORMAT contains neither, for example,
        Africa/Johannesburg where it defines DST transitions for 1942-1944, but
        there seems to be no corresponding change in the abbreviation so FORMAT
        contains no '%' or '/'. Generate a warning for now.
        """
        results: ZonesMap = {}
        removed_zones: CommentsMap = {}
        notable_zones: CommentsMap = {}
        for zone_name, eras in zones_map.items():
            valid = True
            for era in eras:
                if not era['format']:
                    add_comment(removed_zones, zone_name, 'FORMAT is empty')
                    valid = False
                    break

                if era['rules'] == '-' or ':' in era['rules']:
                    if '%' in era['format']:
                        add_comment(
                            removed_zones, zone_name,
                            "RULES is fixed but FORMAT contains '%'")
                        valid = False
                        break
                else:
                    if not ('%' in era['format'] or '/' in era['format']):
                        add_comment(
                            notable_zones, zone_name,
                            "RULES not fixed but FORMAT is missing "
                            + "'%' or '/'")

            if valid:
                results[zone_name] = eras

        self._print_comments_map(
            'Removed %s zones with invalid RULES and FORMAT combo',
            removed_zones,
        )
        self._print_comments_map(
            'Noted %s zones with notable RULES and FORMAT combo', notable_zones,
        )
        merge_comments(self.all_removed_zones, removed_zones)
        merge_comments(self.all_notable_zones, notable_zones)
        return results

    def _create_zones_with_rules_expansion(
        self, zones_map: ZonesMap,
    ) -> ZonesMap:
        """Expand and normalize the zone.rules field (RULES) and create
        zone.era_delta_seconds from zone.rules.

        The RULES field can hold the following:
            1) '-' no rules
            2) a string reference to a set of Rules
            3) a delta offset like "01:00" to be added to the STDOFF field
                (see America/Argentina/San_Luis, Europe/Istanbul for example).

        After this method, the 'zone.rules' contains 3 possible values:
            1) '-' no rules, or
            2) a string reference of the zone policy containing the rules, or
            3) ':' which indicates that 'era_delta_seconds' is defined.
        """
        results: ZonesMap = {}
        removed_zones: CommentsMap = {}
        notable_zones: CommentsMap = {}
        for name, eras in zones_map.items():
            valid = True
            for era in eras:
                rules_string = era['rules']
                if rules_string.find(':') >= 0:
                    if self.scope == 'basic':
                        valid = False
                        add_comment(
                            removed_zones, name,
                            f"unsupported fixed RULES offset '{rules_string}'")
                        break

                    era_delta_seconds = time_string_to_seconds(rules_string)
                    if era_delta_seconds == INVALID_SECONDS:
                        valid = False
                        add_comment(
                            removed_zones, name,
                            f"invalid RULES string '{rules_string}'")
                        break
                    if era_delta_seconds == 0:
                        valid = False
                        add_comment(
                            removed_zones, name,
                            f"unexpected 0:00 RULES string '{rules_string}'")
                        break
                    if era_delta_seconds not in (0, 3600):
                        add_comment(
                            notable_zones, name,
                            f"RULES delta offset '{rules_string}' "
                            "different from 1:00")

                    # Check that RULES delta is a multiple of 15-minutes
                    # (or whatever delta_granularity is set to).
                    era_delta_seconds_truncated = truncate_to_granularity(
                        era_delta_seconds, self.delta_granularity)
                    if era_delta_seconds != era_delta_seconds_truncated:
                        if self.strict:
                            valid = False
                            add_comment(
                                removed_zones, name,
                                f"RULES delta '{rules_string}' must be "
                                f"multiples of '{self.delta_granularity}' "
                                f"seconds")
                            break
                        else:
                            hm = seconds_to_hm_string(
                                era_delta_seconds_truncated)
                            add_comment(
                                notable_zones, name,
                                f"RULES delta offset '{rules_string}'"
                                f"truncated to '{hm}'")
                    else:
                        if era_delta_seconds % 60 != 0:
                            add_comment(
                                notable_zones, name,
                                f"RULES delta offset '{rules_string}' "
                                "not multiple of 1-min")

                    # Check that rules_delta fits inside 4-bits, because that's
                    # how it is stored in the Arduino zonedb files.
                    # TODO: Move this to artransformer.py
                    rules_delta_code = era_delta_seconds_truncated // 900
                    if rules_delta_code < -4 or rules_delta_code > 11:
                        valid = False
                        add_comment(
                            removed_zones, name,
                            f"RULES '{rules_string}' too large for 4-bits")
                        break

                    # Set the ZoneEra['rules'] to ':' to indicate that the RULES
                    # field is a DST offset.
                    era['rules'] = ':'
                    era['era_delta_seconds'] = era_delta_seconds
                    era['era_delta_seconds_truncated'] = \
                        era_delta_seconds_truncated
                else:
                    # If '-' or named policy, set to 0.
                    era['era_delta_seconds'] = 0
                    era['era_delta_seconds_truncated'] = 0
            if valid:
                results[name] = eras

        self._print_comments_map(
            'Removed %s zone infos with invalid RULES', removed_zones,
        )
        self._print_comments_map(
            'Noted %s zone infos with notable RULES', notable_zones,
        )
        merge_comments(self.all_removed_zones, removed_zones)
        merge_comments(self.all_notable_zones, notable_zones)
        return results

    def _remove_zones_with_non_monotonic_until(
        self, zones_map: ZonesMap,
    ) -> ZonesMap:
        """Remove Zone infos whose UNTIL fields are:
            1) not monotonically increasing, or
            2) does not end in year=MAX_UNTIL_YEAR
        """
        results: ZonesMap = {}
        removed_zones: CommentsMap = {}
        for name, eras in zones_map.items():
            valid = True
            prev_until = None
            for era in eras:
                # current_until
                c = (
                    era['until_year'],
                    era['until_month'] if era['until_month'] else 0,
                    era['until_day'] if era['until_day_string'] else 0,
                    era['until_seconds'] if era['until_seconds'] else 0
                )
                if prev_until:
                    if c <= prev_until:
                        valid = False
                        add_comment(
                            removed_zones, name,
                            'non increasing UNTIL: '
                            f'{c[0]:04}-{c[1]:02}-{c[2]:02} {c[3]}s'
                        )
                        break
                prev_until = c
            if valid and c[0] != MAX_UNTIL_YEAR:
                valid = False
                add_comment(
                    removed_zones, name,
                    'invalid final UNTIL: '
                    f'{c[0]:04}-{c[1]:02}-{c[2]:02} {c[3]}s'
                )

            if valid:
                results[name] = eras

        self._print_comments_map(
            'Removed %s zone infos with invalid UNTIL fields', removed_zones,
        )
        merge_comments(self.all_removed_zones, removed_zones)
        return results

    def _create_short_format_strings(self, zones_map: ZonesMap) -> ZonesMap:
        """Convert 'format' with '%s' placeholder to 'format_short' with just a
        '%' placeholder.
        """
        for name, eras in zones_map.items():
            for era in eras:
                era['format_short'] = era['format'].replace('%s', '%')
        return zones_map

    def _create_tiny_until_years(self, zones_map: ZonesMap) -> ZonesMap:
        for name, eras in zones_map.items():
            for era in eras:
                until_year = era['until_year']
                if until_year == MAX_UNTIL_YEAR:
                    continue
                if not is_year_tiny(until_year):
                    raise Exception(f"{name}: UNTIL {until_year} not tiny")
                until_year_tiny = until_year - EPOCH_YEAR_FOR_TINY
                era['until_year_tiny'] = until_year_tiny

        return zones_map

    # --------------------------------------------------------------------
    # Part 3: Transformations requiring both zones_map and policies_map.
    # --------------------------------------------------------------------

    def _remove_unused_policies(
        self, zones_map: ZonesMap, policies_map: PoliciesMap,
    ) -> PoliciesMap:
        results: PoliciesMap = {}
        removed_policies: CommentsMap = {}

        policies_to_zones = _create_policies_to_zones(zones_map, policies_map)
        for policy_name, rules in policies_map.items():
            if policy_name in policies_to_zones:
                results[policy_name] = rules
            else:
                add_comment(removed_policies, policy_name, 'unused')

        self._print_comments_map(
            'Removed %s zone policies unused', removed_policies
        )
        merge_comments(self.all_removed_policies, removed_policies)
        return results

    def _mark_rules_used_by_zones(
        self, zones_map: ZonesMap, policies_map: PoliciesMap,
    ) -> Tuple[ZonesMap, PoliciesMap]:
        """Mark all rules which are required by various zones. There are 2 ways
        that a rule can be used by a zone era:

        1) The rule's from_year or to_year are >= (self.start_year - 1), or
        2) The rule is the most recent transition that happened before
        self.start_year.

        The viewing_months is always 14, so init_for_year() will always be
        called with 2000 or higher, so we just need 1999 data to get the most
        recent prior Transition before Jan 1, 2000.
        """
        for zone_name, eras in zones_map.items():
            begin_year = self.start_year - 1
            for era in eras:
                policy_name = era['rules']
                if policy_name in ['-', ':']:
                    continue

                rules = policies_map.get(policy_name)
                if not rules:
                    raise Exception(
                        f"Zone '{zone_name}': Could not find policy "
                        f"'{policy_name}'")

                # Make all Rules which overlap with the current Zone Era.
                # Some Zone Era have an until_month, until_day and until_time
                # components. To be conservative, we need to expand the
                # until_year to the following year, so the effective zone era
                # interval becomes [begin_year, until_year+1).
                until_year = min(era['until_year'], self.until_year)
                matching_rules = find_matching_rules(
                    rules, begin_year, until_year + 1)
                for rule in matching_rules:
                    rule['used'] = True

                # Find latest Rules just prior to the begin_year.
                # Result: It looks like all of these prior rules are
                # already picked up by previous calls to find_matching_rules().
                prior_rules = find_latest_prior_rules(rules, begin_year)
                for rule in prior_rules:
                    rule['used'] = True

                # Find earliest Rules subsequent to the until_year mark.
                # Result: It looks like all of these subsequent rules are
                # already picked up by previous calls to find_matching_rules().
                subsequent_rules = find_earliest_subsequent_rules(
                    rules, until_year + 1)
                for rule in subsequent_rules:
                    rule['used'] = True

                # Set the begin year of the next ZoneEra
                begin_year = era['until_year']

        return (zones_map, policies_map)

    # --------------------------------------------------------------------
    # Part 4: Transform the policies_map
    # --------------------------------------------------------------------

    def _remove_rules_unused(self, policies_map: PoliciesMap) -> PoliciesMap:
        """Remove RULE entries which have not been marked as used by the
        _mark_rules_used_by_zones() method.
        """
        results: PoliciesMap = {}
        removed_rule_count = 0
        removed_policies: CommentsMap = {}
        for name, rules in policies_map.items():
            used_rules = []
            for rule in rules:
                if rule.get('used'):
                    used_rules.append(rule)
                    # Set the 'used' to None to remove from JSON output.
                    del rule['used']
                else:
                    removed_rule_count += 1
            if used_rules:
                results[name] = used_rules
            else:
                add_comment(removed_policies, name, 'unused')

        logging.info(
            'Removed %s rule policies (with %s rules) not used',
            len(removed_policies),
            removed_rule_count
        )
        merge_comments(self.all_removed_policies, removed_policies)
        return results

    def _remove_rules_out_of_bounds(
        self,
        policies_map: PoliciesMap,
    ) -> PoliciesMap:
        """Remove policies which have FROM and TO fields do not fit in an int8_t
        with a base EPOCH_YEAR_FOR_TINY (2100).
        """
        results: PoliciesMap = {}
        removed_policies: CommentsMap = {}
        for name, rules in policies_map.items():
            valid = True
            for rule in rules:
                from_year = rule['from_year']
                to_year = rule['to_year']
                if not is_year_tiny(from_year):
                    valid = False
                    add_comment(
                        removed_policies, name,
                        f"from_year ({from_year}) exceeds int8_t")
                    break
                if not is_year_tiny(to_year):
                    valid = False
                    add_comment(
                        removed_policies, name,
                        f"to_year ({to_year}) exceeds int8_t")
                    break
            if valid:
                results[name] = rules

        self._print_comments_map(
            'Removed %s policies with FROM or TO out of bounds',
            removed_policies,
        )
        merge_comments(self.all_removed_policies, removed_policies)
        return results

    def _remove_rules_multiple_transitions_in_month(
        self, policies_map: PoliciesMap,
    ) -> PoliciesMap:
        """Some Zone policies have Rules which specify multiple DST transitions
        within in the same month:
            * Egypt (Found '2' transitions in year/month '2010-09')
            * Palestine (Found '2' transitions in year/month '2011-08')
            * Spain (Found '2' transitions in year/month '1938-04')
            * Tunisia (Found '2' transitions in year/month '1943-04')
        """
        CountsMap = Dict[Tuple[str, int, int], int]

        # First pass: collect number of transitions for each (year, month) pair.
        counts: CountsMap = {}
        for name, rules in policies_map.items():
            for rule in rules:
                from_year = rule['from_year']
                to_year = rule['to_year']
                month = rule['in_month']
                for year in range(from_year, to_year + 1):
                    key = (name, year, month)
                    count = counts.get(key)
                    count = count + 1 if count else 1
                    counts[key] = count

        # Second pass: Collect rule policies which have multiple transitions
        # in one month.
        removals: Dict[str, Tuple[int, int, int]] = {}
        for key, count in counts.items():
            if count > 1:
                policy_name = key[0]
                year = key[1]
                month = key[2]
                removals[policy_name] = (count, year, month)

        # Third pass: Remove rule policies with multiple counts.
        results: PoliciesMap = {}
        removed_policies: CommentsMap = {}
        for name, rules in policies_map.items():
            removal = removals.get(name)
            if removal:
                add_comment(
                    removed_policies,
                    name,
                    f"Found {removal[0]} transitions in year/month "
                    f"'{removal[1]:04}-{removal[2]:02}'"
                )
            else:
                results[name] = rules

        self._print_comments_map(
            'Removed %s policies with multiple transitions in 1 month',
            removed_policies,
        )
        merge_comments(self.all_removed_policies, removed_policies)
        return results

    def _create_rules_with_expanded_at_time(
        self,
        policies_map: PoliciesMap,
        policies_to_zones: PoliciesToZones,
    ) -> PoliciesMap:
        """ Create 'at_seconds' parameter from rule['at_time'].
        """
        results: PoliciesMap = {}
        removed_policies: CommentsMap = {}
        notable_policies: CommentsMap = {}
        for policy_name, rules in policies_map.items():
            valid = True
            for rule in rules:
                at_time = rule['at_time']
                at_seconds = time_string_to_seconds(at_time)
                if at_seconds == INVALID_SECONDS:
                    valid = False
                    add_comment(
                        removed_policies, policy_name,
                        f"invalid AT time '{at_time}'" % at_time)
                    break
                if at_seconds < 0:
                    valid = False
                    add_comment(
                        removed_policies, policy_name,
                        f"negative AT time '{at_time}'" % at_time)
                    break

                at_seconds_truncated = truncate_to_granularity(
                    at_seconds, self.until_at_granularity)
                if at_seconds != at_seconds_truncated:
                    if self.strict:
                        valid = False
                        add_comment(
                            removed_policies, policy_name,
                            f"AT time '{at_time}' must be multiples of "
                            f"'{self.until_at_granularity}' seconds")
                        break
                    else:
                        hm = seconds_to_hm_string(at_seconds_truncated)
                        add_comment(
                            notable_policies, policy_name,
                            f"AT time '{at_time}' truncated to '{hm}'")
                else:
                    # Warning if AT has finer granularity than 1-minute
                    if at_seconds % 60 != 0:
                        add_comment(
                            notable_policies, policy_name,
                            f"AT time '{at_time}' not multiple of 1-min")

                rule['at_seconds'] = at_seconds
                rule['at_seconds_truncated'] = at_seconds_truncated
            if valid:
                results[policy_name] = rules

        self._print_comments_map(
            'Removed %s policies with invalid AT field', removed_policies,
        )
        self._print_comments_map(
            'Noted %s policies with notable AT field', notable_policies,
        )
        merge_comments(self.all_removed_policies, removed_policies)
        merge_comments(self.all_notable_policies, notable_policies)
        return results

    def _remove_rules_invalid_at_time_suffix(
        self, policies_map: PoliciesMap,
    ) -> PoliciesMap:
        """Remove rules whose at_time contains an unsupported suffix. Current
        supported suffix is 'w', 's' and 'u'. The 'g' and 'z' are identifical
        to 'u' and they do not currently appear in any TZ file, so let's catch
        them because it could indicate a bug somewhere in our parser or
        somewhere else.
        """
        supported_suffices = ['w', 's', 'u']
        results: PoliciesMap = {}
        removed_policies: CommentsMap = {}
        for name, rules in policies_map.items():
            valid = True
            for rule in rules:
                suffix = rule['at_time_suffix']
                suffix = suffix if suffix else 'w'
                rule['at_time_suffix'] = suffix
                if suffix not in supported_suffices:
                    valid = False
                    add_comment(
                        removed_policies, name,
                        f"unsupported AT time suffix '{suffix}'")
                    break
            if valid:
                results[name] = rules

        self._print_comments_map(
            'Removed %s policies with unsupported AT suffix', removed_policies,
        )
        merge_comments(self.all_removed_policies, removed_policies)
        return results

    def _create_rules_with_expanded_delta_offset(
        self,
        policies_map: PoliciesMap,
    ) -> PoliciesMap:
        """ Create 'delta_seconds' and 'delta_seconds_truncated' from
        rule['delta_offset'].
        """
        results = {}
        removed_policies: CommentsMap = {}
        notable_policies: CommentsMap = {}
        for name, rules in policies_map.items():
            valid = True
            for rule in rules:
                delta_offset = rule['delta_offset']
                delta_seconds = time_string_to_seconds(delta_offset)
                if delta_seconds == INVALID_SECONDS:
                    valid = False
                    add_comment(
                        removed_policies, name,
                        f"invalid SAVE '{delta_offset}'")
                    break
                if delta_seconds not in (0, 3600):
                    add_comment(
                        notable_policies, name,
                        f"SAVE '{delta_offset}' different from 1:00")

                # Truncate to requested granularity.
                delta_seconds_truncated = truncate_to_granularity(
                    delta_seconds, self.delta_granularity)
                if delta_seconds != delta_seconds_truncated:
                    if self.strict:
                        valid = False
                        add_comment(
                            removed_policies, name,
                            f"SAVE '{delta_offset}' must be "
                            f"a multiple of '{self.delta_granularity}' "
                            f"seconds")
                        break
                    else:
                        add_comment(
                            notable_policies, name,
                            f"SAVE '{delta_offset}' truncated to"
                            f"a multiple of '{self.delta_granularity}' "
                            f"seconds")
                else:
                    if delta_seconds % 60 != 0:
                        add_comment(
                            notable_policies, name,
                            f"SAVE '{delta_offset}' not multiple of 1-min")

                # Check that delta seconds can fit in a 4-bit timeCode field
                # with 15-minute granularity, defined as (timeCode =
                # delta_seconds / 900s + 1h) which encodes -1:00 as 0 and 3:45
                # as 15.
                delta_code = delta_seconds_truncated // 900
                if delta_code < -4 or delta_code > 11:
                    valid = False
                    add_comment(
                        removed_policies, name,
                        f"SAVE delta_offset '{delta_offset}' "
                        "too large for 4-bits")
                    break

                rule['delta_seconds'] = delta_seconds
                rule['delta_seconds_truncated'] = delta_seconds_truncated
            if valid:
                results[name] = rules

        self._print_comments_map(
            'Removed %s policies with invalid SAVE field', removed_policies,
        )
        self._print_comments_map(
            'Noted %s policies with notable SAVE field', notable_policies,
        )
        merge_comments(self.all_removed_policies, removed_policies)
        merge_comments(self.all_notable_policies, notable_policies)
        return results

    def _create_rules_with_on_day_expansion(
        self, policies_map: PoliciesMap,
    ) -> PoliciesMap:
        """Create rule['on_day_of_week'] and rule['on_day_of_month'] from
        rule['on_day']. The on_day_of_month will be negative if "<=" is used.
        """
        results: PoliciesMap = {}
        removed_policies: CommentsMap = {}
        for name, rules in policies_map.items():
            valid = True
            for rule in rules:
                on_day = rule['on_day']
                (on_day_of_week, on_day_of_month) = _parse_on_day_string(on_day)

                if (on_day_of_week, on_day_of_month) == (0, 0):
                    valid = False
                    add_comment(
                        removed_policies, name,
                        f"invalid on_day '{on_day}'")
                    break

                # *ZoneProcessor.h classes currently do not support
                # "dayOfWeek<=6" or "dayOfWeek>=26" if the shift causes the year
                # to change.
                if on_day_of_week != 0 and on_day_of_month != 0:
                    if (-7 <= on_day_of_month
                            and on_day_of_month < -1
                            and rule['in_month'] == 1):
                        valid = False
                        add_comment(
                            removed_policies, name,
                            f"cannot shift '{on_day}' from Jan to prev year")
                        break
                    if 26 <= on_day_of_month and rule['in_month'] == 12:
                        valid = False
                        add_comment(
                            removed_policies, name,
                            f"cannot shift '{on_day}' from Dec to next year")
                        break

                rule['on_day_of_week'] = on_day_of_week
                rule['on_day_of_month'] = on_day_of_month
            if valid:
                results[name] = rules

        self._print_comments_map(
            'Removed %s policies with invalid ON field', removed_policies,
        )
        merge_comments(self.all_removed_policies, removed_policies)
        return results

    def _create_rules_with_anchor_transition(
        self, policies_map: PoliciesMap,
    ) -> PoliciesMap:
        """Create a synthetic "anchor" transition with SAVE == 0 with a FROM
        year of MIN_YEAR (i.e. -Infinity) to guarantee that at least one Rule
        matches for any input `year`. According to
        https://data.iana.org/time-zones/tz-how-to.html, the initial LETTER
        should be deduced from the first RULE whose SAVE == 0.
        """
        for name, rules in policies_map.items():
            if len(rules) == 1:
                _convert_to_anchor(rules[0])
            else:
                anchor_rule = _get_anchor_rule(rules)
                rules.insert(0, anchor_rule)
        return policies_map

    def _normalize_letters(self, policies_map: PoliciesMap) -> PoliciesMap:
        """Convert '-' into ''"""
        for name, rules in policies_map.items():
            for rule in rules:
                if rule['letter'] == '-':
                    rule['letter'] = ''
        return policies_map

    def _remove_rules_with_border_transitions(
        self, policies_map: PoliciesMap,
    ) -> PoliciesMap:
        """Remove rules where the transition occurs on the first day of the
        year (Jan 1). That situation is not supported by BasicZoneProcessor. On
        the other hand, a transition at the end of the year (Dec 31) is
        supported by BasicZoneProcessor.
        """
        results: PoliciesMap = {}
        removed_policies: CommentsMap = {}
        for name, rules in policies_map.items():
            valid = True
            for rule in rules:
                from_year = rule['from_year']
                to_year = rule['to_year']
                month = rule['in_month']
                on_day_of_month = rule['on_day_of_month']
                if from_year > MIN_YEAR and to_year > MIN_YEAR:
                    if month == 1 and on_day_of_month == 1:
                        valid = False
                        add_comment(
                            removed_policies, name,
                            "Transition on Jan 1 not supported "
                            f"({from_year:04}-{month:02}-{on_day_of_month:02})"
                        )
                        break
            if valid:
                results[name] = rules

        self._print_comments_map(
            'Removed %s policies with border Transitions', removed_policies,
        )
        merge_comments(self.all_removed_policies, removed_policies)
        return results

    def _remove_rules_long_dst_letter(
        self,
        policies_map: PoliciesMap,
    ) -> PoliciesMap:
        """Return a new map which filters out rules with long DST letter.
        """
        results: PoliciesMap = {}
        removed_policies: CommentsMap = {}
        for name, rules in policies_map.items():
            valid = True
            for rule in rules:
                letter = rule['letter']
                if len(letter) > 1:
                    valid = False
                    add_comment(
                        removed_policies, name,
                        f"LETTER '{letter}' too long")
                    break
            if valid:
                results[name] = rules

        self._print_comments_map(
            'Removed %s policies with long DST letter', removed_policies,
        )
        merge_comments(self.all_removed_policies, removed_policies)
        return results

    # TODO: This does not quite work because there are rules whose
    # [from_year,start_year] straddles the self.start_year. The from_year
    # needs to be extended back to -Infinity.
    def _create_tiny_from_to_years(
        self, policies_map: PoliciesMap
    ) -> PoliciesMap:
        for name, rules in policies_map.items():
            for rule in rules:
                from_year = rule['from_year']
                if from_year != MIN_YEAR and from_year != MAX_TO_YEAR:
                    rule['from_year_tiny'] = from_year - EPOCH_YEAR_FOR_TINY

                to_year = rule['to_year']
                if to_year != MIN_YEAR and to_year != MAX_TO_YEAR:
                    rule['to_year_tiny'] = to_year - EPOCH_YEAR_FOR_TINY

        return policies_map

    # --------------------------------------------------------------------
    # Part 5: Remove unused zones and links.
    # --------------------------------------------------------------------

    def _remove_zones_without_rules(
        self, zones_map: ZonesMap, policies_map: PoliciesMap
    ) -> ZonesMap:
        """Remove zone eras whose RULES field contains a reference to
        a set of Rules, which cannot be found.
        """
        results: ZonesMap = {}
        removed_zones: CommentsMap = {}
        for name, eras in zones_map.items():
            valid = True
            for era in eras:
                policy_name = era['rules']
                if (policy_name not in ['-', ':']
                        and policy_name not in policies_map):
                    valid = False
                    add_comment(
                        removed_zones, name,
                        f"policy '{policy_name}' not found")
                    break
            if valid:
                results[name] = eras

        self._print_comments_map(
            'Removed %s zone infos without rules',
            removed_zones,
        )
        merge_comments(self.all_removed_zones, removed_zones)
        return results

    def _remove_links_to_missing_zones(
        self,
        links_map: LinksMap,
        zones_map: ZonesMap
    ) -> LinksMap:
        results = {}
        removed_links: CommentsMap = {}
        for link_name, zone_name in links_map.items():
            if zones_map.get(zone_name):
                results[link_name] = zone_name
            else:
                add_comment(
                    removed_links, link_name,
                    f'Target Zone "{zone_name}" missing')

        self._print_comments_map(
            'Removed %s links with missing zones',
            removed_links,
        )
        merge_comments(self.all_removed_links, removed_links)
        return results

    # --------------------------------------------------------------------
    # Part 6: Detect zones and links whose normalized names conflict.
    # --------------------------------------------------------------------

    def _detect_zones_and_links_with_similar_names(
        self,
        zones_map: ZonesMap,
        links_map: LinksMap,
    ) -> Tuple[ZonesMap, LinksMap]:
        """If there were 2 zones names like "Etc/GMT-0" and "Etc/GMT_0", both
        would normalize to "Etc/GMT_0", producing a symbol "kZoneEtc_GMT_0. Make
        this a fatal error so that we can fix it instead of removing one of the
        zones or links and continuing.
        """
        normalized_names: Dict[str, str] = {}  # normalized_name, name
        result_zones: ZonesMap = {}
        result_links: LinksMap = {}

        # Check for duplicate zone names.
        for zone_name, zone in zones_map.items():
            nname = normalize_name(zone_name)
            if normalized_names.get(nname):
                raise Exception(
                    f"Duplicate normalized zone name: {zone_name} -> {nname}"
                )
            normalized_names[nname] = zone_name
            result_zones[zone_name] = zone

        # Check for duplicate links.
        for link_name, zone_name in links_map.items():
            nname = normalize_name(link_name)
            if normalized_names.get(nname):
                raise Exception(
                    f"Duplicate normalized link name: {link_name} -> {nname}"
                )
            normalized_names[nname] = link_name
            result_links[link_name] = zone_name

        return result_zones, result_links

    # --------------------------------------------------------------------
    # Part 8: Add additional results
    # --------------------------------------------------------------------

    def _generate_zone_ids(self, zones_map: ZonesMap) -> Dict[str, int]:
        """Generate {zoneName -> zoneId} map of zones. Must not be 0x00 because
        0x00 is used as an error return code in certain methods of the C++ code.
        """
        ids: Dict[str, int] = {
            name: hash_name(name) for name in zones_map.keys()
        }
        for k, v in ids.items():
            if v == 0:
                raise Exception(f"zoneId of {k} is 0x{v:x}")
        return OrderedDict(sorted(ids.items()))

    def _generate_link_ids(self, links_map: LinksMap) -> Dict[str, int]:
        """Generate {linkName -> linkId} map of links. Must not be 0x00 because
        0x00 is used as an error return code in certain methods of the C++ code.
        """
        ids: Dict[str, int] = {
            name: hash_name(name) for name in links_map.keys()
        }
        for k, v in ids.items():
            if v == 0:
                raise Exception(f"zoneId of {k} is {v}")
        return OrderedDict(sorted(ids.items()))


# ISO-8601 specifies Monday=1, Sunday=7
WEEK_TO_WEEK_INDEX = {
    'Mon': 1,
    'Tue': 2,
    'Wed': 3,
    'Thu': 4,
    'Fri': 5,
    'Sat': 6,
    'Sun': 7,
}


def _parse_on_day_string(on_string: str) -> Tuple[int, int]:
    """Parse things like "Sun>=1", "lastSun", "20", "Fri<=2".
    Returns (on_day_of_week, on_day_of_month) where
        (0, dayOfMonth) = exact match on dayOfMonth
        (dayOfWeek, dayOfMonth) = matches dayOfWeek>=dayOfMonth
        (dayOfWeek, -dayOfMonth) = matches dayOfWeek<=dayOfMonth
        (dayOfWeek, 0) = matches lastDayOfWeek
        (0, 0) = syntax error

    where
        dayOfWeek is represented by a number (Mon=1, ..., Sun=7),
        dayOfMonth is 0, 1-31 (if >=), or (-1)-(-31) (if <=).

    """
    if on_string.isdigit():
        return (0, int(on_string))

    if on_string[:4] == 'last':
        dayOfWeek = on_string[4:]
        if dayOfWeek not in WEEK_TO_WEEK_INDEX:
            return (0, 0)
        return (WEEK_TO_WEEK_INDEX[dayOfWeek], 0)

    greater_than_equal_index = on_string.find('>=')
    if greater_than_equal_index >= 0:
        dayOfWeek = on_string[:greater_than_equal_index]
        dayOfMonth = on_string[greater_than_equal_index + 2:]
        if dayOfWeek not in WEEK_TO_WEEK_INDEX:
            return (0, 0)
        return (WEEK_TO_WEEK_INDEX[dayOfWeek], int(dayOfMonth))

    less_than_equal_index = on_string.find('<=')
    if less_than_equal_index >= 0:
        dayOfWeek = on_string[:less_than_equal_index]
        dayOfMonth = on_string[less_than_equal_index + 2:]
        if dayOfWeek not in WEEK_TO_WEEK_INDEX:
            return (0, 0)
        return (WEEK_TO_WEEK_INDEX[dayOfWeek], -int(dayOfMonth))

    return (0, 0)


def time_string_to_seconds(time_string: str) -> int:
    """Converts the '[-]hh:mm:ss' string into +/- total seconds from 00:00.
    Returns INVALID_SECONDS if there is a parsing error.
    """
    sign = 1
    if time_string[0] == '-':
        sign = -1
        time_string = time_string[1:]

    try:
        elems = time_string.split(':')
        if len(elems) == 0:
            return INVALID_SECONDS
        hour = int(elems[0])
        minute = int(elems[1]) if len(elems) > 1 else 0
        second = int(elems[2]) if len(elems) > 2 else 0
        if len(elems) > 3:
            return INVALID_SECONDS
    except Exception:
        return INVALID_SECONDS

    # A number of countries use 24:00, and Japan uses 25:00(!).
    # Rule  Japan   1948    1951  -     Sep Sat>=8  25:00   0   	S
    if hour > 25:
        return INVALID_SECONDS
    if minute > 59:
        return INVALID_SECONDS
    if second > 59:
        return INVALID_SECONDS
    return sign * ((hour * 60 + minute) * 60 + second)


def find_matching_rules(
    rules: List[ZoneRuleRaw],
    era_from: int,
    era_until: int,
) -> List[ZoneRuleRaw]:
    """Return the rules which overlap with the Zone Era interval [eraFrom,
    eraUntil). The Rule interval is [ruleFrom, ruleTo + 1). Overlap happens
    (ruleFrom < eraUntil) && (eraFrom < ruleTo+1). The expression (eraFrom <
    ruleTo+1) can be written as (eraFrom <= ruleTo) since these values are
    integers.
    """
    matches = []
    for rule in rules:
        if rule['from_year'] < era_until and era_from <= rule['to_year']:
            matches.append(rule)
    return matches


def find_latest_prior_rules(
    rules: List[ZoneRuleRaw],
    year: int,
) -> List[ZoneRuleRaw]:
    """Find the most recent prior rules before the given year. The RULE.at_time
    field can be a conditional expression such as 'lastSun' or 'Mon>=8', so it's
    easiest to just compare the (year, month) only. Also, instead of looking for
    the single Rule that is the most recent, we grab all Rules that fit into the
    month bucket. There are 2 reasons:

    1) A handful of Zone Policies have multiple Rules in the same month. From
    _remove_rules_multiple_transitions_in_month():

        * Egypt (Found 2 transitions in year/month '2010-09')
        * Palestine (Found 2 transitions in year/month '2011-08')
        * Spain (Found 2 transitions in year/month '1938-04')
        * Tunisia (Found 2 transitions in year/month '1943-04')

    2) A handful of Zone Policies have Rules which specify transitions in the
    last 2 days of the year. From _remove_rules_with_border_transitions(), we
    find:
        * Arg (Transition in late year (2007-12-30))
        * Dhaka (Transition in late year (2009-12-31))
        * Ghana (Transition in late year (1920-12-31))

    By grabbing all Rules in the last month, we avoid the risk of accidentally
    leaving some Rules out.
    """
    candidates = []
    candidate_date = (0, 0)  # sentinel date earlier than all real Rules
    for rule in rules:
        rule_year = rule['to_year']
        rule_month = rule['in_month']
        if rule_year < year:
            rule_date = (rule_year, rule_month)
            if rule_date > candidate_date:
                candidate_date = rule_date
                candidates = [rule]
            elif rule_date == candidate_date:
                candidates.append(rule)
    return candidates


def find_earliest_subsequent_rules(
    rules: List[ZoneRuleRaw],
    year: int,
) -> List[ZoneRuleRaw]:
    """Find the ealiest subsequent rules on or after the given year. This deals
    with the case where the following (admittedly unlikely) set of conditions
    happen:

    1) an epochSeconds is converted to a UTC dateTime,
    2) we look for Transitions in the current UTC year, but the actual
    year in the local timezone is actually in the following year,
    3) there exists a Rule that specifies a Transition in the first day of the
    new year, which does not get picked up without this scan.

    It's likely that any such Rule would get picked up by the normal
    find_matching_rules() of a Zone Era that stretched to MAX_TO_YEAR, but I'm
    not 100% sure that that's true, and there might be a weird edge case. This
    method helps prevent that edge case.

    Similar to find_latest_prior_rules(), we match all Rules in a given month,
    instead of looking single earliest Rule.
    """
    candidates = []
    # sentinel date later than all real Rules
    candidate_date = (MAX_TO_YEAR, 13)
    for rule in rules:
        rule_year = rule['to_year']
        rule_month = rule['in_month']
        if rule_year >= year:
            rule_date = (rule_year, rule_month)
            if rule_date < candidate_date:
                candidate_date = rule_date
                candidates = [rule]
            elif rule_date == candidate_date:
                candidates.append(rule)
    return candidates


def is_year_tiny(year: int) -> bool:
    """Determine if year fits in an int8_t field."""
    year_tiny = year - EPOCH_YEAR_FOR_TINY
    return (
        year == INVALID_YEAR
        or year == MIN_YEAR
        or year == MAX_TO_YEAR
        or year == MAX_UNTIL_YEAR
        or (MIN_YEAR_TINY < year_tiny and year_tiny < MAX_TO_YEAR_TINY)
    )


def calc_day_of_month(
    year: int,
    month: int,
    on_day_of_week: int,
    on_day_of_month: int,
) -> Tuple[int, int]:
    """Return the actual (month, day) of expressions such as
    (on_day_of_week >= on_day_of_month), (on_day_of_week <= on_day_of_month), or
    (lastMon) See BasicZoneProcessor::calcStartDayOfMonth(). Shifts into
    previous or next month can occur.

    Return (13, xx) if a shift to the next year occurs
    Return (0, xx) if a shift to the previous year occurs
    """
    if on_day_of_week == 0:
        return (month, on_day_of_month)

    if on_day_of_month >= 0:
        days_in_month = _days_in_month(year, month)

        # Handle lastXxx by transforming it into (Xxx >= (daysInMonth - 6))
        if on_day_of_month == 0:
            on_day_of_month = days_in_month - 6

        limit_date = datetime.date(year, month, on_day_of_month)
        day_of_week_shift = (on_day_of_week - limit_date.isoweekday() + 7) % 7
        day = on_day_of_month + day_of_week_shift
        if day > days_in_month:
            day -= days_in_month
            month += 1
        return (month, day)
    else:
        on_day_of_month = -on_day_of_month
        limit_date = datetime.date(year, month, on_day_of_month)
        day_of_week_shift = (limit_date.isoweekday() - on_day_of_week + 7) % 7
        day = on_day_of_month - day_of_week_shift
        if day < 1:
            month -= 1
            days_in_prev_month = _days_in_month(year, month)
            day += days_in_prev_month
        return (month, day)


def _days_in_month(year: int, month: int) -> int:
    """Return the number of days in the given (year, month). The
    month is usually 1-12, but can be 0 to indicate December of the previous
    year, and 13 to indicate Jan of the following year.
    """
    DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    is_leap = (year % 4 == 0) and ((year % 100 != 0) or (year % 400) == 0)
    days = DAYS_IN_MONTH[(month - 1) % 12]
    if month == 2:
        days += is_leap
    return days


def seconds_to_hms(seconds: int) -> Tuple[int, int, int]:
    """Convert seconds to (h,m,s). Works only for positive seconds.
    """
    s = seconds % 60
    minutes = seconds // 60
    m = minutes % 60
    h = minutes // 60
    return (h, m, s)


def seconds_to_hm_string(seconds: int) -> str:
    """Convert seconds to hh:mm. Assumes that seconds is multiples of 60.
    """
    if seconds < 0:
        sign = '-'
        seconds = -seconds
    else:
        sign = ''
    minutes = seconds // 60
    m = minutes % 60
    h = minutes // 60
    return f'{sign}{h:02}:{m:02}'


def hms_to_seconds(h: int, m: int, s: int) -> int:
    """Convert h:m:s to seconds.
    """
    return (h * 60 + m) * 60 + s


def div_to_zero(a: int, b: int) -> int:
    """Integer division (a/b) that truncates towards 0, instead of -infinity as
    is default for Python. Assumes b is positive, but a can be negative or
    positive.
    """
    return a // b if a >= 0 else (a - 1) // b + 1


def truncate_to_granularity(a: int, b: int) -> int:
    """Truncate a to the granularity of b.
    """
    return b * div_to_zero(a, b)


def add_string(strings: 'OrderedDict[str, int]', name: str) -> int:
    """Add the 'name' to the strings (must be an OrderedDict), and return its
    index into the array of strings. If the 'name' already exists, then return
    the previous index. Otherwise, create a new index, and return that.
    """
    if not isinstance(strings, OrderedDict):
        raise Exception('strings must be an OrderedDict')
    index = strings.get(name)
    if index is None:
        index = len(strings)
        strings[name] = index
    return index  # index will never be None


def _create_policies_to_zones(
    zones_map: ZonesMap,
    policies_map: PoliciesMap,
) -> PoliciesToZones:
    """Normally Zones point to Rules. This method causes the reverse to happen,
    making Rules know about Zones, by creating a map of {policy_name ->
    zone_full_name[]}. This allows us to determine which zones that may be
    affected by a change in a particular Rule. Must be called after
    _create_zones_with_rules_expansion() to normalize the RULES column
    (zone.rules).
    """
    policies_to_zones: PoliciesToZones = {}
    for full_name, eras in zones_map.items():
        for era in eras:
            policy_name = era['rules']
            if policy_name not in ['-', ':']:
                zones = policies_to_zones.get(policy_name)
                if not zones:
                    zones = []
                    policies_to_zones[policy_name] = zones
                zones.append(full_name)
    return policies_to_zones


def normalize_name(name: str) -> str:
    """Replace hyphen (-) and slash (/) with underscore (_) to generate valid
    C++ and Python symbols.
    """
    name = name.replace('+', '_PLUS_')
    return re.sub('[^a-zA-Z0-9_]', '_', name)


def normalize_raw(raw_line: str) -> str:
    """Replace hard tabs with 4 spaces.
    """
    return raw_line.replace('\t', '    ')


def hash_name(name: str) -> int:
    """Return the hash of the zone name. Implement the djb2 algorithm:
    https://stackoverflow.com/questions/7666509 and
    http://www.cse.yorku.ca/~oz/hash.html
    """
    U32_MOD = 2**32
    hash = 5381
    for c in name:
        hash = (33 * hash + ord(c)) % U32_MOD
    return hash


def _detect_hash_collisions(zones_map: ZonesMap, links_map: LinksMap) -> None:
    """Detect a hash collision of a zone name or a link name and throw an
    exception. With only about ~400 zone names and ~200 link names, the
    chances of a collision using a 32-bit hash is extremely low. However, if
    it ever happens, it is a severe error because we must guarantee that
    each zone name has a unique and stable hash for the life of this
    library.

    If this exception ever happens, we must create another hash for the
    colliding zone name, and keep the second hash unique and stable as well.
    A possible solution is to keep an internal list of colliding hashes
    (which ought to be few), and use a second hash function on the original
    zone name or link name to generate the new hash, and then use the the
    2nd hash for the 2nd name, while keeping the 1st hash for the original
    name. Because the hash of the 1st name must be remain unchanged.
    """
    hashes: Dict[int, str] = {}

    # Check zone names
    for name, _ in zones_map.items():
        h = hash_name(name)
        colliding_name = hashes.get(h)
        if colliding_name:
            raise Exception(
                "Hash collision: "
                f"Zone {name} with existing {colliding_name}"
            )
        hashes[h] = name

    # Check link names
    for name, _ in links_map.items():
        h = hash_name(name)
        colliding_name = hashes.get(h)
        if colliding_name:
            raise Exception(
                "Hash collision: "
                f"Link {name} with existing {colliding_name}"
            )
        hashes[h] = name

    logging.info('Detected no hash collisions')


def _detect_links_to_links(links_map: LinksMap) -> None:
    """Check for links to links. TZDB 2022f seems to be adding some ground work
    to use that feature in the future. AceTime does not support links-to-links
    currently so let's just throw an exception to notify the human operator.

    I think it would be relatively straightforward to support it by recursively
    resolving the link-to-link until a zone was found. The algorithm needs to
    detect any cycles in the TZDB files. In theory, they should not exist, but
    it would be prudent to check for cycles to avoid an infinite loop.
    """
    for link_name, link in links_map.items():
        target_name = links_map.get(link_name)
        if target_name in links_map:
            raise Exception(
                f"Unsupported Link to Link: {link_name} -> {target_name}"
            )
    logging.info('Detected no links-to-links')


def _detect_tzdb_years(
    zones_map: ZonesMap, policies_map: PoliciesMap,
) -> Tuple[int, int]:
    """Scan the Zone.UNTIL and RULE.FROM fields and determine the min and max
    years.
    """
    min_year = MAX_TO_YEAR
    max_year = MIN_YEAR
    for zone_name, eras in zones_map.items():
        for era in eras:
            era_year = era['until_year']
            if era_year < min_year:
                min_year = era_year
            if era_year != MAX_UNTIL_YEAR and era_year > max_year:
                max_year = era_year

    for name, rules in policies_map.items():
        for rule in rules:
            if rule.get('anchor', False):
                continue
            from_year = rule['from_year']
            if from_year < min_year:
                min_year = from_year
            if from_year != MAX_TO_YEAR and from_year > max_year:
                max_year = from_year

    return min_year, max_year


def _get_anchor_rule(rules: List[ZoneRuleRaw]) -> ZoneRuleRaw:
    """Return the anchor rule that will act as the earliest rule with SAVE
    == 0.
    """
    AnchorInfo = TypedDict('AnchorInfo', {
        'earliestDate': Tuple[int, int, int],
        'rule': Optional[ZoneRuleRaw],
    })

    # Find the earliest rule with a DSTOFF of 0. The `rules` array will
    # never be empty, but the [start_year, until_year) cutoff may eliminate
    # too many rules which may result in no rule with DSTOFF of 0. In
    # practice, I haven't seen this happen, so let's just throw an exception
    # if that is the case. It would take extra logic to fix this.
    anchor_info: AnchorInfo = {
        'earliestDate': (MAX_UNTIL_YEAR, 12, 31),
        'rule': None,
    }
    for rule in rules:
        from_year = rule['from_year']
        in_month = rule['in_month']
        on_day_of_week = rule['on_day_of_week']
        on_day_of_month = rule['on_day_of_month']
        month, day = calc_day_of_month(
            from_year, in_month, on_day_of_week, on_day_of_month)
        rule_date = (from_year, month, day)

        if (rule['delta_seconds'] == 0
                and rule_date < anchor_info['earliestDate']):
            anchor_info['earliestDate'] = rule_date
            anchor_info['rule'] = rule

    # Create a copy of that Rule, preserving the SAVE, LETTER, and original
    # `raw_line`, but clobbering the FROM field to MIN_YEAR so that it is
    # guaranteed to be the first matching Rule.
    #
    # The alternative was to avoid creating a copy, but simply set the
    # original's `from_year` to MIN_YEAR. But that produced an error in the
    # _check_transitions_sorted() method in zone_processor.py for Asia/Gaza
    # in year 19000 because the yearly transition rule that landed too close
    # to the start of the ZoneEra transition, but they were using 2
    # different suffixes (9/30 24:00u versus 10/1 00:00w), and the current
    # zone_processor.py code was not able to handle them.
    assert anchor_info['rule'] is not None
    anchor_rule = anchor_info['rule'].copy()
    _convert_to_anchor(anchor_rule)
    return anchor_rule


def _convert_to_anchor(rule: ZoneRuleRaw) -> None:
    rule['from_year'] = MIN_YEAR
    rule['to_year'] = MIN_YEAR
    rule['in_month'] = 1
    rule['on_day_of_week'] = 0  # 0, match onDayOfMonth exactly
    rule['on_day_of_month'] = 1
    rule['at_time'] = '0'
    rule['at_time_suffix'] = 'w'
    rule['delta_offset'] = '0'
    rule['at_seconds'] = 0
    rule['at_seconds_truncated'] = 0
    rule['delta_seconds'] = 0
    rule['delta_seconds_truncated'] = 0
    rule['raw_line'] = 'Anchor: ' + rule['raw_line']
    rule['anchor'] = True
