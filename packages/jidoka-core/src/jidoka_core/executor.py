"""The apply path: signed intent becomes live configuration, or it becomes nothing.

Every gate in CLAUDE.md's invariant list is enforced here, before the adapter is ever asked
to build a payload. The executor never trusts the plan step, the adapter, or the caller —
a step that reaches the substrate has passed the registry, the ledger and the arming check.

Pure stdlib. The adapter is injected; the ledger is injected; nothing here knows about HTTP.
"""
from dataclasses import dataclass, field
from typing import Any, Callable

from . import transport as tp
from .ledger import Ledger
from .registry import SystemRegistry

# What a step can end as. Nothing else is a legal terminal state.
DRY_RUN, APPLIED, VERIFIED, DRIFTED, FAILED, ROLLED_BACK, REFUSED, HANDED_OFF = (
    "DRY_RUN", "APPLIED", "VERIFIED", "DRIFTED", "FAILED", "ROLLED_BACK", "REFUSED", "HANDED_OFF")
# Written and verified in the source system, but not yet in production. Not terminal.
IN_TRANSPORT = "IN_TRANSPORT"
# Some operations landed, some were rejected. Never a success — the substrate needs a rollback.
PARTIAL = "PARTIAL"

# On the ABAP stack the write is only half the change; the transport is the other half.
# ponytail: a flat tuple, not a plugin registry — SAP ships a handful of ABAP products,
# not an open set. Grows to a registry lookup only if adapters need to declare it themselves.
ABAP_PRODUCTS = ("S4HANA", "S/4HANA", "ECC", "R3")


def is_abap(product: str) -> bool:
    return (product or "").upper().replace(" ", "") in {p.upper() for p in ABAP_PRODUCTS}


class ExecutionRefused(Exception):
    """A gate said no. The message is the refusal an operator will read verbatim."""


@dataclass
class ArmedTarget:
    """Arming a live write is an explicit act with a named target and a named person.

    Invariant 6: Tier-A defaults to dry_run=True. Building one of these is the only way
    a write leaves dry run, and it cannot be built without naming both.
    """
    system_id: str
    armed_by: str
    reason: str = ""

    def __post_init__(self):
        if not self.system_id or not self.armed_by:
            raise ExecutionRefused(
                "Arming a live write requires an explicit target system and a named person.")


@dataclass
class StepResult:
    key: str
    tier: str
    system: str
    status: str
    detail: str = ""
    payload: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)
    before: list = field(default_factory=list)
    transport: dict = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        """Done means done in production. On the ABAP stack a verified write is not that."""
        return self.status in (VERIFIED, HANDED_OFF, ROLLED_BACK)


class Executor:
    """Runs one plan step against one adapter, writing every transition to the ledger.

    The caller supplies `apply_fn`: the thing that actually talks to the substrate,
    called as apply_fn(payload) -> dict. In dry run it is never called at all.
    """

    def __init__(self, registry: SystemRegistry, ledger: Ledger, actor: str):
        if not actor:
            raise ExecutionRefused("Execution requires a named actor — the ledger records who, always.")
        self.registry = registry
        self.ledger = ledger
        self.actor = actor

    # ---- gates ---------------------------------------------------------------

    def _assert_armed(self, ir_record, armed: ArmedTarget | None) -> bool:
        """Returns True when the write is live. Absent arming is not an error — it is dry run."""
        if armed is None:
            return False
        if armed.system_id != ir_record.system_binding:
            raise ExecutionRefused(
                f"Armed for {armed.system_id} but this record binds to {ir_record.system_binding}. "
                f"Arming is per-target and is never inherited.")
        if armed.armed_by == self.actor:
            # Invariant 7: the builder may not also be the one who arms the live write.
            raise ExecutionRefused(
                f"{self.actor} is executing this step and may not also arm it (builder != approver).")
        self.registry.assert_writable(armed.system_id)
        return True

    def _assert_snapshot(self, task: str):
        """Invariant 4: no live write without a prior SNAPSHOT entry on this task's chain."""
        if not any(e["task"] == task and e["action"] == "SNAPSHOT" for e in self.ledger.entries):
            raise ExecutionRefused(
                f"{task}: live write refused — no before-snapshot on the ledger. "
                f"Take a snapshot first; a change that cannot be rolled back is not armed, it is a gamble.")

    # ---- the loop ------------------------------------------------------------

    def snapshot(self, task: str, adapter, ir_record, system) -> list[dict]:
        """Read live state before touching it, and put its fingerprint on the chain."""
        before = adapter.extract(system, ir_record.object)
        self.ledger.append(task, "SNAPSHOT", self.actor,
                           f"{len(before)} rows of {ir_record.object} read from {ir_record.system_binding}",
                           object=ir_record.object, system=ir_record.system_binding, rows=len(before))
        return before

    def execute(self, task: str, adapter, ir_record, *,
                armed: ArmedTarget | None = None,
                apply_fn: Callable[[dict], dict] | None = None,
                live_state: list[dict] | None = None,
                transport_request: "tp.TransportRequest | None" = None,
                route: "tp.TransportRoute | None" = None) -> StepResult:
        """Run one IR record end to end: gate, build, apply, verify — and, on ABAP, transport.

        Tier B and C never write — they produce an artefact for a human and stop.
        On an ABAP product a verified write is IN_TRANSPORT until the request lands in PROD.
        """
        key, tier = ir_record.key, ir_record.tier

        if tier != "A":
            payload = adapter.build_apply(ir_record)
            self.ledger.append(task, "HANDED_OFF", self.actor,
                               f"Tier {tier}: {payload.get('kind', 'artefact')} produced for a person",
                               key=key, tier=tier)
            return StepResult(key, tier, ir_record.system_binding, HANDED_OFF,
                              "This step is done by a person, not by the platform.", payload)

        live = self._assert_armed(ir_record, armed)
        if live:
            self._assert_snapshot(task)

        payload = adapter.build_apply(ir_record)
        # The adapter's own default is dry_run=True. Only an armed target flips it.
        payload = {**payload, "dry_run": not live}

        if not live:
            self.ledger.append(task, "DRY_RUN", self.actor,
                               f"{key}: payload built, nothing written", key=key, tier=tier)
            return StepResult(key, tier, ir_record.system_binding, DRY_RUN,
                              "Dry run — the payload is real, the write did not happen.", payload)

        if apply_fn is None:
            raise ExecutionRefused(
                f"{key}: armed for a live write but no apply function was supplied. Refusing to pretend.")

        self.ledger.append(task, "EXECUTED", self.actor, f"{key}: live write to {armed.system_id}",
                           key=key, tier=tier, armed_by=armed.armed_by)
        try:
            outcome = apply_fn(payload)
        except Exception as exc:  # the substrate failed; say what failed, never why in secrets
            self.ledger.append(task, "FAILED", self.actor, f"{key}: {type(exc).__name__}",
                               key=key, tier=tier)
            return StepResult(key, tier, ir_record.system_binding, FAILED, type(exc).__name__, payload)

        # A batch can half-land: the transport returns 202 while individual operations were
        # rejected. Verifying only this record's key would call that a success, so the caller's
        # count of failed operations is honoured before verify() ever runs.
        # ponytail: a plain int, not a result-object protocol — the caller already parsed the batch.
        if (outcome or {}).get("failed_operations"):
            failed = outcome["failed_operations"]
            self.ledger.append(task, "PARTIAL", self.actor,
                               f"{key}: {failed} of {outcome.get('total_operations', '?')} "
                               f"operations failed — substrate left in a partial state",
                               key=key, tier=tier, failed_operations=failed)
            return StepResult(key, tier, ir_record.system_binding, PARTIAL,
                              f"{failed} operation(s) failed; earlier operations stayed committed. "
                              f"Roll back from the snapshot.", payload)

        state = live_state if live_state is not None else outcome.get("live_state", [])
        verification = adapter.verify(ir_record, state)
        status = VERIFIED if verification.get("status") == "MATCH" else DRIFTED
        # An adapter's verification dict is its own vocabulary and may legitimately carry a
        # "key" (S/4 does — the entity key it checked). The executor's own key/tier/status win,
        # or ledger.append() collides on a duplicate keyword and the success path raises.
        detail = {k: v for k, v in verification.items() if k not in ("status", "key", "tier")}
        self.ledger.append(task, "VERIFIED" if status == VERIFIED else "DRIFT_DETECTED", self.actor,
                           f"{key}: {verification.get('status')}", key=key, tier=tier,
                           verified_key=verification.get("key"), **detail)
        result = StepResult(key, tier, ir_record.system_binding, status,
                            str(verification.get("status")), payload, verification)

        if status != VERIFIED or not is_abap(ir_record.product):
            return result  # non-ABAP: VERIFIED is terminal, exactly as before.

        if transport_request is None or route is None:
            # The write already happened; refusing here would strand it. Say plainly that the
            # change is not finished and what is missing.
            result.status = IN_TRANSPORT
            result.detail = (
                f"Verified in {ir_record.system_binding}, but this is an ABAP system and no transport "
                f"request was supplied. The change is not in production. Attach the transport request "
                f"and its route, then advance it.")
            self.ledger.append(task, "IN_TRANSPORT", self.actor, result.detail, key=key, tier=tier)
            return result

        state = tp.import_status(transport_request, route)
        if state["in_production"]:
            return result
        result.status = IN_TRANSPORT
        result.transport = state
        result.detail = (f"Verified in {ir_record.system_binding} but not yet in production. "
                         f"Next hop: {state['next_hop']}. Advance the transport to complete this step.")
        self.ledger.append(task, "IN_TRANSPORT", self.actor, result.detail,
                           key=key, tier=tier, request_id=state["request_id"],
                           currently_in=state["currently_in"], next_hop=state["next_hop"])
        return result

    # ---- transport ----------------------------------------------------------

    def advance_transport(self, task: str, req, route, *, released_by: str = "") -> dict:
        """Release if still modifiable, then import into the next legal hop.

        transport.release/import_into return ledger-shaped dicts; they go on the chain verbatim
        so the route a change actually took is as verifiable as the write itself.
        """
        route.validate(self.registry)
        if route.next_hop(req.imported_into) is None:
            raise ExecutionRefused(
                f"{req.request_id} has reached the end of its route — it is already in production. "
                f"There is no next hop to import into.")
        try:
            if req.status == tp.MODIFIABLE:
                self._append_transport(task, tp.release(req, released_by or self.actor))
            nxt = route.next_hop(req.imported_into)
            self.registry.assert_writable(nxt)
            self._append_transport(task, tp.import_into(req, route, nxt, self.actor))
        except tp.TransportError as exc:
            # Only the type: a substrate error message can echo a bearer token.
            self.ledger.append(task, "TRANSPORT_FAILED", self.actor, type(exc).__name__,
                               request_id=req.request_id)
            raise ExecutionRefused(
                f"{req.request_id}: transport step refused by the source system "
                f"({type(exc).__name__}). Check the request's state on the route before retrying.")
        return tp.import_status(req, route)

    def _append_transport(self, task: str, entry: dict):
        e = dict(entry)
        self.ledger.append(task, e.pop("action"), e.pop("actor"), e.pop("detail", ""), **e)

    def rollback(self, task: str, before: list[dict], apply_fn: Callable[[dict], dict],
                 ir_record, reason: str) -> StepResult:
        """Put back exactly what the snapshot recorded. No snapshot, no rollback — by design."""
        if not before:
            raise ExecutionRefused(
                f"{task}: rollback refused — the snapshot is empty, so there is nothing proven to restore.")
        # The object rides along: a substrate handed rows with no name for what they are would
        # have to guess where to put them back, and a rollback that guesses is not a rollback.
        payload = {"kind": "restore", "system": ir_record.system_binding,
                   "object": ir_record.object, "dry_run": False, "rows": before}
        apply_fn(payload)
        self.ledger.append(task, "ROLLED_BACK", self.actor, reason,
                           key=ir_record.key, rows=len(before))
        return StepResult(ir_record.key, ir_record.tier, ir_record.system_binding,
                          ROLLED_BACK, reason, payload, before=before)
