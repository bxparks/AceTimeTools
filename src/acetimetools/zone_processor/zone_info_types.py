# Copyright 2018 Brian T. Park
#
# MIT License

"""
Data structures required by ZoneSpecifier class. Created inline by
ZoneInfoInliner. Written out to 'zone_policies.py' and 'zone_infos.py' by
pygenerator.py
"""

from typing import Dict
from typing import List
from typing import Union
from typing_extensions import TypedDict

ZoneRule = TypedDict(
    'ZoneRule', {
        'from_year': int,
        'to_year': int,
        'in_month': int,
        'on_day_of_week': int,
        'on_day_of_month': int,
        'at_seconds': int,
        'at_time_suffix': str,
        'delta_seconds': int,
        'letter': str,
    })

ZonePolicy = TypedDict(
    'ZonePolicy', {
        'name': str,
        'rules': List[ZoneRule],
    })

ZonePolicyMap = Dict[str, ZonePolicy]

ZoneEra = TypedDict(
    'ZoneEra', {
        'offset_seconds': int,
        'zone_policy': Union[ZonePolicy, str],  # '-', ':', or ZonePolicy
        'rules_delta_seconds': int,
        'format': str,
        'until_year': int,
        'until_month': int,
        'until_day': int,
        'until_seconds': int,
        'until_time_suffix': str,
    })

ZoneInfo = TypedDict(
    'ZoneInfo', {
        'name': str,
        'eras': List[ZoneEra],
    })

ZoneInfoMap = Dict[str, ZoneInfo]
