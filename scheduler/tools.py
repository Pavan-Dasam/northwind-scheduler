"""Tools the agent can call. Each tool takes the Store plus keyword arguments
and returns JSON-serialisable data."""

from .slots import (
    SLOTS_PER_DAY,
    availability_from_busy,
    combine_availability,
    find_free_windows,
    slot_to_time,
    time_to_slot,
    time_to_slot_ceil,
)
from .store import Store


def _resolve_person_id(store: Store, identifier: str) -> str | None:
    """Resolve an attendee identifier (ID or full name) to a valid person ID, case-insensitively."""
    cleaned = identifier.strip().lower()
    for person in store.people:
        if person["id"].lower() == cleaned:
            return person["id"]
        if person.get("name", "").lower() == cleaned:
            return person["id"]
    return None


def list_people(store: Store) -> list[dict]:
    """Return everyone in the directory."""
    return store.people


def get_busy_times(store: Store, person: str, date: str) -> list[dict]:
    """Return a person's busy blocks on a date (YYYY-MM-DD)."""
    resolved_id = _resolve_person_id(store, person)
    if not resolved_id:
        raise ValueError(f"Person '{person}' not found in employee directory.")
    return store.calendars.get(resolved_id, {}).get(date, [])


def find_free_slots(
    store: Store,
    attendees: list[str],
    date: str,
    duration_minutes: int,
    earliest: str | None = None,
    latest: str | None = None,
    buffer_minutes: int = 0,
) -> list[dict]:
    """Find every time on `date` when all attendees are free for `duration_minutes`.

    `earliest` and `latest` optionally narrow the search to part of the day
    (e.g. earliest="12:00" for "afternoon").
    `buffer_minutes` optionally enforces a buffer before and after existing meetings.
    """
    if isinstance(attendees, str):
        attendees = [attendees]

    if not attendees:
        raise ValueError("At least one attendee must be specified.")

    resolved_attendees = []
    unknown_attendees = []
    for att in attendees:
        resolved = _resolve_person_id(store, att)
        if resolved:
            resolved_attendees.append(resolved)
        else:
            unknown_attendees.append(att)

    if unknown_attendees:
        raise ValueError(
            f"Unknown attendee(s): {', '.join(unknown_attendees)}. "
            "Only people in the employee directory can be scheduled."
        )

    if not isinstance(duration_minutes, (int, float)) or duration_minutes <= 0:
        raise ValueError("duration_minutes must be a positive number.")

    # In a 30-minute slot calendar, a meeting of duration D requires ceil(D / 30) slots.
    slots_needed = -(-int(duration_minutes) // 30)
    if slots_needed > SLOTS_PER_DAY:
        return []

    calendars = []
    for person_id in resolved_attendees:
        busy = store.calendars.get(person_id, {}).get(date, [])
        calendars.append(availability_from_busy(busy, buffer_minutes=buffer_minutes))

    free = combine_availability(calendars)
    start_slot = max(0, time_to_slot_ceil(earliest)) if earliest else 0
    end_slot = min(SLOTS_PER_DAY, time_to_slot(latest)) if latest else SLOTS_PER_DAY

    starts = find_free_windows(free, slots_needed, start_slot, end_slot)
    return [
        {"start": slot_to_time(s), "end": slot_to_time(s + slots_needed)}
        for s in starts
    ]


TOOLS = {
    "list_people": list_people,
    "get_busy_times": get_busy_times,
    "find_free_slots": find_free_slots,
}
