# Copyright 2020 Brian T. Park
#
# MIT License

from collections import OrderedDict
from dataclasses import dataclass
from typing import Collection
from typing import Dict
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Set
from typing import Tuple
from typing import Union
from typing import cast
from typing_extensions import TypedDict

"""
Data types created or consumed by various classes under the tools package. These
allow typing checking to be performed using mypy. Also contains global constants
used by multiple packages.
"""

# -----------------------------------------------------------------------------
# Constants used by various modules.
# -----------------------------------------------------------------------------

# Indicate +Infinity UNTIL year (represented by empty field).
MAX_UNTIL_YEAR: int = 32767

# Tiny (int8_t) version of MAX_UNTIL_YEAR_TINY.
MAX_UNTIL_YEAR_TINY: int = 127

# Indicate max TO year.
MAX_TO_YEAR: int = MAX_UNTIL_YEAR - 1

# Tiny (int8_t) version of MAX_YEAR.
MAX_TO_YEAR_TINY: int = MAX_UNTIL_YEAR_TINY - 1

# Marker year to indicate -Infinity year for 16-bit zonedb.
MIN_YEAR: int = -32767

# Tiny (int8_t) version of MIN_YEAR. Can't be -128 because that's
# used for INVALID_YEAR_TINY.
MIN_YEAR_TINY: int = -127

# Indicate an invalid year, guaranteed to not appear in a zonedb file.
INVALID_YEAR: int = -32768

# Tiny (int8_t) version of INVALID_YEAR.
INVALID_YEAR_TINY: int = -128


# -----------------------------------------------------------------------------
# Data types produced mostly by extractor.py. Some fields are incrementally
# added by transformer.py and artransformer.py.
# -----------------------------------------------------------------------------

class ZoneRuleRaw(TypedDict, total=False):
    """Represents the input records corresponding to the 'RULE' lines in a
    tz database file. Those entries look like this:

    # Rule  NAME    FROM    TO    TYPE IN   ON      AT      SAVE    LETTER
    Rule    US      2007    max   -    Mar  Sun>=8  2:00    1:00    D
    Rule    US      2007    max   -    Nov  Sun>=1  2:00    0       S
    """
    from_year: int  # from year
    to_year: int  # to year, 1 to MAX_TO_YEAR (9999) means 'max'
    in_month: int  # month index (1-12)
    on_day: str  # 'lastSun' or 'Sun>=2', or 'dayOfMonth'
    at_time: str  # hour at which to transition to and from DST
    at_time_suffix: str  # 's', 'w', 'u'
    delta_offset: str  # DST offset from Standard time ('SAVE' field)
    letter: str  # 'D', 'S', '-', but sometimes longer 'DD', 'CAT', etc.
    raw_line: str  # the original RULE line from the TZ file

    # Derived from above by transformer.py.
    on_day_of_week: int  # 1=Monday, 7=Sunday, 0={exact dayOfMonth match}
    on_day_of_month: int  # 1-31 "dow>=xx", -(1-31) "dow<=xx", 0={lastXxx}
    at_seconds: int  # at_time in seconds since 00:00:00
    at_seconds_truncated: int  # at_seconds truncated to granularity
    delta_seconds: int  # offset from Standard time in seconds
    delta_seconds_truncated: int  # delta_seconds truncated to granularity
    truncated: int  # -1, 0, 1 to indicate rule is outside the zonedb interval
    anchor: bool  # True if this is an Anchor rule

    # Derived from above by artransformer.py
    from_year_tiny: int  # (from_year - tiny_base_year)
    to_year_tiny: int  # (to_year - tiny_base_year)
    at_time_code: int  # at_time in units of 15-min
    at_time_minute: int  # at_time remainder minutes
    at_time_modifier: int  # suffix + at_time_minute
    delta_code: int  # DST delta offset in units of 15-min
    delta_code_encoded: int  # encoded version of delta_code
    letter_index: int  # index into letters_map[], or -1
    # high resolution fields
    at_time_seconds_code: int  # at_time in units of 15-seconds
    at_time_seconds_remainder: int  # at_time remainder seconds
    at_time_seconds_modifier: int  # suffix + at_time_seconds_remainder
    delta_minutes: int

    # gotransformer.py
    go_at_seconds_code: int
    go_at_seconds_remainder: int
    go_at_seconds_suffix_value: int
    go_at_seconds_modifier: int
    go_delta_minutes: int


class ZoneEraRaw(TypedDict, total=False):
    """Represents the input records corresponding to the 'ZONE' lines in a
    tz database file. Those entries look like this:

    # Zone  NAME                STDOFF      RULES   FORMAT  [UNTIL]
    Zone    America/Chicago     -5:50:36    -       LMT     1883 Nov 18 12:09:24
                                -6:00       US      C%sT    1920
                                ...
                                -6:00       US      C%sT

    """
    offset_string: str   # STDOFF columnfrom UTC/GMT
    rules: str  # RULES column, name of RULE, '-', or 'hh:mm'
    format: str  # abbreviation format (e.g. P%sT, E%sT, GMT/BST)
    until_year: int  # MAX_UNTIL_YEAR means 'max'
    until_year_only: bool  # true if only the year is given
    until_month: int  # 1-12
    until_day_string: str  # e.g. 'lastSun', 'Sun>=3', or '1'-'31'
    until_time: str  # e.g. '2:00', '00:01'
    until_time_suffix: str  # '', 's', 'w', 'g', 'u', 'z'
    raw_line: str  # original ZONE line in TZ file

    # Derived from above by transfomer.py
    format_short: str  # compressed format (%s -> %; %z -> '')
    offset_seconds: int  # STD offset from UTC/GMT in seconds
    offset_seconds_truncated: int  # offset_seconds truncated to granularity
    # If RULES is a string reference to a policy (i.e. set of RULES), this is
    # set to the policy name. Otherwise, this is set to 'None' to indicate a
    # fixed DST offset of '-' or 'hh:mm'.
    policy_name: Optional[str]
    # If RULES is a fixed DST offset string of the form 'hh:mm[:ss]', then
    # 'era_delta_seconds' contains the parsed delta offset from UTC in seconds.
    # If RULES is '-' or a named policy name, then this is set to 0.
    era_delta_seconds: int
    era_delta_seconds_truncated: int  # truncated to granularity
    until_day: int  # 1-31
    until_seconds: int  # until_time converted into total seconds
    until_seconds_truncated: int  # untilSeconds after truncation

    # Derived from above by artransformer.py
    offset_code: int  # STD offset in units of 15-min
    offset_minute: int  # STD offset remainder minutes
    delta_code: int  # DST offset in units of 15-min
    delta_code_encoded: int  # (offset_minute << 4 + delta_code)
    until_year_tiny: int  # until_year - tiny_base_year)
    until_time_code: int  # until_time in units of 15-min
    until_time_minute: int  # until_time remainder minutes
    until_time_modifier: int  # suffix + until_time_minute
    # high resolution fields
    offset_seconds_code: int  # STD offset in units of 15 seconds
    offset_seconds_remainder: int  # STD offset remainder seconds
    until_time_seconds_code: int  # until_time in units of 15-seconds
    until_time_seconds_remainder: int  # until_time remainder seconds
    until_time_seconds_modifier: int  # suffix + until_time_seconds_remainder
    delta_minutes: int  # DST offset in units of 1 minute

    # Derived by gotransformer.py
    go_offset_seconds_code: int
    go_offset_seconds_remainder: int
    go_era_delta_minutes: int
    go_until_seconds_code: int
    go_until_seconds_remainder: int
    go_until_seconds_suffix_value: int
    go_until_seconds_modifier: int


class ZonePolicyRaw(TypedDict, total=False):
    """Represents a policy, composed of list of rules."""
    rules: List[ZoneRuleRaw]
    lower_rule_truncated: bool  # rule truncated before start_year
    upper_rule_truncated: bool  # rule truncated on or after until_year


class ZoneInfoRaw(TypedDict, total=False):
    """Represents a single zoneinfo record after parsing and processing the
    TZDB raw data files.
    """
    eras: List[ZoneEraRaw]
    lower_era_truncated: bool  # era truncated before start_year
    upper_era_truncated: bool  # era truncated on or after until_year
    lower_zone_truncated: bool  # zone truncated before start_year
    upper_zone_truncated: bool  # zone truncated on or after until_year


# Map of policyName -> ZonePolicy. Created by extractor.py. Updated by
# transformer.py.
PoliciesMap = Dict[str, ZonePolicyRaw]

# Map of zoneName -> ZoneInfo. Created by extractor.py. Updated by
# transformer.py.
ZonesMap = Dict[str, ZoneInfoRaw]

# Map of linkName -> zoneName. Created by extractor.py. Updated by
# transformer.py.
LinksMap = Dict[str, str]

# -----------------------------------------------------------------------------
# Data types generated by transformer.py, artransformer.py, gotransformer.py.
# -----------------------------------------------------------------------------

# Map of {str -> index}, for example, to store a sorted list of all LETTER
# strings with their associated self-index into the map. Created by
# artransformer.py.
IndexMap = Dict[str, int]

# Map of {str -> [index, offset]}, to store a sorted list of all LETTER strings
# with their associated self-index into the map, along with the byte offset into
# the concatenated string buffer. Created by gotransformer.py.
OffsetMap = Dict[str, Tuple[int, int]]

# Map of {str -> [index, offset, size]}, to store a list of zone
# policies, its sequential index, its rule index into the ZoneRules array, and
# the number of rules.
IndexSizeMap = Dict[str, Tuple[int, int, int]]

# Map of {name -> Set[reason]} used by Transformer to collect de-duped error
# messages or warnings. A set() collection does not serialize well to JSON, so
# jsongenerator.py will convert these into {name -> List[Comment]} internally.
# We use an Collection[str] instead of a Union[Dict[], Dict[]] or even a
# Dict[str, Union[Set[], List[]] to avoid a LOT of headaches with mypy type
# checking.
CommentsMap = Dict[str, Collection[str]]

# Map of {name -> List[Any]}, a merged list of zone comments and policy
# comments. The list can contain `str` or another CommentsMap.
MergedCommentsMap = Dict[str, List[Union[str, CommentsMap]]]

# Map of zoneName -> List[policiNames]. Created by transformer.py.
ZonesToPolicies = Dict[str, Collection[str]]


# Memory consumption for various objects for different processor alignment.
class SizeofMap(TypedDict):
    context: int  # sizeof(ZoneContext)
    rule: int  # sizeof(ZoneRule)
    policy: int  # sizeof(ZonePolicy)
    era: int  # sizeof(ZoneEra)
    info: int  # sizeof(ZoneInfo)
    pointer: int  # sizeof(void*)


# Memory size of each type of objects in zonedb
class MemoryMap(TypedDict, total=False):
    context: int
    rules: int
    policies: int
    eras: int
    zones: int
    links: int
    registry: int
    names: int
    names_original: int
    fragments: int
    formats: int
    letters: int
    total: int

# -----------------------------------------------------------------------------
# Data types used by bufestimator.py
# -----------------------------------------------------------------------------


class CountAndYear(NamedTuple):
    """A tuple that holds a count and the year which it is related to."""
    number: int
    year: int


# zoneName -> CountAndYear
BufSizeMap = Dict[str, CountAndYear]


# -----------------------------------------------------------------------------
# TransformerResult. Holds the various intermediate quantities consumed and
# produced by various transformer objects.
# -----------------------------------------------------------------------------

@dataclass
class TransformerResult:
    """Result type of Transformer.get_data().
    """

    # Data from Extractor filtered through Transformer.
    zones_map: ZonesMap  # {zoneName -> ZoneEraRaw[]}
    policies_map: PoliciesMap  # {policyName -> ZoneRuleRaw[]}
    links_map: LinksMap  # {linkName -> zoneName}
    # Data from Transformer.
    zone_ids: Dict[str, int]  # {zoneName -> zoneHash}
    link_ids: Dict[str, int]  # {linkName -> zoneHash}
    removed_zones: CommentsMap  # {zoneName -> reasons[]}
    removed_policies: CommentsMap  # {policyName -> reasons[]}
    removed_links: CommentsMap  # {linkName -> reasons[]}
    notable_zones: CommentsMap  # {zoneName -> reasons[]}
    notable_policies: CommentsMap  # {policyName -> reasons[]}
    notable_links: CommentsMap  # {linkName -> reasons[]}
    zones_to_policies: ZonesToPolicies  # {zoneName -> policyName[]}
    merged_notable_zones: MergedCommentsMap  # {zoneName -> MergedCommentsMap]}
    # zoneinfo accuracy parameters, year range, truncation
    original_min_year: int  # min year in original TZDB
    original_max_year: int  # max year in original TZDB
    generated_min_year: int  # min year in generated zonedb
    generated_max_year: int  # max year in generated zonedb
    lower_truncated: bool  # if ANY zone truncated at the lower years
    upper_truncated: bool  # if ANY zone truncated at the upper years
    start_year_accurate: int  # start year of accuate transitions
    until_year_accurate: int  # until year of accuate transitions
    # Data from BufSizeEstimator
    buf_sizes: BufSizeMap  # {zoneName -> CountAndYear}
    max_buf_size: int  # max buf size over all zones and years
    estimator_min_year: int  # min year for buf size variations
    estimator_max_year: int  # max year for buf size variations
    # Data from ArduinoTransformer
    letters_map: IndexMap  # {letter -> index}
    formats_map: IndexMap  # {format -> index}
    fragments_map: IndexMap  # {fragment -> index}
    compressed_names: Dict[str, str]  # {zoneName -> compressedName}
    memory_map8: MemoryMap  # flash usage for AceTime, acetimec, 8 bits
    memory_map32: MemoryMap  # flash usage for AceTime, acetimec, 32 bits
    # Data from GoTransformer
    go_letters_map: OffsetMap  # {letter -> byte_offset}
    go_formats_map: OffsetMap  # {format -> byte_offset}
    go_names_map: OffsetMap  # {name -> byte_offset}
    go_zone_and_link_index_map: IndexMap  # {zone -> index}
    go_policy_index_size_map: IndexSizeMap  # {policy -> (index, offset, size)}
    go_info_index_size_map: IndexSizeMap  # info -> (index, offset, size)
    go_memory_map: MemoryMap  # memory usage for acetimego


def add_comment(comments: CommentsMap, name: str, reason: str) -> None:
    """Add the human readable 'reason' to the 'comments' CommentsMap.
    """
    reasons = cast(Optional[Set[str]], comments.get(name))
    if not reasons:
        reasons = set()
        comments[name] = reasons
    reasons.add(reason)


def merge_comments(target: CommentsMap, new: CommentsMap) -> None:
    """Merge 'new' CommentsMap into 'target' CommentsMap.
    """
    for name, new_reasons in new.items():
        old_reasons = cast(Optional[Set[str]], target.get(name))
        if not old_reasons:
            old_reasons = set()
            target[name] = old_reasons
        old_reasons.update(new_reasons)


# -----------------------------------------------------------------------------
# The master ZoneInfo database which can be rendered into different forms by
# various generators (e.g. JSON, or Arduino C++).
# -----------------------------------------------------------------------------

class ZoneInfoDatabase(TypedDict):
    """The complete internal representation of the TZ Database files after
    processing them for the AceTime library.
    """

    # Context data.
    tz_version: str
    tz_version_number: int
    tz_files: List[str]
    scope: str
    start_year: int
    until_year: int
    start_year_accurate: int  # start year of accuracy
    until_year_accurate: int  # until year of accuracy
    until_at_granularity: int
    offset_granularity: int
    delta_granularity: int
    strict: bool
    compress: bool
    num_zones: int
    num_policies: int
    num_links: int
    num_eras: int
    num_rules: int

    # Data from Extractor filtered through Transformer
    zones_map: ZonesMap
    policies_map: PoliciesMap
    links_map: LinksMap

    # Data from Transformer
    zone_ids: Dict[str, int]  # hash(zoneName)
    link_ids: Dict[str, int]  # hash(linkName)
    removed_zones: CommentsMap
    removed_links: CommentsMap
    removed_policies: CommentsMap
    notable_zones: CommentsMap
    merged_notable_zones: MergedCommentsMap
    notable_links: CommentsMap
    notable_policies: CommentsMap
    original_min_year: int
    original_max_year: int
    generated_min_year: int
    generated_max_year: int
    lower_truncated: bool  # if ANY zone truncated at the lower years
    upper_truncated: bool  # if ANY zone truncated at the upper years

    # Data from BufSizeEstimator
    buf_sizes: BufSizeMap
    max_buf_size: int
    estimator_min_year: int
    estimator_max_year: int

    # Data from Commenter
    zones_to_policies: ZonesToPolicies

    # Data from ArduinoTransformer
    letters_map: IndexMap  # all multi-character letters
    formats_map: IndexMap  # all format strings
    fragments_map: IndexMap  # zoneName fragment -> index
    compressed_names: Dict[str, str]  # zoneName -> compressedName
    memory_map8: MemoryMap
    memory_map32: MemoryMap

    # Data from GoTransformer
    go_letters_map: OffsetMap  # all letter strings
    go_formats_map: OffsetMap  # all format strings
    go_names_map: OffsetMap  # all name strings
    go_zone_and_link_index_map: IndexMap  # combined index map, sorted by zoneId
    go_policy_index_size_map: IndexSizeMap  # policy -> (index, offset, size)
    go_info_index_size_map: IndexSizeMap  # info -> (index, offset, size)
    go_memory_map: MemoryMap


def create_zone_info_database(
    tz_version: str,
    tz_files: List[str],
    scope: str,
    start_year: int,
    until_year: int,
    until_at_granularity: int,
    offset_granularity: int,
    delta_granularity: int,
    strict: bool,
    compress: bool,
    tresult: TransformerResult,
) -> ZoneInfoDatabase:
    """Return an instance of ZoneInfoDatabase from the various ingredients."""

    return {
        # Context data.
        'tz_version': tz_version,
        'tz_version_number': _to_version_number(tz_version),
        'tz_files': tz_files,
        'scope': scope,
        'start_year': start_year,
        'until_year': until_year,
        'until_at_granularity': until_at_granularity,
        'offset_granularity': offset_granularity,
        'delta_granularity': delta_granularity,
        'strict': strict,
        'compress': compress,

        # Source data from Transformer.
        'num_zones': len(tresult.zones_map),
        'num_policies': len(tresult.policies_map),
        'num_links': len(tresult.links_map),
        'num_eras': sum([
            len(info['eras'])
            for _, info in tresult.zones_map.items()
        ]),
        'num_rules': sum([
            len(policy['rules'])
            for _, policy in tresult.policies_map.items()
        ]),
        'zones_map': tresult.zones_map,
        'policies_map': tresult.policies_map,
        'links_map': tresult.links_map,

        # Derived data from Transformer.
        'zone_ids': tresult.zone_ids,
        'link_ids': tresult.link_ids,
        'removed_zones': _sort_comments(tresult.removed_zones),
        'removed_links': _sort_comments(tresult.removed_links),
        'removed_policies': _sort_comments(tresult.removed_policies),
        'notable_zones': _sort_comments(tresult.notable_zones),
        'merged_notable_zones': _sort_merged_comments(
            tresult.merged_notable_zones),
        'notable_links': _sort_comments(tresult.notable_links),
        'notable_policies': _sort_comments(tresult.notable_policies),
        'original_min_year': tresult.original_min_year,
        'original_max_year': tresult.original_max_year,
        'generated_min_year': tresult.generated_min_year,
        'generated_max_year': tresult.generated_max_year,
        'lower_truncated': tresult.lower_truncated,
        'upper_truncated': tresult.upper_truncated,
        'start_year_accurate': tresult.start_year_accurate,
        'until_year_accurate': tresult.until_year_accurate,

        # Commenter
        'zones_to_policies': tresult.zones_to_policies,

        # Data from BufSizeEstimator
        'buf_sizes': tresult.buf_sizes,
        'max_buf_size': tresult.max_buf_size,
        'estimator_min_year': tresult.estimator_min_year,
        'estimator_max_year': tresult.estimator_max_year,

        # Data from ArduinoTransformer
        'letters_map': tresult.letters_map,
        'formats_map': tresult.formats_map,
        'fragments_map': tresult.fragments_map,
        'compressed_names': tresult.compressed_names,
        'memory_map8': tresult.memory_map8,
        'memory_map32': tresult.memory_map32,

        # Data from GoTransformer
        'go_letters_map': tresult.go_letters_map,
        'go_formats_map': tresult.go_formats_map,
        'go_names_map': tresult.go_names_map,
        'go_zone_and_link_index_map': tresult.go_zone_and_link_index_map,
        'go_policy_index_size_map': tresult.go_policy_index_size_map,
        'go_info_index_size_map': tresult.go_info_index_size_map,
        'go_memory_map': tresult.go_memory_map,
    }


def _sort_comments(comments: CommentsMap) -> CommentsMap:
    """Sort and convert {name -> Set(str)} to {name -> List(str)} to provide
    deterministic ordering.
    """
    return OrderedDict(
        (k, list(sorted(v)))
        for k, v in sorted(comments.items())
    )


def _sort_merged_comments(
    merged_comments: MergedCommentsMap
) -> MergedCommentsMap:
    """Convert the internal Set[] into List[] for serialization into JSON.
    """
    new_comments: MergedCommentsMap = {}
    for k, v in sorted(merged_comments.items()):
        merged_v: List[Union[str, CommentsMap]] = []
        for e in v:
            if isinstance(e, dict):
                e = _sort_comments(e)
                merged_v.append(e)
            elif isinstance(e, str):
                merged_v.append(e)
            else:
                raise Exception(f"Unknown type: k={k}, v={v}")
        new_comments[k] = merged_v
    return new_comments


def _to_version_number(version: str) -> int:
    """Convert version string (e.g. '2020a') to an integer of the form YYNN
    (e.g. '2001'), where YY is (year - 2000) and NN is the patch number,
    where 'a' is 01.
    """
    year = version[0:4]
    patch = version[4]
    return (int(year) - 2000) * 100 + (ord(patch) - ord('a') + 1)
