#!/usr/bin/env python3
"""Sit the design pass an exam it can fail.

    python tools/jidoka-bench.py bundle.json --system KOM-SF-DEV --object PicklistOption \
        --hide records --compare label [--metadata metadata.json]

Takes something away and sees whether the pass gets there anyway. A pack carries the design documents
*and* the workbooks compiled from them; withhold the workbooks, give the pass only the prose and the
requirements, and compare what it authors against what real consultants really built. On the Komatsu
pack that is 159 picklist options derived from a Solution Design Document — a real exam, marked
against work that shipped.

`missed` is a gap. `extra` is not scored as wrong: sometimes it is invention and sometimes it is what
the project forgot, and a benchmark that punished it would train the pass to author less. Those go to
a person, and this prints them.

This costs money to run — one full design pass at frontier effort per case.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for pkg in ("jidoka-core", "jidoka-adapters", "jidoka-os", "jidoka-knowledge"):
    sys.path.insert(0, str(ROOT / "packages" / pkg / "src"))
sys.path.insert(0, str(ROOT / "services" / "agent" / "src"))

from jidoka_adapters import ADAPTERS  # noqa: E402
from jidoka_agent import bench as b  # noqa: E402
from jidoka_agent import design as d  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("bundle", type=Path)
    ap.add_argument("--system", required=True)
    ap.add_argument("--product", default="SuccessFactors")
    ap.add_argument("--object", default="",
                    help="narrow the right answer to one object type. Empty marks against every "
                         "record the pack compiled, which on a real pack is a long exam.")
    ap.add_argument("--hide", nargs="+", default=["records"],
                    help=f"registers withheld from the pass. One of {list(b.WITHHOLDABLE)}. "
                         f"Withholding nothing is refused — the answer would be in the input.")
    ap.add_argument("--compare", nargs="*", default=[],
                    help="fields compared where a record matches. Without these the exam says "
                         "nothing about the values, only about the objects.")
    ap.add_argument("--brief", default="",
                    help="what the pass is told. Defaults to a brief built from --object.")
    ap.add_argument("--metadata", type=Path)
    ap.add_argument("--max-turns", type=int, default=d.MAX_TURNS)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    if args.product not in ADAPTERS:
        print(f"No adapter for {args.product!r}. Known: {sorted(ADAPTERS)}", file=sys.stderr)
        return 2
    try:
        pack = json.loads(args.bundle.read_text())
    except (OSError, json.JSONDecodeError) as ex:
        print(f"{args.bundle}: {ex}", file=sys.stderr)
        return 2

    expected = b.ground_truth(pack, args.object)
    if not expected:
        scope = f" for {args.object!r}" if args.object else ""
        print(f"This bundle compiled no records{scope}, so there is nothing to mark against.",
              file=sys.stderr)
        return 2

    brief = args.brief or (
        f"Author every {args.object or 'configuration object'} this design calls for. The workbook "
        f"that would have listed them has been withheld: derive them from the documents' prose and "
        f"the requirements. Bind every record to system {args.system!r} and product "
        f"{args.product!r}.")
    try:
        case = b.Case(case_id=f"{args.bundle.stem}/{args.object or 'all'}", brief=brief,
                      hide=tuple(args.hide), expected=expected, compare=tuple(args.compare))
    except b.BenchError as ex:
        print(str(ex), file=sys.stderr)
        return 2

    seen = b.withhold(pack, case.hide)
    session = d.DesignSession(seen, ADAPTERS[args.product](),
                              metadata=json.loads(args.metadata.read_text()) if args.metadata
                                       else {},
                              documents=seen.get("documents", {}))
    try:
        out = d.run(session, case.brief, max_turns=args.max_turns)
    except Exception as ex:                      # noqa: BLE001
        print(f"The design pass failed: {type(ex).__name__}: {ex}", file=sys.stderr)
        return 1

    board = b.Bench()
    marked = board.mark(case, [p.record for p in out.accepted])
    text = json.dumps({"case": case.case_id, "run": out.summary(), "marked": marked,
                       "refused": [p.as_dict() for p in out.refused],
                       "decision_points": out.decisions},
                      indent=2, sort_keys=True, default=str)
    if args.out:
        args.out.write_text(text)
    else:
        print(text)

    print(f"\n{marked['says']}", file=sys.stderr)
    for dis in marked["disagreements"]:
        print(f"  ~ {dis['key']}.{dis['field']}: built {dis['built']!r}, "
              f"authored {dis['authored']!r}", file=sys.stderr)
    for k in marked["extra"]:
        print(f"  ? {k}: authored and never built. Invention, or the thing the project forgot.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
