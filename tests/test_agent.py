import json

from scheduler.agent import SchedulingAgent
from scheduler.model import FakeModel, final, tool_call
from scheduler.store import Store


def test_agent_returns_final_answer():
    model = FakeModel([final("Happy to help!")])
    agent = SchedulingAgent(model, Store.load())
    assert agent.run("hello") == "Happy to help!"


def test_agent_calls_tool_and_returns_result_to_model():
    model = FakeModel([
        tool_call("find_free_slots", attendees=["priya", "sam"],
                  date="2026-11-03", duration_minutes=60, earliest="12:00"),
        final("13:00 works for both."),
    ])
    agent = SchedulingAgent(model, Store.load())

    answer = agent.run("Find an hour for Priya and Sam on Tuesday afternoon")

    assert answer == "13:00 works for both."
    second_call = model.calls[1]
    assert second_call[-1]["role"] == "tool"
    assert {"start": "13:00", "end": "14:00"} in json.loads(second_call[-1]["content"])


def test_system_prompt_includes_directory():
    model = FakeModel([final("ok")])
    SchedulingAgent(model, Store.load()).run("hi")
    system = model.calls[0][0]["content"]
    assert "Priya Raman" in system


def test_agent_handles_invented_person():
    model = FakeModel([
        tool_call("find_free_slots", attendees=["priya", "ghost"], date="2026-11-03", duration_minutes=30),
        final("I could not schedule the meeting because 'ghost' is not in the directory."),
    ])
    agent = SchedulingAgent(model, Store.load())
    answer = agent.run("Schedule a meeting with Priya and ghost")
    assert "not in the directory" in answer
    tool_resp = json.loads(model.calls[1][-1]["content"])
    assert "error" in tool_resp
    assert "ghost" in tool_resp["error"]


def test_agent_handles_markdown_wrapped_json():
    wrapped_json = "```json\n" + final("Available at 14:00") + "\n```"
    model = FakeModel([wrapped_json])
    agent = SchedulingAgent(model, Store.load())
    assert agent.run("When can we meet?") == "Available at 14:00"


def test_agent_handles_malformed_json_and_recovers():
    model = FakeModel([
        "Not JSON at all, just plain text",
        final("Recovered after error."),
    ])
    agent = SchedulingAgent(model, Store.load())
    assert agent.run("Find time") == "Recovered after error."
    assert "Invalid JSON response" in model.calls[1][-1]["content"]


def test_agent_handles_unknown_tool():
    model = FakeModel([
        tool_call("non_existent_tool", some_arg="value"),
        final("Handled unknown tool."),
    ])
    agent = SchedulingAgent(model, Store.load())
    assert agent.run("Do something") == "Handled unknown tool."
    tool_resp = json.loads(model.calls[1][-1]["content"])
    assert "error" in tool_resp
    assert "does not exist" in tool_resp["error"]


def test_agent_handles_bad_tool_arguments():
    model = FakeModel([
        tool_call("find_free_slots", attendees=["priya"], date="2026-11-03", duration_minutes=-10),
        final("Duration must be positive."),
    ])
    agent = SchedulingAgent(model, Store.load())
    assert agent.run("Schedule -10 min meeting") == "Duration must be positive."
    tool_resp = json.loads(model.calls[1][-1]["content"])
    assert "error" in tool_resp


def test_agent_loop_terminates_on_stuck_model():
    # A model that repeatedly calls a tool forever
    stuck_model = FakeModel([
        tool_call("list_people"),
    ], loop_last=True)
    agent = SchedulingAgent(stuck_model, Store.load(), max_turns=3)
    response = agent.run("Find someone")
    assert "could not complete your request within the allowed number of steps" in response
    assert len(stuck_model.calls) == 3


def test_agent_passes_buffer_minutes_to_find_free_slots():
    model = FakeModel([
        tool_call("find_free_slots", attendees=["priya"], date="2026-11-03", duration_minutes=30, buffer_minutes=15),
        final("Priya has free slots with a 15-minute buffer."),
    ])
    agent = SchedulingAgent(model, Store.load())
    answer = agent.run("Find 30 minutes for Priya on Tuesday with 15 minutes buffer")
    assert "15-minute buffer" in answer
    tool_content = json.loads(model.calls[1][-1]["content"])
    assert isinstance(tool_content, list)
    # 13:30-14:00 should not be in the results because of the 14:00 meeting with 15m buffer
    assert not any(s["start"] == "13:30" and s["end"] == "14:00" for s in tool_content)
