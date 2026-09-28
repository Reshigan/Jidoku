#!/usr/bin/env python3
"""Absorb a mobilisation pack: point this at the folder, get the design and the plan.

    python tools/jidoka-absorb.py <pack folder> --term 2026-10 --out bundle.json

A pack is a folder, not a file. This walks it, matches each workbook against a declared profile,
and writes one bundle: the IR records, the contracts, the decision points, and the programme
(conditions, gates, tasks). Nothing is posted and nothing is signed — the bundle is what a person
reads before they sign it, which is the only order this platform allows.

What it prints is as much about what it did not absorb as what it did. A pack reader that quietly
read three sheets of eleven would hand somebody a third of a design to sign as the whole of it, and
that signature is what makes the design executable. So every unmatched file, every unread sheet and
every date that would not resolve is named on stdout, and the exit status is 1 if anything in the
pack was left on the floor.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for pkg in ("jidoka-core", "jidoka-compiler"):
    sys.path.insert(0, str(ROOT / "packages" / pkg / "src"))

from jidoka_compiler.absorb import (Absorbed, absorb_alignment, absorb_document,  # noqa: E402
                                    absorb_plan, duplicates, map_contracts, merge, set_term)
from jidoka_compiler.profile import (KOMATSU_DECISIONS, KOMATSU_INVENTORY,  # noqa: E402
                                     KOMATSU_PICKLISTS, compile_decisions, compile_profiled)

#: Which profile a workbook is read with, by a fragment of its filename. Declared, never sniffed: a
#: reader that guessed a profile from a sheet's contents would read a picklist workbook as an
#: inventory the first time somebody renamed a column.
PROFILES = [
    ("alignment matrix", "alignment"),
    ("picklist design", "picklists"),
    ("integrated plan", "plan"),
    ("object inventory", "inventory"),
    ("decision", "decisions"),
]


def which(path: Path) -> str:
    low = path.name.lower()
    for fragment, kind in PROFILES:
        if fragment in low:
            return kind
    return ""


def absorb(folder: Path, year: int, start_month: int, product: str,
           system: str) -> tuple[Absorbed, list[str], list[Path]]:
    set_term(year, start_month)
    out, notes, unmatched = Absorbed(), [], []

    # The documents first, because the specification is what every register below is scoped to —
    # and because a pack read as workbooks alone is two thirds of a design. On a real pack the
    # Word files carry sixty-two requirements, fifteen control objectives, seventeen decisions
    # nobody wrote into a workbook, eleven ordering constraints and twenty-one design rules.
    for path in sorted(folder.rglob("*.docx")):
        if path.name.startswith("~$"):
            continue
        merge(out, absorb_document(path))
        notes.append(f"{path.name}: read as a design document")

    for path in sorted(folder.rglob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        kind = which(path)
        if not kind:
            unmatched.append(path)
            continue
        if kind == "plan":
            # merge, not field-by-field: the one time this was written out by hand it dropped the
            # one-way doors, which are the entries that need two approvers.
            merge(out, absorb_plan(path, year, year + 1))
        elif kind == "alignment":
            merge(out, absorb_alignment(path))
        elif kind in ("picklists", "inventory"):
            profile = KOMATSU_PICKLISTS if kind == "picklists" else KOMATSU_INVENTORY
            records, got_notes = compile_profiled(path, profile, product, system, path.name)
            out.records += records
            out.notes += got_notes
            # A design workbook carries its own open questions on a Decision Points sheet, and the
            # object profile skips that sheet because it is not a register of objects. Skipped by
            # one profile is not read by none: the decisions are what hard-block the plan.
            decisions, dp_notes = compile_decisions(path, KOMATSU_DECISIONS)
            out.decisions += decisions
            out.notes += dp_notes
            continue
        elif kind == "decisions":
            decisions, got_notes = compile_decisions(path, KOMATSU_DECISIONS)
            out.decisions += decisions
            out.notes += got_notes
            continue
        notes.append(f"{path.name}: read as {kind}")
    return out, notes, unmatched


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--term", required=True,
                    help="the pack's first month, as YYYY-MM. Stated by the plan of record, never "
                         "guessed from a file: a date whose year is inferred puts a gate in the "
                         "wrong place and every gate after it reads as late.")
    ap.add_argument("--product", default="successfactors",
                    help="the product these design workbooks configure. Declared, because the "
                         "adapter for it is what decides each object's tier (ADR-0045) and the "
                         "workbook has no standing to assert one.")
    ap.add_argument("--system", required=True,
                    help="the registered system id this design binds to. An IR record without one "
                         "names no target, and a plan against no target is not a plan.")
    ap.add_argument("--out", type=Path, help="where to write the bundle. stdout if omitted.")
    args = ap.parse_args(argv)

    if not args.folder.is_dir():
        print(f"{args.folder} is not a folder. A mobilisation pack is a folder.", file=sys.stderr)
        return 2
    try:
        year, month = (int(p) for p in args.term.split("-"))
    except ValueError:
        print("--term is YYYY-MM, for example 2026-10.", file=sys.stderr)
        return 2

    pack, read, unmatched = absorb(args.folder, year, month, args.product, args.system)
    placed, mapping_decisions, mapping_notes = map_contracts(pack.records, pack.contracts)
    pack.decisions += mapping_decisions
    pack.notes += mapping_notes

    for line in duplicates(pack):
        pack.notes.append(line)

    bundle = {
        "term": args.term,
        "records": [r if isinstance(r, dict) else r.__dict__ for r in pack.records],
        "interlocks": pack.interlocks,
        "scope": pack.scope,
        "contracts": pack.contracts,
        "contracts_placed": placed,
        "decision_points": pack.decisions,
        "specification": {"requirements": pack.requirements, "controls": pack.controls},
        "ordering": pack.ordering,
        "rules": pack.rules,
        "programme": {"conditions": pack.conditions, "gates": pack.gates, "tasks": pack.tasks},
        "notes": pack.notes,
        "unsigned": ("This bundle is a reading of a pack, not intent. Nothing in it is executable "
                     "until a person signs it: that signature is the only thing that makes the "
                     "difference, which is why this tool does not post it anywhere."),
    }
    text = json.dumps(bundle, indent=2, sort_keys=True, default=str)
    if args.out:
        args.out.write_text(text)
    else:
        print(text)

    for line in read:
        print(f"  {line}", file=sys.stderr)
    for note in pack.notes:
        print(f"  * {note}", file=sys.stderr)
    for path in unmatched:
        print(f"  ! {path.relative_to(args.folder)}: no declared profile matches this filename, so "
              f"nothing in it was read.", file=sys.stderr)
    print(f"\n{len(bundle['records'])} record(s), {len(pack.scope)} scope item(s), "
          f"{len(pack.interlocks)} interlock(s), {len(pack.requirements)} requirement(s), "
          f"{len(pack.controls)} control objective(s), {len(pack.decisions)} decision(s), "
          f"{len(pack.tasks)} task(s), {len(pack.gates)} gate(s), {len(pack.doors)} door(s), "
          f"{len(pack.conditions)} boundary condition(s), {len(pack.ordering)} ordering "
          f"constraint(s), {len(pack.rules)} design rule(s), {len(pack.contracts)} data domain(s).",
          file=sys.stderr)
    if unmatched:
        print(f"{len(unmatched)} file(s) in this pack were not read. Sign nothing until you know "
              f"whether they matter.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
