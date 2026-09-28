"""Execution surface: snapshot, arm, execute, rollback, transport.

Arming and executing are deliberately two calls by two people. An approver arms a named target;
a builder then spends that arming. Neither can do both — the role table forbids it (auth.py) and
the executor forbids it again (armed_by != actor). Two gates, because this is the one endpoint
that changes a customer's production system.
"""
import time

from fastapi import APIRouter, Depends, HTTPException
from jidoka_adapters.base import AdapterError
from jidoka_core import transport as tp
from jidoka_core.clock import stamp
from jidoka_core.drift import intent_hash
from jidoka_core.executor import ArmedTarget, ExecutionRefused, Executor, is_abap
from jidoka_core.registry import RegistryError, WriteLockViolation
from pydantic import BaseModel

from ..auth import Identity, require
from ..connectors import ConnectorError, build as build_connector, build_reader
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/execution", tags=["execution"])

# ponytail: armings live in process memory and die with it — which is the safe failure direction.
# A restart disarms every target rather than leaving a live write primed. Persist only if operators
# ask for armings that survive a deploy.
_ARMED: dict[tuple[str, str], ArmedTarget] = {}

# (eid, key) -> the rows a snapshot actually read. Held server-side on purpose: a rollback that
# restored a client-supplied "before" would be an arbitrary write wearing a snapshot's name, and
# invariant 4's whole point is that the restored state is the one the ledger already fingerprinted.
_BEFORE: dict[tuple[str, str], list[dict]] = {}

# (eid, key) -> the transport request carrying that step's write, and the route it must follow.
# Created when an ABAP step is executed live; the route comes from the registry's declared
# promotion paths, never from the caller.
_TRANSPORTS: dict[tuple[str, str], tuple[tp.TransportRequest, tp.TransportRoute]] = {}


def _route_for(e, system_id: str) -> tp.TransportRoute:
    """Walk the landscape's declared promotion paths from this system to the end of the chain."""
    hops, seen = [system_id], {system_id}
    nxt = dict(e.registry.landscape()["promotion_paths"])
    while hops[-1] in nxt and nxt[hops[-1]] not in seen:
        hops.append(nxt[hops[-1]])
        seen.add(hops[-1])
    return tp.TransportRoute(hops)


def _adapter_for(product: str, connector=None):
    """Resolve the product's adapter. Unknown product is a refusal, never a guess.

    The connector's reader is injected here rather than configured on the adapter, so an adapter
    instance can never outlive the binding that authorised it to read a customer's system.
    """
    from jidoka_adapters import ADAPTERS

    if product not in ADAPTERS:
        raise HTTPException(422, f"No adapter registered for product {product!r}. "
                                 f"Known products: {sorted(ADAPTERS)}.")
    return ADAPTERS[product](fetch=connector.fetch) if connector else ADAPTERS[product]()


def _record_or_404(e, key: str):
    for r in e.ir:
        if r.key == key:
            return r
    raise HTTPException(404, f"No IR record with key {key!r} in this engagement.")


def _executor(e, identity: Identity) -> Executor:
    return Executor(e.registry, e.ledger, identity.subject)


#: How long an arming stands unless the approver says otherwise. Long enough for a cutover step
#: with a person watching, short enough that a forgotten arming lapses before anybody is
#: surprised by it. An approver can ask for less; nothing can ask for more without saying so.
DEFAULT_ARMING_MINUTES = 60
MAX_ARMING_MINUTES = 12 * 60


class Arm(BaseModel):
    system_id: str
    reason: str = ""
    minutes: int = DEFAULT_ARMING_MINUTES


@router.post("/arm")
def arm(eid: str, body: Arm, identity: Identity = Depends(require("arm"))):
    """Approver-only. Refuses immediately if the target is not writable, so an operator learns
    the system is write-locked here rather than halfway through an apply."""
    e = get_or_404(eid)
    try:
        e.registry.assert_writable(body.system_id)
    except WriteLockViolation as ex:
        raise HTTPException(403, str(ex))
    except RegistryError as ex:
        raise HTTPException(404, str(ex))
    if body.minutes < 1 or body.minutes > MAX_ARMING_MINUTES:
        raise HTTPException(
            422, f"An arming stands for between 1 and {MAX_ARMING_MINUTES} minutes. A window "
                 f"longer than that is not a window — arm it again when you need it.")
    expires_at = time.time() + body.minutes * 60
    target = ArmedTarget(body.system_id, identity.subject, body.reason, expires_at=expires_at)
    _ARMED[(eid, body.system_id)] = target
    lapses = stamp(expires_at)
    e.ledger.append("EXECUTION", "ARMED", identity.subject,
                    f"{body.system_id} armed for live write until {lapses}: "
                    f"{body.reason or 'no reason given'}",
                    system=body.system_id, expires_at=lapses, minutes=body.minutes)
    return {"armed": body.system_id, "armed_by": identity.subject, "reason": body.reason,
            "expires_at": lapses, "minutes": body.minutes}


@router.delete("/arm/{system_id}")
def disarm(eid: str, system_id: str, identity: Identity = Depends(require("arm"))):
    e = get_or_404(eid)
    _ARMED.pop((eid, system_id), None)
    e.ledger.append("EXECUTION", "DISARMED", identity.subject, system_id, system=system_id)
    return {"armed": None}


@router.get("/arm")
def armed(eid: str, identity: Identity = Depends(require("read"))):
    """Live armings only. A lapsed one is not shown as armed, because it is not: the console
    would otherwise offer a write the executor is about to refuse."""
    get_or_404(eid)
    return {"armed": [{"system_id": t.system_id, "armed_by": t.armed_by, "reason": t.reason,
                       "expires_at": stamp(t.expires_at)
                       if t.expires_at else ""}
                      for (e_id, _), t in _ARMED.items() if e_id == eid and not t.expired()]}


class Step(BaseModel):
    key: str


class Rollback(Step):
    reason: str = ""


class NotArmed(Exception):
    """A write with no armed target. Undoing one is still a write (ADR-0009)."""


class NoSnapshotHeld(Exception):
    """Nothing proven to restore. Invariant 4 refuses rather than writing a guess."""


def rollback_step(e, identity: Identity, key: str, reason: str):
    """Put back exactly what the snapshot read. The single implementation, shared with the crew.

    Every gate an execute wears, because the direction of a change is irrelevant to the
    invariants: invariant 3 via the registry, invariant 4 via the snapshot the executor refuses to
    proceed without, invariant 6 via the armed target, invariant 7 via armed_by != actor — all
    checked by the executor's own arming gate rather than re-implemented here.
    """
    r = _record_or_404(e, key)
    target = _ARMED.get((e.engagement_id, r.system_binding))
    ex_ = _executor(e, identity)
    if not ex_._assert_armed(r, target):
        raise NotArmed(
            f"{r.system_binding} is not armed. A rollback writes to a live system, so it needs an "
            f"armed target exactly as an execute does — ask an approver to arm it.")
    before = _BEFORE.get((e.engagement_id, key))
    if before is None:
        raise NoSnapshotHeld(
            f"{key}: rollback refused — this process holds no snapshot for this step. Take a "
            f"before-snapshot first; there is nothing proven to restore.")
    if r.system_binding not in e.connectors:
        raise NoSnapshotHeld(
            f"{r.system_binding}: armed, but no connector is bound for {r.product}. A rollback "
            f"with no substrate would report a restore that never happened.")
    return ex_.rollback(key, before, e.connectors[r.system_binding].apply, r, reason)


def snapshot_step(e, identity: Identity, key: str) -> list[dict]:
    """Read live state, chain its fingerprint, and hold the rows server-side.

    The holding is the load-bearing part: a rollback restores what the platform itself read, never
    a "before" a caller supplied (ADR-0009). The crew's operator snapshots through this same
    function, so a run that writes is a run that can be undone — one that snapshotted by some
    other route would leave the rollback path with nothing to restore.
    """
    r = _record_or_404(e, key)
    system = e.registry.get(r.system_binding)
    rows = _executor(e, identity).snapshot(
        key, _adapter_for(r.product, e.connectors.get(r.system_binding)), r, system)
    _BEFORE[(e.engagement_id, key)] = [dict(x) for x in rows]
    return rows


@router.post("/snapshot")
def snapshot(eid: str, body: Step, identity: Identity = Depends(require("snapshot"))):
    """Read live state and chain its fingerprint. Nothing may be written until this has run."""
    e = get_or_404(eid)
    try:
        rows = snapshot_step(e, identity, body.key)
    except RegistryError as ex:
        raise HTTPException(404, str(ex))
    except RuntimeError as ex:
        # The adapter has no reader bound. A snapshot that cannot read is not a snapshot, and
        # letting it pass would satisfy invariant 4 with an empty before-state — worse than failing.
        raise HTTPException(409, f"cannot snapshot — {ex}")
    return {"key": body.key, "rows": len(rows), "before": rows}


def execute_step(e, identity: Identity, key: str):
    """Run one step, armed or not. The single implementation of the apply path.

    The endpoint below maps its refusals onto HTTP; the crew's operator lets them travel back
    through the syscall boundary as a refused step (ADR-0020). Neither gets its own copy of the
    gates, because two copies of a gate are one gate and one bug waiting to happen.

    Arming is read here, never granted here: `_ARMED` is written only by the arm endpoint, which
    an approver holds and a builder does not. Absent an arming this is a dry run, whoever asked.
    """
    eid = e.engagement_id
    r = _record_or_404(e, key)
    target = _ARMED.get((eid, r.system_binding))
    connector = e.connectors.get(r.system_binding)
    req, route = _transport_for(e, eid, key, r) if (target and is_abap(r.product)) else (None, None)
    return _executor(e, identity).execute(
        key, _adapter_for(r.product, connector), r, armed=target,
        apply_fn=_apply_fn(e, r) if target else None,
        transport_request=req, route=route)


@router.post("/execute")
def execute(eid: str, body: Step, identity: Identity = Depends(require("execute"))):
    """Dry run unless an approver has armed this record's target. Tier B/C hand off to a human."""
    e = get_or_404(eid)
    try:
        res = execute_step(e, identity, body.key)
    except ExecutionRefused as ex:
        raise HTTPException(409, str(ex))
    except WriteLockViolation as ex:
        raise HTTPException(403, str(ex))
    except AdapterError as ex:
        # The adapter declining to invent a write path is a refusal, not a fault. Its message
        # names the dishonest tier_map entry, which is the thing that has to be fixed.
        raise HTTPException(422, str(ex))
    return {"key": res.key, "tier": res.tier, "system": res.system, "status": res.status,
            "detail": res.detail, "payload": res.payload, "verification": res.verification,
            "transport": res.transport}


def _transport_for(e, eid: str, key: str, r):
    """The request carrying this step's write, and the route it must travel. Built once per step.

    A landscape with no declared promotion path out of this system has no route, so there is
    nothing to advance: the step still reports IN_TRANSPORT and says what is missing (ADR-0006).
    """
    held = _TRANSPORTS.get((eid, key))
    if held:
        return held
    try:
        route = _route_for(e, r.system_binding).validate(e.registry)
    except (tp.TransportError, RegistryError):
        return None, None
    req = tp.TransportRequest(
        request_id=f"{r.system_binding}-{abs(hash(key)) % 900000 + 100000}",
        owner=r.source.get("signed_by", ""), description=key,
        source_system=r.system_binding, objects=[r.object])
    _TRANSPORTS[(eid, key)] = (req, route)
    return req, route


# ---- rollback: restoring a prior state is a write, and wears every gate a write wears ---------


@router.post("/rollback")
def rollback(eid: str, body: Rollback, identity: Identity = Depends(require("execute"))):
    """Put back exactly what the snapshot read. Same gates as execute, for the same reason:
    this call changes a customer's live system, and the direction of the change is irrelevant
    to the invariants.

    Invariant 3 via registry.assert_writable + a bound connector; invariant 4 via the snapshot
    the executor refuses to proceed without; invariant 6 via the armed target; invariant 7 via
    armed_by != actor, checked by the executor's own arming gate rather than re-implemented here.
    """
    e = get_or_404(eid)
    try:
        res = rollback_step(e, identity, body.key, body.reason or "rolled back from the console")
    except NotArmed as exc:
        raise HTTPException(403, str(exc))
    except NoSnapshotHeld as exc:
        raise HTTPException(409, str(exc))
    except ExecutionRefused as exc:
        raise HTTPException(409 if "refused" in str(exc) else 403, str(exc))
    except WriteLockViolation as exc:
        raise HTTPException(403, str(exc))
    except RegistryError as exc:
        raise HTTPException(404, str(exc))
    except ConnectorError as exc:
        raise HTTPException(422, str(exc))
    return {"key": res.key, "tier": res.tier, "system": res.system, "status": res.status,
            "detail": res.detail, "rows": len(res.before)}


# ---- transport: on the ABAP stack the write is only half the change (ADR-0006) ----------------


class NoTransportHeld(Exception):
    """Asked to advance a step that never captured a transport. Not a fault — a wrong question."""


def advance_step(e, identity: Identity, key: str) -> dict:
    """One hop along the declared route. The single implementation, shared with the crew.

    A transport exists only because an armed live write was captured in it, and the route came
    from the promotion paths a human registered — so moving a change along it is the completion
    of an authorised write (ADR-0006), not a new authority.
    """
    r = _record_or_404(e, key)
    if not is_abap(r.product):
        raise tp.TransportError(
            f"{r.product} is not an ABAP product — its changes do not travel by transport, "
            f"so there is nothing to advance.")
    held = _TRANSPORTS.get((e.engagement_id, key))
    if held is None:
        raise NoTransportHeld(
            f"{key}: no transport request is held for this step. Execute it live first — "
            f"a transport exists because a write was captured in it, never before.")
    req, route = held
    state = _executor(e, identity).advance_transport(key, req, route)
    landed = state["currently_in"]
    e.ledger.append(key, "TRANSPORT_ADVANCED", identity.subject,
                    f"{req.request_id} imported into {landed} "
                    f"({e.registry.get(landed).environment}); next hop {state['next_hop'] or 'none — in production'}",
                    request_id=req.request_id, target_system=landed,
                    target_environment=e.registry.get(landed).environment,
                    next_hop=state["next_hop"], in_production=state["in_production"])
    return {"key": key, **state}


@router.post("/transport")
def advance(eid: str, body: Step, identity: Identity = Depends(require("transport"))):
    """Release if still modifiable, then import into the next legal hop. One call, one hop."""
    e = get_or_404(eid)
    try:
        return advance_step(e, identity, body.key)
    except NoTransportHeld as exc:
        raise HTTPException(404, str(exc))
    except ExecutionRefused as exc:
        raise HTTPException(409, str(exc))
    except WriteLockViolation as exc:
        raise HTTPException(403, str(exc))
    except tp.TransportError as exc:
        raise HTTPException(422, str(exc))
    except RegistryError as exc:
        raise HTTPException(404, str(exc))


@router.get("/transport")
def transports(eid: str, identity: Identity = Depends(require("read"))):
    """Where every in-flight transport currently sits. The console reads this, never guesses it."""
    get_or_404(eid)
    return {"transports": [{"key": k, **tp.import_status(req, route)}
                           for (e_id, k), (req, route) in _TRANSPORTS.items() if e_id == eid]}


def _apply_fn(e, r):
    """The substrate call. Left unbound until a connector is bound to this system: refusing is
    correct, because a silently no-op apply reported as success is the worst outcome."""
    def _refuse(payload):
        raise ExecutionRefused(
            f"{r.system_binding}: armed, but no connector is bound for {r.product}. "
            f"Bind a connector before arming, or run unarmed for a dry run.")

    c = e.connectors.get(r.system_binding)
    return c.apply if c else _refuse


class Attest(BaseModel):
    key: str
    note: str = ""


@router.post("/attest")
def attest(eid: str, body: Attest, identity: Identity = Depends(require("execute"))):
    """A person states they did work this platform has no way to read back (ADR-0022).

    Offered only where the adapter says the product publishes no read path. Everywhere else the
    live system is the answer, and accepting somebody's word instead would let a claim mask a
    machine-checkable failure — which is the whole disease this platform exists to treat.

    The attestation is written by the act, under the caller's own identity (ADR-0015), and it
    carries the hash of the intent it covers so that a later change to that intent retires it
    rather than silently inheriting it.
    """
    e = get_or_404(eid)
    r = _record_or_404(e, body.key)
    connector = e.connectors.get(r.system_binding)
    adapter = _adapter_for(r.product, connector)
    if adapter.verifiable(r.object):
        raise HTTPException(
            409, f"{r.object} can be read back on {r.product}, so JIDOKA checks it rather than "
                 f"taking anyone's word for it. Run a verification.")
    entry = e.ledger.append(body.key, "ATTESTED", identity.subject,
                            body.note or f"{identity.subject} states this change was made by hand",
                            intent_hash=intent_hash(r.intent), object=r.object,
                            system=r.system_binding)
    return {"key": body.key, "attested_by": identity.subject, "at": entry["ts"],
            "note": entry["detail"]}


class Bind(BaseModel):
    system_id: str
    kind: str = "mock"
    base_url: str = ""
    secret_env: str = ""      # NAME of the env var prefix holding the credential — never a secret


@router.post("/connector")
def bind_connector(eid: str, body: Bind, identity: Identity = Depends(require("register_system"))):
    """Give a system a reader and a writer. Refuses anything invariant 3 forbids, at bind time
    rather than at write time — the earlier refusal is the kinder one."""
    e = get_or_404(eid)
    product = next((r.product for r in e.ir if r.system_binding == body.system_id), "")
    if not product:
        raise HTTPException(404, f"No IR record binds to {body.system_id!r}, so its product is "
                                 f"unknown and no adapter can be chosen for it.")
    try:
        connector = build_connector(body.kind, body.system_id, product, e.registry,
                                    body.base_url, body.secret_env)
    except WriteLockViolation as ex:
        raise HTTPException(403, str(ex))
    except RegistryError as ex:
        raise HTTPException(404, str(ex))
    except ConnectorError as ex:
        raise HTTPException(422, str(ex))
    e.connectors[body.system_id] = connector
    e.ledger.append("EXECUTION", "CONNECTOR_BOUND", identity.subject,
                    f"{body.system_id} bound to a {body.kind} connector for {product}",
                    system=body.system_id, kind=body.kind)
    return {"system_id": body.system_id, "kind": connector.kind, "product": product}


@router.post("/connector/reader")
def bind_reader(eid: str, body: Bind, identity: Identity = Depends(require("register_system"))):
    """Give a system a reader with no writer.

    A harvest reads a system's structure, and the systems most worth reading — SOURCE_LEGACY,
    TWIN — are exactly the ones that may never hold a write credential (invariant 3). `build`
    refuses them, correctly. This binds something with no write half instead, so the invariant
    holds by the shape of the binding rather than by anyone remembering not to write through it.

    The product comes off the registry record, not off IR: a legacy system is worth reading
    before any intent binds to it, and often that is the only time it is read at all.
    """
    e = get_or_404(eid)
    try:
        rec = e.registry.get(body.system_id)
    except RegistryError as ex:
        raise HTTPException(404, str(ex))
    try:
        connector = build_reader(body.kind, body.system_id, rec.product, e.registry,
                                 body.base_url, body.secret_env)
    except ConnectorError as ex:
        raise HTTPException(422, str(ex))
    e.connectors[body.system_id] = connector
    e.ledger.append("EXECUTION", "READER_BOUND", identity.subject,
                    f"{body.system_id} bound read-only for {rec.product}",
                    system=body.system_id, kind=connector.kind)
    return {"system_id": body.system_id, "kind": connector.kind, "product": rec.product}


@router.get("/connector")
def connectors(eid: str, identity: Identity = Depends(require("read"))):
    e = get_or_404(eid)
    return {"connectors": [{"system_id": k, "kind": c.kind, "describe": c.describe}
                           for k, c in e.connectors.items()]}
