"""K5 consultant service: Anthropic tool-use loop over the JIDOKA API.

Role invariant: the agent is BUILDER only — it can snapshot, plan, prepare applies, post evidence;
it has no approve capability by construction (the approve endpoint is simply not in its tool set)."""
import json, os, urllib.request
from typing import Any, Callable

from .client import JidokaClient
from .skills import load_skills, promoted_prompt

API = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("JIDOKA_AGENT_MODEL", "claude-opus-5")
MAX_ITERATIONS = 12  # a consultant that needs more turns than this is looping, not working

TOOLS = [  # deliberately excludes /ledger/approve — see role invariant above
    {"name": "load_ir", "description": "Upload validated IR records to an engagement",
     "input_schema": {"type": "object", "properties": {"eid": {"type": "string"},
                      "records": {"type": "array"}}, "required": ["eid", "records"]}},
    {"name": "build_plan", "description": "Build the dependency-ordered, tier-split run plan",
     "input_schema": {"type": "object", "properties": {"eid": {"type": "string"}}, "required": ["eid"]}},
    {"name": "ledger_append", "description": "Record snapshot/executed evidence on the governance ledger",
     "input_schema": {"type": "object", "properties": {"eid": {"type": "string"}, "task": {"type": "string"},
                      "action": {"type": "string", "enum": ["SNAPSHOT", "EXECUTED"]},
                      "detail": {"type": "string"}}, "required": ["eid", "task", "action"]}},
    {"name": "raise_dp", "description": "Raise a typed Decision Point instead of guessing a value",
     "input_schema": {"type": "object", "properties": {"eid": {"type": "string"}, "dp_id": {"type": "string"},
                      "dp_type": {"type": "string"}, "question": {"type": "string"},
                      "owner": {"type": "string"}}, "required": ["eid", "dp_id", "dp_type", "question", "owner"]}},
    {"name": "get_plan", "description": "Read the current run plan for an engagement",
     "input_schema": {"type": "object", "properties": {"eid": {"type": "string"}}, "required": ["eid"]}},
    {"name": "get_ledger", "description": "Read the verified governance ledger chain",
     "input_schema": {"type": "object", "properties": {"eid": {"type": "string"}}, "required": ["eid"]}},
]

SYSTEM = """You are JIDOKA's K5 senior SAP consultant (builder role only; humans approve).
Operating rules, non-negotiable: never invent statutory or client values — raise a typed Decision Point;
sequence before configuring; every claim about a product's behaviour must cite metadata, documentation,
or a signed engagement source; challenge weak designs with rationale; treat irreversible actions as ceremonies
requiring named human approvers; write rationale, not just conclusions."""


def system_prompt() -> str:
    """SYSTEM plus only those skills that passed the K5 exam (governed learning gate)."""
    promoted = promoted_prompt(load_skills())
    return f"{SYSTEM}\n\n{promoted}" if promoted else SYSTEM


def ask(messages: list[dict], system: str | None = None) -> dict:
    req = urllib.request.Request(API, method="POST",
        headers={"content-type": "application/json",
                 "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                 "anthropic-version": "2023-06-01"},
        data=json.dumps({"model": MODEL, "max_tokens": 16000, "system": system or SYSTEM,
                         "thinking": {"type": "adaptive"},
                         "tools": TOOLS, "messages": messages}).encode())
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def dispatch(client: JidokaClient, name: str, args: dict) -> Any:
    """Map a tool_use block to the builder-only client. Unknown names are refused, not guessed."""
    fn = {"load_ir": client.load_ir, "build_plan": client.build_plan,
          "ledger_append": client.ledger_append, "raise_dp": client.raise_dp,
          "get_plan": client.get_plan, "get_ledger": client.get_ledger}.get(name)
    if fn is None:
        raise KeyError(f"no such tool: {name}")
    return fn(**args)


def run(prompt: str, client: JidokaClient, ask_fn: Callable[..., dict] = ask,
        max_iterations: int = MAX_ITERATIONS) -> list[dict]:
    """Drive the tool-use loop to end_turn, returning the full transcript.

    ask_fn is injectable so the loop is testable without a key or a network."""
    messages: list[dict] = [{"role": "user", "content": prompt}]
    system = system_prompt()
    for _ in range(max_iterations):
        reply = ask_fn(messages, system)
        messages.append({"role": "assistant", "content": reply["content"]})
        if reply.get("stop_reason") != "tool_use":
            return messages
        results = []
        for block in reply["content"]:
            if block.get("type") != "tool_use":
                continue
            try:
                out, err = dispatch(client, block["name"], block["input"]), False
            except Exception as ex:  # a failed tool is reported back, never dropped
                out, err = f"{type(ex).__name__}: {ex}", True
            results.append({"type": "tool_result", "tool_use_id": block["id"],
                            "content": json.dumps(out), "is_error": err})
        messages.append({"role": "user", "content": results})  # all results in ONE user message
    raise RuntimeError(f"tool-use loop did not terminate within {max_iterations} iterations")
