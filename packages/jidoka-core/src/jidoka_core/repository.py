"""Persistence behind repository interfaces. sqlite3 is stdlib — jidoka-core stays dependency-free.

The in-memory implementation is the reference semantics; SQLite must behave identically. Both are
exercised by the same test suite (tests/test_repository.py parametrises over them).

Invariant note: the ledger repository is append-only at the storage layer too — there is no update or
delete path here. Tamper-evidence is verified by re-reading the chain, not trusted from the writer.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Iterable, Protocol


class RepositoryError(Exception): ...


class Repository(Protocol):
    """Storage for one engagement's mutable state. Implementations must be interchangeable."""

    def save_engagement(self, eid: str, name: str, client: str, phase: str) -> None: ...
    def load_engagement(self, eid: str) -> dict | None: ...
    def list_engagements(self) -> list[dict]: ...
    def append_ledger(self, eid: str, entry: dict) -> None: ...
    def load_ledger(self, eid: str) -> list[dict]: ...
    def save_ir(self, eid: str, records: list[dict], open_dps: dict) -> None: ...
    def load_ir(self, eid: str) -> tuple[list[dict], dict]: ...
    def save_systems(self, eid: str, systems: list[dict], paths: list) -> None: ...
    def load_systems(self, eid: str) -> tuple[list[dict], list]: ...
    def save_dps(self, eid: str, dps: list[dict]) -> None: ...
    def load_dps(self, eid: str) -> list[dict]: ...
    def save_claims(self, eid: str, claims: list[dict]) -> None: ...
    def load_claims(self, eid: str) -> list[dict]: ...


class InMemoryRepository:
    """Reference implementation. Fast, and the semantics the SQLite store must match."""

    def __init__(self) -> None:
        self._eng: dict[str, dict] = {}
        self._ledger: dict[str, list[dict]] = {}
        self._ir: dict[str, tuple[list[dict], dict]] = {}
        self._systems: dict[str, tuple[list[dict], list]] = {}
        self._dps: dict[str, list[dict]] = {}
        self._claims: dict[str, list[dict]] = {}

    def save_engagement(self, eid: str, name: str, client: str, phase: str) -> None:
        self._eng[eid] = {"engagement_id": eid, "name": name, "client": client, "phase": phase}

    def load_engagement(self, eid: str) -> dict | None:
        rec = self._eng.get(eid)
        return dict(rec) if rec else None

    def list_engagements(self) -> list[dict]:
        return [dict(e) for e in self._eng.values()]

    def append_ledger(self, eid: str, entry: dict) -> None:
        self._ledger.setdefault(eid, []).append(dict(entry))

    def load_ledger(self, eid: str) -> list[dict]:
        return [dict(e) for e in self._ledger.get(eid, [])]

    def save_ir(self, eid: str, records: list[dict], open_dps: dict) -> None:
        self._ir[eid] = ([dict(r) for r in records], dict(open_dps))

    def load_ir(self, eid: str) -> tuple[list[dict], dict]:
        recs, dps = self._ir.get(eid, ([], {}))
        return [dict(r) for r in recs], dict(dps)

    def save_systems(self, eid: str, systems: list[dict], paths: list) -> None:
        self._systems[eid] = ([dict(s) for s in systems], [tuple(p) for p in paths])

    def load_systems(self, eid: str) -> tuple[list[dict], list]:
        systems, paths = self._systems.get(eid, ([], []))
        return [dict(s) for s in systems], [tuple(p) for p in paths]

    def save_dps(self, eid: str, dps: list[dict]) -> None:
        self._dps[eid] = [dict(d) for d in dps]

    def load_dps(self, eid: str) -> list[dict]:
        return [dict(d) for d in self._dps.get(eid, [])]

    def save_claims(self, eid: str, claims: list[dict]) -> None:
        self._claims[eid] = [dict(c) for c in claims]

    def load_claims(self, eid: str) -> list[dict]:
        return [dict(c) for c in self._claims.get(eid, [])]


_SCHEMA = """
CREATE TABLE IF NOT EXISTS engagements (
    engagement_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    client TEXT NOT NULL,
    phase TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger (
    engagement_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    entry TEXT NOT NULL,
    PRIMARY KEY (engagement_id, seq)
);
CREATE TABLE IF NOT EXISTS blobs (
    engagement_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (engagement_id, kind)
);
"""


class SqliteRepository:
    """SQLite-backed store. Same semantics as InMemoryRepository, survives restarts.

    ponytail: IR/systems/DPs are stored as one JSON blob per engagement per kind rather than
    normalised tables. They are always read and written whole, so rows would buy nothing. Normalise
    if a query ever needs to filter IR records server-side.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def save_engagement(self, eid: str, name: str, client: str, phase: str) -> None:
        self._conn.execute(
            "INSERT INTO engagements (engagement_id, name, client, phase) VALUES (?,?,?,?) "
            "ON CONFLICT(engagement_id) DO UPDATE SET name=excluded.name, client=excluded.client, "
            "phase=excluded.phase",
            (eid, name, client, phase),
        )
        self._conn.commit()

    def load_engagement(self, eid: str) -> dict | None:
        row = self._conn.execute(
            "SELECT engagement_id, name, client, phase FROM engagements WHERE engagement_id=?", (eid,)
        ).fetchone()
        return dict(row) if row else None

    def list_engagements(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT engagement_id, name, client, phase FROM engagements ORDER BY engagement_id"
        ).fetchall()
        return [dict(r) for r in rows]

    def append_ledger(self, eid: str, entry: dict) -> None:
        # seq is derived under the same transaction as the insert: the chain cannot interleave.
        with self._conn:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(seq), 0) AS m FROM ledger WHERE engagement_id=?", (eid,)
            ).fetchone()
            self._conn.execute(
                "INSERT INTO ledger (engagement_id, seq, entry) VALUES (?,?,?)",
                (eid, row["m"] + 1, json.dumps(entry, sort_keys=True)),
            )

    def load_ledger(self, eid: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT entry FROM ledger WHERE engagement_id=? ORDER BY seq", (eid,)
        ).fetchall()
        return [json.loads(r["entry"]) for r in rows]

    def _put_blob(self, eid: str, kind: str, payload) -> None:
        self._conn.execute(
            "INSERT INTO blobs (engagement_id, kind, payload) VALUES (?,?,?) "
            "ON CONFLICT(engagement_id, kind) DO UPDATE SET payload=excluded.payload",
            (eid, kind, json.dumps(payload)),
        )
        self._conn.commit()

    def _get_blob(self, eid: str, kind: str, default):
        row = self._conn.execute(
            "SELECT payload FROM blobs WHERE engagement_id=? AND kind=?", (eid, kind)
        ).fetchone()
        return json.loads(row["payload"]) if row else default

    def save_ir(self, eid: str, records: list[dict], open_dps: dict) -> None:
        self._put_blob(eid, "ir", {"records": records, "open_dps": open_dps})

    def load_ir(self, eid: str) -> tuple[list[dict], dict]:
        blob = self._get_blob(eid, "ir", {"records": [], "open_dps": {}})
        return blob["records"], blob["open_dps"]

    def save_systems(self, eid: str, systems: list[dict], paths: list) -> None:
        self._put_blob(eid, "systems", {"systems": systems, "paths": [list(p) for p in paths]})

    def load_systems(self, eid: str) -> tuple[list[dict], list]:
        blob = self._get_blob(eid, "systems", {"systems": [], "paths": []})
        return blob["systems"], [tuple(p) for p in blob["paths"]]

    def save_dps(self, eid: str, dps: list[dict]) -> None:
        self._put_blob(eid, "dps", dps)

    def load_dps(self, eid: str) -> list[dict]:
        return self._get_blob(eid, "dps", [])

    def save_claims(self, eid: str, claims: list[dict]) -> None:
        # Superseded claims are written too: closing an interval is not deleting a belief.
        self._put_blob(eid, "claims", claims)

    def load_claims(self, eid: str) -> list[dict]:
        return self._get_blob(eid, "claims", [])


def open_repository(db_url: str | None) -> Repository:
    """Factory from a JIDOKA_DB_URL. `sqlite:///path` or None (in-memory reference impl)."""
    if not db_url:
        return InMemoryRepository()
    if db_url.startswith("sqlite:///"):
        return SqliteRepository(db_url[len("sqlite:///"):])
    if db_url == "sqlite://:memory:":
        return SqliteRepository(":memory:")
    raise RepositoryError(f"Unsupported JIDOKA_DB_URL {db_url!r} — use sqlite:///path or leave unset.")
