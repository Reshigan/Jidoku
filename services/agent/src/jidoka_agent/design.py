"""The design pass: a client's own documents in, signed-shape intent out.

The consultant in `consultant.py` runs a design it was handed. Its six tools all operate on records
somebody else authored, which made the agent a plan-runner wearing a consultant's job title — and
made "the platform does the configuration" false in the place that mattered most. On the Komatsu
pack, 86 of 87 catalogued object types had no intent at all, and the 62 requirements that describe
them are prose in a Word document that the absorber deliberately does not interpret.

This module is the missing half. It gives the agent the tools to *author* intent, and then refuses
to accept what it authors until four gates pass:

  **It must validate as IR.** `jidoka_core.ir.validate_record` — the same function the API uses.
  Unsigned intent is unloadable (invariant 1) and that is checked here rather than three steps later.

  **Its tier must be the adapter's, not the model's.** ADR-0045. A model that wrote `tier: A` for a
  file-import object would produce a plan of API calls against something SAP publishes no write path
  for, and the plan would look right.

  **Its payload must fit the tenant's own `$metadata`.** `SchemaTwin` checks required fields,
  unknown fields and picklist references against what the *live tenant* publishes — not against what
  the model remembers about SuccessFactors. This is the difference between a plausible record and a
  loadable one.

  **Every value must have a source, or be a decision.** Invariant 2: the platform never invents a
  statutory or client value. A model that cannot source a value raises a typed decision point, and
  `propose_ir` refuses a record whose provenance is empty.

A rejected proposal is returned to the model as a tool result naming what failed, so it fixes it.
That loop — propose, check against the substrate, fix — is what "smart enough" has to mean here: the
platform does not trust the model, it checks it, and it keeps the receipts either way.
"""
import json
import os
from dataclasses import dataclass, field

from jidoka_core import proposals
from jidoka_core.requirements import Requirement
from jidoka_core.schema import IR_SCHEMA
from jidoka_core.twin import SchemaTwin

MODEL = os.environ.get("JIDOKA_DESIGN_MODEL", "claude-opus-5")

#: Effort for the design pass. A wrong field on a pay component is a wrong payslip, so this is not
#: where we economise; the mechanical passes elsewhere in the service can run lower.
EFFORT = os.environ.get("JIDOKA_DESIGN_EFFORT", "xhigh")

#: A token ceiling the model can see and pace itself against, rather than a turn cap it cannot.
#: `MAX_ITERATIONS = 12` in consultant.py is honest for a single question and meaningless for a
#: whole configuration: the model gets cut off mid-object with no way to have known.
TASK_BUDGET = int(os.environ.get("JIDOKA_DESIGN_BUDGET", "400000"))
TASK_BUDGET_BETA = "task-budgets-2026-03-13"

#: Hard stop on the loop regardless of budget. Not a working limit — a runaway guard, because a
#: tool that always errors would otherwise spend the budget arguing with itself.
MAX_TURNS = int(os.environ.get("JIDOKA_DESIGN_MAX_TURNS", "120"))

PROPOSED = "IR_PROPOSED"
REFUSED = "IR_PROPOSAL_REFUSED"
TRACED = "REQUIREMENT_TRACED"


class DesignError(Exception): ...


@dataclass
class Proposal:
    """One authored record, and what the platform found when it checked it."""
    record: dict
    accepted: bool
    problems: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"object": self.record.get("object", ""),
                "external_code": self.record.get("external_code", ""),
                "accepted": self.accepted, "problems": self.problems}


@dataclass
class Outcome:
    """What a design pass produced. Refusals are first-class: a pass that authored forty records
    and refused nine is a more useful report than one that authored thirty-one."""
    accepted: list = field(default_factory=list)
    refused: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    traces: list = field(default_factory=list)
    turns: int = 0
    stopped: str = ""
    transcript: list = field(default_factory=list)

    def summary(self) -> dict:
        return {"accepted": len(self.accepted), "refused": len(self.refused),
                "decisions": len(self.decisions), "traces": len(self.traces),
                "turns": self.turns, "stopped": self.stopped,
                # What the pass actually did, turn by turn. The only record of it, so it is reported
                # rather than kept: a receipt nobody reads is not a receipt.
                "transcript": self.transcript,
                "says": self._says()}

    def _says(self) -> str:
        parts = [f"{len(self.accepted)} record(s) authored and checked against the tenant"]
        if self.refused:
            parts.append(f"{len(self.refused)} refused by the platform's own gates")
        if self.decisions:
            parts.append(f"{len(self.decisions)} decision(s) raised rather than answered")
        if not self.accepted and not self.decisions:
            return ("Nothing was authored and nothing was asked. A design pass that produces "
                    "neither is a pass that did not read its inputs.")
        return ". ".join(parts) + f". Stopped: {self.stopped}."


# --- the tool surface ------------------------------------------------------------------------

def ir_tool_schema() -> dict:
    """The published IR schema, as a tool's input schema.

    A projection, not a copy: the meta keys (`$schema`, `$id`, `title`) mean nothing to a tool
    definition. The projection is deliberately not authoritative — `validate_record` is, and it runs
    on every proposal — so a drift between the two is caught by the gate rather than trusted.
    """
    out = {k: v for k, v in IR_SCHEMA.items() if not k.startswith("$") and k != "title"}
    # The published schema requires source.signed_by and source.date — correctly, for a *signed*
    # record. A drafter is not a signer: asking the model to fill those in would have the tool schema
    # demand the very field `proposals.check` refuses, and would invite a fabricated name. The drafter
    # cites where the values came from; a person signs (invariant 1, invariant 7).
    out["properties"] = {**out["properties"], "source": {
        "type": "object", "required": ["workbook"],
        "properties": {"workbook": {"type": "string", "minLength": 1,
                                    "description": "the document section or decision point"}}}}
    return out


def tools(schema: dict | None = None) -> list[dict]:
    """The design tools. Every closed-shape tool is `strict`, so a malformed call cannot reach the
    gates and does not cost a turn.

    `propose_ir` is the exception and it is not an oversight: an IR record carries `intent`, a
    free-form object whose shape is the product's, and `strict` requires a closed schema at every
    level. A strict `propose_ir` would either reject every real record or need `intent` flattened to
    a string, and the four gates below validate it properly anyway.
    """
    schema = schema or ir_tool_schema()
    return [
        {"name": "read_pack",
         "description": "The absorbed mobilisation pack: requirements, controls, decisions, "
                        "conditions, gates, tasks, contracts, interlocks, scope, ordering, rules.",
         "strict": True,
         "input_schema": {"type": "object", "properties": {
             "register": {"type": "string", "enum": [
                 "requirements", "controls", "decision_points", "programme", "contracts",
                 "interlocks", "scope", "ordering", "rules", "notes"]}},
             "required": ["register"], "additionalProperties": False}},
        {"name": "read_document",
         "description": "A design document's prose and tables. The absorber does not interpret "
                        "prose; this is where it is read. Sections come back whole.",
         "strict": True,
         "input_schema": {"type": "object", "properties": {
             "name": {"type": "string", "description": "the document, as read_pack names it"},
             "section": {"type": "string", "description": "a heading, or empty for the outline"}},
             "required": ["name", "section"], "additionalProperties": False}},
        {"name": "read_metadata",
         "description": "What THIS tenant publishes for an entity: its fields, which are required, "
                        "and which are picklist-backed. The authority on whether a record will load.",
         "strict": True,
         "input_schema": {"type": "object", "properties": {"entity": {"type": "string"}},
                          "required": ["entity"], "additionalProperties": False}},
        {"name": "read_tier",
         "description": "The adapter's tier for an object: A where the product publishes a write "
                        "API, B where a person imports a file, C where only a UI exists. The "
                        "product decides this, never the design.",
         "strict": True,
         "input_schema": {"type": "object", "properties": {"object": {"type": "string"}},
                          "required": ["object"], "additionalProperties": False}},
        {"name": "propose_ir",
         "description": "Author one configuration record. Checked against IR validation, the "
                        "adapter's tier map and the tenant's $metadata before it is accepted; a "
                        "refusal comes back naming what failed so you can fix it. Every value needs "
                        "a source — a document reference or a resolved decision.",
         # Not strict: see the docstring. `intent` is the product's shape, not ours.
         "input_schema": {"type": "object", "properties": {
             "record": schema,
             "sources": {"type": "array", "items": {"type": "string"},
                         "description": "where each value came from: document section, or DP id"}},
             "required": ["record", "sources"], "additionalProperties": False}},
        {"name": "propose_trace",
         "description": "Say which configuration objects satisfy a requirement. A judgement about "
                        "the client's design: proposed here, signed by a person.",
         "strict": True,
         "input_schema": {"type": "object", "properties": {
             "req_id": {"type": "string"},
             "objects": {"type": "array", "items": {"type": "string"}},
             "why": {"type": "string"}},
             "required": ["req_id", "objects", "why"], "additionalProperties": False}},
        {"name": "raise_dp",
         "description": "The value is the client's to choose or is set by statute and you cannot "
                        "source it. Raise it. Never guess it — a guessed statutory value is the one "
                        "failure this platform exists to prevent.",
         "strict": True,
         "input_schema": {"type": "object", "properties": {
             "dp_id": {"type": "string"},
             "dp_type": {"type": "string", "enum": ["DESIGN", "STATUTORY", "ONE_WAY", "COMMERCIAL"]},
             "question": {"type": "string"},
             "owner": {"type": "string"},
             "why_not_sourced": {"type": "string"}},
             "required": ["dp_id", "dp_type", "question", "owner", "why_not_sourced"],
             "additionalProperties": False}},
    ]


SYSTEM = """You are JIDOKA's design authority pass. You author SAP configuration intent from a \
client's own signed documents, and nothing else.

Rules, in order of precedence:

1. Never invent a value. Every field you write traces to a document section you have read or to a \
resolved decision point. If you cannot source it, call raise_dp. A statutory value you guessed is \
the single failure this platform exists to prevent, and it will reach a payslip.
2. The product decides the tier, not you. Call read_tier before you write one.
3. The tenant decides the shape, not your memory of SuccessFactors. Call read_metadata before you \
write an entity's fields; write only fields it publishes, and every field it requires.
4. Read before you write. The pack's registers and the documents' prose are the inputs; a record \
authored without reading them is a guess with paperwork.
5. A refusal is information, not an obstacle. When propose_ir refuses a record, fix what it names \
and propose again. Do not work around a gate.
6. You are the builder, never the approver. Nothing you author executes until a person signs it, \
and you cannot sign: never write source.signed_by or source.date — cite where each value came from in \
`sources` and the platform records it. A record carrying a name you wrote is refused. Write the \
rationale a reviewer needs, not just the conclusion.
7. Say what you could not do. A design pass that silently skipped a scope item is worse than one \
that raised a decision about it."""


class DesignSession:
    """The tool implementations, and the gates they answer to.

    Constructed with the things the platform already knows: the absorbed pack, the documents, the
    adapter (for the tier map) and the tenant's `$metadata` (for the twin). Nothing here reaches the
    network — a design pass reads what has already been read, which is also what makes it testable.
    """

    def __init__(self, pack: dict, adapter, metadata: dict | None = None,
                 documents: dict | None = None, picklists: dict | None = None):
        self.pack = pack
        self.adapter = adapter
        self.twin = SchemaTwin(metadata or {})
        self.metadata = metadata or {}
        self.documents = documents or {}
        self.picklists = picklists
        self.out = Outcome()

    # --- reads -------------------------------------------------------------------------------

    def read_pack(self, register: str) -> dict:
        if register == "requirements":
            return {"requirements": self.pack.get("specification", {}).get("requirements", [])}
        if register == "controls":
            return {"controls": self.pack.get("specification", {}).get("controls", [])}
        if register in ("programme", "contracts", "interlocks", "scope", "ordering", "rules",
                        "notes", "decision_points"):
            return {register: self.pack.get(register, [] if register != "contracts" else {})}
        return {"error": f"{register!r} is not a register of this pack."}

    def read_document(self, name: str, section: str) -> dict:
        doc = self.documents.get(name)
        if doc is None:
            return {"error": f"{name!r} is not a document of this pack. Available: "
                             f"{sorted(self.documents)}"}
        if not section:
            return {"outline": doc.get("headings", []),
                    "note": "Ask for a section by heading. The prose is the reasoning; the tables "
                            "are already in the pack's registers."}
        want = section.strip().lower()
        hit = [h for h in doc.get("headings", []) if want in h.lower()]
        if not hit:
            return {"error": f"no section of {name!r} matches {section!r}",
                    "outline": doc.get("headings", [])}
        return {"section": hit[0], "text": doc.get("sections", {}).get(hit[0], "")}

    def read_metadata(self, entity: str) -> dict:
        ent = self.metadata.get(entity)
        if ent is None:
            return {"error": f"this tenant's $metadata does not publish {entity!r}. Either the "
                             f"object is not configurable through the API on this release, or the "
                             f"name is wrong. Do not write a record against it.",
                    "published": sorted(self.metadata)[:40]}
        return {"entity": entity, "fields": ent["fields"]}

    def read_tier(self, object: str) -> dict:  # noqa: A002 — the schema's field name
        tier = self.adapter.tier_map().get(object)
        if tier is None:
            return {"object": object, "tier": None,
                    "note": "no adapter declares this object. It may be tier B or C — a person "
                            "does it — and it may never be tier A: a claimed write path nothing "
                            "can name is a claim with nothing behind it."}
        return {"object": object, "tier": tier,
                "write_target": self.adapter.write_target(object) or ""}

    # --- writes, and the gates ---------------------------------------------------------------

    def propose_ir(self, record: dict, sources: list) -> dict:
        if not isinstance(record, dict):
            return {"accepted": False,
                    "problems": [f"A record is an object, not a {type(record).__name__}. Send the "
                                 f"fields, not a description of them."]}
        sources = list(sources or [])
        problems = self._check(record, sources)
        # Stored as a draft: provenance from what was *cited*, and no signature at all. Whatever
        # `source` the model typed is replaced, so a proposal that passes cannot carry a name.
        stored = proposals.draft(record, sources) if not problems else record
        proposal = Proposal(record=stored, accepted=not problems, problems=problems)
        (self.out.accepted if proposal.accepted else self.out.refused).append(proposal)
        if problems:
            return {"accepted": False, "problems": problems,
                    "note": "Fix these and propose again. Do not work around them."}
        return {"accepted": True, "object": record.get("object"),
                "external_code": record.get("external_code", ""),
                "note": "Recorded as a draft. It has no signature and cannot have one from you — a "
                        "person signs it, and until then it is not intent."}

    def _check(self, record: dict, sources: list) -> list[str]:
        """The four gates. Every one of them is a check the platform already trusted somewhere
        else; what is new is running them before a record is counted as authored."""
        problems = []

        if not [s for s in sources if str(s).strip()]:
            problems.append(
                "No source given. Every value traces to a document section you read or to a "
                "resolved decision point; a record with no provenance is a guess, and invariant 2 "
                "says the platform does not make them.")

        # Provenance is the drafter's `sources`, so `source.workbook` is stamped from it below; what
        # matters here is that the record carries no signature and is otherwise valid.
        stamped = {**record, "source": {**(record.get("source") or {}),
                                        "workbook": "; ".join(map(str, sources)) or ""}}
        problems.extend(proposals.check(stamped))
        open_dps = _placeholders(record.get("intent"))
        if open_dps:
            problems.append(
                f"Unresolved decision placeholders in the intent: {open_dps}. Raise them with "
                f"raise_dp rather than leaving them in a record — an open decision point "
                f"hard-blocks the plan, so a record carrying one cannot be built anyway.")

        obj = record.get("object", "")
        declared = record.get("tier")
        honest = self.adapter.tier_map().get(obj)
        if honest is None and declared == "A":
            problems.append(
                f"{obj} is declared tier A and no adapter knows it, so nothing can name its write "
                f"path. Tier B or C is available; tier A is not.")
        elif honest is not None and declared != honest:
            problems.append(
                f"Tier mismatch on {obj}: the record says {declared!r} and the "
                f"{self.adapter.product} adapter declares {honest!r}. The product decides what it "
                f"publishes a write path for.")

        # The twin, last, because it is the most specific and its message is the most useful once
        # the cheaper gates have passed.
        if self.metadata:
            entity = self.adapter.write_target(obj) or obj
            if errs := self.twin.validate_payload(entity, record.get("intent", {}),
                                                  self.picklists):
                problems.extend(f"$metadata: {e}" for e in errs)
        return problems

    def propose_trace(self, req_id: str, objects: list, why: str) -> dict:
        known = {r["req_id"] for r in self.pack.get("specification", {}).get("requirements", [])}
        if req_id not in known:
            return {"error": f"{req_id} is not a requirement of this specification."}
        objects = [o.strip() for o in objects if o.strip()]
        if not objects:
            return {"error": "Tracing a requirement to nothing is what it already says. If nothing "
                             "satisfies it, that is a gap for the design authority to record."}
        self.out.traces.append({"req_id": req_id, "objects": objects, "why": why})
        return {"traced": req_id, "objects": objects,
                "note": "Recorded as a proposal. A person signs it — the platform does not accept "
                        "its own traceability."}

    def raise_dp(self, dp_id: str, dp_type: str, question: str, owner: str,
                 why_not_sourced: str) -> dict:
        self.out.decisions.append({"dp_id": dp_id, "dp_type": dp_type, "question": question,
                                   "owner": owner, "why_not_sourced": why_not_sourced})
        return {"raised": dp_id, "dp_type": dp_type,
                "note": "Raised. This blocks planning for anything that depends on it, which is the "
                        "point — it does not block you from authoring the rest."}

    # --- dispatch ----------------------------------------------------------------------------

    HANDLERS = ("read_pack", "read_document", "read_metadata", "read_tier", "propose_ir",
                "propose_trace", "raise_dp")

    def dispatch(self, name: str, args: dict) -> dict:
        if name not in self.HANDLERS:
            return {"error": f"{name!r} is not a tool of the design pass."}
        try:
            return getattr(self, name)(**args)
        except TypeError as ex:
            return {"error": f"{name}: {ex}"}


# --- the loop --------------------------------------------------------------------------------

def request(session: DesignSession, messages: list, schema: dict | None = None,
            system: str = SYSTEM) -> dict:
    """The request body. Separated from the call so a test can assert its shape without a network.

    Cache placement is the whole cost story of a full-configuration run: the pack, the tier map and
    the system prompt are the same on every one of hundreds of turns, and only the last user message
    moves. `cache_control` caches the last cacheable block, so the tools and the system prompt — the
    stable prefix, rendered before messages — are what gets reused.
    """
    return {
        "model": MODEL,
        # Large on purpose, and paired with streaming: a design turn at this effort over a design
        # pack is exactly the shape that hits an HTTP timeout on a non-streaming request, and a
        # timeout halfway through a paid pass is the worst outcome available.
        "max_tokens": 64000,
        "system": system,
        "tools": tools(schema),
        # A snapshot, not the live list. The loop appends to `messages` as it goes, so a request
        # body holding the list itself would keep changing after it was sent — which makes a logged
        # request, or a test's record of one, a description of the present rather than of the call.
        "messages": list(messages),
        "cache_control": {"type": "ephemeral"},
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": EFFORT,
                          "task_budget": {"type": "tokens", "total": TASK_BUDGET}},
        "betas": [TASK_BUDGET_BETA],
    }


def send(client, body: dict):
    """One turn, streamed.

    Streaming is not an optimisation here. A design turn runs adaptive thinking at high effort over
    a whole design pack with a large output ceiling, which is precisely the request shape that hits
    an HTTP timeout — and a timeout halfway through a paid pass loses the turn and the money. The
    stream is not consumed event by event because nothing here displays progress; it is opened so the
    connection stays alive, and `get_final_message` returns the same message a non-streaming call
    would have.
    """
    with client.beta.messages.stream(**body) as stream:
        return stream.get_final_message()


def run(session: DesignSession, brief: str, schema: dict | None = None, client=None,
        max_turns: int = MAX_TURNS) -> Outcome:
    """Author a design from the pack, one turn at a time, until the model stops calling tools.

    `client` is injected: the tests drive this with a scripted client and no network, which is the
    only way a loop like this gets tested at all. In production it is `anthropic.Anthropic()`.
    """
    if client is None:                      # pragma: no cover — requires credentials
        try:
            import anthropic
        except ImportError:                 # the SDK is the `live` extra, not a test dependency
            raise DesignError(
                "Running a design pass needs the Anthropic SDK: pip install "
                "'jidoka-agent[live]'. Testing one does not, which is why it is an extra.") from None
        client = anthropic.Anthropic()

    messages = [{"role": "user", "content": brief}]
    out = session.out
    for turn in range(max_turns):
        out.turns = turn + 1
        message = send(client, request(session, messages, schema))
        blocks = [b for b in message.content if getattr(b, "type", "") == "tool_use"]
        out.transcript.append({"stop_reason": message.stop_reason,
                               "tools": [b.name for b in blocks]})
        messages.append({"role": "assistant", "content": message.content})

        if message.stop_reason == "refusal":
            out.stopped = "the model declined the request"
            return out
        if not blocks:
            out.stopped = "the model stopped calling tools"
            return out

        # Every result in one user message. Split across several, and the model learns not to make
        # parallel calls — which on a per-object design pass is most of the throughput.
        results = []
        for b in blocks:
            got = session.dispatch(b.name, dict(b.input))
            results.append({"type": "tool_result", "tool_use_id": b.id,
                            "content": json.dumps(got, default=str),
                            **({"is_error": True} if "error" in got else {})})
        messages.append({"role": "user", "content": results})

    out.stopped = (f"the runaway guard stopped this pass at {max_turns} turns. Whatever it had "
                   f"authored is above; it is not a complete design and is not claimed as one")
    return out


def requirements_of(pack: dict) -> list[Requirement]:
    """The pack's specification as kernel objects, so a caller can report coverage over what a pass
    authored without the agent service knowing how coverage is computed."""
    return [Requirement(**{k: (tuple(v) if k == "objects" else v) for k, v in r.items()
                           if k in Requirement.__dataclass_fields__})
            for r in pack.get("specification", {}).get("requirements", [])]


def _placeholders(node, path="intent") -> list[str]:
    """Decision-point placeholders left in an intent tree, by path. The same walk the IR loader does
    (`jidoka_core.ir._find_decision_points`), reached without loading a record."""
    from jidoka_core.ir import _find_decision_points
    return _find_decision_points(node or {}, path)
