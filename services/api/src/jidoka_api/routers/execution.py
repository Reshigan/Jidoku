"""Execution surface: snapshot, arm, execute, rollback, transport.

Arming and executing are deliberately two calls by two people. An approver arms a named target;
a builder then spends that arming. Neither can do both — the role table forbids it (auth.py) and
the executor forbids it again (armed_by != actor). Two gates, because this is the one endpoint
that changes a customer's production system.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_adapters.base import AdapterError
from jidoka_core import transport as tp
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


class Arm(BaseModel):
    system_id: str
    reason: str = ""


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
    target = ArmedTarget(body.system_id, identity.subject, body.reason)
    _ARMED[(eid, body.system_id)] = target
    e.ledger.append("EXECUTION", "ARMED", identity.subject,
                    f"{body.system_id} armed for live write: {body.reason or 'no reason given'}",
                    system=body.system_id)
    return {"armed": body.system_id, "armed_by": identity.subject, "reason": body.reason}


@router.delete("/arm/{system_id}")
def disarm(eid: str, system_id: str, identity: Identity = Depends(require("arm"))):
    e = get_or_404(eid)
    _ARMED.pop((eid, system_id), None)
    e.ledger.append("EXECUTION", "DISARMED", identity.subject, system_id, system=system_id)
    return {"armed": None}


@router.get("/arm")
def armed(eid: str, identity: Identity = Depends(require("read"))):
    get_or_404(eid)
    return {"armed": [{"system_id": t.system_id, "armed_by": t.armed_by, "reason": t.reason}
                      for (e_id, _), t in _ARMED.items() if e_id == eid]}


class Step(BaseModel):
    key: str


class Rollback(Step):
    reason: str = ""


@router.post("/snapshot")
def snapshot(eid: str, body: Step, identity: Identity = Depends(require("snapshot"))):
    """Read live state and chain its fingerprint. Nothing may be written until this has run."""
    e = get_or_404(eid)
    r = _record_or_404(e, body.key)
    try:
        system = e.registry.get(r.system_binding)
    except RegistryError as ex:
        raise HTTPException(404, str(ex))
    try:
        rows = _executor(e, identity).snapshot(
            body.key, _adapter_for(r.product, e.connectors.get(r.system_binding)), r, system)
    except RuntimeError as ex:
        # The adapter has no reader bound. A snapshot that cannot read is not a snapshot, and
        # letting it pass would satisfy invariant 4 with an empty before-state — worse than failing.
        raise HTTPException(409, f"{r.system_binding}: cannot snapshot — {ex}")
    _BEFORE[(eid, body.key)] = [dict(x) for x in rows]
    return {"key": body.key, "rows": len(rows), "before": rows}


@router.post("/execute")
def execute(eid: str, body: Step, identity: Identity = Depends(require("execute"))):
    """Dry run unless an approver has armed this record's target. Tier B/C hand off to a human."""
    e = get_or_404(eid)
    r = _record_or_404(e, body.key)
    target = _ARMED.get((eid, r.system_binding))
    connector = e.connectors.get(r.system_binding)
    req, route = _transport_for(e, eid, body.key, r) if (target and is_abap(r.product)) else (None, None)
    try:
        res = _executor(e, identity).execute(
            body.key, _adapter_for(r.product, connector), r, armed=target,
            apply_fn=_apply_fn(e, r) if target else None,
            transport_request=req, route=route)
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
    r = _record_or_404(e, body.key)
    target = _ARMED.get((eid, r.system_binding))
    ex_ = _executor(e, identity)
    try:
        # The arming gate, verbatim: right target, someone other than the operator armed it,
        # and the registry still says the system may be written.
        if not ex_._assert_armed(r, target):
            raise HTTPException(
                403, f"{r.system_binding} is not armed. A rollback writes to a live system, so it "
                     f"needs an armed target exactly as an execute does — ask an approver to arm it.")
    except ExecutionRefused as exc:
        raise HTTPException(403, str(exc))
    except WriteLockViolation as exc:
        raise HTTPException(403, str(exc))
    except RegistryError as exc:
        raise HTTPException(404, str(exc))

    before = _BEFORE.get((eid, body.key))
    if before is None:
        raise HTTPException(
            409, f"{body.key}: rollback refused — this process holds no snapshot for this step. "
                 f"Take a before-snapshot first; there is nothing proven to restore.")
    if r.system_binding not in e.connectors:
        raise HTTPException(
            409, f"{r.system_binding}: armed, but no connector is bound for {r.product}. "
                 f"A rollback with no substrate would report a restore that never happened.")
    try:
        res = ex_.rollback(body.key, before, e.connectors[r.system_binding].apply, r,
                           body.reason or "rolled back from the console")
    except ExecutionRefused as exc:
        raise HTTPException(409, str(exc))
    except ConnectorError as exc:
        raise HTTPException(422, str(exc))
    return {"key": res.key, "tier": res.tier, "system": res.system, "status": res.status,
            "detail": res.detail, "rows": len(res.before)}


# ---- transport: on the ABAP stack the write is only half the change (ADR-0006) ----------------


@router.post("/transport")
def advance(eid: str, body: Step, identity: Identity = Depends(require("transport"))):
    """Release if still modifiable, then import into the next legal hop. One call, one hop."""
    e = get_or_404(eid)
    r = _record_or_404(e, body.key)
    if not is_abap(r.product):
        raise HTTPException(
            422, f"{r.product} is not an ABAP product — its changes do not travel by transport, "
                 f"so there is nothing to advance.")
    held = _TRANSPORTS.get((eid, body.key))
    if held is None:
        raise HTTPException(
            404, f"{body.key}: no transport request is held for this step. Execute it live first — "
                 f"a transport exists because a write was captured in it, never before.")
    req, route = held
    try:
        state = _executor(e, identity).advance_transport(body.key, req, route)
    except ExecutionRefused as exc:
        raise HTTPException(409, str(exc))
    except WriteLockViolation as exc:
        raise HTTPException(403, str(exc))
    except tp.TransportError as exc:
        raise HTTPException(422, str(exc))
    except RegistryError as exc:
        raise HTTPException(404, str(exc))
    landed = state["currently_in"]
    e.ledger.append(body.key, "TRANSPORT_ADVANCED", identity.subject,
                    f"{req.request_id} imported into {landed} "
                    f"({e.registry.get(landed).environment}); next hop {state['next_hop'] or 'none — in production'}",
                    request_id=req.request_id, target_system=landed,
                    target_environment=e.registry.get(landed).environment,
                    next_hop=state["next_hop"], in_production=state["in_production"])
    return {"key": body.key, **state}


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
