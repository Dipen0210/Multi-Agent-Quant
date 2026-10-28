"""Explicit NYSE regular-session calendar; NASDAQ equities share these regular hours.
Session range is bounded. Exceptional closures use the pinned package's calendar.
"""
from functools import lru_cache
from zoneinfo import ZoneInfo
import exchange_calendars as xcals
import pandas as pd


@lru_cache(maxsize=1)
def calendar():
    return xcals.get_calendar('XNYS', start='2000-01-01', end='2035-12-31')


def validate_session(start, end):
    day = start.astimezone(ZoneInfo('America/New_York')).date().isoformat()
    cal = calendar()
    if not cal.is_session(day):
        raise ValueError('Market observation is on a non-trading date')
    if pd.Timestamp(start) != cal.session_open(day) or pd.Timestamp(end) != cal.session_close(day):
        raise ValueError('Daily observation must match regular session including early closes')


def session_times(day: str):
    cal = calendar()
    if not cal.is_session(day):
        raise ValueError('Non-trading date')
    return cal.session_open(day).to_pydatetime(), cal.session_close(day).to_pydatetime()
