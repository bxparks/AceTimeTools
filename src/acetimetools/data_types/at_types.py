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

# AceTime Epoch is 2000-01-01 00:00:00
EPOCH_YEAR: int = 2000

# Indicate +Infinity UNTIL year (represented by empty field).
MAX_UNTIL_YEAR: int = 10000

# Tiny (int8_t) version of MAX_UNTIL_YEAR_TINY.
MAX_UNTIL_YEAR_TINY: int = 127

# Indicate max TO or FROM year.
MAX_YEAR: int = MAX_UNTIL_YEAR - 1

# Tiny (int8_t) version of MAX_YEAR.
MAX_YEAR_TINY: int = MAX_UNTIL_YEAR_TINY - 1

# Marker year to indicate -Infinity year.
MIN_YEAR: int = 0

# Tiny (int8_t) version of MIN_YEAR. Can't be -128 because that's
# used for INVALID_YEAR_TINY.
MIN_YEAR_TINY: int = -127

# Indicate an invalid year.
INVALID_YEAR: int = -1

# Tiny (int8_t) version of INVALID_YEAR.
INVALID_YEAR_TINY: int = -128

# Number of seconds from Unix Epoch (1970-01-01 00:00:00) to AceTime Epoch
# (2000-01-01 00:00:00)
SECONDS_SINCE_UNIX_EPOCH = 946684800


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
    to_year: int  # to year, 1 to MAX_YEAR (9999) means 'max'
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
    used: Optional[bool]  # whether or not the rule is used by a zone
    anchor: Optional[bool]  # True if this is an Anchor rule

    # Derived from above by artransformer.py
    from_year_tiny: int  # (from_year - 2000), w/ special cases for MIN and MAX
    to_year_tiny: int  # (to_year - 2000), w/ special cases for MIN and MAX
    at_time_code: int  # at_time in units of 15-min
    at_time_minute: int  # at_time remainder minutes
    at_time_modifier: int  # 's', 'w' or 'u' + at_time_minute
    delta_code: int  # DST delta offset in units of 15-min
    delta_code_encoded: int  # encoded version of delta_code
    letter_index_per_policy: int  # index into letters_per_policy, or -1
    letter_index: int  # index into letters_map[], or -1

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
    offset_string: str   # STD offset from UTC/GMT
    rules: str  # name of the Rule in effect, '-', or ':'
    format: str  # abbreviation format (e.g. P%sT, E%sT, GMT/BST)
    until_year: int  # MAX_UNTIL_YEAR means 'max'
    until_year_only: bool  # true if only the year is given
    until_month: int  # 1-12
    until_day_string: str  # e.g. 'lastSun', 'Sun>=3', or '1'-'31'
    until_time: str  # e.g. '2:00', '00:01'
    until_time_suffix: str  # '', 's', 'w', 'g', 'u', 'z'
    raw_line: str  # original ZONE line in TZ file

    # Derived from above by transfomer.py
    offset_seconds: int  # STD offset from UTC/GMT in seconds
    offset_seconds_truncated: int  # offset_seconds truncated to granularity
    # If RULES is a DST offset string of the form # hh:mm[:ss], then 'rules' is
    # set to ':', and'era_delta_seconds' contains the parsed delta offset from
    # UTC in seconds. If RULES is '-', then this is set to 0.
    era_delta_seconds: int
    era_delta_seconds_truncated: int  # truncated to granularity
    until_day: int  # 1-31
    until_seconds: int  # until_time converted into total seconds
    until_seconds_truncated: int  # untilSeconds after truncation

    # Derived from above by artransformer.py
    offset_code: int  # STD offset in units of 15-min
    offset_minute: int  # STD offset remainder minutes
    delta_code: int  # DST offset in units of 15-min
    delta_code_encoded: int  # delta_code + offset_minute, in 2 x 4-bits
    until_year_tiny: int  # until_year - 2000, w/ special cases for MIN and MAX
    until_time_code: int  # until_time in units of 15-min
    until_time_minute: int  # until_time remainder minutes
    until_time_modifier: int  # 's', 'w' or 'u' + until_time_minute
    format_short: str  # Arduino version of format with %s -> %

    # Derived by gotransformer.py
    go_offset_seconds_code: int
    go_offset_seconds_remainder: int
    go_era_delta_minutes: int
    go_until_seconds_code: int
    go_until_seconds_remainder: int
    go_until_seconds_suffix_value: int
    go_until_seconds_modifier: int


# Map of policyName -> ZoneRuleRaw[]. Created by extractor.py. Updated by
# transformer.py.
PoliciesMap = Dict[str, List[ZoneRuleRaw]]

# Map of zoneName -> ZoneEraRaw[]. Created by extractor.py. Updated by
# transformer.py.
ZonesMap = Dict[str, List[ZoneEraRaw]]

# Map of linkName -> zoneName. Created by extractor.py. Updated by
# transformer.py.
LinksMap = Dict[str, str]

# -----------------------------------------------------------------------------
# Data types generated by transformer.py and artransformer.py
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

# Map of LETTER strings that are more than 1-character long, grouped by
# ZonePolicy. Allows the 'letter' index to be localzed to the given ZonePolicy
# (i.e. will only be 0 or 1). Created by artransformer.py. map{policy_name ->
# map{letter -> index}}
LettersPerPolicy = Dict[str, IndexMap]

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


@dataclass
class TransformerResult:
    """Result type of Transformer.get_data().
    """

    zones_map: ZonesMap  # {zoneName -> ZoneEraRaw[]}
    policies_map: PoliciesMap  # {policyName -> ZoneRuleRaw[]}
    links_map: LinksMap  # {linkName -> zoneName}
    removed_zones: CommentsMap  # {zoneName -> reasons[]}
    removed_policies: CommentsMap  # {policyName -> reasons[]}
    removed_links: CommentsMap  # {linkName -> reasons[]}
    notable_zones: CommentsMap  # {zoneName -> reasons[]}
    notable_policies: CommentsMap  # {policyName -> reasons[]}
    notable_links: CommentsMap  # {linkName -> reasons[]}
    zones_to_policies: ZonesToPolicies  # {zoneName -> policyName[]}
    merged_notable_zones: MergedCommentsMap  # {zoneName -> MergedCommentsMap]}
    original_min_year: int  # min year in original TZDB
    original_max_year: int  # max year in original TZDB
    generated_min_year: int  # min year in generated zonedb
    generated_max_year: int  # max year in generated zonedb
    zone_ids: Dict[str, int]  # {zoneName -> zoneHash}
    link_ids: Dict[str, int]  # {linkName -> zoneHash}
    letters_per_policy: LettersPerPolicy  # {policyName -> {letter -> index}}
    letters_map: IndexMap  # {letter -> index}
    formats_map: IndexMap  # {format -> index}
    fragments_map: IndexMap  # {fragment -> index}
    compressed_names: Dict[str, str]  # {zoneName -> compressedName}
    go_letters_map: OffsetMap  # {letter -> byte_offset}
    go_formats_map: OffsetMap  # {format -> byte_offset}
    go_names_map: OffsetMap  # {name -> byte_offset}
    go_zone_and_link_index_map: IndexMap  # {zone -> index}
    go_policy_index_size_map: IndexSizeMap  # {policy -> (index, offset, size)}
    go_rule_count: int  # total num rules across all policies
    go_info_index_size_map: IndexSizeMap  # info -> (index, offset, size)
    go_era_count: int  # total num eras across all zone infos


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
# Data types used by bufestimator.py
# -----------------------------------------------------------------------------

class CountAndYear(NamedTuple):
    """A tuple that holds a count and the year which it is related to."""
    number: int
    year: int


# zoneName -> CountAndYear
BufSizeMap = Dict[str, CountAndYear]


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
    until_at_granularity: int
    offset_granularity: int
    delta_granularity: int
    strict: bool
    num_zones: int
    num_policies: int
    num_links: int

    # Data from Extractor filtered through Transformer
    zones_map: ZonesMap
    policies_map: PoliciesMap
    links_map: LinksMap

    # Data from Transformer
    zones_to_policies: ZonesToPolicies
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

    # Data from BufSizeEstimator
    buf_sizes: BufSizeMap
    max_buf_size: int

    # Data from ArduinoTransformer
    zone_ids: Dict[str, int]  # hash(zoneName)
    link_ids: Dict[str, int]  # hash(linkName)
    letters_per_policy: LettersPerPolicy  # multi-char letters by zonePolicy
    letters_map: IndexMap  # all multi-character letters
    formats_map: IndexMap  # all format strings
    fragments_map: IndexMap  # zoneName fragment -> index
    compressed_names: Dict[str, str]  # zoneName -> compressedName

    # Data from GoTransformer
    go_letters_map: OffsetMap  # all letter strings
    go_formats_map: OffsetMap  # all format strings
    go_names_map: OffsetMap  # all name strings
    go_zone_and_link_index_map: IndexMap  # combined index map, sorted by zoneId
    go_policy_index_size_map: IndexSizeMap  # policy -> (index, offset, size)
    go_rule_count: int  # total num rules across all policies
    go_info_index_size_map: IndexSizeMap  # info -> (index, offset, size)
    go_era_count: int  # total num eras across all zone infos


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
    tresult: TransformerResult,
    buf_size_map: BufSizeMap,
    max_buf_size: int,
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

        # Data from Extractor filtered through Transformer.
        'num_zones': len(tresult.zones_map),
        'num_policies': len(tresult.policies_map),
        'num_links': len(tresult.links_map),
        'zones_map': tresult.zones_map,
        'policies_map': tresult.policies_map,
        'links_map': tresult.links_map,

        # Data from Transformer.
        'zones_to_policies': tresult.zones_to_policies,
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

        # Data from BufSizeEstimator
        'buf_sizes': buf_size_map,
        'max_buf_size': max_buf_size,

        # Data from ArduinoTransformer
        'zone_ids': tresult.zone_ids,
        'link_ids': tresult.link_ids,
        'letters_per_policy': tresult.letters_per_policy,
        'letters_map': tresult.letters_map,
        'formats_map': tresult.formats_map,
        'fragments_map': tresult.fragments_map,
        'compressed_names': tresult.compressed_names,

        # Data from GoTransformer
        'go_letters_map': tresult.go_letters_map,
        'go_formats_map': tresult.go_formats_map,
        'go_names_map': tresult.go_names_map,
        'go_zone_and_link_index_map': tresult.go_zone_and_link_index_map,
        'go_policy_index_size_map': tresult.go_policy_index_size_map,
        'go_rule_count': tresult.go_rule_count,
        'go_info_index_size_map': tresult.go_info_index_size_map,
        'go_era_count': tresult.go_era_count,
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
