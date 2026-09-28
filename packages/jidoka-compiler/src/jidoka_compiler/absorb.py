"""Absorb a mobilisation pack: the design, the plan, and what the plan is waiting on.

A real pack is not one workbook. It is a design authority folder, a plan of record, an alignment
matrix and a task register, and between them they carry everything a programme runs on: option sets
and their owners, cross-module interlocks, a hundred tasks with weeks and dependencies, nineteen
gates with named approvers, twenty decisions on the critical path and eight boundary conditions.
The platform was asked to absorb that rather than to be fed a sheet at a time.

Absorbing is not parsing. Three rules make the difference:

  **Every profile is declared, and every sheet not read is named.** A reader that took three of
  eleven sheets and said nothing would report a third of a design as the whole of it.

  **Dates resolve against the pack's own term, or not at all.** "Fri 9 Oct" means nothing without a
  year, and a register whose late column fires on a string comparison of prose is wrong in both
  directions. The term comes from the caller — the plan of record states it — and a date that will
  not resolve is left unresolved so that lateness is not claimed for it.

  **What is absorbed is a claim, not a fact.** The register says a task is done; the chain says
  whether it is. `jidoka_core.programme` keeps those apart and this hands it both.
"""
from dataclasses import dataclass, field
from datetime import datetime

from .profile import DecisionProfile, Profile, compile_decisions, compile_profiled, _header_row
from openpyxl import load_workbook

#: Register prefixes. A pack numbers each register from one — gates G1.., deliverables T1..,
#: doors D1.., competence checks K1.. — and two of them will eventually collide. On a hash-chained
#: ledger a shared key means one register's answer resolves the other's entry, so the prefix is
#: applied at absorption and named in the notes. The pack's own words stay in the name.
DELIVERABLE = "DEL-"
DOOR = "DOOR-"
KT = "KT-"

MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}


def resolve_date(text: str, year: int, fallback_year: int | None = None) -> str:
    """"Fri 9 Oct" -> "2026-10-09". Empty where the text does not carry a day and a month.

    A pack spans a year boundary — 1 Oct to 8 Jan — so a month earlier than the term's start month
    belongs to the following year. That rule is stated here rather than inferred per row, because a
    January date silently filed under the starting year puts a gate eleven months in the past.
    """
    if not text:
        return ""
    words = str(text).replace(",", " ").split()
    day = month = None
    for w in words:
        clean = w.strip(".").lower()
        if clean[:3] in MONTHS:
            month = MONTHS[clean[:3]]
        elif clean.isdigit() and 1 <= int(clean) <= 31:
            day = int(clean)
    if not (day and month):
        return ""
    y = year
    if fallback_year and month < _start_month(year):
        y = fallback_year
    try:
        return datetime(y, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return ""


_START_MONTH = {}


def _start_month(year: int) -> int:
    return _START_MONTH.get(year, 1)


def set_term(year: int, start_month: int) -> None:
    """The pack's term. Declared by the caller from the plan of record, never guessed from a file."""
    _START_MONTH[year] = start_month


@dataclass
class Absorbed:
    """Everything a pack yielded, and everything it did not."""
    records: list = field(default_factory=list)
    contracts: dict = field(default_factory=dict)       # object key -> {owner, consumers}
    decisions: list = field(default_factory=list)
    conditions: list = field(default_factory=list)
    gates: list = field(default_factory=list)
    #: One-way doors. Kept apart from gates because they need two approvers and gates need one.
    doors: list = field(default_factory=list)
    tasks: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def summary(self) -> dict:
        return {"records": len(self.records), "contracts": len(self.contracts),
                "decisions": len(self.decisions), "conditions": len(self.conditions),
                "gates": len(self.gates), "doors": len(self.doors), "tasks": len(self.tasks),
                "notes": self.notes}


def _blocks(path, sheet: str) -> list[dict]:
    """A sheet's registers, in order. One sheet is not one table.

    The Komatsu plan taught this: its "Gates" sheet holds five gates, a blank row, a caption, and
    then six one-way doors under a different header — a register with different columns and a
    different meaning. A reader that found the first header and then read to the bottom of the sheet
    reported eleven gates, two of which were a caption and a header row, and lost the one-way doors
    entirely. Those are the entries that need two approvers, so losing them is the most expensive
    thing this module could do quietly.

    The rule is structural, not clever: a blank row ends a register, and the next non-blank row
    starts the next one by being its header.
    """
    wb = load_workbook(path, data_only=True)
    if sheet not in wb.sheetnames:
        return []
    out: list[dict] = []
    cols: dict[str, int] | None = None
    for row in wb[sheet].iter_rows(values_only=True):
        cells = ["" if c is None else str(c).strip() for c in row]
        if not any(cells):
            cols = None
            continue
        if cols is None:
            # A header names at least two columns. A single-cell row is a caption, and a caption is
            # not a register — treated as one it becomes a row with an id and nothing else.
            named = [(c, i) for i, c in enumerate(cells) if c]
            if len(named) < 2:
                continue
            cols = {c: i for c, i in named}
            out.append({"header": list(cols), "rows": []})
            continue
        rec = {name: cells[i] if i < len(cells) else "" for name, i in cols.items()}
        if any(rec.values()):
            out[-1]["rows"].append(rec)
    return [b for b in out if b["rows"]]


def _rows(path, sheet: str, header_contains: str):
    """The rows of the register in `sheet` whose header carries `header_contains`.

    Only that register. Where a sheet holds several, the others are read by their own header — see
    `_blocks`, and see what happened when this read to the bottom of the sheet instead.
    """
    for block in _blocks(path, sheet):
        if any(header_contains in name for name in block["header"]):
            return block["rows"]
    return []


def absorb_plan(path, year: int, fallback_year: int | None = None) -> Absorbed:
    """The plan of record's workbook: tasks, gates, decisions, boundary conditions."""
    out = Absorbed()

    for r in _rows(path, "Conditions", "Condition"):
        what = r.get("Condition", "")
        if not what:
            continue
        out.conditions.append({"what": what, "by": r.get("By", ""),
                               "consequence": r.get("Consequence if it fails", "")})

    for r in _rows(path, "Gates", "Gate"):
        gid = r.get("Gate", "")
        if not gid or gid == "Gate":
            continue
        out.gates.append({"gate_id": gid, "name": r.get("Name", ""), "date": r.get("Date", ""),
                          "due_on": resolve_date(r.get("Date", ""), year, fallback_year),
                          "criteria": r.get("Criteria", ""), "evidence": r.get("Evidence", ""),
                          "approver": r.get("Approver", "")})

    for r in _rows(path, "Decisions", "DP"):
        dp = r.get("DP", "")
        if not dp or dp == "DP":
            continue
        out.decisions.append({"dp_id": dp, "dp_type": "DESIGN",
                              "question": r.get("Decision", ""), "owner": r.get("Owner", ""),
                              "options": [r.get("GONXT position", "")] if r.get("GONXT position") else [],
                              "required_by": r.get("Due", "")})

    for r in _rows(path, "Tasks", "ID"):
        tid = r.get("ID", "")
        if not tid or tid == "ID":
            continue
        deps = tuple(d.strip() for d in r.get("Depends on", "").replace(";", ",").split(",")
                     if d.strip())
        out.tasks.append({"task_id": tid, "task": r.get("Task", ""), "week": r.get("Week", ""),
                          "owner": r.get("Owner", ""), "due": r.get("Due", ""),
                          "gate": r.get("Gate/Control", ""), "depends_on": deps,
                          "declared_status": r.get("Status", ""), "watches": ""})

    # One-way doors are not gates, and reading them as gates was the pack's sharpest lesson. A door
    # is a decision that cannot be taken back — a production data load, a legacy set made read-only,
    # a purge — and invariant 5 says one needs two distinct named approvers. A gate needs one. So a
    # door absorbed as a gate loses the second approver, which is the only thing protecting it.
    for r in _rows(path, "Gates", "Door"):
        did = r.get("#", "")
        if not did:
            continue
        approvers = [a.strip() for a in r.get("Approver", "").replace("&", "+").split("+")
                     if a.strip()]
        out.doors.append({"door_id": f"{DOOR}{did}", "door": r.get("Door", ""), "when": r.get("When", ""),
                          "due_on": resolve_date(r.get("When", ""), year, fallback_year),
                          "control": r.get("Control", ""), "approvers": approvers})
    short = [d["door_id"] for d in out.doors if len(d["approvers"]) < 2]
    if out.doors:
        out.decisions += [{"dp_id": d["door_id"], "dp_type": "ONE_WAY",
                           "question": f"{d['door']} — {d['control']}", "owner": "; ".join(d["approvers"]),
                           "options": [], "required_by": d["when"]} for d in out.doors]
        out.notes.append(
            f"{len(out.doors)} one-way door(s) registered as ONE_WAY decisions, not as gates: each "
            f"one needs two distinct named approvers to resolve, where a gate needs one.")
    if short:
        out.notes.append(
            f"{len(short)} one-way door(s) name fewer than two approvers: {', '.join(short)}. They "
            f"cannot be resolved until a second person is named — which is the rule working, not "
            f"the load failing.")

    # The knowledge-transfer tracker is a task register with a different header. Its competence
    # checks carry a week, a person to do them with, evidence and a signature — the same shape as a
    # task, and leaving them out would report a transition plan with no transition in it.
    for r in _rows(path, "KT Tracker", "Competence check"):
        cid = r.get("#", "")
        if not cid or cid == "#":
            continue
        out.tasks.append({"task_id": f"{KT}{cid}", "task": r.get("Competence check", ""),
                          "week": r.get("Week", ""), "owner": r.get("With", ""), "due": "",
                          "gate": "", "depends_on": (),
                          "declared_status": r.get("Status", ""), "watches": ""})

    # Deliverables are gates, not tasks: each one passes on evidence, validated by one party and
    # accepted by another. Absorbing them as tasks would lose the approver the pack names.
    for r in _rows(path, "Deliverables", "Deliverable"):
        did = r.get("#", "")
        if not did or did == "#":
            continue
        out.gates.append({"gate_id": f"{DELIVERABLE}{did}", "name": r.get("Deliverable", ""),
                          "date": r.get("Final due", ""),
                          "due_on": resolve_date(r.get("Final due", ""), year, fallback_year),
                          "criteria": f"validated by {r.get('Validated by', '')}".strip(),
                          "evidence": r.get("Validated by", ""),
                          "approver": r.get("Accepted by", "")})

    # Every distinct thing that will hold a ledger key of its own. A door is deliberately both a
    # door and a ONE_WAY decision — the same entry seen twice — so its decision id is not counted
    # against it, or the check would report the design as a defect.
    doors = {d["door_id"] for d in out.doors}
    ids = ([g["gate_id"] for g in out.gates] + [t["task_id"] for t in out.tasks] + sorted(doors)
           + [d["dp_id"] for d in out.decisions if d["dp_id"] not in doors])
    clashes = sorted({i for i in ids if ids.count(i) > 1})
    if clashes:
        out.notes.append(
            f"{len(clashes)} identifier(s) appear in more than one register even after prefixing: "
            f"{', '.join(clashes)}. On a hash-chained ledger a shared key means one register's "
            f"answer resolves the other's entry, so these have to be made distinct in the pack "
            f"before it is signed.")
    out.notes.append(
        f"register prefixes applied so two registers cannot share a ledger key: deliverables "
        f"{DELIVERABLE}, one-way doors {DOOR}, competence checks {KT}. Gates and tasks keep the "
        f"pack's own identifiers, and every entry carries the pack's own words as its name.")

    nameless = [g["gate_id"] for g in out.gates if not g["approver"].strip()]
    if nameless:
        out.notes.append(
            f"{len(nameless)} gate(s) name no approver: {', '.join(nameless)}. Registering this "
            f"programme will be refused until the pack says who passes them — a gate whose evidence "
            f"is filed and which nobody accepted is a date. Fix the workbook, not the load.")

    unread = [s for s in load_workbook(path, read_only=True).sheetnames
              if s not in ("Tasks", "Gates", "Decisions", "Conditions", "KT Tracker",
                           "Deliverables")]
    if unread:
        out.notes.append(
            f"{len(unread)} sheet(s) in this workbook were not absorbed: {', '.join(unread)}. They "
            f"are views over the sheets above rather than registers of their own — but nothing here "
            f"checked that, so anything they carry that the registers do not is not in the "
            f"platform.")

    out.notes.append(
        f"plan of record: {len(out.tasks)} task(s), {len(out.gates)} gate(s), "
        f"{len(out.doors)} one-way door(s), "
        f"{len(out.decisions)} decision(s), {len(out.conditions)} boundary condition(s). "
        f"{sum(1 for g in out.gates if not g['due_on'])} gate date(s) did not resolve to a day, so "
        f"lateness is not claimed for them.")
    design = [d for d in out.decisions if d["dp_type"] == "DESIGN"]
    if design:
        out.notes.append(
            f"{len(design)} decision(s) registered as DESIGN: the workbook states no type, "
            f"and a STATUTORY decision needs a signed evidence reference to resolve where a DESIGN "
            f"one does not. Any of these whose answer is a statutory value has to be re-typed by a "
            f"person before it is answered.")
    return out


def absorb_alignment(path) -> Absorbed:
    """The cross-module alignment matrix: who owns what, who reads it, and what depends on what.

    This is the sheet the contract registry was built for and never had. Owners and consumers both
    come from the design authority's own words, so "one writer, declared readers" is checked against
    what the programme declared rather than against what the platform inferred.
    """
    out = Absorbed()
    for r in _rows(path, "Data Ownership", "Data domain"):
        domain = r.get("Data domain", "")
        if not domain or domain == "Data domain":
            continue
        consumers = [c.strip() for c in r.get("Consumers", "").replace(";", ",").split(",")
                     if c.strip()]
        out.contracts[domain] = {"owner": r.get("Owner (system of record)", ""),
                                 "consumers": consumers,
                                 "note": r.get("Alignment note", "")}

    interlocks = _rows(path, "Interlocks", "ID")
    out.notes.append(
        f"alignment matrix: {len(out.contracts)} data domain(s) with a declared owner and "
        f"{sum(len(v['consumers']) for v in out.contracts.values())} registered reader(s); "
        f"{len([i for i in interlocks if i.get('ID') not in ('', 'ID')])} interlock(s) with a "
        f"stated failure mode.")
    out.records = [{"interlock": i.get("ID"), "source": i.get("Source"), "target": i.get("Target"),
                    "flows": i.get("What flows / logic"),
                    "failure_mode": i.get("Failure mode if not held"),
                    "control": i.get("Ctrl"), "week": i.get("Week")}
                   for i in interlocks if i.get("ID") not in ("", "ID")]
    return out


def map_contracts(records: list, contracts: dict) -> tuple[list, list, list]:
    """Attach the matrix's owners and readers to the objects they describe.

    The matrix names *data domains* — "Employment and job information" — and the IR names *objects*
    — `PicklistOption`, `LegalEntity`. Those are not the same vocabulary, and a mapping between them
    is a judgement about a client's design, not a string match. So this attaches a contract only
    where the domain names the object (or the record declares which domain it belongs to), and every
    domain it could not place comes back as a decision for a person.

    Returning the unplaced domains rather than swallowing them is the point. A contract registry that
    reported "no undeclared readers" because it had been given no readers would be the most
    dangerous screen in the platform: the interlock the matrix exists to protect would read as held.
    """
    by_key = {}
    for domain, c in contracts.items():
        by_key[domain.strip().lower()] = (domain, c)

    placed, mapped = [], []
    for rec in records:
        obj = getattr(rec, "object", None) or (rec.get("object") if isinstance(rec, dict) else None)
        domain = (rec.get("domain") if isinstance(rec, dict) else getattr(rec, "domain", "")) or ""
        hit = by_key.get(str(domain).strip().lower()) or by_key.get(str(obj or "").strip().lower())
        if not hit:
            continue
        name, c = hit
        placed.append({"object": obj, "domain": name, "owner": c["owner"],
                       "consumers": c["consumers"]})
        mapped.append(name)

    unplaced = [d for d in contracts if d not in set(mapped)]
    decisions = [{"dp_id": f"DP-MAP-{i:02d}", "dp_type": "DESIGN",
                  "question": f"Which configuration objects hold {d!r}? The alignment matrix says "
                              f"{contracts[d]['owner'] or 'an unnamed system'} owns it and "
                              f"{len(contracts[d]['consumers'])} module(s) read it, and until the "
                              f"objects are named the platform cannot tell who a change to them "
                              f"breaks.",
                  "owner": contracts[d]["owner"], "options": [],
                  "required_by": ""}
                 for i, d in enumerate(sorted(unplaced), start=1)]
    notes = [f"{len(placed)} object(s) carry a contract from the alignment matrix. "
             f"{len(unplaced)} data domain(s) could not be matched to a configuration object, so "
             f"their readers are not in the registry and a change to those objects will report no "
             f"undeclared readers because it was given none. One DESIGN decision has been raised "
             f"per unmatched domain."] if contracts else []
    return placed, decisions, notes
