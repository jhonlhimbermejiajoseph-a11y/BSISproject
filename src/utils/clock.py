"""One place for every date/time the system uses, so the rest of the code never touches the PC clock.

- today() / now()      : the only source of "today" (change here and the whole system follows)
- parse_date(text)     : safe date reading; returns None instead of crashing on bad input
- check_clock()        : detects a PC clock that was turned BACK (used to dodge expiry dates)
"""
import os
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STAMP = os.path.join(ROOT, ".last_seen")          # remembers the latest time the system ran
MAX_BACK = timedelta(hours=1)                      # small corrections (time sync, daylight saving) are fine
MAX_YEARS = 20                                     # dates outside this window are treated as typos


def today():
    return date.today()


def now():
    return datetime.now()


def today_str():
    return today().isoformat()


def now_str():
    return now().strftime("%Y-%m-%d %H:%M")


def parse_date(text):
    """'2027-06-30' -> date, or None if it is empty, malformed or unreasonable."""
    try:
        d = date.fromisoformat(str(text).strip())
    except (ValueError, TypeError):
        return None
    t = today()
    if not (t.replace(year=t.year - MAX_YEARS) <= d <= t.replace(year=t.year + MAX_YEARS)):
        return None
    return d


def check_clock():
    """Call once at startup. Returns a warning text if the clock went backwards, else None."""
    current = now()
    warning = None
    try:
        with open(STAMP) as f:
            last = datetime.fromisoformat(f.read().strip())
        if current + MAX_BACK < last:
            warning = (f"The computer clock ({current:%Y-%m-%d %H:%M}) is earlier than the last time the "
                       f"system was used ({last:%Y-%m-%d %H:%M}).\nExpiry dates and reports may be wrong. "
                       "Please correct the date and time of this computer.")
            current = last                          # never move the stamp backwards
    except (OSError, ValueError):
        pass
    try:
        with open(STAMP, "w") as f:
            f.write(current.isoformat(timespec="seconds"))
    except OSError:
        pass                                        # read-only folder: skip, never crash
    return warning