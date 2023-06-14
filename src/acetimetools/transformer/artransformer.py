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
from acetimetools.datatypes.attyping import ZonesMap
from acetimetools.datatypes.attyping import PoliciesMap
from acetimetools.datatypes.attyping import LinksMap
from acetimetools.datatypes.attyping import LettersPerPolicy
from acetimetools.datatypes.attyping import IndexMap
from acetimetools.datatypes.attyping import TransformerResult
from acetimetools.datatypes.attyping import MemoryMap
from acetimetools.datatypes.attyping import SizeofMap


class ArduinoTransformer:
    """Process the ZonesMap and PoliciesMap for the zone_info.{h,cpp} and
    zone_policies.{h,cpp} files required by the AceTime and `acetimepy`
    libraries. Produces a new TransformerResult from get_data().
    """

    SIZEOF_LOW8: SizeofMap = {
        'context': 16,
        'rule': 9,
        'policy': 3,
        'era': 11,
        'info': 13,
        'pointer': 2,  # sizeof(void*)
    }

    SIZEOF_LOW32: SizeofMap = {
        'context': 24,  # 22 rounded to 4-byte alignment
        'rule': 12,  # 9 rounded to 4-byte alignment
        'policy': 8,  # 5 rounded to 4-byte alignment
        'era': 16,  # 15 rounded to 4-byte alignment
        'info': 24,  # 21 rounded to 4-byte alignment
        'pointer': 4,  # sizeof(void*)
    }

    SIZEOF_MID8: SizeofMap = {
        'context': 16,
        'rule': 11,
        'policy': 3,
        'era': 12,
        'info': 13,
        'pointer': 2,  # sizeof(void*)
    }

    SIZEOF_MID32: SizeofMap = {
        'context': 24,  # 22 rounded to 4-byte alignment
        'rule': 12,  # 11 rounded to 4-byte alignment
        'policy': 8,  # 5 rounded to 4-byte alignment
        'era': 16,  # 16 rounded to 4-byte alignment
        'info': 24,  # 21 rounded to 4-byte alignment
        'pointer': 4,  # sizeof(void*)
    }

    SIZEOF_HIRES8: SizeofMap = {
        'context': 16,
        'rule': 12,
        'policy': 3,
        'era': 15,
        'info': 13,
        'pointer': 2,  # sizeof(void*)
    }

    SIZEOF_HIRES32: SizeofMap = {
        'context': 24,  # 22 rounded to 4-byte alignment
        'rule': 12,  # 12 rounded to 4-byte alignment
        'policy': 8,  # 5 rounded to 4-byte alignment
        'era': 20,  # 19 rounded to 4-byte alignment
        'info': 24,  # 21 rounded to 4-byte alignment
        'pointer': 4,  # sizeof(void*)
    }

    def __init__(
        self,
        scope: str,
        compress: bool,
        time_code_format: str,
    ) -> None:
        self.scope = scope
        self.compress = compress
        self.time_code_format = time_code_format

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

        self._process_rules_from_to_at(self.policies_map)
        self._process_rules_letter(
            self.policies_map, self.letters_map, self.letters_per_policy)
        self._process_rules_delta(self.policies_map)

        self._process_eras_stdoff_delta(self.zones_map)
        self._process_eras_until(self.zones_map)

        if self.compress:
            self.fragments_map = _generate_fragments(
                self.zones_map, self.links_map)
            self.compressed_names = _generate_compressed_names(
                self.zones_map, self.links_map, self.fragments_map
            )
        else:
            self.fragments_map = {}
            self.compressed_names = {}

        if self.scope == 'complete':
            memory_map8 = self._generate_memory_map(self.SIZEOF_HIRES8)
            memory_map32 = self._generate_memory_map(self.SIZEOF_HIRES32)
        elif self.scope == 'extended':
            memory_map8 = self._generate_memory_map(self.SIZEOF_MID8)
            memory_map32 = self._generate_memory_map(self.SIZEOF_MID32)
        elif self.scope == 'basic':
            memory_map8 = self._generate_memory_map(self.SIZEOF_LOW8)
            memory_map32 = self._generate_memory_map(self.SIZEOF_LOW32)

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

    def _process_rules_from_to_at(self, policies_map: PoliciesMap) -> None:
        """Convert the FROM, TO, and AT fields of ZoneRuleRaw into values that
        are consumed by the ZonePolicy classes of the Arduino AceTime library.
        """
        for policy_name, policy in policies_map.items():
            rules = policy['rules']
            for rule in rules:
                seconds = rule['at_seconds_truncated']
                suffix = rule['at_time_suffix']
                if self.time_code_format == 'low':
                    if seconds % 60 != 0:
                        raise Exception(
                            f'seconds={seconds} is '
                            'not a multiple of 0:01 minute')
                    encoded = _to_encoded_time_minutes(
                        seconds=seconds, suffix=suffix)
                    rule['at_time_code'] = encoded.code
                    rule['at_time_minute'] = encoded.remainder
                    rule['at_time_modifier'] = encoded.modifier
                elif self.time_code_format == 'high':
                    encoded = _to_encoded_time_seconds(
                        seconds=seconds, suffix=suffix)
                    rule['at_time_seconds_code'] = encoded.code
                    rule['at_time_seconds_remainder'] = encoded.remainder
                    rule['at_time_seconds_modifier'] = encoded.modifier

    def _process_rules_letter(
        self,
        policies_map: PoliciesMap,
        letters_map: IndexMap,
        letters_per_policy: LettersPerPolicy,
    ) -> None:
        """Convert the LETTER fields of ZoneRuleRaw into values that are
        consumed by the ZonePolicy classes of the Arduino AceTime library.
        """
        for policy_name, policy in policies_map.items():
            rules = policy['rules']
            for rule in rules:
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

    def _process_rules_delta(self, policies_map: PoliciesMap) -> None:
        """Convert the delta_seconds extracted from the SAVE field of a RULE
        entry.

        There are 2 time code formats supported by the AceTime library, through
        the classes defined in the ZoneInfo{Low,Mid,High}.h header files:
        * 'low'
            * delta_code: unit of 15-minutes
            * delta_code_encoded: delta_code shifted by 4, so that the 15-minute
              increments from [-1:00,2:45] can be represented in a 4-bit
              unsigned integer [0,15].
        * 'high.
            * delta_minutes: unit of 1-minute
        """
        for policy_name, policy in policies_map.items():
            rules = policy['rules']
            for rule in rules:
                delta_seconds = rule['delta_seconds_truncated']
                if self.time_code_format == 'low':
                    if delta_seconds % 900 != 0:
                        raise Exception(
                            f'delta_seconds={delta_seconds} is '
                            'not a multiple of 0:15 minutes')
                    delta_code = delta_seconds // 900
                    delta_code_encoded = delta_code + 4
                    # Make sure this fits in 4-bits.
                    if delta_code_encoded < 0 or delta_code_encoded > 15:
                        raise Exception(
                            f'delta_code={delta_code} does not fit in 4-bits')
                    rule['delta_code'] = delta_code
                    rule['delta_code_encoded'] = delta_code_encoded
                elif self.time_code_format == 'high':
                    if delta_seconds % 60 != 0:
                        raise Exception(
                            f'delta_seconds={delta_seconds} is '
                            'not a multiple of 0:01 minutes')
                    rule['delta_minutes'] = delta_seconds // 60

    def _process_eras_stdoff_delta(self, zones_map: ZonesMap) -> None:
        """Convert the STDOFF and RULES/DSTOFF fields of ZoneEraRaw into values
        that are consumed by the ZoneInfo classes of the Arduino AceTime
        library.

        There are 2 time code formats supported by the AceTime library, through
        the classes defined in the ZoneInfo{Low,Mid,High}.h header files:
        * 'low'
            * offset_code: unit of 15-minutes
            * offset_minute: remainder minutes
            * delta_code: unit of 15 mintes
        * 'high.
            * offset_seconds_code: unit of 15 seconds
            * offset_seconds_remainder: remainder seconds
            * delta_minutes: minutes
        """
        for zone_name, info in zones_map.items():
            eras = info['eras']
            for era in eras:
                offset_seconds = era['offset_seconds_truncated']
                delta_seconds = era['era_delta_seconds_truncated']

                if self.time_code_format == 'low':
                    if offset_seconds % 60 != 0:
                        raise Exception(
                            f'offset_seconds={offset_seconds} is '
                            'not a multiple of 0:01 minute')
                    if delta_seconds % 900 != 0:
                        raise Exception(
                            f'delta_seconds={delta_seconds} is '
                            'not a multiple of 0:15 minutes')
                    offset_code = offset_seconds // 900
                    offset_minute = (offset_seconds % 900) // 60
                    delta_code = delta_seconds // 900
                    delta_code_shifted = delta_code + 4  # always positive
                    if delta_code_shifted < 0 or delta_code_shifted > 15:
                        raise Exception(
                            f'delta_code={delta_code} does not fit in 4-bits')
                    delta_code_encoded = (
                        (offset_minute << 4)
                        + delta_code_shifted)
                    era['offset_code'] = offset_code
                    era['offset_minute'] = offset_minute
                    era['delta_code'] = delta_code
                    era['delta_code_encoded'] = delta_code_encoded
                elif self.time_code_format == 'high':
                    offset_seconds_code = offset_seconds // 15
                    offset_seconds_remainder = offset_seconds % 15
                    era['offset_seconds_code'] = offset_seconds_code
                    era['offset_seconds_remainder'] = offset_seconds_remainder

                    if delta_seconds % 60 != 0:
                        raise Exception(
                            f'delta_seconds={delta_seconds} is '
                            'not a multiple of 0:01 minute')
                    delta_minutes = delta_seconds // 60
                    if delta_minutes < -128 or delta_minutes > 127:
                        raise Exception(
                            f'delta_minutes={delta_minutes} '
                            'does not fit in 1 byte')
                    era['delta_minutes'] = delta_minutes

    def _process_eras_until(self, zones_map: ZonesMap) -> None:
        """Convert the UNTIL field of ZoneEraRaw into values that are consumed
        by the ZoneInfo classes of the Arduino AceTime library.

        There are 2 time code formats supported by the AceTime library, through
        the classes defined in the ZoneInfo{Low,Mid,High}.h header files:
        * 'low'
            * time_code: unit of 15-minutes
            * time_minute: remainder minutes
            * time_modifier: suffix ('w', 's', 'u')
        * 'high.
            * time_seconds_code: unit of 15-seconds
            * time_seconds_remainder: remainder seconds
            * time_seconds_modifier: suffix ('w', 's', 'u')
        """
        for zone_name, info in zones_map.items():
            eras = info['eras']
            for era in eras:
                seconds = era['until_seconds_truncated']
                suffix = era['until_time_suffix']
                if self.time_code_format == 'low':
                    if seconds % 60 != 0:
                        raise Exception(
                            f'seconds={seconds} is '
                            'not a multiple of 0:01 minute')
                    encoded = _to_encoded_time_minutes(
                        seconds=seconds, suffix=suffix)
                    era['until_time_code'] = encoded.code
                    era['until_time_minute'] = encoded.remainder
                    era['until_time_modifier'] = encoded.modifier
                elif self.time_code_format == 'high':
                    encoded = _to_encoded_time_seconds(
                        seconds=seconds, suffix=suffix)
                    era['until_time_seconds_code'] = encoded.code
                    era['until_time_seconds_remainder'] = encoded.remainder
                    era['until_time_seconds_modifier'] = encoded.modifier

    def _generate_memory_map(self, sizes: SizeofMap) -> MemoryMap:
        # Context
        context_size = sizes['context']

        num_zones = len(self.zones_map)
        num_links = len(self.links_map)
        num_policies = len(self.policies_map)
        num_zones_and_links = num_zones + num_links

        # Policies
        num_rules = sum([
            len(policy['rules'])
            for _, policy in self.policies_map.items()
        ])
        rule_size = sizes['rule'] * num_rules
        policy_size = sizes['policy'] * num_policies

        # Zones
        num_eras = sum([
            len(info['eras'])
            for _, info in self.zones_map.items()
        ])
        era_size = sizes['era'] * num_eras
        zone_size = sizes['info'] * num_zones

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
            context_size
            + rule_size
            + policy_size
            + era_size
            + zone_size
            + link_size
            + registry_size
            + name_size
            + fragment_size
            + letter_size
            + format_size
        )

        return {
            'context': context_size,
            'rules': rule_size,
            'policies': policy_size,
            'eras': era_size,
            'zones': zone_size,
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
    for policy_name, policy in sorted(policies_map.items()):
        rules = policy['rules']
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
    for zone_name, info in zones_map.items():
        eras = info['eras']
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


class EncodedTime(NamedTuple):
    """Break apart the AT or UNTIL time with its suffix (e.g. 02:00w) into the
    components.
    """
    code: int  # AT or UNTIL time, 15-minute or 15-second units
    remainder: int  # remainder minutes or seconds [0-14]
    modifier: int  # suffix_code | time_remainder


def _to_encoded_time_minutes(seconds: int, suffix: str) -> EncodedTime:
    suffix_code = _to_suffix_code(suffix)
    time_code = seconds // 900  # 15-minute units
    time_remainder = seconds % 900 // 60  # remainder minutes
    time_modifier = time_remainder + suffix_code
    return EncodedTime(
        code=time_code,
        remainder=time_remainder,
        modifier=time_modifier)


def _to_encoded_time_seconds(seconds: int, suffix: str) -> EncodedTime:
    suffix_code = _to_suffix_code(suffix)
    time_code = seconds // 15  # 15-second units
    time_remainder = seconds % 15  # remainder seconds
    time_modifier = time_remainder + suffix_code
    return EncodedTime(
        code=time_code,
        remainder=time_remainder,
        modifier=time_modifier)


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
