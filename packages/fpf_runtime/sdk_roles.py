"""OpenAI Agents SDK-backed DEV/QA API sessions. Does not access ChatGPT UI threads."""
from __future__ import annotations
from pathlib import Path
from .adapters import ROLE_INSTRUCTIONS, RoleResult

class AgentsSDKRoles:
    def __init__(self, model: str, task_id: str, sessions_db: Path):
        try:
            from agents import Agent, Runner, SQLiteSession
        except ImportError as exc:
            raise RuntimeError("Install the optional SDK: pip install -e '.[agents]'") from exc
        sessions_db = sessions_db.resolve()
        sessions_db.parent.mkdir(parents=True, exist_ok=True)
        self.runner = Runner
        self.agents = {
            role: Agent(name="FPF_" + role, instructions=instructions, model=model)
            for role, instructions in ROLE_INSTRUCTIONS.items()
        }
        self.sessions = {
            role: SQLiteSession(task_id + "::" + role, str(sessions_db))
            for role in ROLE_INSTRUCTIONS
        }

    def ask(self, role: str, message: str, previous_response_id: str | None = None) -> RoleResult:
        if role not in self.agents:
            raise ValueError("Unsupported role: " + role)
        result = self.runner.run_sync(self.agents[role], message, session=self.sessions[role])
        output = str(result.final_output or "").strip()
        if not output:
            raise RuntimeError("SDK role returned an empty response")
        # The SDK persists conversation history; it is not a Responses response ID.
        return RoleResult(output, None)
