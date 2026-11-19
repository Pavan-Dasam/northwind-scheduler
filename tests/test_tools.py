import pytest

from scheduler.store import Store
from scheduler.tools import find_free_slots, get_busy_times


def test_get_busy_times():
    store = Store.load()
    busy = get_busy_times(store, "sam", "2026-11-04")
    assert busy == [{"start": "09:00", "end": "09:30", "title": "Standup"}]


def test_get_busy_times_unknown_person_raises():
    store = Store.load()
    with pytest.raises(ValueError, match="not found in employee directory"):
        get_busy_times(store, "ghost_user", "2026-11-04")


def test_find_free_slots_for_two_people_in_the_afternoon():
    store = Store.load()
    slots = find_free_slots(
        store,
        attendees=["priya", "sam"],
        date="2026-11-03",
        duration_minutes=30,
        earliest="13:00",
    )
    assert slots == [
        {"start": "13:00", "end": "13:30"},
        {"start": "13:30", "end": "14:00"},
        {"start": "15:00", "end": "15:30"},
        {"start": "16:00", "end": "16:30"},
        {"start": "16:30", "end": "17:00"},
    ]


def test_find_free_slots_hour_long_meeting():
    store = Store.load()
    slots = find_free_slots(
        store, attendees=["priya", "sam"], date="2026-11-03", duration_minutes=60
    )
    assert {"start": "13:00", "end": "14:00"} in slots


def test_find_free_slots_45_min_meeting_allocates_two_slots():
    store = Store.load()
    slots = find_free_slots(
        store, attendees=["priya", "sam"], date="2026-11-03", duration_minutes=45
    )
    # A 45-min meeting requires 2 slots (60 mins), so isolated 30-min free windows like 15:00-15:30 must not be returned
    assert {"start": "13:00", "end": "14:00"} in slots
    assert not any(s["start"] == "15:00" and s["end"] == "15:30" for s in slots)


def test_find_free_slots_rejects_unknown_attendees():
    store = Store.load()
    with pytest.raises(ValueError, match="Unknown attendee"):
        find_free_slots(store, attendees=["priya", "nobody"], date="2026-11-03", duration_minutes=30)


def test_find_free_slots_empty_attendees_raises():
    store = Store.load()
    with pytest.raises(ValueError, match="At least one attendee"):
        find_free_slots(store, attendees=[], date="2026-11-03", duration_minutes=30)


def test_find_free_slots_resolves_full_name_and_case_insensitivity():
    store = Store.load()
    slots = find_free_slots(
        store,
        attendees=["Priya Raman", "SAM"],
        date="2026-11-03",
        duration_minutes=60,
    )
    assert {"start": "13:00", "end": "14:00"} in slots


def test_find_free_slots_earliest_ceiling_boundary():
    store = Store.load()
    # Earliest 13:15 should skip the 13:00-13:30 slot and start at 13:30
    slots = find_free_slots(
        store,
        attendees=["priya", "sam"],
        date="2026-11-03",
        duration_minutes=30,
        earliest="13:15",
    )
    assert not any(s["start"] == "13:00" for s in slots)
    assert any(s["start"] == "13:30" for s in slots)


def test_find_free_slots_with_buffer_minutes():
    store = Store.load()
    # Priya has meetings 09:30-11:00 and 14:00-15:00.
    # Without buffer, 13:30-14:00 is free.
    # With a 15-minute buffer, the 14:00-15:00 meeting requires buffer from 13:45 to 14:00,
    # which overlaps slot 13:30-14:00 and marks it busy.
    slots_without_buffer = find_free_slots(
        store, attendees=["priya"], date="2026-11-03", duration_minutes=30, earliest="13:00"
    )
    assert {"start": "13:30", "end": "14:00"} in slots_without_buffer

    slots_with_buffer = find_free_slots(
        store, attendees=["priya"], date="2026-11-03", duration_minutes=30, earliest="13:00", buffer_minutes=15
    )
    assert {"start": "13:30", "end": "14:00"} not in slots_with_buffer
