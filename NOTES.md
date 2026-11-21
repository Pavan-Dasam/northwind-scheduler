# Notes on Northwind Scheduling Assistant

## 1. Problems Found and Fixed

- **Off-by-One in `find_free_windows` (`scheduler/slots.py`)**:
  - *What it was*: The loop ran `range(start_slot, end_slot - slots_needed)`. In Python, `range(a, b)` excludes `b`, which means the last valid start slot (`end_slot - slots_needed`) was never evaluated. For a standard 16-slot workday (09:00–17:00), this completely excluded any meeting ending at 17:00 (such as 16:30–17:00 for 30-min meetings or 16:00–17:00 for 60-min meetings).
  - *How found*: Inspected loop bounds while auditing edge-of-day availability, confirmed by running tests where Priya and Sam were both free from 16:30 to 17:00 on Nov 3.
  - *What changed*: Updated the loop to `range(start_slot, end_slot - slots_needed + 1)` and clamped `start_slot` and `end_slot` to valid bounds (`[0, SLOTS_PER_DAY]`). Also updated the test `test_find_free_slots_for_two_people_in_the_afternoon` in `tests/test_tools.py` to reflect that the 16:30–17:00 slot is actually free for both attendees.

- **Duration Under-Allocation via Floor Division (`scheduler/tools.py`)**:
  - *What it was*: `slots_needed = duration_minutes // 30` used integer floor division. A 45-minute meeting resulted in `45 // 30 = 1` slot (30 minutes), which was insufficient to hold the meeting. Non-positive durations also produced 0 or negative slots.
  - *How found*: Manual review of `find_free_slots` input handling.
  - *What changed*: Changed to ceiling division `-(-int(duration_minutes) // 30)` (or `math.ceil`) so a 45-minute meeting is allocated 2 slots (60 minutes). Added input validation to reject non-positive durations.

- **Earliest/Latest Time Boundary Clamping (`scheduler/tools.py`)**:
  - *What it was*: `earliest` used `time_to_slot(earliest)` which rounded down. For example, `earliest="09:15"` resolved to slot 0 (09:00), allowing meetings to start earlier than requested. Furthermore, times earlier than 09:00 produced negative slot indices, causing negative indexing into Python lists.
  - *How found*: Code inspection and boundary analysis on `time_to_slot` and `time_to_slot_ceil`.
  - *What changed*: Used `time_to_slot_ceil` for `earliest` clamped to `max(0, ...)`, and `time_to_slot` for `latest` clamped to `min(SLOTS_PER_DAY, ...)`.

- **Invented/Hallucinated Attendees Treated as Free (`scheduler/tools.py`)**:
  - *What it was*: When `find_free_slots` or `get_busy_times` received an attendee not in `people.json`, `store.calendars.get(person, {})` defaulted to `{}`. `availability_from_busy([])` treated them as having zero meetings, falsely indicating they were completely free all day.
  - *How found*: Requirement review ("No invented people. The assistant must never propose a meeting that includes someone who isn't in the directory").
  - *What changed*: Added attendee validation against `store.people` with case-insensitive resolution for both employee IDs and full names. If an attendee cannot be resolved, a `ValueError` is raised (or returned as an error object) explaining that the attendee is not in the directory.

- **Agent Fragility & Unhandled Exceptions (`scheduler/agent.py`)**:
  - *What it was*: The agent directly called `json.loads(raw)` and indexed `TOOLS[action["tool"]]` with `**action["args"]`. Any malformed JSON, markdown-wrapped JSON (` ```json ... ``` `), nonexistent tool call, or argument mismatch crashed the entire process.
  - *How found*: Stress testing agent handling with malformed `FakeModel` responses.
  - *What changed*: Added markdown fence stripping (`_extract_json`), caught JSON decode errors, validated action schema, checked tool existence, and wrapped tool calls in exception handlers returning structured error messages to the model so it can recover or inform the user.

- **Unbounded Agent Loop (`scheduler/agent.py`)**:
  - *What it was*: The loop used `while True:` without a counter. If the model got stuck repeatedly calling tools or emitting invalid responses (simulated by `FakeModel(..., loop_last=True)`), the loop ran indefinitely.
  - *How found*: Testing with `loop_last=True`.
  - *What changed*: Added `max_turns` limit (default 10). If exceeded without a final answer, it returns a polite, informative message indicating the turn limit was reached.

---

## 2. Your Addition (Part B)

- **Feature**: **Meeting Buffer Protection (`buffer_minutes`)**
- **What was built**:
  - Added an optional `buffer_minutes: int = 0` parameter to `find_free_slots` and `availability_from_busy`.
  - Automatically pads busy blocks by `buffer_minutes` on either side before converting them to calendar slots.
  - Exposed this capability in the system prompt so the LLM can use it when users request "time between meetings" or "buffer time".
- **Who it helps**:
  - Employees scheduling meetings who want to avoid back-to-back meeting fatigue, travel between rooms, or take a mental break between calls.
- **Why chosen over other options**:
  - Back-to-back scheduling is a primary friction point in real calendar assistants.
  - Directly integrates with the deterministic slot model without introducing complex external dependencies.
  - Clean to test deterministically and backward-compatible with default `buffer_minutes=0`.

---

## 3. How AI Tools Were Used

- **What was delegated**:
  - Boilerplate test case scaffolding across `test_slots.py`, `test_tools.py`, and `test_agent.py`.
  - Verification of edge cases in time arithmetic.
- **Specific case of rejecting/correcting an AI suggestion**:
  - *Case*: An initial suggestion for handling non-30-minute meeting durations proposed returning partial minutes in the slot dict (e.g. `{"start": "13:00", "end": "13:45"}`).
  - *Correction/Rejection*: Rejected this approach because the underlying architecture specifies that Northwind Labs schedules meetings in fixed 30-minute increments across the working day. Arbitrary minute intervals would break slot indexing and compatibility with subsequent slot combination logic. Instead, ceiling slot allocation (`-(-duration // 30)`) was used to reserve the necessary 30-minute increment block (e.g., 60 minutes for a 45-minute request), preserving the deterministic discrete slot model.

---

## 4. What To Do Next

- **What to change or add with more time**:
  - **Multi-Day Range Search**: Allow `find_free_slots` to accept a date range (e.g., `start_date` and `end_date`) or search across an entire work week to answer queries like "find the earliest slot this week".
  - **Lunch Hour Protection**: Add an employee preference to protect 12:00–13:00 as a lunch hour unless explicitly requested.
  - **Timezone Awareness**: In a distributed team, attendees across different time zones would need UTC-normalized slot calculations.
  - **Fuzzy Name Matching**: Expand directory resolution from exact/case-insensitive full name matching to fuzzy phonetic matching (e.g., Levenshtein distance) to handle minor spelling errors.

- **Things noticed but deliberately left alone**:
  - **Calendar Write Operations / Booking**: Noticed the assistant only reads availability and cannot create or send calendar invites. Left alone because the specification explicitly marks booking and calendar mutation as out of scope.
  - **30-Minute Discrete Slot Engine**: Noticed that arbitrary meeting lengths (e.g. 20 or 40 minutes) are rounded up to 30-minute slot boundaries. Left alone because the business rules state Northwind schedules in 30-minute increments, and rewriting the core to 1-minute intervals would add unnecessary complexity and risk regressions without changing the fundamental behavior.
  - **Recurring Meetings and Multiple Calendar Sources**: Left out per the instructions ("Time zones, recurring meetings, or calendar data beyond the sample files are out of scope").
