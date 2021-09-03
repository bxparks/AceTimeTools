# Copyright 2019 Brian T. Park
#
# MIT License

import logging
from collections import OrderedDict

from acetimetools.data_types.at_types import ZonesMap, PoliciesMap
from acetimetools.data_types.at_types import BufSizeInfo, BufSizeMap
from acetimetools.data_types.at_types import CountAndYear
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

        # Calculate buffer sizes using a ZoneProcessor.
        buf_sizes = self.calculate_buf_sizes(zone_infos, zone_policies)
        max_buf_size = max([cy.number for cy in buf_sizes.values()])
        logging.info('Found max_buffer_size=%d', max_buf_size)

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

            # The TransitionStorage size should be one more than the estimate
            # because TransitionStorage.getFreeAgent() needs one slot even if
            # it's not used.
            count_and_year = CountAndYear(
                buffer_size_info.max_buffer_size.number,
                buffer_size_info.max_buffer_size.year,
            )

            buf_sizes[zone_name] = count_and_year

        return buf_sizes
