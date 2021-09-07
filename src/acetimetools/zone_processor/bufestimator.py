# Copyright 2019 Brian T. Park
#
# MIT License

from typing import List, Tuple
import logging
from collections import OrderedDict

from acetimetools.data_types.at_types import ZonesMap, PoliciesMap
from acetimetools.data_types.at_types import BufSizeInfo, BufSizeMap
from .zone_processor import ZoneProcessor
from .zone_info_types import ZoneInfoMap
from .zone_info_types import ZonePolicyMap
from .zone_info_inliner import ZoneInfoInliner


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

    def estimate(self) -> BufSizeInfo:
        """Calculate the (dict) of {full_name -> buf_size} where buf_size is one
        more than the estimate from ZoneProcessor.get_buffer_sizes(). Also
        return the maximum.
        """
        # Generate internal zone_infos and zone_policies to be used by
        # ZoneProcessor.
        zone_info_inliner = ZoneInfoInliner(self.zones_map, self.policies_map)
        zone_infos, zone_policies = zone_info_inliner.generate_zonedb()
        logging.info(
            'InlinedZoneInfo: Zones %d; Policies %d',
            len(zone_infos), len(zone_policies))

        # Calculate expected buffer sizes for each zone using a ZoneProcessor.
        buf_sizes = self.calculate_buf_sizes(zone_infos, zone_policies)

        # Determine the maximum buffer size, the zone(s) which generate that
        # size, and the year which that occurs.
        max_buf_size = max([cy.number for cy in buf_sizes.values()])
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

        # Sort by zone_name
        buf_sizes = OrderedDict(sorted(buf_sizes.items()))

        return {
            'buf_sizes': buf_sizes,
            'max_buf_size': max_buf_size,
        }

    def calculate_buf_sizes(
        self,
        zone_infos: ZoneInfoMap,
        zone_policies: ZonePolicyMap,
    ) -> BufSizeMap:

        buf_sizes: BufSizeMap = {}
        for zone_name, zone_info in zone_infos.items():
            zone_processor = ZoneProcessor(zone_info)

            # get_buffer_sizes() returns a BufferSizeInfo(NamedTuple) composed
            # of max_actives(count, year) and max_buffer_size(count, year).
            buffer_size_info = zone_processor.get_buffer_sizes(
                start_year=self.start_year,
                until_year=self.until_year,
            )

            # Currently, we just care about the max buffer size.
            buf_sizes[zone_name] = buffer_size_info.max_buffer_size

        return buf_sizes
