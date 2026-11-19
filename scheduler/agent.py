"""The scheduling agent: a simple tool-calling loop."""

import json

from .model import Model
from .prompts import build_system_prompt
from .store import Store
from .tools import TOOLS


def _extract_json(text: str) -> str:
    """Strip optional markdown code block wrappers from model output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


class SchedulingAgent:
    def __init__(
        self,
        model: Model,
        store: Store,
        today: str = "2026-11-02",
        max_turns: int = 10,
    ):
        self.model = model
        self.store = store
        self.today = today
        self.max_turns = max_turns

    def run(self, user_request: str) -> str:
        """Handle one user request and return the assistant's final answer."""
        messages = [
            {"role": "system", "content": build_system_prompt(self.store.people, self.today)},
            {"role": "user", "content": user_request},
        ]

        for _ in range(self.max_turns):
            raw = self.model.complete(messages)
            cleaned = _extract_json(raw)

            try:
                action = json.loads(cleaned)
            except json.JSONDecodeError as err:
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": f"Invalid JSON response: {err}. Please respond ONLY with a valid JSON object.",
                })
                continue

            if not isinstance(action, dict):
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": "Invalid response: Expected a JSON object with either 'final' or 'tool' key.",
                })
                continue

            messages.append({"role": "assistant", "content": raw})

            if "final" in action:
                return str(action["final"])

            if "tool" not in action:
                messages.append({
                    "role": "user",
                    "content": "Invalid response: Expected 'tool' or 'final' key in JSON.",
                })
                continue

            tool_name = action["tool"]
            args = action.get("args", {})

            if not isinstance(tool_name, str) or tool_name not in TOOLS:
                available = ", ".join(TOOLS.keys())
                messages.append({
                    "role": "tool",
                    "content": json.dumps({"error": f"Tool '{tool_name}' does not exist. Available tools: {available}."}),
                })
                continue

            if not isinstance(args, dict):
                messages.append({
                    "role": "tool",
                    "content": json.dumps({"error": f"Arguments for tool '{tool_name}' must be a JSON object (dict)."}),
                })
                continue

            try:
                tool = TOOLS[tool_name]
                result = tool(self.store, **args)
                messages.append({"role": "tool", "content": json.dumps(result)})
            except (TypeError, ValueError) as err:
                messages.append({"role": "tool", "content": json.dumps({"error": str(err)})})
            except Exception as err:
                messages.append({
                    "role": "tool",
                    "content": json.dumps({"error": f"Unexpected error executing '{tool_name}': {err}"}),
                })

        return "I could not complete your request within the allowed number of steps. Please try again with a more specific request."
