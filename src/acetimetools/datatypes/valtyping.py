# Copyright 2020 Brian T. Park
#
# MIT License
#
"""
Data types for representing the time zone validation data. The ValidationData
type can be serialized to JSON directly. The JSON looks like:
{
  'start_year': int,
  'until_year': int,
  'epoch_year': int,
  'scope': str,
  'source': str,
  'version': str,
  'tz_version': str,
  'has_valid_abbrev': bool,
  'has_valid_dst': bool,
  'offset_granularity': int,
  'test_data': {
    '{zone_name}: {
      "transitions": [
        {
        'epoch': int,
        'total_offset': int,
        'dst_offset': int,
        'y': int,
        'M': int,
        'd': int,
        'h': int,
        'm': int,
        's': int,
        'abbrev': str,
        'type', str,
        },
        {...}
      ],
      "samples": [
        {...},
      ]
    },
    {...}
  },
}
"""

from typing import List, Dict, Optional
from typing_extensions import TypedDict

# An entry in the test data set.
# Each TestData is annotated with a 'type' as:
# * 'A': pre-transition where the UTC offset is different
# * 'B': post-transition where the UTC offset is different
# * 'a': pre-transition where only the DST offset is different
# * 'b': post-transition where only the DST offset is different
# * 'S': a monthly test sample, on the 1st day of the month
# * 'T': a monthly test sample, if the 1st was invalid for some reason
# * 'Y': end of year test sample
TestItem = TypedDict("TestItem", {
    'epoch': int,  # seconds from AceTime epoch (usually 2050-01-01)
    'total_offset': int,  # total UTC offset in seconds
    'dst_offset': int,  # DST offset in seconds
    'y': int,
    'M': int,
    'd': int,
    'h': int,
    'm': int,
    's': int,
    'abbrev': Optional[str],
    'type': str,
})

# Test entry is the set of transitions and samples for a single zone.
TestEntry = TypedDict('TestEntry', {
    'transitions': List[TestItem],
    'samples': List[TestItem],
})

# The test data set {zone_name -> TestEntry}
TestData = Dict[str, TestEntry]

# The top-level validation data collection. This can be serialized to JSON.
ValidationData = TypedDict('ValidationData', {
    'start_year': int,
    'until_year': int,
    'epoch_year': int,
    'scope': str,
    'source': str,
    'version': str,
    'tz_version': str,
    'has_valid_abbrev': bool,  # 'abbrev' values are reliable
    'has_valid_dst': bool,  # DST offsets are reliable
    'offset_granularity': int,  # total UTC offset resolution
    'test_data': TestData,
})
