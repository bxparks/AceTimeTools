# Copyright 2019 Brian T. Park
#
# MIT License

from typing import List, Tuple
from typing import NamedTuple
import logging
from collections import OrderedDict

from acetimetools.data_types.at_types import TransformerResult
from acetimetools.data_types.at_types import ZonesMap, PoliciesMap
from acetimetools.data_types.at_types import BufSizeMap, CountAndYear
from acetime.zone_processor import ZoneProcessor
from acetime.zonedb_types import ZoneInfoMap
from .zone_info_inliner import ZoneInfoInliner


# The value of `ExtendedZoneProcessor.kMaxTransitions` which determines the
# buffer size in the TransitionStorage class. The value returned by
# calculate_max_buf_size() must be equal or smaller than this constant.
EXTENDED_ZONE_PROCESSOR_MAX_TRANSITIONS = 8


class MaxBufferSizeInfo(NamedTuple):
    """A tuple containings the number of active transitions and the current
    buffer_size of TransitionStorage.
    """
    max_active_size: CountAndYear
    max_buffer_size: CountAndYear
    # The first (smallest) year when zone_processor.is_terminal_year() is True
    terminal_year: int


class BufSizeEstimator:
    """Estimate the buffer size of the C++
    ExtendedZoneProcessor::TransitionStorage class for each zone.
    """

    def __init__(
        self,
        start_year: int,
        until_year: int,
        ignore_buf_size_too_large: bool,
    ) -> None:
        self.start_year = start_year
        self.until_year = until_year
        self.ignore_buf_size_too_large = ignore_buf_size_too_large

    def transform(self, tresult: TransformerResult) -> None:
        self.zones_map = tresult.zones_map
        self.policies_map = tresult.policies_map

        logging.info(
            'Requested years: [%d, %d)',
            self.start_year, self.until_year)
        logging.info(
            'Generated years: [%d, %d]',
            tresult.generated_min_year, tresult.generated_max_year)

        start_year = min(tresult.generated_min_year, self.start_year)
        until_year = max(tresult.generated_max_year + 1, self.until_year)
        logging.info(
            'Checking years:  [%d, %d)', start_year, until_year)

        logging.info('Calculating buf_size_map')
        buf_sizes, max_terminal_year = calculate_buf_size_map(
            start_year,
            until_year,
            self.zones_map,
            self.policies_map,
        )
        logging.info('Calculating max_buf_size')
        max_buf_size = calculate_max_buf_size(buf_sizes)
        logging.info(f'max_terminal_year: {max_terminal_year}')

        # Check if the estimated buffer size is too big
        if max_buf_size > EXTENDED_ZONE_PROCESSOR_MAX_TRANSITIONS:
            msg = (
                f"Max buffer size={max_buf_size} "
                f"is larger than ExtendedZoneProcessor.kMaxTransitions="
                f"{EXTENDED_ZONE_PROCESSOR_MAX_TRANSITIONS}"
            )
            if self.ignore_buf_size_too_large:
                logging.warning(msg)
            else:
                raise Exception(msg)

        # Populate the TransformerResult
        tresult.buf_sizes = buf_sizes
        tresult.max_buf_size = max_buf_size
        tresult.max_terminal_year = max_terminal_year

    def print_summary(self, tresult: TransformerResult) -> None:
        pass


def calculate_buf_size_map(
    start_year: int,
    until_year: int,
    zones_map: ZonesMap,
    policies_map: PoliciesMap,
) -> Tuple[BufSizeMap, int]:
    """Calculate the (dict) of {full_name -> (max_buffer_size, year)} where
    max_buffer_size is the maximum TransitionStorage buffer size required by
    ZoneProcessor across [start_year, until_year), and year is the year in
    which the maximum occurred.
    """
    # Generate internal zone_infos and zone_policies to be used by
    # ZoneProcessor.
    zone_info_inliner = ZoneInfoInliner(zones_map, policies_map)
    zone_infos, zone_policies = zone_info_inliner.generate_zonedb()

    # Calculate expected buffer sizes for each zone using a ZoneProcessor.
    # Include (start_year - 1) and (until_year + 1) to support conversions
    # from epochSeconds where the local year may shift to the previous or
    # next year depending on the UTC offset of the given timezone.
    logging.info(
        'Calculating buf sizes per zone [%s, %s)',
        start_year - 1,
        until_year + 1,
    )
    buf_size_map, max_terminal_year = _calculate_buf_sizes_per_zone(
        zone_infos,
        start_year - 1,
        until_year + 1,
    )

    return OrderedDict(sorted(buf_size_map.items())), max_terminal_year


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
) -> Tuple[BufSizeMap, int]:
    """
    Return the maximum active transition size and maximum buffer size for each
    zone listed in zone_infos.
    """
    buf_sizes: BufSizeMap = {}
    max_terminal_year = 0
    for zone_name, zone_info in zone_infos.items():
        zone_processor = ZoneProcessor(zone_info)

        # Calculate max_actives(count, year) and max_buffer_size(count, year).
        try:
            max_buffer_size_info = _find_max_buffer_sizes(
                zone_processor,
                start_year=start_year,
                until_year=until_year,
            )
        except:  # noqa E722
            logging.info(f'*** Error processing {zone_name}')
            raise

        # Currently, we just care about the max buffer size, not the max
        # active size.
        buf_sizes[zone_name] = max_buffer_size_info.max_buffer_size
        terminal_year = max_buffer_size_info.terminal_year
        if terminal_year > max_terminal_year:
            max_terminal_year = terminal_year

    return buf_sizes, max_terminal_year


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
        # Get the buffer sizes for given year (within the 3-year window).
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

        # Terminate the loop if the (year-2) is a terminal year. This check is
        # performed at the end of the loop body so that the buffer size
        # calculation is done at least once.
        #
        # We use (year-2) because we use a 3-year window [year-1, year+1] around
        # the current `year` when calculating the Transitions, and we want any
        # most recent prior year (<= year-2) to also be a terminal year.
        #
        # All future years after `year` will produce the same number of
        # Transitions within the window. This allow this function to bail early
        # and finish in a reasonable amount of time when very large `until_year`
        # (e.g. 10000, infinity) is given.
        if zone_processor.is_terminal_year(year - 2):
            break

    return MaxBufferSizeInfo(
        max_active_size=max_active_size,
        max_buffer_size=max_buffer_size,
        terminal_year=year,
    )
