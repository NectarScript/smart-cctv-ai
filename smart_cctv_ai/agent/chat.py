"""Ask-your-cameras chat agent.

Flow (one round-trip for most questions):
  1. User asks: "how many intrusions on cam1 in the last hour?"
  2. Prompt the LLM with TOOL_SPEC + the question. It returns strict JSON.
  3. We execute the chosen tool against SQLite.
  4. Second LLM call turns the raw tool result into a sentence.

Uses the same local Ollama model as VLM verification (plan: one model, no swap).
"""
from __future__ import annotations
import json
import re
from typing import Any
import httpx
from loguru import logger
from .tools import TOOLS, TOOL_SPEC


class ChatAgent:
    def __init__(self, model: str, ollama_url: str, timeout_seconds: float = 20.0):
        self.model = model
        self.url = ollama_url.rstrip("/")
        self.timeout = timeout_seconds

    def ask(self, question: str) -> dict:
        """Returns {answer, tool, args, result}. Never raises."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                plan = self._plan(client, question)
                tool_name = plan.get("tool")
                args = plan.get("args") or {}
                fn = TOOLS.get(tool_name)
                if fn is None:
                    return {"answer": f"I don't have a tool called '{tool_name}'.",
                            "tool": tool_name, "args": args, "result": None}
                try:
                    result = fn(**args)
                except TypeError as e:
                    result = {"error": f"bad arguments: {e}"}
                except Exception as e:
                    result = {"error": str(e)}
                answer = self._explain(client, question, tool_name, args, result)
                return {"answer": answer, "tool": tool_name,
                        "args": args, "result": result}
        except Exception as e:
            logger.warning(f"chat agent failed: {e}")
            return {"answer": f"(chat offline: {e})",
                    "tool": None, "args": {}, "result": None}

    def _plan(self, client: httpx.Client, question: str) -> dict:
        prompt = (f"You are a helpful assistant that converts a user's question "
                  f"about CCTV events into a tool call.\n{TOOL_SPEC}\n"
                  f"User question: {question}\nJSON:")
        r = client.post(f"{self.url}/api/generate",
                        json={"model": self.model, "prompt": prompt,
                              "stream": False, "format": "json",
                              "options": {"temperature": 0.1}})
        r.raise_for_status()
        text = r.json().get("response", "").strip()
        return _extract_json(text) or {"tool": "list_events", "args": {"limit": 5}}

    def _explain(self, client: httpx.Client, question: str, tool: str,
                 args: dict, result: Any) -> str:
        prompt = (f"The user asked: {question}\n"
                  f"We ran tool `{tool}` with args {json.dumps(args)} and got:\n"
                  f"{json.dumps(result)[:1500]}\n"
                  f"Reply in ONE short sentence that answers the question "
                  f"using these numbers. Do not add explanations about tools.")
        r = client.post(f"{self.url}/api/generate",
                        json={"model": self.model, "prompt": prompt,
                              "stream": False,
                              "options": {"temperature": 0.3}})
        r.raise_for_status()
        return r.json().get("response", "").strip() or "(empty response)"


def _extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None
