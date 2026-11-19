from scheduler.slots import (
    availability_from_busy,
    combine_availability,
    find_free_windows,
    slot_to_time,
    time_to_slot,
    time_to_slot_ceil,
)


def test_slot_to_time():
    assert slot_to_time(0) == "09:00"
    assert slot_to_time(3) == "10:30"


def test_time_to_slot():
    assert time_to_slot("09:00") == 0
    assert time_to_slot("10:45") == 3


def test_time_to_slot_ceil():
    assert time_to_slot_ceil("09:00") == 0
    assert time_to_slot_ceil("09:15") == 1
    assert time_to_slot_ceil("10:30") == 3


def test_availability_marks_partial_overlap_busy():
    free = availability_from_busy([{"start": "10:00", "end": "10:45"}])
    assert free[2] is False  # 10:00-10:30
    assert free[3] is False  # 10:30-11:00, partially busy
    assert free[4] is True


def test_combine_availability():
    a = [True, True, False, True]
    b = [True, False, True, True]
    assert combine_availability([a, b])[:4] == [True, False, False, True]


def test_find_free_windows():
    free = [False, True, True, True, False, True] + [False] * 10
    assert find_free_windows(free, 2) == [1, 2]


def test_find_free_windows_reaches_end_of_day():
    # Last two slots of the day (indices 14 and 15, corresponding to 16:00 - 17:00)
    free = [False] * 14 + [True, True]
    windows = find_free_windows(free, slots_needed=2)
    assert windows == [14]


def test_find_free_windows_invalid_slots():
    free = [True] * 16
    assert find_free_windows(free, slots_needed=0) == []
    assert find_free_windows(free, slots_needed=-1) == []
    assert find_free_windows(free, slots_needed=2, start_slot=15, end_slot=10) == []
