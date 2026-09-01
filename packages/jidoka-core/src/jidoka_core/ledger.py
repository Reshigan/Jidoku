"""Hash-chained append-only governance ledger: checkpoints, apjidokals, SoD.
Tamper-evidence is cryptographic, not procedural — an auditor can verify the chain offline."""
import hashlib, json, time

class SoDViolation(Exception): ...
class LedgerTampered(Exception): ...

GENESIS = "0" * 64

class Ledger:
    def __init__(self):
        self.entries: list[dict] = []

    def _hash(self, entry: dict, prev_hash: str) -> str:
        payload = json.dumps({**entry, "prev": prev_hash}, sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()

    def append(self, task: str, action: str, actor: str, detail: str = "", **extra) -> dict:
        prev = self.entries[-1]["hash"] if self.entries else GENESIS
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "task": task, "action": action, "actor": actor, "detail": detail, **extra}
        entry["hash"] = self._hash(entry, prev)
        entry["prev"] = prev
        self.entries.append(entry)
        return entry

    def approve(self, task: str, reviewer: str) -> dict:
        builders = {e["actor"] for e in self.entries if e["task"] == task and e["action"] == "EXECUTED"}
        if reviewer in builders:
            raise SoDViolation(f"{reviewer} executed {task} and may not approve it (builder != reviewer).")
        snaps = [e for e in self.entries if e["task"] == task and e["action"] == "SNAPSHOT"]
        if not snaps:
            raise SoDViolation(f"{task}: apjidokal refused — no before-snapshot on the ledger.")
        return self.append(task, "APPROVED", reviewer)

    def verify_chain(self) -> bool:
        prev = GENESIS
        for e in self.entries:
            body = {k: v for k, v in e.items() if k not in ("hash", "prev")}
            if e["prev"] != prev or self._hash(body, prev) != e["hash"]:
                raise LedgerTampered(f"Chain broken at task={e.get('task')} action={e.get('action')}")
            prev = e["hash"]
        return True
