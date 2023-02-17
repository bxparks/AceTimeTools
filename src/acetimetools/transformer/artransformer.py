# Copyright 2020 Brian T. Park
#
# MIT License

from typing import NamedTuple
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple
from collections import OrderedDict, Counter
import itertools
import logging
from acetimetools.data_types.at_types import ZonesMap
from acetimetools.data_types.at_types import PoliciesMap
from acetimetools.data_types.at_types import LinksMap
from acetimetools.data_types.at_types import LettersPerPolicy
from acetimetools.data_types.at_types import IndexMap
from acetimetools.data_types.at_types import TransformerResult
from acetimetools.data_types.at_types import MemoryMap
from acetimetools.data_types.at_types import SizeofMap
from acetimetools.data_types.at_types import EPOCH_YEAR
from acetimetools.data_types.at_types import MAX_YEAR
from acetimetools.data_types.at_types import MAX_YEAR_TINY
from acetimetools.data_types.at_types import MIN_YEAR
from acetimetools.data_types.at_types import MIN_YEAR_TINY
from acetimetools.data_types.at_types import MAX_UNTIL_YEAR
from acetimetools.data_types.at_types import MAX_UNTIL_YEAR_TINY
from acetimetools.data_types.at_types import add_comment


class ArduinoTransformer:
    """Process the ZonesMap and PoliciesMap for the zone_info.{h,cpp} and
    zone_policies.{h,cpp} files required by the AceTime and AceTimePython
    libraries. Produces a new TransformerResult from get_data().
    """

    SIZEOF8: SizeofMap = {
        'rule': 11,
        'policy': 3,
        'era': 12,
        'info': 13,
        'pointer': 2,  # sizeof(void*)
    }

    # High resolution version
    SIZEOF_HIRES8: SizeofMap = {
        'rule': 12,
        'policy': 3,
        'era': 15,
        'info': 13,
        'pointer': 2,  # sizeof(void*)
    }

    SIZEOF32: SizeofMap = {
        'rule': 12,  # 11 rounded to 4-byte alignment
        'policy': 8,  # 5 rounded to 4-byte alignment
        'era': 16,  # 16 rounded to 4-byte alignment
        'info': 24,  # 21 rounded to 4-byte alignment
        'pointer': 4,  # sizeof(void*)
    }

    SIZEOF_HIRES32: SizeofMap = {
        'rule': 12,  # 12 rounded to 4-byte alignment
        'policy': 8,  # 5 rounded to 4-byte alignment
        'era': 20,  # 19 rounded to 4-byte alignment
        'info': 24,  # 21 rounded to 4-byte alignment
        'pointer': 4,  # sizeof(void*)
    }

    def __init__(self, compress: bool, generate_hires: bool) -> None:
        self.compress = compress
        self.generate_hires = generate_hires

    def transform(self, tresult: TransformerResult) -> None:
        self.tresult = tresult

        self.zones_map = tresult.zones_map
        self.policies_map = tresult.policies_map
        self.links_map = tresult.links_map
        zone_ids = tresult.zone_ids
        link_ids = tresult.link_ids

        self.letters_per_policy, self.letters_map = _collect_letter_strings(
            self.policies_map)
        self.formats_map = _collect_format_strings(self.zones_map)
        self._process_rules(
            self.policies_map, self.letters_map, self.letters_per_policy)
        self._process_eras(self.zones_map)
        if self.compress:
            self.fragments_map = _generate_fragments(
                self.zones_map, self.links_map)
            self.compressed_names = _generate_compressed_names(
                self.zones_map, self.links_map, self.fragments_map
            )
        else:
            self.fragments_map = {}
            self.compressed_names = {}

        if self.generate_hires:
            memory_map8 = self._generate_memory_map(self.SIZEOF_HIRES8)
            memory_map32 = self._generate_memory_map(self.SIZEOF_HIRES32)
        else:
            memory_map8 = self._generate_memory_map(self.SIZEOF8)
            memory_map32 = self._generate_memory_map(self.SIZEOF32)

        tresult.zone_ids = zone_ids
        tresult.link_ids = link_ids
        tresult.letters_per_policy = self.letters_per_policy
        tresult.letters_map = self.letters_map
        tresult.formats_map = self.formats_map
        tresult.fragments_map = self.fragments_map
        tresult.compressed_names = self.compressed_names
        tresult.memory_map8 = memory_map8
        tresult.memory_map32 = memory_map32

    def print_summary(self, tresult: TransformerResult) -> None:
        logging.info(
            "Summary"
            f": {len(tresult.zones_map)} Zones"
            f"; {len(tresult.policies_map)} Policies"
            f"; {len(tresult.links_map)} Links"
        )

    def _process_rules(
        self,
        policies_map: PoliciesMap,
        letters_map: IndexMap,
        letters_per_policy: LettersPerPolicy,
    ) -> None:
        """Convert various ZoneRule fields into values that are consumed by the
        ZoneInfo and ZonePolicy classes of the Arduino AceTime library.
        """
        for policy_name, rules in policies_map.items():
            for rule in rules:
                rule['from_year_tiny'] = _to_tiny_year(rule['from_year'])
                rule['to_year_tiny'] = _to_tiny_year(rule['to_year'])

                # Convert at_seconds to at_time_code and at_time_modifier
                at_encoded = _to_encoded_at_or_until_time(
                    seconds=rule['at_seconds_truncated'],
                    suffix=rule['at_time_suffix'],
                )
                rule['at_time_code'] = at_encoded.time_code
                rule['at_time_minute'] = at_encoded.time_remainder
                rule['at_time_modifier'] = at_encoded.time_modifier
                rule['at_time_seconds_code'] = at_encoded.time_seconds_code
                rule['at_time_seconds_remainder'] = \
                    at_encoded.time_seconds_remainder
                rule['at_time_seconds_modifier'] = \
                    at_encoded.time_seconds_modifier

                # Check if AT is not on 15-minute boundary
                if at_encoded.time_remainder != 0:
                    add_comment(
                        self.tresult.notable_policies, policy_name,
                        f"AT '{rule['at_time']}' not on 15-minute boundary"
                    )

                # These will always be integers because transformer.py
                # truncated them to 900 seconds appropriately.
                delta_encoded = _to_rule_delta(rule['delta_seconds_truncated'])
                rule['delta_code'] = delta_encoded.delta_code
                rule['delta_code_encoded'] = delta_encoded.delta_code_encoded
                rule['delta_minutes'] = delta_encoded.delta_minutes

                # Get letter indexes, per policy and global
                letter = rule['letter']
                rule['letter_index'] = _to_letter_index(
                    letter=letter,
                    indexed_letters=self.letters_map,
                )
                indexed_letters = letters_per_policy.get(policy_name)
                assert indexed_letters is not None
                rule['letter_index_per_policy'] = _to_letter_index(
                    letter=letter,
                    indexed_letters=indexed_letters,
                )
                if len(letter) > 1:
                    add_comment(
                        self.tresult.notable_policies, policy_name,
                        f"LETTER '{letter}' not single character"
                    )

    def _process_eras(self, zones_map: ZonesMap) -> None:
        """Convert various ZoneRule fields into values that are consumed by the
        ZoneInfo and ZonePolicy classes of the Arduino AceTime library.
        """
        for zone_name, eras in zones_map.items():
            for era in eras:

                # Determine the current delta seconds, based on the RULES field.
                rule_policy_name = era['rules']
                if rule_policy_name == ':':
                    delta_seconds = era['era_delta_seconds_truncated']
                else:
                    delta_seconds = 0

                # Generate the STDOFF and DST delta offset codes.
                offset_encoded = _to_era_offset_and_delta(
                    offset_seconds=era['offset_seconds_truncated'],
                    delta_seconds=delta_seconds,
                )
                era['offset_code'] = offset_encoded.offset_code
                era['offset_minute'] = offset_encoded.offset_remainder
                era['delta_code'] = offset_encoded.delta_code
                era['delta_code_encoded'] = offset_encoded.delta_code_encoded

                era['offset_seconds_code'] = offset_encoded.offset_seconds_code
                era['offset_seconds_remainder'] = \
                    offset_encoded.offset_seconds_remainder
                era['delta_minutes'] = offset_encoded.delta_minutes

                # Check if STDOFF is not on 15-minute boundary
                if offset_encoded.offset_remainder != 0:
                    add_comment(
                        self.tresult.notable_zones, zone_name,
                        f"STDOFF '{era['offset_string']}' "
                        "not on 15-minute boundary"
                    )

                # Generate the UNTIL fields needed by Arduino ZoneProcessors
                era['until_year_tiny'] = _to_tiny_until_year(era['until_year'])
                until_encoded = _to_encoded_at_or_until_time(
                    seconds=era['until_seconds_truncated'],
                    suffix=era['until_time_suffix'],
                )
                era['until_time_code'] = until_encoded.time_code
                era['until_time_minute'] = until_encoded.time_remainder
                era['until_time_modifier'] = until_encoded.time_modifier
                era['until_time_seconds_code'] = \
                    until_encoded.time_seconds_code
                era['until_time_seconds_remainder'] = \
                    until_encoded.time_seconds_remainder
                era['until_time_seconds_modifier'] = \
                    until_encoded.time_seconds_modifier

                # Check if UNTIL is not on 15-minute boundary
                if until_encoded.time_remainder != 0:
                    add_comment(
                        self.tresult.notable_zones, zone_name,
                        f"UNTIL '{era['until_time']}' not on 15-minute boundary"
                    )

    def _generate_memory_map(self, sizes: SizeofMap) -> MemoryMap:
        num_infos = len(self.zones_map)
        num_links = len(self.links_map)
        num_policies = len(self.policies_map)
        num_zones_and_links = num_infos + num_links

        # Policies
        num_rules = sum([len(rules) for _, rules in self.policies_map.items()])
        rule_size = sizes['rule'] * num_rules
        policy_size = sizes['policy'] * num_policies

        # Zones
        num_eras = sum([len(eras) for _, eras in self.zones_map.items()])
        era_size = sizes['era'] * num_eras
        info_size = sizes['info'] * num_infos

        # Links reuse the ZoneEras from the target Zone.
        link_size = sizes['info'] * num_links

        # Registry
        registry_size = num_zones_and_links * sizes['pointer']

        # Zone and Link names
        name_orig_size = sum([len(name) + 1 for name in self.zones_map.keys()])
        name_orig_size += sum([len(name) + 1 for name in self.links_map.keys()])

        if self.compress:
            name_size = sum([
                len(self.compressed_names[name]) + 1
                for name in self.zones_map.keys()
            ])
            name_size += sum([
                len(self.compressed_names[name]) + 1
                for name in self.links_map.keys()
            ])
        else:
            name_size = name_orig_size

        # Fragment and Letter strings are stored in separate arrays as
        # kFragments and kLetters. So we include the pointers to these.
        fragment_size = sum([len(s) + 1 for s in self.fragments_map.keys()])
        fragment_size += len(self.fragments_map) * sizes['pointer']
        letter_size = sum([len(s) + 1 for s in self.letters_map.keys()])
        letter_size += len(self.letters_map) * sizes['pointer']

        # Formats are stored directly in ZoneEra, so no need to add pointers.
        format_size = sum([len(s) + 1 for s in self.formats_map.keys()])

        # Total
        total_size = (
            rule_size
            + policy_size
            + era_size
            + info_size
            + link_size
            + registry_size
            + name_size
            + fragment_size
            + letter_size
            + format_size
        )

        return {
            'rules': rule_size,
            'policies': policy_size,
            'eras': era_size,
            'infos': info_size,
            'links': link_size,
            'registry': registry_size,
            'names': name_size,
            'names_original': name_orig_size,
            'fragments': fragment_size,
            'formats': format_size,
            'letters': letter_size,
            'total': total_size,
        }


def _collect_letter_strings(
    policies_map: PoliciesMap,
) -> Tuple[LettersPerPolicy, IndexMap]:
    """Loop through all ZoneRules and collect:
    1) a sorted collection of all multi-LETTERs, with their self index,
    2) collection of multi-LETTERs, grouped by policyName
    """

    # Create a global set() of letters, and a per-policy set() of letters
    letters_per_policy: LettersPerPolicy = OrderedDict()
    all_letters: Set[str] = set()
    all_letters.add('')  # TODO: delete? letter '-' is normalized to ''
    for policy_name, rules in sorted(policies_map.items()):
        policy_letters: Set[str] = set()
        policy_letters.add('')  # TODO: delete? letter '-' is normalized to ''
        for rule in rules:
            letter = rule['letter']
            all_letters.add(letter)
            policy_letters.add(letter)

        # Create per-policy letters index map
        if policy_letters:
            indexed_letters: IndexMap = OrderedDict()
            index = 0
            for letter in sorted(policy_letters):
                indexed_letters[letter] = index
                index += 1
            letters_per_policy[policy_name] = indexed_letters

    # Create a global letters index map
    index = 0
    letters_map: IndexMap = OrderedDict()
    for letter in sorted(all_letters):
        letters_map[letter] = index
        index += 1

    return letters_per_policy, letters_map


def _collect_format_strings(zones_map: ZonesMap) -> IndexMap:
    """Collect the 'formats' field and return a map of indexes."""
    short_formats: Set[str] = set()
    for zone_name, eras in zones_map.items():
        for era in eras:
            format = era['format']
            short_format = format.replace('%s', '%')
            short_formats.add(short_format)

    index = 0
    short_formats_map: IndexMap = OrderedDict()
    for short_format in sorted(short_formats):
        short_formats_map[short_format] = index
        index += 1

    return short_formats_map


def _to_tiny_year(year: int) -> int:
    """Convert 16-bit year into 8-bit year, taking into account special
    values for MIN and MAX years.
    """
    if year == MAX_YEAR:
        return MAX_YEAR_TINY
    elif year == MIN_YEAR:
        return MIN_YEAR_TINY
    else:
        return year - EPOCH_YEAR


def _to_tiny_until_year(year: int) -> int:
    """Convert 16-bit UNTIL year into 8-bit UNTIL year, taking into account
    special values for MIN and MAX years.
    """
    if year == MAX_UNTIL_YEAR:
        return MAX_UNTIL_YEAR_TINY
    elif year == MIN_YEAR:
        return MIN_YEAR_TINY
    else:
        return year - EPOCH_YEAR


class EncodedTime(NamedTuple):
    """Break apart the AT or UNTIL time with its suffix (e.g. 02:00w) into the
    components.
    """
    suffix_code: int  # integer version of 'w', 's', 'u' (0x00, 0x10, 0x20)

    # one-minute resolution
    time_code: int  # AT or UNTIL time, in 15 minute units
    time_remainder: int  # remainder minutes [0-14]
    time_modifier: int  # suffix_code | time_remainder

    # one-second resolution
    time_seconds_code: int  # AT or UNTIL time in 15-second units
    time_seconds_remainder: int  # remainder seconds [0-14]
    time_seconds_modifier: int  # suffix_code | time_seconds_remainder


def _to_encoded_at_or_until_time(seconds: int, suffix: str) -> EncodedTime:
    suffix_code = _to_suffix_code(suffix)

    time_code = seconds // 900
    time_remainder = seconds % 900 // 60
    time_modifier = time_remainder + suffix_code

    time_seconds_code = seconds // 15
    time_seconds_remainder = seconds % 15
    time_seconds_modifier = time_seconds_remainder + suffix_code

    return EncodedTime(
        suffix_code=suffix_code,
        time_code=time_code,
        time_remainder=time_remainder,
        time_modifier=time_modifier,
        time_seconds_code=time_seconds_code,
        time_seconds_remainder=time_seconds_remainder,
        time_seconds_modifier=time_seconds_modifier,
    )


def _to_suffix_code(suffix: str) -> int:
    """These fit in the upper 4-bits of an 8-bit integer."""
    if suffix == 'w':
        return 0x00
    elif suffix == 's':
        return 0x10
    elif suffix == 'u':
        return 0x20
    else:
        raise Exception(f'Unknown suffix {suffix}')


class EncodedRuleDelta(NamedTuple):
    delta_code: int  # delta offset in units of 15-min
    delta_code_encoded: int  # delta_code + 4 (1h)
    delta_minutes: int  # in minutes


def _to_rule_delta(delta_seconds: int) -> EncodedRuleDelta:
    """Convert the delta_seconds extracted from the SAVE column of a RULE entry
    to an EncodedRuleDelta. The transformer.py ensures that all entries are in
    multiples of 15-minutes, so we don't need to worry about remainder minutes.
    """
    delta_code = delta_seconds // 900
    delta_code_encoded = delta_code + 4
    # Make sure this fits in 4-bits. TODO: Move to the calling function.
    if delta_code_encoded < 0 or delta_code_encoded > 15:
        raise Exception(f'delta_code={delta_code} does not fit in 4-bits')
    delta_minutes = delta_seconds // 60
    return EncodedRuleDelta(
        delta_code=delta_code,
        delta_code_encoded=delta_code_encoded,
        delta_minutes=delta_minutes,
    )


class EncodedOffsetAndDelta(NamedTuple):
    # 1-minute resolution
    offset_code: int  # STDOFF in 15-minute units
    offset_remainder: int  # STDOFF remainder minutes [0-14]
    delta_code: int  # delta (DSTOFF) in 15-minute units
    delta_code_encoded: int  # offset_remainder<<4 | (delta_code + 4)

    # 1-second resolution
    offset_seconds_code: int  # STDOFF in 15-second units
    offset_seconds_remainder: int  # STDOFF remainder seconds [0-14]
    delta_minutes: int  # DSTOFF in minutes


def _to_era_offset_and_delta(
    offset_seconds: int,
    delta_seconds: int,
) -> EncodedOffsetAndDelta:
    """Convert offset_seconds and delta_seconds to an EncodedOffsetAndDelta
    suitable for the AceTime or AceTimeC library.
    """
    offset_code = offset_seconds // 900  # truncate to -infinty
    offset_remainder = (offset_seconds % 900) // 60  # always positive
    delta_code = delta_seconds // 900
    delta_code_shifted = delta_code + 4  # always positive
    if delta_code_shifted < 0 or delta_code_shifted > 15:
        raise Exception(f'delta_code={delta_code} does not fit in 4-bits')
    delta_code_encoded = (offset_remainder << 4) + (delta_code_shifted)

    offset_seconds_code = offset_seconds // 15  # 15-second increments
    offset_seconds_remainder = offset_seconds % 15
    delta_minutes = delta_seconds // 60

    return EncodedOffsetAndDelta(
        offset_code=offset_code,
        offset_remainder=offset_remainder,
        delta_code=delta_code,
        delta_code_encoded=delta_code_encoded,
        offset_seconds_code=offset_seconds_code,
        offset_seconds_remainder=offset_seconds_remainder,
        delta_minutes=delta_minutes,
    )


def _to_letter_index(
    letter: str,
    indexed_letters: IndexMap
) -> int:
    """Return an index into the indexed_letters."""
    letter_index = indexed_letters[letter]
    if letter_index < 0:
        raise Exception(f'letter "{letter}" not found')
    return letter_index


def _generate_fragments(zones_map: ZonesMap, links_map: LinksMap) -> IndexMap:
    """Generate a list of fragments and their indexes, sorted by fragment.
    E.g. { "Africa": 1, "America": 2, ... }
    """
    # Collect the frequency of fragments longer than 3 characters
    fragments: Dict[str, int] = Counter()
    for name in itertools.chain(zones_map.keys(), links_map.keys()):
        fragment_list = _extract_fragments(name)
        for fragment in fragment_list:
            if len(fragment) > 3:
                fragments[fragment] += 1

    # Collect fragments which occur more than 3 times.
    fragments_map: IndexMap = OrderedDict()
    index = 1  # start at 1 because '\0' is the c-string termination char
    for fragment, count in sorted(fragments.items()):
        if count > 3:
            fragments_map[fragment] = index
            index += 1
        else:
            logging.info(
                f"Ignoring fragment '{fragment}' with count {count}, too few"
            )

    # Make sure that index is < 32, before ASCII-space.
    if index >= 32:
        raise Exception("Too many fragments {index}")

    return fragments_map


def _extract_fragments(name: str) -> List[str]:
    """Return the fragments deliminted by '/', excluding the final component.
    Since every component before the final component is followed by a '/', each
    fragment returned by this method includes the trailing '/' to obtain higher
    compression. For example, "America/Argentina/Buenos_Aires" returns
    ["America/", "Argentina/"]. But "UTC" returns [].
    """
    components = name.split('/')
    return [component + '/' for component in components[:-1]]


def _generate_compressed_names(
    zones_map: ZonesMap,
    links_map: LinksMap,
    fragments_map: IndexMap,
) -> Dict[str, str]:
    compressed_names: Dict[str, str] = OrderedDict()
    for name in sorted(zones_map.keys()):
        compressed_names[name] = _compress_name(name, fragments_map)
    for name in sorted(links_map.keys()):
        compressed_names[name] = _compress_name(name, fragments_map)
    return compressed_names


def _compress_name(name: str, fragments: IndexMap) -> str:
    """Convert 'name' into keyword-compressed format suitable for the C++
    KString class. For example, "America/Chicago" -> "\x01Chicago".
    Returns the compressed name.
    """
    compressed = ''
    components = name.split('/')
    for component in components[:-1]:
        fragment = component + '/'
        keyword_index = fragments.get(fragment)
        if keyword_index is None:
            compressed += fragment
        else:
            compressed += chr(keyword_index)
    compressed += components[-1]
    return compressed
