"""
anysql/tracers/agent.py
Agent tracer for UC4 — Cross-Session Agent Debugging.

LangChain usage:
    tracer = AgentTracer(db, session_id="session-123")
    agent_executor.invoke({"input": "..."}, config={"callbacks": [tracer]})

Manual usage (any framework):
    tracer = AgentTracer(db, session_id="session-xyz")
    tracer.trace_tool_call("search", input={"q": "..."}, output="...", status="success")
    tracer.trace_step("llm_call", description="Summarize results")
"""

import uuid
import time
import json
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional, Any


class AgentTracer:
    def __init__(self, db, session_id: Optional[str] = None):
        self._db = db
        self.session_id = session_id or str(uuid.uuid4())
        self._step_counter = 0
        self._pending_tool = {}

    @contextmanager
    def session(self, session_id: Optional[str] = None):
        if session_id:
            self.session_id = session_id
        self._step_counter = 0
        yield self

    def trace_tool_call(
        self, tool_name: str,
        input: Any = None, output: Any = None,
        status: str = "success",
        error_message: Optional[str] = None,
        latency_ms: Optional[int] = None,
        human_override: bool = False,
    ) -> str:
        self._step_counter += 1
        call_id = str(uuid.uuid4())
        self._db.insert("agent.tool_calls", [{
            "call_id":       call_id,
            "session_id":    self.session_id,
            "step_order":    self._step_counter,
            "tool_name":     tool_name,
            "tool_input":    json.dumps(input, default=str) if input is not None else None,
            "tool_output":   json.dumps(output, default=str) if output is not None else None,
            "status":        status,
            "error_message": error_message,
            "latency_ms":    latency_ms,
            "human_override": human_override,
            "called_at":     datetime.now(timezone.utc).isoformat(),
        }])
        return call_id

    def trace_step(
        self, step_type: str,
        description: Optional[str] = None,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        human_override: bool = False,
        time_to_intervention_ms: Optional[int] = None,
    ) -> str:
        self._step_counter += 1
        trace_id = str(uuid.uuid4())
        self._db.insert("agent.trace", [{
            "trace_id":                  trace_id,
            "session_id":                self.session_id,
            "step_order":                self._step_counter,
            "step_type":                 step_type,
            "step_description":          description,
            "input_summary":             input_summary,
            "output_summary":            output_summary,
            "human_override":            human_override,
            "time_to_intervention_ms":   time_to_intervention_ms,
            "timestamp":                 datetime.now(timezone.utc).isoformat(),
        }])
        return trace_id

    # LangChain BaseCallbackHandler interface
    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        self._pending_tool = {
            "tool_name": serialized.get("name", "unknown"),
            "input": input_str,
            "start": time.monotonic(),
            "step_order": self._step_counter + 1,
        }
        self._step_counter += 1

    def on_tool_end(self, output: str, **kwargs) -> None:
        p = self._pending_tool
        elapsed = int((time.monotonic() - p.get("start", time.monotonic())) * 1000)
        self._db.insert("agent.tool_calls", [{
            "call_id": str(uuid.uuid4()), "session_id": self.session_id,
            "step_order": p.get("step_order", self._step_counter),
            "tool_name": p.get("tool_name", "unknown"),
            "tool_input": p.get("input"), "tool_output": output,
            "status": "success", "latency_ms": elapsed,
            "human_override": False,
            "called_at": datetime.now(timezone.utc).isoformat(),
        }])
        self._pending_tool = {}

    def on_tool_error(self, error: Exception, **kwargs) -> None:
        p = self._pending_tool
        elapsed = int((time.monotonic() - p.get("start", time.monotonic())) * 1000)
        self._db.insert("agent.tool_calls", [{
            "call_id": str(uuid.uuid4()), "session_id": self.session_id,
            "step_order": p.get("step_order", self._step_counter),
            "tool_name": p.get("tool_name", "unknown"),
            "tool_input": p.get("input"), "tool_output": None,
            "status": "error", "error_message": str(error),
            "latency_ms": elapsed, "human_override": False,
            "called_at": datetime.now(timezone.utc).isoformat(),
        }])
        self._pending_tool = {}

    def on_agent_action(self, action, **kwargs) -> None:
        self.trace_step("tool_call",
            description=f"Action: {getattr(action, 'tool', 'unknown')}",
            input_summary=str(getattr(action, "tool_input", ""))[:500])

    def on_agent_finish(self, finish, **kwargs) -> None:
        self.trace_step("finish", description="Agent finished",
            output_summary=str(getattr(finish, "return_values", ""))[:500])
