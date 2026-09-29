"""
Optional per-service schedule stored in Service.availability:

    [{"date": "2026-10-01", "times": ["10:00", "14:30"]}, ...]

Each time is the start of a slot lasting `service.duration` minutes.
An empty list means the service has no own schedule and follows the
business working hours. A date listed with no times is a day off.
"""
import re
from datetime import date, datetime, time

from ninja.errors import HttpError

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)(:00)?$")

# Slots never cross midnight, same cap as working_day_bounds (23:59 in minutes)
DAY_END_MINUTES = 23 * 60 + 59

MAX_SCHEDULE_DATES = 366
MAX_TIMES_PER_DATE = 288


def _parse_date(value):
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and DATE_RE.match(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError(f"Invalid date {value!r}, expected YYYY-MM-DD")


def _parse_time(value):
    if isinstance(value, time):
        if value.second or value.microsecond:
            raise ValueError(f"Invalid time {value!r}, expected HH:MM")
        return value.replace(tzinfo=None)
    if isinstance(value, str):
        match = TIME_RE.match(value)
        if match:
            return time(int(match.group(1)), int(match.group(2)))
    raise ValueError(f"Invalid time {value!r}, expected HH:MM")


def minutes_of(value):
    """Minutes since midnight of a time."""
    return value.hour * 60 + value.minute


def time_of(minutes):
    """Inverse of minutes_of for 0 <= minutes < 24 * 60."""
    return time(minutes // 60, minutes % 60)


def _slot_end(start, duration):
    """
    End of a slot, or None when it would run past 23:59.
    Plain minute arithmetic, not datetime + timedelta, which overflows
    on 9999-12-31.
    """
    end = minutes_of(start) + duration
    if end > DAY_END_MINUTES:
        return None
    return time_of(end)


def normalize_availability(value, duration=None):
    """
    Validates a schedule and returns it in canonical form: entries sorted by
    date, times de-duplicated and sorted, all values as strings.
    With `duration` (minutes) also rejects slots that would end after 23:59.
    Raises ValueError with a message that can be shown to the user.
    """
    if value is None:
        return []

    if not isinstance(value, (list, tuple)):
        raise ValueError("availability must be a list of {date, times} objects")

    if len(value) > MAX_SCHEDULE_DATES:
        raise ValueError(f"availability can hold at most {MAX_SCHEDULE_DATES} dates")

    days = {}

    for entry in value:
        if hasattr(entry, "model_dump"):
            entry = entry.model_dump()

        if not isinstance(entry, dict) or "date" not in entry or "times" not in entry:
            raise ValueError("Each availability entry must have date and times")

        day = _parse_date(entry["date"])

        if day in days:
            raise ValueError(f"Date {day.isoformat()} appears more than once")

        times = entry["times"]
        if not isinstance(times, (list, tuple)):
            raise ValueError(f"times for {day.isoformat()} must be a list of HH:MM strings")

        if len(times) > MAX_TIMES_PER_DATE:
            raise ValueError(f"At most {MAX_TIMES_PER_DATE} times per date")

        starts = sorted({_parse_time(t) for t in times})

        # A duration below 1 minute is rejected by the callers themselves
        if duration is not None and duration >= 1:
            for start in starts:
                if _slot_end(start, duration) is None:
                    raise ValueError(
                        f"Slot at {start:%H:%M} on {day.isoformat()} would end after 23:59"
                    )

        days[day] = [start.strftime("%H:%M") for start in starts]

    return [
        {"date": day.isoformat(), "times": days[day]}
        for day in sorted(days)
    ]


def has_own_schedule(service):
    return bool(service.availability)


def schedule_slots(service, day):
    """
    (start_time, end_time) pairs the service offers on `day` from its own
    schedule, or None when the service has no schedule (working hours apply).
    Malformed stored values are skipped.
    """
    if not has_own_schedule(service):
        return None

    # A zero duration (possible via the ORM, PositiveIntegerField allows it)
    # gives no bookable slot
    if service.duration is None or service.duration < 1:
        return []

    day_str = day.isoformat()
    slots = set()

    for entry in service.availability:
        if not isinstance(entry, dict) or entry.get("date") != day_str:
            continue
        for value in entry.get("times") or []:
            try:
                start = _parse_time(value)
            except ValueError:
                continue
            end = _slot_end(start, service.duration)
            if end is not None:
                slots.add((start, end))

    return sorted(slots)


def check_service_schedule(service, day, start_time, end_time):
    """
    Booking-time check for services with their own schedule: start_time must
    be one of the times listed for `day` and end_time must equal
    start_time + duration. Raises HttpError(400) otherwise.

    Returns True when the schedule was applied (callers should then skip the
    working-hours check) and False for services without a schedule.
    """
    slots = schedule_slots(service, day)

    if slots is None:
        return False

    if not slots:
        raise HttpError(400, "Service is not available on this date")

    for start, end in slots:
        if start == start_time:
            if end != end_time:
                raise HttpError(
                    400,
                    f"end_time must be {end:%H:%M} for the {start:%H:%M} slot"
                )
            return True

    raise HttpError(400, "Selected time is not in the service schedule")
