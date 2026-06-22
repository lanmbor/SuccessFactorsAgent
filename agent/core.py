# agent/core.py
import json
import litellm
from pathlib import Path
from typing import Any
from agent.tools import TOOLS, sf_list_entities, sf_get_schema, sf_query, sf_create, sf_update, sf_delete
from sf.client import SFClient
from config import Config

_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "system.md"
_LOCAL_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "system_local.md"
SYSTEM_PROMPT = _PROMPT_FILE.read_text(encoding="utf-8").strip()
if _LOCAL_PROMPT_FILE.exists():
    _local = _LOCAL_PROMPT_FILE.read_text(encoding="utf-8").strip()
    if _local:
        SYSTEM_PROMPT += "\n\n" + _local

MAX_TOOL_ROUNDS = 20
MAX_TOOL_RESPONSE_CHARS = 20_000  # ~5k tokens — truncate oversized tool results
MAX_HISTORY_MESSAGES = 40         # keep system prompt + last 40 messages


def _truncate(text: str) -> str:
    if len(text) <= MAX_TOOL_RESPONSE_CHARS:
        return text
    kept = text[:MAX_TOOL_RESPONSE_CHARS]
    return kept + f"\n\n[...truncated, {len(text) - MAX_TOOL_RESPONSE_CHARS} chars omitted]"


def _trim_history(history: list[dict]) -> list[dict]:
    """Keep the system prompt + the most recent MAX_HISTORY_MESSAGES messages."""
    system = [m for m in history if m["role"] == "system"]
    rest = [m for m in history if m["role"] != "system"]
    if len(rest) > MAX_HISTORY_MESSAGES:
        rest = rest[-MAX_HISTORY_MESSAGES:]
    return system + rest


class Agent:
    def __init__(self, sf_client: SFClient, config: Config) -> None:
        self._client = sf_client
        self._config = config
        self._sessions: dict[str, list[dict]] = {}

    def _history(self, session_id: str) -> list[dict]:
        if session_id not in self._sessions:
            self._sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        return self._sessions[session_id]

    async def _dispatch(self, name: str, args: dict[str, Any]) -> str:
        if name == "sf_list_entities":
            return await sf_list_entities(self._client)
        if name == "sf_get_schema":
            return await sf_get_schema(self._client, args["entity_name"])
        if name == "sf_query":
            entity = args["entity_name"]
            remaining = {k: v for k, v in args.items() if k != "entity_name"}
            return await sf_query(self._client, entity, **remaining)
        if name == "sf_create":
            return await sf_create(self._client, args["entity_name"], args["data"])
        if name == "sf_update":
            return await sf_update(self._client, args["entity_name"], args["key"], args["data"])
        if name == "sf_delete":
            return await sf_delete(self._client, args["entity_name"], args["key"])
        return f"Unknown tool: {name}"

    async def chat(self, session_id: str, message: str) -> str:
        history = self._history(session_id)
        history.append({"role": "user", "content": message})
        model = f"{self._config.LLM_PROVIDER.lower()}/{self._config.LLM_MODEL}"
        kwargs: dict = {
            "model": model,
            "messages": history,
            "tools": TOOLS,
            "tool_choice": "auto",
        }
        if self._config.LLM_API_KEY:
            kwargs["api_key"] = self._config.LLM_API_KEY
        if self._config.LLM_API_BASE:
            kwargs["api_base"] = self._config.LLM_API_BASE

        for _ in range(MAX_TOOL_ROUNDS):
            kwargs["messages"] = _trim_history(history)
            response = await litellm.acompletion(**kwargs)
            msg = response.choices[0].message
            assistant_entry: dict = {"role": "assistant"}
            if msg.content is not None:
                assistant_entry["content"] = msg.content
            if msg.tool_calls:
                assistant_entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ]
            history.append(assistant_entry)

            if not msg.tool_calls:
                return msg.content or ""

            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError as e:
                    result = f"Tool call failed: invalid JSON arguments — {e}"
                    args = {}
                else:
                    result = await self._dispatch(tc.function.name, args)
                result = _truncate(result)
                history.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        return "Agent exceeded maximum tool-call rounds without a final response."
