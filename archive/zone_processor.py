# Copyright 2018 Brian T. Park
#
# MIT License

"""
A early Python version of the C++ ExtendedZoneProcessor class to allow easier
and faster iteration of its algorithms. It is too cumbersome and tedious to
experiment and debug the C++ code in the Arduino environment. The actual Python
implementation of ExtendedZoneProcessor is given in zone_processor.py.
"""

import sys
import logging
from datetime import datetime
from datetime import timedelta
from datetime import date
from typing import Any
from typing import Dict
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Tuple
from typing import TYPE_CHECKING
from typing import Union
from typing import cast
from typing_extensions import Protocol
from typing_extensions import TypedDict

from acetimetools.datatypes.attyping import CountAndYear
from .common import MIN_YEAR
from .common import SECONDS_SINCE_UNIX_EPOCH
from .common import seconds_to_hms
from .common import hms_to_seconds
from .common import calc_day_of_month
from .zonedb_types import ZoneRule
from .zonedb_types import ZonePolicy
from .zonedb_types import ZoneEra
from .zonedb_types import ZoneInfo


class DateTuple(NamedTuple):
    """A datetime representation using seconds instead of h:m:s. I think this
    class makes arithmetic operations on this easier.
    """
    y: int  # year
    M: int  # month
    d: int  # day
    ss: int  # total number of seconds
    f: str  # modifier ('w', 's', 'u')


class YearMonthTuple(NamedTuple):
    """A tuple of (year, month)"""
    y: int
    M: int


class OffsetInfo(NamedTuple):
    """Various bits of the Transition information at the current time.
    """
    total_offset: int  # total_offset = utc_offset + dst_offset
    utc_offset: int  # seconds
    dst_offset: int  # seconds
    abbrev: str  # short abbreviations
    fold: int  # same meaning as datetime.fold


class BufferSizeInfo(NamedTuple):
    """A tuple containings the maximum active transitions and the year which
    that occurred, and the max_buffer_size of TransitionStorage and its year.
    """
    max_actives: CountAndYear
    max_buffer_size: CountAndYear


ACETIME_EPOCH = datetime(2000, 1, 1)  # in UTC


def policy_name_of(era: ZoneEra) -> str:
    """Return the effective policy name of the given ZoneEra."""
    if era['zone_policy'] in ['-', ':']:
        return cast(str, era['zone_policy'])
    else:
        return cast(ZonePolicy, era['zone_policy'])['name']


class MatchingEra:
    """A version of ZoneEra that overlaps with the [start, end) interval of
    interest. The interval is usually a 14-month interval that begins a month
    before the year of interest, and extends a month after the year of interest.
    """
    __slots__ = [
        'start_date_time',  # the until_time of the previous ZoneEra
        'until_date_time',  # the until_time of the current ZoneEra
        'zone_era',  # the ZoneEra corresponding to this match
    ]

    # Hack because '__slots__' is unsupported by mypy. See
    # https://github.com/python/mypy/issues/5941.
    if TYPE_CHECKING:
        start_date_time: DateTuple
        until_date_time: DateTuple
        zone_era: ZoneEra

    def __init__(self, arg: Dict[str, Any]):
        for s in self.__slots__:
            setattr(self, s, None)
        if isinstance(arg, dict):
            for key, value in arg.items():
                setattr(self, key, value)
        elif isinstance(arg, MatchingEra):
            for s in MatchingEra.__slots__:
                setattr(self, s, getattr(arg, s))

    def copy(self) -> 'MatchingEra':
        result = cast(MatchingEra, self.__class__.__new__(self.__class__))
        for s in self.__slots__:
            setattr(result, s, getattr(self, s))
        return result

    def __repr__(self) -> str:
        return (
            'MatchingEra('
            f'start: {date_tuple_to_string(self.start_date_time)}'
            f'; until: {date_tuple_to_string(self.until_date_time)}'
            f'; policy_name: {policy_name_of(self.zone_era)}'
            ')'
        )


class Transition:
    """A description of a potential change in DST offset. It can come from
    a number of sources:

    1) An instance of a ZoneRule that was referenced by the RULES column,
       instantiated for the given year, which then determines the start date
       and until date.
    2) A boundary between one ZoneEra and the next ZoneEra.
    3) A ZoneRule that has been shifted to the boundary of a ZoneEra.
    """
    __slots__ = [
        # The start and until times are initially copied from MatchingEra, where
        #
        # * 'start_date_time' is the UNTIL time of the previous ZoneEra, and
        # * 'until_date_time' is the UNTIL time of the current ZoneEra.
        #
        # Then the transition times are generated. Then these fields are updated
        # in-situ by _generate_start_until_times() using those transition times:
        #
        # * 'start_date_time' is set to the current transition_time converted
        #   into the UTC offset of the current Transition.
        # * 'until_date_time' is set to the transition_time of the *next*
        #   Transition.
        # * 'start_epoch_seconds' is set to the 'start_date_time' converted
        #   to epoch seconds using the UTC offset of the *prev* transition
        'start_date_time',  # replaced with actual start time
        'until_date_time',  # replaced with actual until time
        'zone_era',  # (ZoneEra)
        'start_epoch_second',  # the starting time in epoch seconds

        # These transition times (in 'w', 's' and 'u' variants) are added for
        # both simple Match and named Match.
        #
        # For a simple Transition, the transition_time is the startTime of the
        # ZoneEra. For a named Transition, the transition_time is the AT field
        # of the corresponding ZoneRule (see _create_transition_for_year()).
        #
        # The 'transition_time' is the wall date-time of the transition, using
        # the UTC offset of the *previous* transition. The TZ file will
        # sometimes specify these as 's' or 'u', so the _fix_transition_times()
        # will normalize and generate all 3 versions.
        'transition_time',  # 'w' time
        'transition_time_s',  # 's' time
        'transition_time_u',  # 'u' time

        # For the latest prior transition, the actual transition time is shifted
        # to be the start time of the MatchingEra. This field preserves the
        # original transition time for debugging. Not used by any subsequent
        # calculation.
        'original_transition_time',  # transition time before shifting

        'abbrev',  # abbreviation

        # Added for named Match.
        'zone_rule',  # Defined for named Match.

        # Flag to indicate if Transition is active or not
        'is_active',  # Transition is inside MatchingEra and is active
    ]

    # Hack because '__slots__' is unsupported by mypy. See
    # https://github.com/python/mypy/issues/5941.
    if TYPE_CHECKING:
        start_date_time: DateTuple
        until_date_time: DateTuple
        zone_era: ZoneEra
        original_transition_time: DateTuple
        transition_time: DateTuple
        transition_time_s: DateTuple
        transition_time_u: DateTuple
        abbrev: str
        start_epoch_second: int
        zone_rule: Optional[ZoneRule]
        is_active: bool

    def __init__(self, arg: Union[MatchingEra, Dict[str, Any]]):
        for s in self.__slots__:
            setattr(self, s, None)
        if isinstance(arg, dict):
            for key, value in arg.items():
                setattr(self, key, value)
        elif isinstance(arg, MatchingEra):
            for s in MatchingEra.__slots__:
                setattr(self, s, getattr(arg, s))

    @property
    def format(self) -> str:
        return self.zone_era['format']

    @property
    def offset_seconds(self) -> int:
        return self.zone_era['offset_seconds']

    @property
    def letter(self) -> str:
        return self.zone_rule['letter'] if self.zone_rule else ''

    @property
    def delta_seconds(self) -> int:
        return self.zone_rule['delta_seconds'] if self.zone_rule \
            else self.zone_era['rules_delta_seconds']

    def copy(self) -> 'Transition':
        result = cast('Transition', self.__class__.__new__(self.__class__))
        for s in self.__slots__:
            setattr(result, s, getattr(self, s))
        return result

    def __repr__(self) -> str:
        sepoch = self.start_epoch_second if self.start_epoch_second else '-'
        policy_name = policy_name_of(self.zone_era)
        offset_seconds = self.offset_seconds
        delta_seconds = self.delta_seconds
        format = self.format
        abbrev = self.abbrev if self.abbrev else ''

        # yapf: disable
        if policy_name in ['-', ':']:
            return (
                'T('
                f"{to_utc_string(offset_seconds, delta_seconds)};"
                f"act={'y' if self.is_active else '-'};"
                f"tt={date_tuple_to_string(self.transition_time)};"
                f"st={date_tuple_to_string(self.start_date_time)};"
                f"ut={date_tuple_to_string(self.until_date_time)};"
                f"ep={sepoch};"
                f"pol={policy_name};"
                f"fmt={format};"
                f"ab={abbrev})"
            )
        else:
            delta_seconds = self.delta_seconds
            letter = self.letter
            zone_rule = self.zone_rule
            zone_rule_from = cast(ZoneRule, zone_rule)['from_year']
            zone_rule_to = cast(ZoneRule, zone_rule)['to_year']
            original_transition = (
                date_tuple_to_string(self.original_transition_time)
                if self.original_transition_time
                else ''
            )

            return (
                'T('
                f"{to_utc_string(offset_seconds, delta_seconds)};"
                f"act={'y' if self.is_active else '-'};"
                f"tt={date_tuple_to_string(self.transition_time)};"
                f"st={date_tuple_to_string(self.start_date_time)};"
                f"ut={date_tuple_to_string(self.until_date_time)};"
                f"ot={original_transition};"
                f"ep={sepoch};"
                f"pol={policy_name}[{zone_rule_from},{zone_rule_to}];"
                f"fmt={format}({letter});"
                f"ab={abbrev})"
            )
        # yapf: enable


class TransitionMatch(NamedTuple):
    """The result of a _find_transition_for_seconds().
    * fold=0 means there was no overlap with the previous transition
    * fold=1 means there was an overlap with the previous transition
    """
    transition: Transition
    fold: int


def _to_offset_info(transition: Transition, fold: int) -> OffsetInfo:
    """Convert a Transition and fold into a OffsetInfo.
    """
    return OffsetInfo(
        transition.offset_seconds + transition.delta_seconds,
        transition.offset_seconds,
        transition.delta_seconds,
        transition.abbrev,
        fold,
    )


class ZoneProcessor:
    """Extract DST transition information for a given ZoneInfo. The
    DST transition information can be retrieved using the following methods:

    * get_timezone_info_for_seconds(): get info using epoch_seconds (from
        2000-01-01 00:00:00 UTC)
    * get_timezone_info_for_datetime(): get info using a 'datetime.datetime'
        instance

    The DST transition information is returned as an OffsetInfo tuple
    contain (total_offset, utc_offset, dst_offset, abbrev, fold) which is valid
    at the given epoch_seconds or 'datetime'.

    Both get_timezone_info_for_seconds() and get_timezone_info_for_datetime()
    call init_for_year() using a window size (e.g. 12, 13, 14 or 36 months)
    around the closest 'year' to the given argument. (The 'closest' year could
    be (year-1) if the datetime was on Jan 1 of the following year in UTC time).
    The window size can be specified using the 'viewing_months' parameter in the
    constructor.

    The init_for_year() method calculates the relevant Transitions for the given
    year and caches results. Subsequent queries for different epoch_seconds or
    'datetime' will be efficient if the closest 'year' is the same. See
    init_for_year() for high level explanation of the internal algorithm.

    Usage:
        zone_processor = ZoneProcessor(zone_info [, viewing_months, debug])

        # Validate matches and transitions
        zone_processor.init_for_year(args.year)
        zone_processor.print_matches_and_transitions()

        # Get OffsetInfo for an epoch_seconds.
        info = zone_processor.get_timezone_info_for_seconds(epoch_seconds)

        # Get OffsetInfo for a datetime.
        info = zone_processor.get_timezone_info_for_datetime(dt)

    Note:
        The viewing_months parameter determines the month interval to use to
        calculate the transitions:

        * 12 = [year-Jan, (year+1)-Jan) (experimental)
        * 13 = [year-Jan, (year+1)-Feb) (works)
        * 14 = [(year-1)-Dec, (year+1)-Feb) (works, and well tested)
        * 36 = [(year-1)-Jan, (year+2)-Jan) (not well tested,
               seems to mostly work except for 2000)
    """

    def __init__(
            self,
            zone_info: ZoneInfo,
            viewing_months: int = 14,
            debug: bool = False,
            in_place_transitions: bool = True,
            optimize_candidates: bool = True,
            use_python_transition: bool = False,
    ):
        """Constructor.

        Args:
            zone_info (dict): one of the ZONE_INFO_xxx constants from
                zone_infos.py. It can contain a reference to a zone_policy_data
                map. We need to convert these into ZoneEra and ZoneRule classes.
            viewing_months (int): size of the window to consider when
                determining the DST transitions (default: 14)
            debug (bool): set to True to enable logging
            in_place_transitions (bool): set to True to use
                ActiveSelectorInPlace class instead of ActiveSelectorBasic
                to determine the Transitions which overlap with the time
                interval specified by MatchingEra
            optimize_candidates (bool): set to True to use
                CandidateFinderOptimized class instead of CandidateFinderBasic
                to obtain the list of candidate Transitions
        """
        self.zone_info = zone_info
        self.viewing_months = viewing_months
        self.in_place_transitions = in_place_transitions
        self.optimize_candidates = optimize_candidates
        self.use_python_transition = use_python_transition

        # Used by init_*() to indicate the current year of interest.
        self.year = 0

        # List of ZoneEra which match the interval of interest.
        self.matches: List[MatchingEra] = []

        # Cummulative list of all candidate Transitions across all calls to
        # find_candidate_transitions() method for the year given to
        # init_for_year(). It was initially thought to be useful for figuring
        # out the buffer size needed by the C++ implementation of this class but
        # the C++ code removes those candidate Transitions which aren't needed
        # after each iteration of MatchingEra, and reuses the buffer consumed by
        # those ignored Transitions, so this cummulative list is not as useful.
        # It is useful to print out for debugging though.
        self.all_candidate_transitions: List[Transition] = []

        # List of matching (and active) Transition objects for the year given to
        # init_for_year().
        self.transitions: List[Transition] = []

        # The maximum value of (len(self.transitions) +
        # len(candidate_transitions)) across all calls to
        # _create_transitions_from_named_match() for the year given to
        # init_for_year(). The C++ version of this class uses a single pool of
        # Transitions to hold both active and candidate transitions. This value
        # should correspond to the largest number of slots consumed in the pool
        # by the C++ code.
        self.max_transition_buffer_size = 0

        self.debug = debug

    def get_transition_for_seconds(
        self,
        epoch_seconds: int,
    ) -> Optional[Transition]:
        """Return Transition for the given epoch_seconds.

        TOOD: Does not seem to be used at all. Remove?
        """
        self._init_for_second(epoch_seconds)
        tmatch = self._find_transition_for_seconds(epoch_seconds)
        return tmatch.transition if tmatch else None

    def get_transition_for_datetime(
        self,
        dt: datetime,
    ) -> Optional[Transition]:
        """Return Transition for the given datetime.

        TODO: Used only in zinfo.py and test_zone_processor.py. I think this
        could be replaced by get_timezone_info_for_datetime().
        """
        self.init_for_year(dt.year)
        return self._find_transition_for_datetime(dt)

    def get_timezone_info_for_seconds(
        self,
        epoch_seconds: int
    ) -> Optional[OffsetInfo]:
        """Return the OffsetInfo of the given epoch_seconds.
        """
        self._init_for_second(epoch_seconds)

        tmatch = self._find_transition_for_seconds(epoch_seconds)
        return (
            _to_offset_info(tmatch.transition, tmatch.fold)
            if tmatch
            else None
        )

    def get_timezone_info_for_datetime(
        self,
        dt: datetime,
    ) -> Optional[OffsetInfo]:
        """Return the OffsetInfo of the Transition for a given datetime.
        """
        self.init_for_year(dt.year)
        transition = self._find_transition_for_datetime(dt)
        if not transition:
            return None
        return _to_offset_info(transition, fold=dt.fold)

    def init_for_year(self, year: int) -> None:
        """Initialize the Matches and Transitions for the year. Call this
        explicitly before accessing self.matches, self.transitions, and
        self.all_candidate_transitions. The high level algorithm is as follows:

        * Extract the list of ZoneEras which overlap with the given year
          and the given window size (e.g. 13, 14, 36 months). These
          are called MatchingEraes.
        * Find the list of Transitions corresponding to the MatchingEraes
          using _create_transitions_for_match().
        * Convert the transition times of the Transition objects into
          start and until times according to the UTC offset of each
          Transition.
        * Determine the start and until times of each transitions according
          to the wall time of each Transition.
        * Determine the time zone abbreviations (e.g. "PDT", "GMT") of
          each Transition.
        """
        if self.debug:
            logging.info('init_for_year(): year: %d', year)
        # Check if cache filled
        if self.year == year:
            if self.debug:
                logging.info('init_for_year(): cached')
            return

        self.year = year
        self.max_transition_buffer_size = 0
        self.matches = []
        self.transitions = []
        self.all_candidate_transitions = []

        if self.viewing_months == 12:
            start_ym = YearMonthTuple(year, 1)
            until_ym = YearMonthTuple(year + 1, 1)
        elif self.viewing_months == 13:
            start_ym = YearMonthTuple(year, 1)
            until_ym = YearMonthTuple(year + 1, 2)
        elif self.viewing_months == 14:
            start_ym = YearMonthTuple(year - 1, 12)
            until_ym = YearMonthTuple(year + 1, 2)
        elif self.viewing_months == 36:
            start_ym = YearMonthTuple(year - 1, 1)
            until_ym = YearMonthTuple(year + 2, 1)
        else:
            raise Exception(
                f'Unsupported viewing_months: {self.viewing_months}')

        if self.debug:
            logging.info('==== Step 1: Finding matches')
        self.matches = self._find_matches(start_ym, until_ym)

        if self.debug:
            logging.info('==== Step 2: Creating (raw) transitions')
        self._create_transitions(self.matches)
        if self.debug:
            print_transitions(self.transitions)

        # Some transitions from simple match may be in 's' or 'u', so
        # convert to 'w'.
        if self.debug:
            logging.info('==== Step 3: Fixing transitions times')
        self._fix_transition_times(self.transitions)
        if self.debug:
            print_transitions(self.transitions)

        if self.debug:
            logging.info('==== Step 4: Generating start and until times')
        self._generate_start_until_times(self.transitions)
        if self.debug:
            print_transitions(self.transitions)

        if self.debug:
            logging.info('==== Step 5: Calculating abbreviations')
        self._calc_abbrev(self.transitions)
        if self.debug:
            print_transitions(self.transitions)

    def get_buffer_sizes(
        self,
        start_year: int,
        until_year: int,
    ) -> BufferSizeInfo:
        """Find the maximum number of actual transitions and the maximum number
        of candidate transitions across the given start_year and until_year.
        This is useful for determining that buffer size of the C++ version
        of this code which uses static sizes for the Transition buffers.
        """
        max_actives = CountAndYear(0, 0)
        max_buffer_size = CountAndYear(0, 0)
        for year in range(start_year, until_year):
            self.init_for_year(year)

            # Number of active transitions.
            transition_count = len(self.transitions)
            if transition_count > max_actives.number:
                max_actives = CountAndYear(transition_count, year)

            # Max size of the transition buffer.
            buffer_size = self.max_transition_buffer_size
            if buffer_size > max_buffer_size.number:
                max_buffer_size = CountAndYear(buffer_size, year)

        return BufferSizeInfo(
            max_actives=max_actives,
            max_buffer_size=max_buffer_size,
        )

    # The following methods are designed to be used internally.

    def _update_transition_buffer_size(
        self,
        candidate_transitions: List[Transition],
    ) -> None:
        """Update the statistics on the number of active Transitions
        and the size of the Transition buffer that may be required in the C++
        code.
        """
        total = len(candidate_transitions) + len(self.transitions)
        if total > self.max_transition_buffer_size:
            self.max_transition_buffer_size = total
        if self.debug:
            logging.info(
                '_update_transition_buffer_size(): '
                'max_transition_buffer_size: %s',
                self.max_transition_buffer_size,
            )
        self.all_candidate_transitions.extend(candidate_transitions)

    def _init_for_second(self, epoch_seconds: int) -> None:
        """Initialize the Transitions from the given epoch_seconds.
        """
        ldt = datetime.utcfromtimestamp(
            epoch_seconds + SECONDS_SINCE_UNIX_EPOCH)

        if self.viewing_months < 14:
            if ldt.month == 1 and ldt.day == 1:
                year = ldt.year - 1
            else:
                year = ldt.year
        else:
            # If viewing_months >= 14, then this shift to the nearest whole
            # year on Jan 1 or Dec 31 does not seem necessary since the unit
            # tests all pass without this.
            #
            # if ldt.month == 12 and ldt.day == 31:
            #    year = ldt.year + 1
            # elif ldt.month == 1 and ldt.day == 1:
            #    year = ldt.year - 1
            # else:
            #    year = ldt.year

            year = ldt.year

        self.init_for_year(year)

    def _find_transition_for_seconds(
        self,
        epoch_seconds: int,
    ) -> Optional[TransitionMatch]:
        """Return the matching transition along with the 'fold' information.
        Return None if not found.

        * fold==0 if the transition was the first matching transition
        * fold==1 if the transition was the second of an overlapping match.
        """
        # Use indexing instead of iterator because we need access to the
        # transition[match-2] element, and it's much easier to do that with
        # indexing. Scan until we get to a transition *just* after the one that
        # matches.
        matching_index = -1
        for i in range(len(self.transitions)):
            transition = self.transitions[i]
            if transition.start_epoch_second > epoch_seconds:
                break
            matching_index = i

        # If no match, return None.
        if matching_index == -1:
            return None

        fold = self._determine_fold(epoch_seconds, matching_index)

        transition_match = TransitionMatch(
            self.transitions[matching_index],
            fold,
        )
        return transition_match

    def _determine_fold(self, epoch_seconds: int, matching_index: int) -> int:
        """Determine the 'fold' by looking at the transition just before the
        matching one. If the prev and current transition overlap, *and* the
        epoch_seconds falls within the overlap, then set the fold to 1,
        otherwise 0.
        """
        if matching_index < 1:
            return 0

        overlap_interval = _subtract_date_tuple(
            self.transitions[matching_index - 1].until_date_time,
            self.transitions[matching_index].start_date_time,
        )
        if overlap_interval <= 0:
            return 0

        seconds_from_zone_era_start = (
            epoch_seconds
            - self.transitions[matching_index].start_epoch_second
        )

        if seconds_from_zone_era_start >= overlap_interval:
            return 0

        return 1

    def _find_transition_for_datetime(
        self,
        dt: datetime,
    ) -> Optional[Transition]:
        if self.use_python_transition:
            return self._find_transition_for_datetime_python(dt)
        else:
            return self._find_transition_for_datetime_cpp(dt)

    def _find_transition_for_datetime_cpp(
        self,
        dt: datetime,
    ) -> Optional[Transition]:
        """Return the best matching transition matching the local datetime 'dt'.
        The algorithm matches the one implemented by
        ExtendedZoneProcessor::findTransitionForDateTime():

        1) If the 'dt' falls in a DST gap, the transition just before the DST
        gap is returned.

        2) If the 'dt' falls within a DST overlap, there are 2 matching
        transitions. The algorithm returns the later transition.

        The method can return None if the 'dt' is earlier than any known
        transition.
        """
        dt_time = _datetime_to_datetuple(dt, 'w')

        match: Optional[Transition] = None
        for transition in self.transitions:
            start_time = transition.start_date_time
            if start_time > dt_time:
                break
            match = transition
        return match

    def _find_transition_for_datetime_python(
        self,
        dt: datetime,
    ) -> Optional[Transition]:
        """Return the match transition using an algorithm that works for
        Python's datetime.tzinfo. See PEP 495
        (https://www.python.org/dev/peps/pep-0495/) for how to handle the 'fold'
        parameter in the 'datetime' within the fold and within the gap.

        * If the 'dt' is in the overlap:
            * return the earlier transition (earlier UTC) if dt.fold == 0,
            * return the later transition (later UTC) if dt.fold == 1.
        * If the 'dt' is in the gap:
            * return the earlier transition (later UTC) if dt.fold == 0,
            * return the later transition (earlier UTC) if dt.fold == 1,
            * see PEP 495 for details.
        """
        dt_time = _datetime_to_datetuple(dt, 'w')

        prev_exact: Optional[Transition] = None
        prev_transition: Optional[Transition] = None
        for transition in self.transitions:
            start_time = transition.start_date_time
            until_time = transition.until_date_time

            exact_match = start_time <= dt_time and dt_time < until_time
            if exact_match:
                if dt.fold == 0:
                    return transition
                if prev_exact is not None:
                    # In the fold/overlap.
                    return transition
                prev_exact = transition
            elif start_time > dt_time:
                if prev_exact:
                    return prev_exact
                # In the gap.
                if dt.fold == 0:
                    return prev_transition
                else:
                    return transition

            prev_transition = transition

        return prev_exact or prev_transition

    def _find_matches(
        self,
        start_ym: YearMonthTuple,
        until_ym: YearMonthTuple,
    ) -> List[MatchingEra]:
        """Find the Zone Eras which overlap [start_ym, until_ym), ignoring
        day, time and timeSuffix. The start and until fields are truncated at
        the low and high end by start_ym and until_ym, respectively.

        The size of the [start_ym, until_ym) is determined by the viewing_months
        flag. Normally, viewing_months will be greater than one years, to
        compensate for our inability to precisely determine which local 'year'
        is associated with a given epochSecond.

        When the epochSeconds is converted to a year using the UTC timezone, the
        actual local DateTime could be Dec 31 of the previous year, or Jan 1 of
        the following year. Unfortunately, we don't know the local time zone
        offset until we generate the Transitions of the local year, and we don't
        know the local year until we generate the Transitions. To get around
        this problem, we create a [start_ym, until_ym) interval that's slightly
        larger than the current year of interest.

        If viewing_months==14, we include the prior December and subsequent
        January. This works well but often produces too many candidate
        Transitions because it spans 3 whole years, potentially 4 years for the
        'most recent prior year'.

        If viewing_months==13, we include only the subsequent January, which
        works because we push the year of interest to the next year if the
        epoch_seconds is on Dec 31.

        If viewing_months==12, this is an experimental option to see if we can
        reduce the number of candidate transitions.
        """
        zone_eras = self.zone_info['eras']
        prev_era: Optional[ZoneEra] = None  # the earliest possible
        matches: List[MatchingEra] = []
        for zone_era in zone_eras:
            if self._era_overlaps_interval(
                    prev_era, zone_era, start_ym, until_ym
            ):
                match = self._create_match(
                    prev_era, zone_era, start_ym, until_ym)
                if self.debug:
                    logging.info('_find_matches(): %s', match)
                matches.append(match)
            prev_era = zone_era
        return matches

    def _create_transitions(self, matches: List[MatchingEra]) -> None:
        """Create the relevant transitions from the matching ZoneEras.
        This method must update self.transitions within the loop for each
        MatchingEra, instead of collecting and returning the accumulated
        transitions array, to allow _update_transition_buffer_size() to can
        collect the buffer size statistics correctly using the intermediate
        self.transitions results.
        """
        if self.debug:
            logging.info('_create_transitions()')
        for match in matches:
            transitions_for_match = self._create_transitions_for_match(match)
            self.transitions.extend(transitions_for_match)

    def _create_transitions_for_match(
        self,
        match: MatchingEra,
    ) -> List[Transition]:
        """Determine if the given MatchingEra is a simple MatchingEra (contains
        an explicit DST offset) or named (references a named ZonePolicy to
        determine the DST offset). Then find the Transitions of the given match
        using the appropriate algorithm.
        """
        if self.debug:
            logging.info('_create_transitions_for_match(): %s', match)

        zone_era = match.zone_era
        zone_policy = zone_era['zone_policy']
        if zone_policy in ['-', ':']:
            return self._create_transitions_from_simple_match(match)
        else:
            return self._create_transitions_from_named_match(match)

    def _create_transitions_from_simple_match(
        self,
        match: MatchingEra,
    ) -> List[Transition]:
        """The zone_policy is '-' or ':' then the Zone Era itself defines the
        UTC offset and the abbreviation. Returns a list of one Transition
        object, to make it compatible with the return type of
        _create_transitions_from_named_match().
        """
        if self.debug:
            logging.info('_create_transitions_from_simple_match(): %s', match)
        transition = Transition(match)
        transition.transition_time = match.start_date_time
        transitions = [transition]
        self._update_transition_buffer_size(transitions)
        if self.debug:
            print_transitions(transitions)
        return transitions

    def _create_transitions_from_named_match(
        self,
        match: MatchingEra,
    ) -> List[Transition]:
        """Create the transitions of the named MatchingEra. The search for the
        relevant Transition occurs in 3 passes:

        1. Find the candidate Transitions defined by the MatchingEra using the
           *whole* years of the MatchingEra (i.e. ignoring the month, day, and
           time fields).
            * Whole years are used because the ZoneRules define recurring rules
              based on whole years.
            * This pass includes something called the "most recent prior"
              Transition, because we need to know the Transition that occurred
              just before the beginning of the given year.
            * Multiple "prior" Transitions may be included as candidates.
            * Two versions:
                * class CandidateFinderBasic
                * class CandidateFinderOptimized
        2. Fix the transition times.
            * Convert the transition_time to the wall time ('w') of the previous
              rule's time offset.
            * If the transition times are given in standard ('s') or UTC ('u')
              time, they are normalized to 'w'.
        3. Select the Transitions which are "active".
            * Active is determined by the entire date and time fields of
              MatchingEra (including month, day and time) fields.
            * Only a single "most recent prior" Transition will be found.
            * Two versions:
                * class ActiveSelectorBasic
                * class ActiveSelectorInPlace

        Two versions are implemented for Passes 1 and 3. The "Basic" versions
        are the earlier versions which use simpler code, at the expense of using
        more memory. The "Optimized" and "InPlace" versions are my subsequent
        improvements to those algorithms, making them use less memory and
        hopefully be faster. Using less memory is important because those
        algorithms will be reimplemenented in C++ for the Arduino
        microcontroller environments which have limited memory (~32kB of flash
        RAM, and ~2kB of static RAM).

        The 'self.max_transition_buffer_size' counter and
        'self.all_candidate_transitions' list attempt to track the amount of
        internal buffer space needed by the various algorithms. See comments in
        __init__().
        """
        if self.debug:
            logging.info('_create_transitions_from_named_match(): %s', match)

        # Pass 1: Find candidate transitions using whole years.
        if self.debug:
            logging.info(
                '---- Pass 1: Get candidate transitions for MatchingEra')
        zone_era = match.zone_era
        zone_policy = cast(ZonePolicy, zone_era['zone_policy'])
        # assert isinstance(zone_policy, ZonePolicy)
        rules = zone_policy['rules']
        finder: 'CandidateFinder'
        if self.optimize_candidates:
            finder = CandidateFinderOptimized(self.debug)
        else:
            finder = CandidateFinderBasic(self.debug)
        candidate_transitions = finder.find_candidate_transitions(match, rules)
        if self.debug:
            print_transitions(candidate_transitions)
        self._check_transitions_sorted(candidate_transitions)

        # Pass 2: Fix the transitions times, converting 's' and 'u' into 'w'
        # uniformly.
        if self.debug:
            logging.info('---- Pass 2: Fix transition times')
        self._fix_transition_times(candidate_transitions)
        if self.debug:
            print_transitions(candidate_transitions)
        self._check_transitions_sorted(candidate_transitions)

        # Update statistics on active transitions
        self._update_transition_buffer_size(candidate_transitions)

        # Pass 3: Select only those Transitions which overlap with the actual
        # start and until times of the MatchingEra.
        if self.debug:
            logging.info('---- Pass 3: Select active transitions')
        selector: 'ActiveSelector'
        if self.in_place_transitions:
            selector = ActiveSelectorInPlace(self.debug)
        else:
            selector = ActiveSelectorBasic(self.debug)
        try:
            transitions = selector.select_active_transitions(
                candidate_transitions, match)
        except:  # noqa: E722
            logging.exception(
                "Zone '%s'; year '%04d'",
                self.zone_info['name'],
                self.year)
            raise
        if self.debug:
            print_transitions(transitions)

        # Verify that the "most recent prior" Transition is properly sorted.
        if self.debug:
            logging.info('---- Final check for sorted transitions')
        self._check_transitions_sorted(transitions)
        if self.debug:
            print_transitions(transitions)

        return transitions

    def print_matches_and_transitions(self) -> None:
        logging.info('---- Buffer Size')
        logging.info('Max: %s', self.max_transition_buffer_size)
        logging.info('---- Matches')
        for m in self.matches:
            logging.info(m)
        logging.info('---- Transitions')
        for t in self.transitions:
            logging.info(t)
        logging.info('---- Candidate Transitions')
        for t in self.all_candidate_transitions:
            logging.info(t)

    @staticmethod
    def _check_transitions_sorted(transitions: List[Transition]) -> None:
        """Check transitions are sorted.
        """
        prev = None
        for transition in transitions:
            if not prev:
                prev = transition
                continue
            if prev.transition_time > transition.transition_time:
                print_transitions(transitions)
                raise Exception('Transitions not sorted')

    @staticmethod
    def _create_match(
        prev_era: Optional[ZoneEra],
        zone_era: ZoneEra,
        start_ym: YearMonthTuple,
        until_ym: YearMonthTuple,
    ) -> MatchingEra:
        """Create the Zone Match object for the given Zone Era, truncated at
        the low and high end by start_ym and until_ym:

        * MatchingEra.start_date_time is prev_era.until_time
        * MatchingEra.until_date_time is zone_era.until_time
        * MatchingEra.policy_name is '-', ':' or the string name of ZonePolicy

        The start_date_time of the current MatchingEra is determined by the
        UNTIL datetime of the prev_era, which uses the UTC offset of the
        *previous* era, not the current era. Therefore, the start_date_time and
        until_date_time is accurate to a resolution of one day. This is good
        enough to generate Transitions, which also will have dateTime fields
        accurate to within a day or so, assuming we don't have 2 DST transitions
        in a single day.

        See _fix_transition_times() which normalizes these start times to the
        wall time uniformly.

        A value of `prev_era==None` means the earliest possible ZoneEra.
        """
        if prev_era is None:
            start_date_time = DateTuple(
                y=MIN_YEAR, M=1, d=1, ss=0, f='w')
        else:
            start_date_time = DateTuple(
                y=prev_era['until_year'],
                M=prev_era['until_month'],
                d=prev_era['until_day'],
                ss=prev_era['until_seconds'],
                f=prev_era['until_time_suffix'])
        if start_date_time < DateTuple(
                y=start_ym.y, M=start_ym.M, d=1, ss=0, f='w'):
            start_date_time = DateTuple(
                y=start_ym.y, M=start_ym.M, d=1, ss=0, f='w')

        until_date_time = DateTuple(
            y=zone_era['until_year'],
            M=zone_era['until_month'],
            d=zone_era['until_day'],
            ss=zone_era['until_seconds'],
            f=zone_era['until_time_suffix'])
        if until_date_time > DateTuple(
                y=until_ym.y, M=until_ym.M, d=1, ss=0, f='w'):
            until_date_time = DateTuple(
                y=until_ym.y, M=until_ym.M, d=1, ss=0, f='w')

        return MatchingEra({
            'start_date_time': start_date_time,
            'until_date_time': until_date_time,
            'zone_era': zone_era
        })

    @staticmethod
    def _generate_start_until_times(transitions: List[Transition]) -> None:
        """Calculate the various start and until times of the Transitions in the
        following way:

        1) The 'until_date_time' of the previous Transition is the
           'transition_time' of the current Transition with no adjustments.
        2) The local 'start_date_time' of the current Transition is
           the current 'transition_time' - (prevOffset + prevDelta) +
           (currentOffset + currentDelta), which converts it into the UTC offset
           of the current transition.
        3) The 'start_epoch_second' of the current Transition is the
           'transition_time' using the UTC offset of the *previous*
           Transition.

        Got all that? Good, because I often cannot understand my own comments
        after a period of time.

        The 'transition_time' field is assumed to have been normalized into the
        'w' mode by calling _fix_transition_times() before this method is
        called.
        """

        # As before, bootstrap the prev transition with the first transition
        # so that we have a UTC offset to work with.
        prev = transitions[0]
        is_after_first = False
        for transition in transitions:
            tt = transition.transition_time

            # 1) Update the 'until_date_time' of the previous Transition.
            if is_after_first:
                prev.until_date_time = tt

            # 2) Calculate the current start_date_time by shifting the
            # transition time into the current UTC offset. This algorithm should
            # be able to handle transition time of 24:00 (or even 25:00) of the
            # previous day.
            secs = (tt.ss - prev.offset_seconds - prev.delta_seconds
                    + transition.offset_seconds + transition.delta_seconds)
            # If (secs < 0 or secs >= 24 * 60 * 60), then we shifted into a
            # different day. During debugging, it was useful to know that, but
            # not so useful in production code, so don't print anything.
            st = datetime(tt.y, tt.M, tt.d)
            st += timedelta(seconds=secs)
            transition.start_date_time = _datetime_to_datetuple(st, tt.f)

            # 3) The epochSecond of the 'transition_time' is determined by the
            # UTC offset of the *previous* Transition. However, the
            # transition_time can be represented by an illegal time (e.g.
            # 24:00). So use the properly normalized start_date_time
            # (calculated above) with the *current* UTC offset.
            #
            # A previous version of this used a `timezone` object set to the
            # fixed `utc_offset_seconds`, then converted the timezone-naive `st`
            # object into a timezone-aware `st` object at that fixed `timezone`.
            # But this bring in the only dependency to the Python `timezone`
            # class which is unnecessary because we can calculate the epoch
            # seconds directly.
            utc_offset_seconds = (
                transition.offset_seconds + transition.delta_seconds)
            dt = st - timedelta(seconds=utc_offset_seconds)  # dt now in UTC
            epoch_second = int((dt - ACETIME_EPOCH).total_seconds())
            transition.start_epoch_second = epoch_second

            prev = transition
            is_after_first = True

        # Finally, fix the last transition's until time
        (udt, udts, udtu) = ZoneProcessor._expand_date_tuple(
            transition.until_date_time, transition.offset_seconds,
            transition.delta_seconds)
        transition.until_date_time = udt

    @staticmethod
    def _fix_transition_times(transitions: List[Transition]) -> None:
        """Convert the transtion['transition_time'] to the wall time ('w') of
        the previous rule's time offset. The Transition time comes from either:

        1) The UNTIL field of the previous Zone Era entry, or
        2) The (in_month, on_day, at_seconds) fields of the Zone Rule.

        In most cases these times are specified as the wall clock 'w' by
        default, but a few cases use 's' (standard) or 'u' (utc). We don't need
        to support 'g' and 'z' because they mean exactly the same as 'u' and
        they don't appear anywhere in the current TZ files. The transformer.py
        will detect and filter those out.

        To convert these into the more common 'wall' time, we need to
        use the UTC offset of the *previous* Transition.
        """
        # Bootstrap the transition with the first transition, effectively
        # extending the first transition backwards to -infinity. This won't be
        # 100% correct with respect to the TZ Database but it will be good
        # enough for the first transition that we care about.
        prev = transitions[0].copy()
        for transition in transitions:
            (
                transition.transition_time,
                transition.transition_time_s,
                transition.transition_time_u,
            ) = ZoneProcessor._expand_date_tuple(
                transition.transition_time,
                prev.offset_seconds,
                prev.delta_seconds,
            )
            prev = transition

    @staticmethod
    def _expand_date_tuple(
        dt: DateTuple,
        offset_seconds: int,
        delta_seconds: int,
    ) -> Tuple[DateTuple, DateTuple, DateTuple]:
        """Convert 's', 'u', or 'w' time into the other 2 versions using the
        given base UTC offset and the delta DST offset. Return a tuple of
        *normalized* (wall, standard, utc) date tuples. The dates are normalized
        so that transitions occurring at 24:00:00 is moved to the next day.
        """
        delta_seconds = delta_seconds if delta_seconds else 0
        offset_seconds = offset_seconds if offset_seconds else 0

        if dt.f == 'w':
            dtw = dt
            dts = DateTuple(
                y=dt.y, M=dt.M, d=dt.d, ss=dtw.ss - delta_seconds, f='s')
            ss = dtw.ss - delta_seconds - offset_seconds
            dtu = DateTuple(y=dt.y, M=dt.M, d=dt.d, ss=ss, f='u')
        elif dt.f == 's':
            dts = dt
            dtw = DateTuple(
                y=dt.y, M=dt.M, d=dt.d, ss=dts.ss + delta_seconds, f='w')
            dtu = DateTuple(
                y=dt.y, M=dt.M, d=dt.d, ss=dts.ss - offset_seconds, f='u')
        elif dt.f == 'u':
            dtu = dt
            ss = dtu.ss + delta_seconds + offset_seconds
            dtw = DateTuple(y=dtu.y, M=dtu.M, d=dtu.d, ss=ss, f='w')
            dts = DateTuple(
                y=dtu.y, M=dtu.M, d=dtu.d, ss=dtu.ss + offset_seconds, f='s')
        else:
            logging.error("Unrecognized Rule.AT suffix '%s'; date=%s", dt.f,
                          dt)
            sys.exit(1)

        dtw = _normalize_date_tuple(dtw)
        dts = _normalize_date_tuple(dts)
        dtu = _normalize_date_tuple(dtu)

        return (dtw, dts, dtu)

    @staticmethod
    def _calc_abbrev(transitions: List[Transition]) -> None:
        """Calculate the time zone abbreviations for each Transition.
        There are several cases:
        1) 'format' contains 'A/B', meaning 'A' for standard time, and 'B'
            for DST time.
        2) 'format' contains a %s, which substitutes the 'letter'
            2a) If 'letter' is '-', replace with nothing.
            2b) The 'format' could be just a '%s'.
        """
        for transition in transitions:
            format = transition.format
            delta_seconds = transition.delta_seconds

            index = format.find('/')
            if index >= 0:
                if delta_seconds == 0:
                    abbrev = format[:index]
                else:
                    abbrev = format[index + 1:]
            elif format.find('%s') >= 0:
                letter = transition.letter
                if letter == '-':
                    letter = ''
                abbrev = format % letter
            else:
                abbrev = format

            transition.abbrev = abbrev

    @staticmethod
    def _era_overlaps_interval(
        prev_era: Optional[ZoneEra],
        era: ZoneEra,
        start_ym: YearMonthTuple,
        until_ym: YearMonthTuple,
    ) -> bool:
        """Determines if era overlaps the interval [start_ym, until_ym),
        ignoring the day, time and timeSuffix. The start date of the current
        era is represented by the prev_era.UNTIL, so the interval of the current
        era is [start_era, until_era) = [prev_era.UNTIL, era.UNTIL). Overlap
        happens if (start_era < until_ym) and (until_era > start_ym). A
        'prev_era==None' means the earliest possible ZoneEra.
        """
        return (
            (prev_era is None
                or ZoneProcessor._compare_era_to_year_month(
                    prev_era, until_ym.y, until_ym.M) < 0)
            and ZoneProcessor._compare_era_to_year_month(
                era, start_ym.y, start_ym.M) > 0
        )

    @staticmethod
    def _compare_era_to_year_month(
        era: ZoneEra,
        year: int,
        month: int,
    ) -> int:
        """Compare the zone_era with year, returning -1, 0 or 1. The day of
        month is implicitly 1. Ignore the until_time_suffix suffix. Maybe it's
        not needed in this context?
        """
        if era['until_year'] < year:
            return -1
        if era['until_year'] > year:
            return 1
        if era['until_month'] < month:
            return -1
        if era['until_month'] > month:
            return 1
        if era['until_day'] > 1:
            return 1
        if era['until_seconds'] < 0:
            return -1
        if era['until_seconds'] > 0:
            return 1
        return 0


class CandidateFinder(Protocol):
    """Define the common methods of CandidateFinderBasic and
    CandidateFinderOptimized for mypy type checking.
    """

    def find_candidate_transitions(
        self,
        match: MatchingEra,
        rules: List[ZoneRule],
    ) -> List[Transition]:
        ...


class CandidateFinderBasic:
    def __init__(self, debug: bool):
        self.debug = debug

    def find_candidate_transitions(
        self,
        match: MatchingEra,
        rules: List[ZoneRule],
    ) -> List[Transition]:
        """Get the list of candidate transitions from the 'rules' which overlap
        the whole years [start_y, end_y] (inclusive)) defined by the given
        MatchingEra. This list potentially includes multiple prior transitions,
        one of which would become the "most recent prior" transition. We use
        whole years because 'rules' define repetitive transitions using whole
        years.
        """
        if self.debug:
            logging.info('Basic.find_candidate_transitions()')

        # If MatchEra.until_date_time is exactly Jan 1 00:00, set the end_year
        # to the prior year.
        start_y = match.start_date_time.y
        until = match.until_date_time
        if until.M == 1 and until.d == 1 and until.ss == 0:
            end_y = until.y - 1
        else:
            end_y = until.y

        transitions: List[Transition] = []
        for rule in rules:
            from_year = rule['from_year']
            to_year = rule['to_year']
            years = self.get_candidate_years(
                from_year, to_year, start_y, end_y)
            for year in years:
                _add_transition_sorted(
                    transitions,
                    _create_transition_for_year(year, rule, match),
                )

        return transitions

    @staticmethod
    def get_candidate_years(
        from_year: int,
        to_year: int,
        start_year: int,
        end_year: int,
    ) -> List[int]:
        """Return the array of years within the Rule's [from_year, to_year]
        range which should be evaluated to obtain the transitions necessary for
        the matched ZoneEra that spans [start_year, end_year].

        1) Include all years which overlap [start_year, end_year].
        2) Add the latest year prior to [start_year]. This is guaranteed to
           exists because we added an anchor rule at year 0 for those zone
           policies that need it.

        If [start_year, end_year] spans a 3-year interval (which will be the
        case for all supported values of 'viewing_months'), then the maximum
        number of elements in 'years' will be 4.
        """
        years = _get_interior_years(from_year, to_year, start_year, end_year)

        # Add most recent Rule year prior to Match years.
        prior_year = _get_most_recent_prior_year(
            from_year, to_year, start_year, end_year)
        if prior_year >= 0:
            years.append(prior_year)

        return years


class CandidateFinderOptimized:
    def __init__(self, debug: bool):
        self.debug = debug

    def find_candidate_transitions(
        self,
        match: MatchingEra,
        rules: List[ZoneRule],
    ) -> List[Transition]:
        """Similar to CandidateFinderBasic.find_candidate_transitions() except
        that prior Transitions which are obviously non-candidates are filtered
        out early. This reduces the size of the statically allocated Transitions
        array in the C++ implementation.
        """
        if self.debug:
            logging.info('Optimized.find_candidate_transitions()')

        # If MatchEra.until_date_time is exactly Jan 1 00:00, set the end_year
        # to the prior year.
        start_y = match.start_date_time.y
        end_y = match.until_date_time.y
        until = match.until_date_time
        if until.M == 1 and until.d == 1 and until.ss == 0:
            end_y = until.y - 1
        else:
            end_y = until.y

        transitions: List[Transition] = []
        prior_transition: Optional[Transition] = None
        for rule in rules:
            from_year = rule['from_year']
            to_year = rule['to_year']
            years = _get_interior_years(from_year, to_year, start_y, end_y)
            if self.debug:
                logging.info(
                    'find_candidate_transitions(): interior years: %s', years)

            # Examine transitions in the interior years. Keep track of potential
            # prior transition.
            for year in years:
                transition = _create_transition_for_year(year, rule, match)
                # Use fuzzy check to filter out transitions which cannot be
                # candidates.
                comp = _compare_transition_to_match_fuzzy(transition, match)
                if comp < 0:
                    prior_transition = self._select_prior_transition(
                        prior_transition, transition)
                elif comp == 1:
                    _add_transition_sorted(transitions, transition)

            # Explicitly examine the transition of the prior year and compare
            # it with the other candidate prior transitions from above.
            prior_year = _get_most_recent_prior_year(
                from_year, to_year, start_y, end_y)
            if self.debug:
                logging.info('find_candidate_transitions(): prior year: %s',
                             prior_year)
            if prior_year >= 0:
                transition = _create_transition_for_year(
                    prior_year, rule, match)
                prior_transition = self._select_prior_transition(
                    prior_transition, transition)

        # Add the most recent prior transition if it exists.
        if prior_transition:
            _add_transition_sorted(transitions, prior_transition)

        return transitions

    @staticmethod
    def _select_prior_transition(
        prior_transition: Optional[Transition],
        transition: Transition,
    ) -> Transition:
        """Select the latest prior transition given the previous prior
        transition and the current transition.
        """
        if prior_transition:
            if transition.transition_time > prior_transition.transition_time:
                return transition
            else:
                return prior_transition
        else:
            return transition


class ProcessTransitionResult(TypedDict):
    start_transition_found: Optional[bool]
    latest_prior_transition: Optional[Transition]
    transitions: List[Transition]


class ActiveSelector(Protocol):
    """Define the common methods of ActiveSelectorBasic and
    ActiveSelectorInPlace for mypy type checking.
    """

    def select_active_transitions(
        self,
        transitions: List[Transition],
        match: MatchingEra,
    ) -> List[Transition]:
        ...


class ActiveSelectorBasic:
    def __init__(self, debug: bool):
        self.debug = debug

    def select_active_transitions(
        self,
        transitions: List[Transition],
        match: MatchingEra,
    ) -> List[Transition]:
        """Select those Transitions which overlap with the MatchingEra interval
        which may not be at year boundary. Also select the latest prior
        transition before the given MatchingEra, shifting the transition time to
        the start of the MatchingEra.

        This implementation copies the active Transitions into a new
        'results_transitions' list.
        """
        if self.debug:
            logging.info('ActiveSelectorBasic.select_active_transitions()')

        # Commulative results of _process_transition()
        results_transitions: List[Transition] = []
        results: ProcessTransitionResult = {
            'start_transition_found': None,
            'latest_prior_transition': None,
            'transitions': results_transitions,
        }

        # Categorize each transition into the 'results' object.
        for transition in transitions:
            self._process_transition(match, transition, results)

        # Add the latest prior transition if it exists.
        if not results.get('start_transition_found'):
            prior_transition = results.get('latest_prior_transition')
            if not prior_transition:
                raise Exception(
                    'Prior transition not found; should not happen')

            # Adjust the transition time to be the start of the MatchingEra.
            prior_transition = prior_transition.copy()
            prior_transition.original_transition_time = \
                prior_transition.transition_time
            prior_transition.transition_time = match.start_date_time
            _add_transition_sorted(results_transitions, prior_transition)

        return results_transitions

    @staticmethod
    def _process_transition(
        match: MatchingEra,
        transition: Transition,
        results: ProcessTransitionResult,
    ) -> None:
        """Compare the given transition to the given match, checking the
        following situations:

        1) If the Transition is outside the time range of the MatchingEra,
           ignore the transition.
        2) If the Transition is within the matching MatchingEra, it is added
           to the map at results['transitions'].
        2a) If the Transition occurs at the very start of the MatchingEra, then
            set the flag "start_transition_found" to true.
        3) If the Transition is earlier than the MatchingEra, then add it to the
           'latest_prior_transition' if it is the largest prior transition.

        This method assumes that the transition time of the Transition has been
        fixed using the _fix_transition_times() method, so that the comparison
        with the MatchingEra can occur accurately.

        The 'results' is a map that keeps track of the processing, and contains:

        {
            'start_transition_found': bool,
            'latest_prior_transition': transition,
            'transitions': {}
        }

        where:

        * If transition >= match.until:
            * do nothing
        * If transition within match:
            * add transition to results['transitions']
            * if transition == match.start
                * set results['start_transition_found'] = True
        * If transition < match:
            * if not start_transition_found:
                * set results['latest_prior_transition'] = latest
        """
        # Determine if the transition falls within the match range.
        transition_compared_to_match = _compare_transition_to_match(
            transition, match)
        if transition_compared_to_match == 2:
            return
        elif transition_compared_to_match in [0, 1]:
            _add_transition_sorted(results['transitions'], transition)
            if transition_compared_to_match == 0:
                results['start_transition_found'] = True
        else:  # transition_compared_to_match < 0:
            # If a Transition exists on the start bounary of the MatchingEra,
            # then we don't need to search for the latest prior.
            if results.get('start_transition_found'):
                return

            # Determine the latest prior transition
            latest_prior_transition = results.get('latest_prior_transition')
            if not latest_prior_transition:
                results['latest_prior_transition'] = transition
            else:
                transition_time = transition.transition_time
                if transition_time > latest_prior_transition.transition_time:
                    results['latest_prior_transition'] = transition


class ActiveSelectorInPlace:
    def __init__(self, debug: bool):
        self.debug = debug

    def select_active_transitions(
        self,
        transitions: List[Transition],
        match: MatchingEra,
    ) -> List[Transition]:
        """Similar to ActiveSelectorBasic.select_active_transitions() except it
        uses an inlined Transition.is_active flag to mark if a Transition is
        active or not. The final result is returned in a new
        'active_transitions' list, but in the C++ version, we can avoid
        allocating an extra array by filter on the 'is_active' flag and resizing
        the transitions array.
        """
        if self.debug:
            logging.info('ActiveSelectorInPlace.select_active_transitions()')

        prior: Optional[Transition] = None
        for transition in transitions:
            prior = self._process_transition(match, transition, prior)

        if prior and prior.transition_time < match.start_date_time:
            prior.original_transition_time = prior.transition_time
            prior.transition_time = match.start_date_time

        active_transitions = []
        for transition in transitions:
            if transition.is_active:
                active_transitions.append(transition)
        return active_transitions

    @staticmethod
    def _process_transition(
        match: MatchingEra,
        transition: Transition,
        prior: Optional[Transition],
    ) -> Optional[Transition]:
        """A version of ActiveSelectorBasic._process_transition() that does
        not allocate new array members, rather uses an internal flag. This
        assumes that all Transitions have been fixed using
        _fix_transition_times().
        """
        transition_compared_to_match = _compare_transition_to_match(
            transition, match)
        if transition_compared_to_match == 2:
            transition.is_active = False
        elif transition_compared_to_match == 1:
            transition.is_active = True
        elif transition_compared_to_match == 0:
            transition.is_active = True
            # This transition falls exactly on the match.start boundary.
            # So we need to invalidate any previous prior transition candidate.
            if prior:
                prior.is_active = False
            prior = transition
        else:  # transition_compared_to_match < 0:
            if prior:
                if transition.transition_time > prior.transition_time:
                    prior.is_active = False
                    transition.is_active = True
                    prior = transition
            else:
                transition.is_active = True
                prior = transition
        return prior


def print_transitions(transitions: List[Transition]) -> None:
    logging.info('print_transitions(): num transitions: %d', len(transitions))
    for t in transitions:
        logging.info(t)


def _add_transition_sorted(
        transitions: List[Transition],
        transition: Transition,
) -> None:
    """Add the transition to the transitions array, using an Insertion Sort
    algorithm, so that 'transitions' array is always sorted by transition_time.

    In normal Python code, we would accumulate the unsorted 'transitions' list,
    then call 'sort()` after all the elements have been added. But this code is
    emulating the equivalent Arduino C++ code without without dynamic arrays and
    a sort() function. By using an incremental Insertion Sort algorithm, we can
    convert this into C++ more easily. The O(N^2) Insertion Sort algorithm
    should be more than fast enough since N <= ~7 (up to 4 interior transitions,
    plus 1 in Jan of the current year, plus 1 in Jan of the following year, and
    1 most recent prior transition.)
    """
    transitions.append(transition)
    for i in range(len(transitions) - 1, 0, -1):
        curr = transitions[i]
        prev = transitions[i - 1]
        if _compare_date_tuple(curr.transition_time, prev.transition_time) < 0:
            transitions[i - 1] = curr
            transitions[i] = prev


def _compare_date_tuple(a: DateTuple, b: DateTuple) -> int:
    if a.y < b.y: return -1  # noqa: #701
    if a.y > b.y: return 1  # noqa: #701
    if a.M < b.M: return -1  # noqa: #701
    if a.M > b.M: return 1  # noqa: #701
    if a.d < b.d: return -1  # noqa: #701
    if a.d > b.d: return 1  # noqa: #701
    return 0


def _datetime_to_datetuple(dt: datetime, format: str) -> DateTuple:
    """Create a DateTuple from the given 'datetime' along with the 'format'
    modifer ('s', 'u', 'w').
    """
    secs = hms_to_seconds(dt.hour, dt.minute, dt.second)
    return DateTuple(y=dt.year, M=dt.month, d=dt.day, ss=secs, f=format)


def _normalize_date_tuple(tt: DateTuple) -> DateTuple:
    """Return the normalized DateTuple where the dt.ss could be negative or
    greater than 24h. Throws exception if the normalization fails.
    """
    if tt.y == MIN_YEAR:
        return DateTuple(y=MIN_YEAR, M=1, d=1, ss=0, f=tt.f)

    try:
        st = datetime(tt.y, tt.M, tt.d)
        delta = timedelta(seconds=tt.ss)
        st += delta
        return _datetime_to_datetuple(st, tt.f)
    except:  # noqa: E722
        logging.error('Invalid datetime: %s + %s', st, delta)
        raise


def _create_transition_for_year(
    year: int,
    rule: ZoneRule,
    match: MatchingEra,
) -> Transition:
    """Create the transition from the given 'rule' for the given 'year'.
    Return None if 'year' does not overlap with the [from, to] of the rule. The
    Transition object is a replica of the underlying Match object, with
    additional bookkeeping info.
    """
    transition = Transition(match)
    transition.transition_time = _get_transition_time(year, rule)
    transition.zone_rule = rule
    return transition


def _get_interior_years(
    from_year: int,
    to_year: int,
    start_year: int,
    end_year: int,
) -> List[int]:
    """Return the Rule years that overlap with the Match[start_year, end_year].
    """
    years = []
    for year in range(start_year, end_year + 1):
        if from_year <= year and year <= to_year:
            years.append(year)
    return years


def _get_most_recent_prior_year(
    from_year: int,
    to_year: int,
    start_year: int,
    end_year: int,
) -> int:
    """Return the most recent prior year of the rule[from_year, to_year].
    Return -1 if the rule[from_year, to_year] has no prior year to the
    match[start_year, end_year].
    """
    if from_year < start_year:
        if to_year < start_year:
            return to_year
        else:
            return start_year - 1
    else:
        return -1


def _compare_transition_to_match(
    transition: Transition,
    match: MatchingEra,
) -> int:
    """Determine if transition_time applies to given range of the match.

    To allow the Transition time to be compared correctly to the MatchingEra
    time, which may be specified in the TZ database in ('w', 's', or 'u')
    formats, the Transition.transition_time is assumed to have already
    been expanded (through _fix_transition_times()) to include all 3 versions.
    The MatchingEra.start_date_time and MatchingEra.until_date_time are compared
    to the appropriate version of 'transition_time' as determined by the
    modifier suffix of 'start_date_time' and 'until_date_time'.

    Return:
        * -1 if less than match
        * 0 if equal to match_start
        * 1 if within match,
        * 2 if greater than match
    """
    match_start = match.start_date_time
    if match_start.f == 'w':
        transition_time = transition.transition_time
    elif match_start.f == 's':
        transition_time = transition.transition_time_s
    elif match_start.f == 'u':
        transition_time = transition.transition_time_u
    else:
        raise Exception(f"Unknown suffix: {match_start.f}")
    if transition_time < match_start:
        return -1
    if transition_time == match_start:
        return 0

    match_until = match.until_date_time
    if match_until.f == 'w':
        transition_time = transition.transition_time
    elif match_until.f == 's':
        transition_time = transition.transition_time_s
    elif match_until.f == 'u':
        transition_time = transition.transition_time_u
    else:
        raise Exception(f"Unknown suffix: {match_until.f}")
    if match_until <= transition_time:
        return 2

    return 1


def _compare_transition_to_match_fuzzy(
    transition: Transition,
    match: MatchingEra,
) -> int:
    """Like _compare_transition_to_match() except perform a fuzzy match
    within at least one-month of the match.start or match.until. This is useful
    because unlike _compare_transition_to_match(), the Transition object does
    not need its 'transition_time' to be "fixed" (through
    _fix_transition_times()) to be able to use this function, so we can use this
    function earlier in the filtering process of finding candidate transitions.

    A value of 0 is never returned since we cannot make a direct comparison
    to match_start.

    Return:
        * -1 if less than match
        * 1 if within match,
        * 2 if greater than match
    """
    tt = transition.transition_time
    transition_time = 12 * tt.y + tt.M

    ms = match.start_date_time
    match_start = 12 * ms.y + ms.M
    if transition_time < match_start - 1:
        return -1

    mu = match.until_date_time
    match_until = 12 * mu.y + mu.M
    if match_until + 2 <= transition_time:
        return 2

    return 1


def _get_transition_time(year: int, rule: ZoneRule) -> DateTuple:
    """Return the (year, month, day, seconds, suffix) of the Rule in given
    year.
    """
    month, day = calc_day_of_month(
        year,
        rule['in_month'],
        rule['on_day_of_week'],
        rule['on_day_of_month']
    )
    seconds = rule['at_seconds']
    suffix = rule['at_time_suffix']
    return DateTuple(y=year, M=month, d=day, ss=seconds, f=suffix)


def date_tuple_to_string(dt: DateTuple) -> str:
    (h, m, s) = seconds_to_hms(dt.ss)
    return f'{dt.y:04}-{dt.M:02}-{dt.d:02} {h:02}:{m:02}{dt.f}'


def to_utc_string(utcoffset: int, dstoffset: int) -> str:
    return (
        'UTC'
        f'{seconds_to_hm_string(utcoffset)}'
        f'{seconds_to_hm_string(dstoffset)}'
    )


def seconds_to_hm_string(secs: int) -> str:
    if secs < 0:
        hms = seconds_to_hms(-secs)
        return f'-{hms[0]:02}:{hms[1]:02}'
    else:
        hms = seconds_to_hms(secs)
        return f'+{hms[0]:02}:{hms[1]:02}'


def _subtract_date_tuple(a: DateTuple, b: DateTuple) -> int:
    """Number of seconds in (a - b), ignoring the 'format' field.
    """
    da = date(a.y, a.M, a.d)
    db = date(b.y, b.M, b.d)
    diff_days = da.toordinal() - db.toordinal()
    diff_seconds = a.ss - b.ss
    return diff_days * 86400 + diff_seconds
