# Copyright 2021 Brian T. Park
#
# MIT License

"""
Common constants and functions used by zone_processor.py. Most of were copied
from transformer/transformer.py, in preparation for them to be moved into a new
AceTimePython project, while avoiding circular dependendence between
AceTimeTools and AceTimePython. The unit tests are in tests/test_transformer.py.
Maybe those should be copied too?
"""

from typing import Tuple
import datetime


# Marker year to indicate -Infinity year.
MIN_YEAR: int = 0

# Number of seconds from Unix Epoch (1970-01-01 00:00:00) to AceTime Epoch
# (2000-01-01 00:00:00)
SECONDS_SINCE_UNIX_EPOCH = 946684800


def seconds_to_hms(seconds: int) -> Tuple[int, int, int]:
    """Convert seconds to (h,m,s). Works only for positive seconds.
    """
    s = seconds % 60
    minutes = seconds // 60
    m = minutes % 60
    h = minutes // 60
    return (h, m, s)


def hms_to_seconds(h: int, m: int, s: int) -> int:
    """Convert h:m:s to seconds.
    """
    return (h * 60 + m) * 60 + s


def calc_day_of_month(
    year: int,
    month: int,
    on_day_of_week: int,
    on_day_of_month: int,
) -> Tuple[int, int]:
    """Return the actual (month, day) of expressions such as
    (on_day_of_week >= on_day_of_month), (on_day_of_week <= on_day_of_month), or
    (lastMon) See BasicZoneProcessor::calcStartDayOfMonth(). Shifts into
    previous or next month can occur.

    Return (13, xx) if a shift to the next year occurs
    Return (0, xx) if a shift to the previous year occurs
    """
    if on_day_of_week == 0:
        return (month, on_day_of_month)

    if on_day_of_month >= 0:
        days_in_month = _days_in_month(year, month)

        # Handle lastXxx by transforming it into (Xxx >= (daysInMonth - 6))
        if on_day_of_month == 0:
            on_day_of_month = days_in_month - 6

        limit_date = datetime.date(year, month, on_day_of_month)
        day_of_week_shift = (on_day_of_week - limit_date.isoweekday() + 7) % 7
        day = on_day_of_month + day_of_week_shift
        if day > days_in_month:
            day -= days_in_month
            month += 1
        return (month, day)
    else:
        on_day_of_month = -on_day_of_month
        limit_date = datetime.date(year, month, on_day_of_month)
        day_of_week_shift = (limit_date.isoweekday() - on_day_of_week + 7) % 7
        day = on_day_of_month - day_of_week_shift
        if day < 1:
            month -= 1
            days_in_prev_month = _days_in_month(year, month)
            day += days_in_prev_month
        return (month, day)


def _days_in_month(year: int, month: int) -> int:
    """Return the number of days in the given (year, month). The
    month is usually 1-12, but can be 0 to indicate December of the previous
    year, and 13 to indicate Jan of the following year.
    """
    DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    is_leap = (year % 4 == 0) and ((year % 100 != 0) or (year % 400) == 0)
    days = DAYS_IN_MONTH[(month - 1) % 12]
    if month == 2:
        days += is_leap
    return days
