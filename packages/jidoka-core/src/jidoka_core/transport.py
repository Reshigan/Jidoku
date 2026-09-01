"""ABAP transport / CTS+ awareness: a config change is not done when the write succeeds,
it is done when a released transport lands in PROD. Pure stdlib; never imports the ledger —
every state change returns a dict the caller appends."""
from dataclasses import dataclass, field
import time

from .registry import WRITE_FORBIDDEN_ROLES

MODIFIABLE, RELEASED, IMPORTED = "MODIFIABLE", "RELEASED", "IMPORTED"

class TransportError(Exception): ...

def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

@dataclass
class TransportRequest:
    request_id: str            # e.g. "S4DK900123"
    owner: str
    description: str
    source_system: str
    objects: list[str] = field(default_factory=list)
    status: str = MODIFIABLE
    released_at: str = ""
    released_by: str = ""
    imported_into: list[str] = field(default_factory=list)

@dataclass
class TransportRoute:
    """Ordered chain of system_ids, DEV -> QA -> PROD, validated against the SystemRegistry."""
    systems: list[str]

    def validate(self, registry) -> "TransportRoute":
        if len(self.systems) < 2:
            raise TransportError("A transport route needs at least a source and one target hop.")
        for sid in self.systems:
            registry.get(sid)  # raises RegistryError if unregistered
        final = registry.get(self.systems[-1])
        if final.role in WRITE_FORBIDDEN_ROLES:
            raise TransportError(
                f"Route ends at {final.system_id} (role {final.role}) which may not be written to. "
                f"A transport route must terminate at a writable target.")
        return self

    def next_hop(self, imported_into: list[str]) -> str | None:
        for sid in self.systems[1:]:
            if sid not in imported_into:
                return sid
        return None

def release(req: TransportRequest, released_by: str) -> dict:
    """One-way: MODIFIABLE -> RELEASED. Requires an owner."""
    if not req.owner:
        raise TransportError(f"{req.request_id}: release refused — transport has no owner.")
    if req.status != MODIFIABLE:
        raise TransportError(
            f"{req.request_id}: release is one-way — already {req.status}, cannot release again.")
    req.status, req.released_at, req.released_by = RELEASED, _now(), released_by
    return {"action": "TRANSPORT_RELEASED", "actor": released_by, "request_id": req.request_id,
            "source_system": req.source_system, "objects": list(req.objects),
            "released_at": req.released_at, "detail": req.description}

def import_into(req: TransportRequest, route: TransportRoute, target: str, actor: str) -> dict:
    """Import must follow the route in order — no skipping QA to reach PROD."""
    if req.status == MODIFIABLE:
        raise TransportError(
            f"{req.request_id} is MODIFIABLE — an unreleased transport cannot be imported anywhere.")
    if target in req.imported_into:
        raise TransportError(f"{req.request_id} is already IMPORTED into {target} — re-import refused.")
    nxt = route.next_hop(req.imported_into)
    if nxt is None:
        raise TransportError(f"{req.request_id} has reached the end of its route; {target} is not a hop.")
    if target != nxt:
        raise TransportError(
            f"{req.request_id}: import into {target} refused — next legal hop is {nxt}. "
            f"Route order is not optional.")
    req.imported_into.append(target)
    req.status = IMPORTED
    return {"action": "TRANSPORT_IMPORTED", "actor": actor, "request_id": req.request_id,
            "target_system": target, "objects": list(req.objects),
            "imported_at": _now(), "next_hop": route.next_hop(req.imported_into),
            "detail": f"{req.description} -> {target}"}

def import_status(req: TransportRequest, route: TransportRoute) -> dict:
    """Where the request currently sits and what the next legal hop is."""
    nxt = route.next_hop(req.imported_into)
    return {"request_id": req.request_id, "status": req.status,
            "currently_in": req.imported_into[-1] if req.imported_into else req.source_system,
            "imported_into": list(req.imported_into),
            "next_hop": nxt,
            "in_production": nxt is None and req.status == IMPORTED,
            "route": list(route.systems)}
