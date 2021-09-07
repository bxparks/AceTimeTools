# Copyright 2018 Brian T. Park
#
# MIT License

from typing import cast
import unittest
from datetime import datetime

from acetimetools.zonedbpy import zone_infos
from acetimetools.zone_processor.zone_processor import DateTuple
from acetimetools.zone_processor.zone_processor import Transition
from acetimetools.zone_processor.zone_processor import MatchingEra
from acetimetools.zone_processor.zone_processor import ZoneProcessor
from acetimetools.zone_processor.zone_processor import _get_interior_years
from acetimetools.zone_processor.zone_processor import _compare_transition_to_match  # noqa
from acetimetools.zone_processor.zone_processor import _compare_transition_to_match_fuzzy  # noqa
from acetimetools.zone_processor.zone_processor import _subtract_date_tuple
from acetimetools.zone_processor.zone_processor import _normalize_date_tuple
from acetimetools.zone_processor.zone_info_types import ZoneInfo
from acetimetools.zone_processor.zone_info_types import ZonePolicy


class TestZoneProcessorHelperMethods(unittest.TestCase):
    def test_get_interior_years(self) -> None:
        self.assertEqual([2, 3],
                         sorted(_get_interior_years(1, 4, 2, 3)))
        self.assertEqual([2, 3],
                         sorted(_get_interior_years(0, 4, 2, 3)))
        self.assertEqual([],
                         sorted(_get_interior_years(4, 5, 2, 3)))
        self.assertEqual([],
                         sorted(_get_interior_years(0, 2, 5, 6)))
        self.assertEqual([5],
                         sorted(_get_interior_years(0, 5, 5, 6)))
        self.assertEqual([0, 1, 2],
                         sorted(_get_interior_years(0, 2, 0, 2)))
        self.assertEqual([2, 3, 4],
                         sorted(_get_interior_years(0, 4, 2, 4)))

    def test_expand_date_tuple(self) -> None:
        self.assertEqual((DateTuple(2000, 1, 30, 10800, 'w'),
                          DateTuple(2000, 1, 30, 7200, 's'),
                          DateTuple(2000, 1, 30, 0, 'u')),
                         ZoneProcessor._expand_date_tuple(
                             DateTuple(2000, 1, 30, 10800, 'w'),
                             offset_seconds=7200,
                             delta_seconds=3600))

        self.assertEqual((DateTuple(2000, 1, 30, 10800, 'w'),
                          DateTuple(2000, 1, 30, 7200, 's'),
                          DateTuple(2000, 1, 30, 0, 'u')),
                         ZoneProcessor._expand_date_tuple(
                             DateTuple(2000, 1, 30, 7200, 's'),
                             offset_seconds=7200,
                             delta_seconds=3600))

        self.assertEqual((DateTuple(2000, 1, 30, 10800, 'w'),
                          DateTuple(2000, 1, 30, 7200, 's'),
                          DateTuple(2000, 1, 30, 0, 'u')),
                         ZoneProcessor._expand_date_tuple(
                             DateTuple(2000, 1, 30, 0, 'u'),
                             offset_seconds=7200,
                             delta_seconds=3600))

    def test_normalize_date_tuple(self) -> None:
        self.assertEqual(
            DateTuple(2000, 2, 1, 0, 'w'),
            _normalize_date_tuple(DateTuple(2000, 2, 1, 0, 'w')))

        self.assertEqual(
            DateTuple(2000, 2, 1, 0, 's'),
            _normalize_date_tuple(DateTuple(2000, 1, 31, 24 * 3600, 's')))

        self.assertEqual(
            DateTuple(2000, 2, 29, 23 * 3600, 'u'),
            _normalize_date_tuple(DateTuple(2000, 3, 1, -3600, 'u')))

    def test_subtract_date_tuple(self) -> None:
        self.assertEqual(
            -1,
            _subtract_date_tuple(
                DateTuple(2000, 1, 1, 43, 'w'),
                DateTuple(2000, 1, 1, 44, 'w'),
            )
        )

        self.assertEqual(
            24 * 3600 - 1,
            _subtract_date_tuple(
                DateTuple(2000, 1, 2, 43, 'w'),
                DateTuple(2000, 1, 1, 44, 'w'),
            )
        )

        self.assertEqual(
            -31 * 24 * 3600 + 24 * 3600 - 1,
            _subtract_date_tuple(
                DateTuple(2000, 1, 2, 43, 'w'),
                DateTuple(2000, 2, 1, 44, 'w'),
            )
        )


class TestCompareTransitionToMatch(unittest.TestCase):
    def test_compare_exact(self) -> None:
        match = MatchingEra({
            'start_date_time': DateTuple(2000, 1, 1, 0, 'w'),
            'until_date_time': DateTuple(2001, 1, 1, 0, 'w')
        })

        transition = Transition({
            'transition_time':
            DateTuple(1999, 12, 31, 0, 'w')
        })
        self.assertEqual(-1, _compare_transition_to_match(transition, match))

        transition = Transition({
            'transition_time': DateTuple(2000, 1, 1, 0, 'w')
        })
        self.assertEqual(0, _compare_transition_to_match(transition, match))

        transition = Transition({
            'transition_time': DateTuple(2000, 1, 2, 0, 'w')
        })
        self.assertEqual(1, _compare_transition_to_match(transition, match))

        transition = Transition({
            'transition_time': DateTuple(2001, 1, 2, 0, 'w')
        })
        self.assertEqual(2, _compare_transition_to_match(transition, match))

    def test_compare_fuzzy(self) -> None:
        match = MatchingEra({
            'start_date_time': DateTuple(2000, 1, 1, 0, 'w'),
            'until_date_time': DateTuple(2001, 1, 1, 0, 'w')
        })

        transition = Transition({
            'transition_time':
            DateTuple(1999, 11, 1, 0, 'w')
        })
        self.assertEqual(-1,
                         _compare_transition_to_match_fuzzy(transition, match))

        transition = Transition({
            'transition_time':
            DateTuple(1999, 12, 1, 0, 'w')
        })
        self.assertEqual(1,
                         _compare_transition_to_match_fuzzy(transition, match))

        transition = Transition({
            'transition_time': DateTuple(2000, 1, 1, 0, 'w')
        })
        self.assertEqual(1,
                         _compare_transition_to_match_fuzzy(transition, match))

        transition = Transition({
            'transition_time': DateTuple(2001, 1, 1, 0, 'w')
        })
        self.assertEqual(1,
                         _compare_transition_to_match_fuzzy(transition, match))

        transition = Transition({
            'transition_time': DateTuple(2001, 2, 1, 0, 'w')
        })
        self.assertEqual(1,
                         _compare_transition_to_match_fuzzy(transition, match))

        transition = Transition({
            'transition_time': DateTuple(2001, 3, 1, 0, 'w')
        })
        self.assertEqual(2,
                         _compare_transition_to_match_fuzzy(transition, match))


class TestZoneProcessorMatchesAndTransitions(unittest.TestCase):
    def test_Los_Angeles(self) -> None:
        """America/Los_Angela uses a simple US rule.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_America_Los_Angeles),
        )
        zone_processor.init_for_year(2000)

        matches = zone_processor.matches
        self.assertEqual(1, len(matches))

        self.assertEqual(
            DateTuple(1999, 12, 1, 0, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2001, 2, 1, 0, 'w'), matches[0].until_date_time)
        zone_policy = cast(ZonePolicy, matches[0].zone_era['zone_policy'])
        self.assertEqual('US', zone_policy['name'])

        transitions = zone_processor.transitions
        self.assertEqual(3, len(transitions))

        self.assertEqual(
            DateTuple(1999, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2000, 4, 2, 2 * 3600, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(-8 * 3600, transitions[0].offset_seconds)
        self.assertEqual(0, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2000, 4, 2, 3 * 3600, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2000, 10, 29, 2 * 3600, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(-8 * 3600, transitions[1].offset_seconds)
        self.assertEqual(1 * 3600, transitions[1].delta_seconds)

        self.assertEqual(
            DateTuple(2000, 10, 29, 1 * 3600, 'w'),
            transitions[2].start_date_time)
        self.assertEqual(
            DateTuple(2001, 2, 1, 0, 'w'), transitions[2].until_date_time)
        self.assertEqual(-8 * 3600, transitions[2].offset_seconds)
        self.assertEqual(0 * 3600, transitions[2].delta_seconds)

    def test_Petersburg(self) -> None:
        """America/Indianapolis/Petersbug moved from central to eastern time in
        1977, then switched back in 2006, then switched back again in 2007.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_America_Indiana_Petersburg),
        )
        zone_processor.init_for_year(2006)

        matches = zone_processor.matches
        self.assertEqual(2, len(matches))

        self.assertEqual(
            DateTuple(2005, 12, 1, 0, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2006, 4, 2, 2 * 3600, 'w'), matches[0].until_date_time)
        self.assertEqual('-', matches[0].zone_era['zone_policy'])

        self.assertEqual(
            DateTuple(2006, 4, 2, 2 * 3600, 'w'), matches[1].start_date_time)
        self.assertEqual(
            DateTuple(2007, 2, 1, 0, 'w'), matches[1].until_date_time)
        zone_policy = cast(ZonePolicy, matches[1].zone_era['zone_policy'])
        self.assertEqual('US', zone_policy['name'])

        transitions = zone_processor.transitions
        self.assertEqual(3, len(transitions))

        self.assertEqual(
            DateTuple(2005, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2006, 4, 2, 2 * 3600, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(-5 * 3600, transitions[0].offset_seconds)
        self.assertEqual(0 * 3600, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2006, 4, 2, 2 * 3600, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2006, 10, 29, 2 * 3600, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(-6 * 3600, transitions[1].offset_seconds)
        self.assertEqual(1 * 3600, transitions[1].delta_seconds)

        self.assertEqual(
            DateTuple(2006, 10, 29, 1 * 3600, 'w'),
            transitions[2].start_date_time)
        self.assertEqual(
            DateTuple(2007, 2, 1, 0, 'w'), transitions[2].until_date_time)
        self.assertEqual(-6 * 3600, transitions[2].offset_seconds)
        self.assertEqual(0 * 3600, transitions[2].delta_seconds)

    def test_London(self) -> None:
        """Europe/London uses a EU which has a 'u' in the AT field.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_Europe_London),
        )
        zone_processor.init_for_year(2000)

        matches = zone_processor.matches
        self.assertEqual(1, len(matches))

        self.assertEqual(
            DateTuple(1999, 12, 1, 0, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2001, 2, 1, 0, 'w'), matches[0].until_date_time)
        zone_policy = cast(ZonePolicy, matches[0].zone_era['zone_policy'])
        self.assertEqual('EU', zone_policy['name'])

        transitions = zone_processor.transitions
        self.assertEqual(3, len(transitions))

        self.assertEqual(
            DateTuple(1999, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2000, 3, 26, 1 * 3600, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(0 * 3600, transitions[0].offset_seconds)
        self.assertEqual(0 * 3600, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2000, 3, 26, 2 * 3600, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2000, 10, 29, 2 * 3600, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(0 * 3600, transitions[1].offset_seconds)
        self.assertEqual(1 * 3600, transitions[1].delta_seconds)

        self.assertEqual(
            DateTuple(2000, 10, 29, 1 * 3600, 'w'),
            transitions[2].start_date_time)
        self.assertEqual(
            DateTuple(2001, 2, 1, 0, 'w'), transitions[2].until_date_time)
        self.assertEqual(0 * 3600, transitions[2].offset_seconds)
        self.assertEqual(0 * 3600, transitions[2].delta_seconds)

    def test_Winnipeg(self) -> None:
        """America/Winnipeg uses 'Rule Winn' until 2006 which has an 's' suffix
        in the Rule.AT field.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_America_Winnipeg),
        )
        zone_processor.init_for_year(2005)

        matches = zone_processor.matches
        self.assertEqual(2, len(matches))

        self.assertEqual(
            DateTuple(2004, 12, 1, 0, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2006, 1, 1, 0 * 3600, 'w'), matches[0].until_date_time)
        zone_policy = cast(ZonePolicy, matches[0].zone_era['zone_policy'])
        self.assertEqual('Winn', zone_policy['name'])

        self.assertEqual(
            DateTuple(2006, 1, 1, 0 * 3600, 'w'), matches[1].start_date_time)
        self.assertEqual(
            DateTuple(2006, 2, 1, 0 * 3600, 'w'), matches[1].until_date_time)
        zone_policy = cast(ZonePolicy, matches[1].zone_era['zone_policy'])
        self.assertEqual('Canada', zone_policy['name'])

        transitions = zone_processor.transitions
        self.assertEqual(4, len(transitions))

        self.assertEqual(
            DateTuple(2004, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2005, 4, 3, 2 * 3600, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(-6 * 3600, transitions[0].offset_seconds)
        self.assertEqual(0 * 3600, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2005, 4, 3, 3 * 3600, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2005, 10, 30, 3 * 3600, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(-6 * 3600, transitions[1].offset_seconds)
        self.assertEqual(1 * 3600, transitions[1].delta_seconds)

        self.assertEqual(
            DateTuple(2005, 10, 30, 2 * 3600, 'w'),
            transitions[2].start_date_time)
        self.assertEqual(
            DateTuple(2006, 1, 1, 0, 'w'), transitions[2].until_date_time)
        self.assertEqual(-6 * 3600, transitions[2].offset_seconds)
        self.assertEqual(0 * 3600, transitions[2].delta_seconds)

        self.assertEqual(
            DateTuple(2006, 1, 1, 0 * 3600, 'w'),
            transitions[3].start_date_time)
        self.assertEqual(
            DateTuple(2006, 2, 1, 0, 'w'), transitions[3].until_date_time)
        self.assertEqual(-6 * 3600, transitions[3].offset_seconds)
        self.assertEqual(0 * 3600, transitions[3].delta_seconds)

    def test_Moscow(self) -> None:
        """Europe/Moscow uses 's' in the Zone UNTIL field.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_Europe_Moscow),
        )
        zone_processor.init_for_year(2011)

        matches = zone_processor.matches
        self.assertEqual(2, len(matches))

        self.assertEqual(
            DateTuple(2010, 12, 1, 0, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2011, 3, 27, 2 * 3600, 's'), matches[0].until_date_time)
        zone_policy = cast(ZonePolicy, matches[0].zone_era['zone_policy'])
        self.assertEqual('Russia', zone_policy['name'])

        self.assertEqual(
            DateTuple(2011, 3, 27, 2 * 3600, 's'), matches[1].start_date_time)
        self.assertEqual(
            DateTuple(2012, 2, 1, 0, 'w'), matches[1].until_date_time)
        self.assertEqual('-', matches[1].zone_era['zone_policy'])

        transitions = zone_processor.transitions
        self.assertEqual(2, len(transitions))

        self.assertEqual(
            DateTuple(2010, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2011, 3, 27, 2 * 3600, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(3 * 3600, transitions[0].offset_seconds)
        self.assertEqual(0 * 3600, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2011, 3, 27, 3 * 3600, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2012, 2, 1, 0 * 3600, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(4 * 3600, transitions[1].offset_seconds)
        self.assertEqual(0 * 3600, transitions[1].delta_seconds)

    def test_Famagusta(self) -> None:
        """Asia/Famagusta uses 'u' in the Zone UNTIL field.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_Asia_Famagusta),
        )
        zone_processor.init_for_year(2017)

        matches = zone_processor.matches
        self.assertEqual(2, len(matches))

        self.assertEqual(
            DateTuple(2016, 12, 1, 0, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2017, 10, 29, 1 * 3600, 'u'), matches[0].until_date_time)
        self.assertEqual('-', matches[0].zone_era['zone_policy'])

        self.assertEqual(
            DateTuple(2017, 10, 29, 1 * 3600, 'u'), matches[1].start_date_time)
        self.assertEqual(
            DateTuple(2018, 2, 1, 0, 'w'), matches[1].until_date_time)
        zone_policy = cast(ZonePolicy, matches[1].zone_era['zone_policy'])
        self.assertEqual('EUAsia', zone_policy['name'])

        transitions = zone_processor.transitions
        self.assertEqual(2, len(transitions))

        self.assertEqual(
            DateTuple(2016, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2017, 10, 29, 4 * 3600, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(3 * 3600, transitions[0].offset_seconds)
        self.assertEqual(0 * 3600, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2017, 10, 29, 3 * 3600, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2018, 2, 1, 0 * 3600, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(2 * 3600, transitions[1].offset_seconds)
        self.assertEqual(0 * 3600, transitions[1].delta_seconds)

    def test_Santo_Domingo(self) -> None:
        """America/Santo_Domingo uses 2 ZoneEra changes in year 2000.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_America_Santo_Domingo),
        )
        zone_processor.init_for_year(2000)

        matches = zone_processor.matches
        self.assertEqual(3, len(matches))

        self.assertEqual(
            DateTuple(1999, 12, 1, 0, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2000, 10, 29, 2 * 3600, 'w'), matches[0].until_date_time)
        self.assertEqual('-', matches[0].zone_era['zone_policy'])

        self.assertEqual(
            DateTuple(2000, 10, 29, 2 * 3600, 'w'), matches[1].start_date_time)
        self.assertEqual(
            DateTuple(2000, 12, 3, 1 * 3600, 'w'), matches[1].until_date_time)
        zone_policy = cast(ZonePolicy, matches[1].zone_era['zone_policy'])
        self.assertEqual('US', zone_policy['name'])

        self.assertEqual(
            DateTuple(2000, 12, 3, 1 * 3600, 'w'), matches[2].start_date_time)
        self.assertEqual(
            DateTuple(2001, 2, 1, 0, 'w'), matches[2].until_date_time)
        self.assertEqual('-', matches[2].zone_era['zone_policy'])

        transitions = zone_processor.transitions
        self.assertEqual(3, len(transitions))

        self.assertEqual(
            DateTuple(1999, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2000, 10, 29, 2 * 3600, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(-4 * 3600, transitions[0].offset_seconds)
        self.assertEqual(0 * 3600, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2000, 10, 29, 1 * 3600, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2000, 12, 3, 1 * 3600, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(-5 * 3600, transitions[1].offset_seconds)
        self.assertEqual(0 * 3600, transitions[1].delta_seconds)

        self.assertEqual(
            DateTuple(2000, 12, 3, 2 * 3600, 'w'),
            transitions[2].start_date_time)
        self.assertEqual(
            DateTuple(2001, 2, 1, 0, 'w'), transitions[2].until_date_time)
        self.assertEqual(-4 * 3600, transitions[2].offset_seconds)
        self.assertEqual(0 * 3600, transitions[2].delta_seconds)

    def test_Moncton(self) -> None:
        """America/Moncton transitioned DST at 00:01 through 2006.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_America_Moncton),
        )
        zone_processor.init_for_year(2006)

        matches = zone_processor.matches
        self.assertEqual(2, len(matches))

        self.assertEqual(
            DateTuple(2005, 12, 1, 0, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2007, 1, 1, 0 * 3600, 'w'), matches[0].until_date_time)
        zone_policy = cast(ZonePolicy, matches[0].zone_era['zone_policy'])
        self.assertEqual('Moncton', zone_policy['name'])

        self.assertEqual(
            DateTuple(2007, 1, 1, 0 * 3600, 'w'), matches[1].start_date_time)
        self.assertEqual(
            DateTuple(2007, 2, 1, 0, 'w'), matches[1].until_date_time)
        zone_policy = cast(ZonePolicy, matches[1].zone_era['zone_policy'])
        self.assertEqual('Canada', zone_policy['name'])

        transitions = zone_processor.transitions
        self.assertEqual(4, len(transitions))

        self.assertEqual(
            DateTuple(2005, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2006, 4, 2, 0 * 3600 + 60, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(-4 * 3600, transitions[0].offset_seconds)
        self.assertEqual(0 * 3600, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2006, 4, 2, 1 * 3600 + 60, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2006, 10, 29, 0 * 3600 + 60, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(-4 * 3600, transitions[1].offset_seconds)
        self.assertEqual(1 * 3600, transitions[1].delta_seconds)

        self.assertEqual(
            DateTuple(2006, 10, 28, 23 * 3600 + 60, 'w'),
            transitions[2].start_date_time)
        self.assertEqual(
            DateTuple(2007, 1, 1, 0, 'w'), transitions[2].until_date_time)
        self.assertEqual(-4 * 3600, transitions[2].offset_seconds)
        self.assertEqual(0 * 3600, transitions[2].delta_seconds)

        self.assertEqual(
            DateTuple(2007, 1, 1, 0 * 3600, 'w'),
            transitions[3].start_date_time)
        self.assertEqual(
            DateTuple(2007, 2, 1, 0, 'w'), transitions[3].until_date_time)
        self.assertEqual(-4 * 3600, transitions[3].offset_seconds)
        self.assertEqual(0 * 3600, transitions[3].delta_seconds)

    def test_Istanbul(self) -> None:
        """Europe/Istanbul uses an 'hh:mm' offset in the RULES field in 2015.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_Europe_Istanbul),
        )
        zone_processor.init_for_year(2015)

        matches = zone_processor.matches
        self.assertEqual(3, len(matches))

        self.assertEqual(
            DateTuple(2014, 12, 1, 0, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2015, 10, 25, 1 * 3600, 'u'), matches[0].until_date_time)
        zone_policy = cast(ZonePolicy, matches[0].zone_era['zone_policy'])
        self.assertEqual('EU', zone_policy['name'])

        self.assertEqual(
            DateTuple(2015, 10, 25, 1 * 3600, 'u'), matches[1].start_date_time)
        self.assertEqual(
            DateTuple(2015, 11, 8, 1 * 3600, 'u'), matches[1].until_date_time)
        self.assertEqual(':', matches[1].zone_era['zone_policy'])

        self.assertEqual(
            DateTuple(2015, 11, 8, 1 * 3600, 'u'), matches[2].start_date_time)
        self.assertEqual(
            DateTuple(2016, 2, 1, 0, 'w'), matches[2].until_date_time)
        zone_policy = cast(ZonePolicy, matches[2].zone_era['zone_policy'])
        self.assertEqual('EU', zone_policy['name'])

        transitions = zone_processor.transitions
        self.assertEqual(4, len(transitions))

        self.assertEqual(
            DateTuple(2014, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2015, 3, 29, 3 * 3600, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(2 * 3600, transitions[0].offset_seconds)
        self.assertEqual(0 * 3600, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2015, 3, 29, 4 * 3600, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2015, 10, 25, 4 * 3600, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(2 * 3600, transitions[1].offset_seconds)
        self.assertEqual(1 * 3600, transitions[1].delta_seconds)

        self.assertEqual(
            DateTuple(2015, 10, 25, 4 * 3600, 'w'),
            transitions[2].start_date_time)
        self.assertEqual(
            DateTuple(2015, 11, 8, 4 * 3600, 'w'),
            transitions[2].until_date_time)
        self.assertEqual(2 * 3600, transitions[2].offset_seconds)
        self.assertEqual(1 * 3600, transitions[2].delta_seconds)

        self.assertEqual(
            DateTuple(2015, 11, 8, 3 * 3600, 'w'),
            transitions[3].start_date_time)
        self.assertEqual(
            DateTuple(2016, 2, 1, 0, 'w'), transitions[3].until_date_time)
        self.assertEqual(2 * 3600, transitions[3].offset_seconds)
        self.assertEqual(0 * 3600, transitions[3].delta_seconds)

    def test_Dublin(self) -> None:
        """Europe/Dublin uses negative DST during Winter.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_Europe_Dublin),
        )
        zone_processor.init_for_year(2000)

        matches = zone_processor.matches
        self.assertEqual(1, len(matches))

        self.assertEqual(
            DateTuple(1999, 12, 1, 0, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2001, 2, 1, 0, 'w'), matches[0].until_date_time)
        zone_policy = cast(ZonePolicy, matches[0].zone_era['zone_policy'])
        self.assertEqual('Eire', zone_policy['name'])

        transitions = zone_processor.transitions
        self.assertEqual(3, len(transitions))

        self.assertEqual(
            DateTuple(1999, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2000, 3, 26, 1 * 3600, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(1 * 3600, transitions[0].offset_seconds)
        self.assertEqual(-1 * 3600, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2000, 3, 26, 2 * 3600, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2000, 10, 29, 2 * 3600, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(1 * 3600, transitions[1].offset_seconds)
        self.assertEqual(0 * 3600, transitions[1].delta_seconds)

        self.assertEqual(
            DateTuple(2000, 10, 29, 1 * 3600, 'w'),
            transitions[2].start_date_time)
        self.assertEqual(
            DateTuple(2001, 2, 1, 0, 'w'), transitions[2].until_date_time)
        self.assertEqual(1 * 3600, transitions[2].offset_seconds)
        self.assertEqual(-1 * 3600, transitions[2].delta_seconds)

    def test_Apia(self) -> None:
        """Pacific/Apia uses a transition time of 24:00 on Dec 29, 2011,
        going from Thursday 29th December 2011 23:59:59 Hours to Saturday 31st
        December 2011 00:00:00 Hours.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_Pacific_Apia),
        )
        zone_processor.init_for_year(2011)

        matches = zone_processor.matches
        self.assertEqual(2, len(matches))

        self.assertEqual(
            DateTuple(2010, 12, 1, 0, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2011, 12, 29, 24 * 3600, 'w'), matches[0].until_date_time)
        zone_policy = cast(ZonePolicy, matches[0].zone_era['zone_policy'])
        self.assertEqual('WS', zone_policy['name'])

        self.assertEqual(
            DateTuple(2011, 12, 29, 24 * 3600, 'w'), matches[1].start_date_time)
        self.assertEqual(
            DateTuple(2012, 2, 1, 0, 'w'), matches[1].until_date_time)
        zone_policy = cast(ZonePolicy, matches[1].zone_era['zone_policy'])
        self.assertEqual('WS', zone_policy['name'])

        transitions = zone_processor.transitions
        self.assertEqual(4, len(transitions))

        self.assertEqual(
            DateTuple(2010, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2011, 4, 2, 4 * 3600, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(-11 * 3600, transitions[0].offset_seconds)
        self.assertEqual(1 * 3600, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2011, 4, 2, 3 * 3600, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2011, 9, 24, 3 * 3600, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(-11 * 3600, transitions[1].offset_seconds)
        self.assertEqual(0 * 3600, transitions[1].delta_seconds)

        self.assertEqual(
            DateTuple(2011, 9, 24, 4 * 3600, 'w'),
            transitions[2].start_date_time)
        self.assertEqual(
            DateTuple(2011, 12, 30, 0, 'w'), transitions[2].until_date_time)
        self.assertEqual(-11 * 3600, transitions[2].offset_seconds)
        self.assertEqual(1 * 3600, transitions[2].delta_seconds)

        self.assertEqual(
            DateTuple(2011, 12, 31, 0 * 3600, 'w'),
            transitions[3].start_date_time)
        self.assertEqual(
            DateTuple(2012, 2, 1, 0, 'w'), transitions[3].until_date_time)
        self.assertEqual(13 * 3600, transitions[3].offset_seconds)
        self.assertEqual(1 * 3600, transitions[3].delta_seconds)

    def test_Macquarie(self) -> None:
        """Antarctica/Macquarie changes ZoneEra in 2011 using a 'w' time, but
        the ZoneRule transitions use an 's' time, which happens to coincide with
        the change in ZoneEra. The code must treat those 2 transition times as
        the same point in time.

        In TZ version 2020b (specifically commit
        6427fe6c0cca1dc0f8580f8b96348911ad051570 for github.com/eggert/tz on Thu
        Oct 1 23:59:18 2020) adds an additional ZoneEra line for 2010, changing
        this from 2 to 3. Antarctica/Macquarie stays on AEDT all year in 2010.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_Antarctica_Macquarie),
        )
        zone_processor.init_for_year(2010)

        matches = zone_processor.matches
        self.assertEqual(3, len(matches))

        # Match 0
        self.assertEqual(
            DateTuple(2009, 12, 1, 0, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2010, 1, 1, 0, 'w'), matches[0].until_date_time)
        zone_policy = cast(ZonePolicy, matches[0].zone_era['zone_policy'])
        self.assertEqual('AT', zone_policy['name'])

        # Match 1
        self.assertEqual(
            DateTuple(2010, 1, 1, 0, 'w'), matches[1].start_date_time)
        self.assertEqual(
            DateTuple(2011, 1, 1, 0, 'w'), matches[1].until_date_time)
        self.assertEqual(':', matches[1].zone_era['zone_policy'])

        # Match 2
        self.assertEqual(
            DateTuple(2011, 1, 1, 0, 'w'), matches[2].start_date_time)
        self.assertEqual(
            DateTuple(2011, 2, 1, 0, 'w'), matches[2].until_date_time)
        zone_policy = cast(ZonePolicy, matches[2].zone_era['zone_policy'])
        self.assertEqual('AT', zone_policy['name'])

        transitions = zone_processor.transitions
        self.assertEqual(3, len(transitions))

        # Transition 0
        self.assertEqual(
            DateTuple(2009, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2010, 1, 1, 0, 'w'), transitions[0].until_date_time)
        self.assertEqual(10 * 3600, transitions[0].offset_seconds)
        self.assertEqual(1 * 3600, transitions[0].delta_seconds)

        # Transition 1
        self.assertEqual(
            DateTuple(2010, 1, 1, 0, 'w'), transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2011, 1, 1, 0, 'w'), transitions[1].until_date_time)
        self.assertEqual(10 * 3600, transitions[1].offset_seconds)
        self.assertEqual(1 * 3600, transitions[1].delta_seconds)

        # Transition 2
        self.assertEqual(
            DateTuple(2011, 1, 1, 0, 'w'), transitions[2].start_date_time)
        self.assertEqual(
            DateTuple(2011, 2, 1, 0, 'w'), transitions[2].until_date_time)
        self.assertEqual(10 * 3600, transitions[2].offset_seconds)
        self.assertEqual(1 * 3600, transitions[2].delta_seconds)

    def test_Simferopol(self) -> None:
        """Asia/Simferopol in 2014 uses a bizarre mixture of 'w' when using EU
        rules (which itself uses 'u' in the UNTIL fields), then uses 's' time to
        switch to Moscow time.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_Europe_Simferopol),
        )
        zone_processor.init_for_year(2014)

        matches = zone_processor.matches
        self.assertEqual(3, len(matches))

        self.assertEqual(
            DateTuple(2013, 12, 1, 0 * 3600, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2014, 3, 30, 2 * 3600, 'w'), matches[0].until_date_time)
        zone_policy = cast(ZonePolicy, matches[0].zone_era['zone_policy'])
        self.assertEqual('EU', zone_policy['name'])

        self.assertEqual(
            DateTuple(2014, 3, 30, 2 * 3600, 'w'), matches[1].start_date_time)
        self.assertEqual(
            DateTuple(2014, 10, 26, 2 * 3600, 's'), matches[1].until_date_time)
        self.assertEqual('-', matches[1].zone_era['zone_policy'])

        self.assertEqual(
            DateTuple(2014, 10, 26, 2 * 3600, 's'), matches[2].start_date_time)
        self.assertEqual(
            DateTuple(2015, 2, 1, 0 * 3600, 'w'), matches[2].until_date_time)
        self.assertEqual('-', matches[2].zone_era['zone_policy'])

        transitions = zone_processor.transitions
        self.assertEqual(3, len(transitions))

        self.assertEqual(
            DateTuple(2013, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2014, 3, 30, 2 * 3600, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(2 * 3600, transitions[0].offset_seconds)
        self.assertEqual(0 * 3600, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2014, 3, 30, 4 * 3600, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2014, 10, 26, 2 * 3600, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(4 * 3600, transitions[1].offset_seconds)
        self.assertEqual(0 * 3600, transitions[1].delta_seconds)

        self.assertEqual(
            DateTuple(2014, 10, 26, 1 * 3600, 'w'),
            transitions[2].start_date_time)
        self.assertEqual(
            DateTuple(2015, 2, 1, 0 * 3600, 'w'),
            transitions[2].until_date_time)
        self.assertEqual(3 * 3600, transitions[2].offset_seconds)
        self.assertEqual(0 * 3600, transitions[2].delta_seconds)

    def test_Kamchatka(self) -> None:
        """Asia/Kamchatka uses 's' in the Zone UNTIL and Rule AT fields.
        """
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_Asia_Kamchatka),
        )
        zone_processor.init_for_year(2011)

        matches = zone_processor.matches
        self.assertEqual(2, len(matches))

        self.assertEqual(
            DateTuple(2010, 12, 1, 0 * 3600, 'w'), matches[0].start_date_time)
        self.assertEqual(
            DateTuple(2011, 3, 27, 2 * 3600, 's'), matches[0].until_date_time)
        zone_policy = cast(ZonePolicy, matches[0].zone_era['zone_policy'])
        self.assertEqual('Russia', zone_policy['name'])

        self.assertEqual(
            DateTuple(2011, 3, 27, 2 * 3600, 's'), matches[1].start_date_time)
        self.assertEqual(
            DateTuple(2012, 2, 1, 0 * 3600, 'w'), matches[1].until_date_time)
        self.assertEqual('-', matches[1].zone_era['zone_policy'])

        transitions = zone_processor.transitions
        self.assertEqual(2, len(transitions))

        self.assertEqual(
            DateTuple(2010, 12, 1, 0, 'w'), transitions[0].start_date_time)
        self.assertEqual(
            DateTuple(2011, 3, 27, 2 * 3600, 'w'),
            transitions[0].until_date_time)
        self.assertEqual(11 * 3600, transitions[0].offset_seconds)
        self.assertEqual(0 * 3600, transitions[0].delta_seconds)

        self.assertEqual(
            DateTuple(2011, 3, 27, 3 * 3600, 'w'),
            transitions[1].start_date_time)
        self.assertEqual(
            DateTuple(2012, 2, 1, 0 * 3600, 'w'),
            transitions[1].until_date_time)
        self.assertEqual(12 * 3600, transitions[1].offset_seconds)
        self.assertEqual(0 * 3600, transitions[1].delta_seconds)


class TestZoneProcessorGetTransition(unittest.TestCase):
    def test_get_transition_for_datetime(self) -> None:
        zone_processor = ZoneProcessor(
            cast(ZoneInfo, zone_infos.ZONE_INFO_America_Los_Angeles),
        )

        # Just after a DST transition
        dt = datetime(2000, 4, 2, 3, 0, 0)
        transition = zone_processor.get_transition_for_datetime(dt)
        self.assertIsNotNone(transition)

        # DST gap does not exist, but a transition should be returned.
        dt = datetime(2000, 4, 2, 2, 59, 59)
        transition = zone_processor.get_transition_for_datetime(dt)
        self.assertIsNotNone(transition)
