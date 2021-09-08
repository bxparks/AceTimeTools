# Copyright 2019 Brian T. Park
#
# MIT License

from typing import List, Tuple
from typing import NamedTuple
import logging
from collections import OrderedDict

from acetimetools.data_types.at_types import ZonesMap, PoliciesMap
from acetimetools.data_types.at_types import BufSizeMap, CountAndYear
from .zone_processor import ZoneProcessor
from .zone_info_types import ZoneInfoMap
from .zone_info_inliner import ZoneInfoInliner


class MaxBufferSizeInfo(NamedTuple):
    """A tuple containings the number of active transitions and the current
    buffer_size of TransitionStorage.
    """
    max_active_size: CountAndYear
    max_buffer_size: CountAndYear


class BufSizeEstimator:
    """Estimate the buffer size of the C++
    ExtendedZoneProcessor::TransitionStorage class for each zone.
    """

    def __init__(
        self,
        zones_map: ZonesMap,
        policies_map: PoliciesMap,
        start_year: int,
        until_year: int,
    ):
        """
        Args:
            zone_infos: dict of ZoneInfos
            zone_policies dict of ZonePolicies
            start_year: start year
            until_year: until year
        """
        self.zones_map = zones_map
        self.policies_map = policies_map
        self.start_year = start_year
        self.until_year = until_year

    def calculate_buf_size_map(self) -> BufSizeMap:
        """Calculate the (dict) of {full_name -> (max_buffer_size, year)} where
        max_buffer_size is the maximum TransitionStorage buffer size required by
        ZoneProcessor across [start_year, until_year), and year is the year in
        which the maximum occurred.
        """
        # Generate internal zone_infos and zone_policies to be used by
        # ZoneProcessor.
        zone_info_inliner = ZoneInfoInliner(self.zones_map, self.policies_map)
        zone_infos, zone_policies = zone_info_inliner.generate_zonedb()
        logging.info(
            'ZoneInfoInliner: Zones %d; Policies %d',
            len(zone_infos), len(zone_policies))

        # Calculate expected buffer sizes for each zone using a ZoneProcessor.
        buf_size_map = _calculate_buf_sizes_per_zone(
            zone_infos,
            self.start_year,
            self.until_year,
        )

        return OrderedDict(sorted(buf_size_map.items()))


def calculate_max_buf_size(buf_sizes: BufSizeMap) -> int:
    """Calculate the maximum Transition buffer size, across all zones,
    over all years from [start_year, until_year).
    """
    # Determine the maximum buffer size, the zone(s) which generate that
    # size, and the year which that occurs.
    max_buf_size = max([cy.number for cy in buf_sizes.values()])

    # Determine the zone and year when the max_buf_size occurred.
    # item[0]: str = key = zone name
    # item[1]: CountAndYear = max buffer size and year
    max_buf_zones: List[Tuple[str, int]] = [
        (item[0], item[1].year) for item in filter(
            lambda item: item[1].number == max_buf_size,
            buf_sizes.items()
        )
    ]

    logging.info('Found max_buffer_size=%d', max_buf_size)
    for item in max_buf_zones:
        logging.info('  %s in %d', item[0], item[1])

    return max_buf_size


def _calculate_buf_sizes_per_zone(
    zone_infos: ZoneInfoMap,
    start_year: int,
    until_year: int,
) -> BufSizeMap:
    """
    Return the maximum active transition size and maximum buffer size for each
    zone listed in zone_infos.
    """
    buf_sizes: BufSizeMap = {}
    for zone_name, zone_info in zone_infos.items():
        zone_processor = ZoneProcessor(zone_info)

        # Calculate max_actives(count, year) and max_buffer_size(count, year).
        max_buffer_size_info = _find_max_buffer_sizes(
            zone_processor,
            start_year=start_year,
            until_year=until_year,
        )

        # Currently, we just care about the max buffer size, not the max
        # active size.
        buf_sizes[zone_name] = max_buffer_size_info.max_buffer_size

    return buf_sizes


def _find_max_buffer_sizes(
    zone_processor: ZoneProcessor,
    start_year: int,
    until_year: int,
) -> MaxBufferSizeInfo:
    """Find the maximum active transition size and the maximum buffer size of
    the given ZoneProcessor, over the years from start_year to until_year. This
    is useful for determining that buffer size of the C++ version of this code
    which uses static sizes for the Transition buffers.
    """
    max_active_size = CountAndYear(0, 0)
    max_buffer_size = CountAndYear(0, 0)
    for year in range(start_year, until_year):
        zone_processor.init_for_year(year)
        buffer_size_info = zone_processor.get_buffer_sizes()

        # Max number of active transitions.
        if buffer_size_info.active_size > max_active_size.number:
            max_active_size = CountAndYear(
                buffer_size_info.active_size, year)

        # Max size of the transition buffer.
        if buffer_size_info.buffer_size > max_buffer_size.number:
            max_buffer_size = CountAndYear(
                buffer_size_info.buffer_size, year)

    return MaxBufferSizeInfo(
        max_active_size=max_active_size,
        max_buffer_size=max_buffer_size,
    )
