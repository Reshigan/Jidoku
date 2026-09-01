"""Engagement store, persisted behind jidoka_core.repository (E1).

The Engagement object is still the in-memory working set — core's Ledger/Registry/DecisionEngine hold
the real semantics and must not be reimplemented against SQL. The repository is a durability layer:
mutations are mirrored to it, and a cold process rehydrates the same objects from it. That keeps every
governance gate in jidoka-core, where the tests already prove them, rather than splitting enforcement
between Python and SQL.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from jidoka_core.decisions import DecisionEngine, DecisionPoint
from jidoka_core.ir import IRRecord
from jidoka_core.ledger import Ledger
from jidoka_core.lifecycle import PHASES
from jidoka_core.registry import SystemRecord, SystemRegistry
from jidoka_core.repository import Repository, open_repository
from jidoka_knowledge import Claim, ProjectStore, SystemStore


class PersistentLedger(Ledger):
    """A Ledger that mirrors every append to storage. Append-only in both places; the chain is still
    computed and verified in core, so tamper-evidence does not depend on the database."""

    def __init__(self, repo: Repository, eid: str) -> None:
        super().__init__()
        self._repo, self._eid = repo, eid

    def append(self, task: str, action: str, actor: str, detail: str = "", **extra) -> dict:
        entry = super().append(task, action, actor, detail, **extra)
        self._repo.append_ledger(self._eid, entry)
        return entry


@dataclass
class Engagement:
    engagement_id: str
    name: str
    client: str
    phase: str = PHASES[0]
    ir: list = field(default_factory=list)
    open_dps: dict = field(default_factory=dict)
    ledger: Ledger = None
    registry: SystemRegistry = field(default_factory=SystemRegistry)
    decisions: DecisionEngine = None
    # Project memory: this engagement's beliefs, on the same ledger as its config (ADR-0010).
    memory: ProjectStore = None
    repo: Repository | None = None
    # system_id -> connector. Never persisted: a connector holds live credentials, and a restart
    # must unbind every one of them rather than reload a write path nobody re-authorised.
    connectors: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.ledger is None:
            self.ledger = Ledger()
        if self.decisions is None:
            self.decisions = DecisionEngine(self.ledger)
        if self.memory is None:
            self.memory = ProjectStore(self.engagement_id, ledger=self.ledger)

    def bind_ledger(self, ledger) -> None:
        """Swap in the persistent ledger, carrying every component that writes to it.

        __post_init__ builds a throwaway in-memory Ledger; the store replaces it once the repo is
        known. Rebinding component-by-component at each call site is how one of them gets missed,
        so every writer is re-pointed here, once.
        """
        self.ledger = ledger
        self.decisions = DecisionEngine(ledger)
        self.memory = ProjectStore(self.engagement_id, ledger=ledger)

    # --- persistence mirrors: called after a mutation that core has already accepted -------------
    def persist_header(self) -> None:
        if self.repo:
            self.repo.save_engagement(self.engagement_id, self.name, self.client, self.phase)

    def persist_ir(self) -> None:
        if self.repo:
            self.repo.save_ir(self.engagement_id, [_ir_to_dict(r) for r in self.ir], self.open_dps)

    def persist_systems(self) -> None:
        if self.repo:
            land = self.registry.landscape()
            self.repo.save_systems(self.engagement_id, land["systems"], land["promotion_paths"])

    def persist_dps(self) -> None:
        if self.repo:
            self.repo.save_dps(self.engagement_id, [_dp_to_dict(d) for d in self.decisions.dps.values()])

    def persist_memory(self) -> None:
        if self.repo:
            # all(), not current(): a closed interval is history, and history is the point.
            self.repo.save_claims(self.engagement_id, [c.to_dict() for c in self.memory.all()])


def _ir_to_dict(r: IRRecord) -> dict:
    return {"object": r.object, "product": r.product, "system_binding": r.system_binding,
            "intent": r.intent, "tier": r.tier, "source": r.source, "country": r.country,
            "depends_on": r.depends_on, "external_code": r.external_code}


def _dp_to_dict(d: DecisionPoint) -> dict:
    return {"dp_id": d.dp_id, "dp_type": d.dp_type, "question": d.question, "owner": d.owner,
            "options": d.options, "resolution": d.resolution}


class Store:
    """Engagement registry with write-through persistence and lazy rehydration."""

    def __init__(self, repo: Repository | None = None) -> None:
        self.repo = repo if repo is not None else open_repository(os.environ.get("JIDOKA_DB_URL"))
        self._cache: dict[str, Engagement] = {}

    def create(self, eid: str, name: str, client: str) -> Engagement:
        e = Engagement(eid, name, client, repo=self.repo)
        e.bind_ledger(PersistentLedger(self.repo, eid))
        self._cache[eid] = e
        e.persist_header()
        return e

    def get(self, eid: str) -> Engagement | None:
        if eid in self._cache:
            return self._cache[eid]
        header = self.repo.load_engagement(eid)
        if header is None:
            return None
        return self._rehydrate(header)

    def _rehydrate(self, header: dict) -> Engagement:
        eid = header["engagement_id"]
        e = Engagement(eid, header["name"], header["client"], header.get("phase", PHASES[0]),
                       repo=self.repo)
        ledger = PersistentLedger(self.repo, eid)
        # Replay stored entries directly: re-appending would re-hash and duplicate the chain.
        ledger.entries = self.repo.load_ledger(eid)
        e.bind_ledger(ledger)
        for d in self.repo.load_dps(eid):
            e.decisions.dps[d["dp_id"]] = DecisionPoint(
                d["dp_id"], d["dp_type"], d["question"], d["owner"],
                d.get("options") or [], d.get("resolution"))
        for raw in self.repo.load_claims(eid):
            e.memory._claims.append(Claim.from_dict(raw))
        raw_ir, e.open_dps = self.repo.load_ir(eid)
        e.ir = [IRRecord(**r) for r in raw_ir]
        systems, paths = self.repo.load_systems(eid)
        for s in systems:
            e.registry._systems[s["system_id"]] = SystemRecord(**s)
        e.registry._promotion_paths = list(paths)
        self._cache[eid] = e
        return e

    def list(self) -> list[Engagement]:
        for header in self.repo.list_engagements():
            if header["engagement_id"] not in self._cache:
                self._rehydrate(header)
        return list(self._cache.values())

    def reset(self) -> None:
        """Test hook: drop the cache and the backing store."""
        self._cache.clear()
        self.repo = open_repository(os.environ.get("JIDOKA_DB_URL"))


STORE = Store()
