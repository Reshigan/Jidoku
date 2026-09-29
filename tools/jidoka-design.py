#!/usr/bin/env python3
"""Author a design from an absorbed pack.

    python tools/jidoka-design.py bundle.json --system KOM-SF-DEV --brief "scope item G01" \
        [--metadata metadata.json] [--out proposals.json]

Reads the bundle `tools/jidoka-absorb.py` produced — its registers *and* the prose its documents
carry — and authors IR records for the objects the design names. Nothing is posted and nothing is
signed: the output is proposals a person reads, which is the only order this platform allows.

What comes back is as much about what the platform refused as what the model wrote. Four gates run
on every proposal — IR validation, the adapter's tier map, the tenant's own `$metadata`, and a
required provenance — and a refused proposal is reported with the reason rather than dropped. A pass
that authored forty records and refused nine is a more useful report than one that authored
thirty-one.

This costs money to run: it calls the Anthropic API, at frontier effort, over a design pack. The
budget is a token ceiling the model can see (`--budget`), not a turn cap it cannot.
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
from jidoka_agent import design as d  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("bundle", type=Path, help="the JSON tools/jidoka-absorb.py wrote")
    ap.add_argument("--system", required=True,
                    help="the registered system id the authored records bind to")
    ap.add_argument("--product", default="SuccessFactors",
                    help="the product whose adapter decides each object's tier (ADR-0045)")
    ap.add_argument("--brief", required=True,
                    help="what to design, in the pack's own words — a scope item, a module, an "
                         "object. One brief per pass: a pass told to 'do everything' spends its "
                         "budget deciding where to start.")
    ap.add_argument("--metadata", type=Path,
                    help="the tenant's $metadata, parsed (jidoka_adapters...odata.parse_metadata). "
                         "Without it the $metadata gate is skipped and the run says so — a record "
                         "authored against nobody's tenant is a guess about a product.")
    ap.add_argument("--picklists", type=Path,
                    help="picklist code sets, as {picklist: [values]}, so a value that references "
                         "an option the tenant does not have is refused as an orphan")
    ap.add_argument("--budget", type=int, default=d.TASK_BUDGET,
                    help="token ceiling the model paces itself against")
    ap.add_argument("--max-turns", type=int, default=d.MAX_TURNS, help="runaway guard")
    ap.add_argument("--out", type=Path, help="where to write the proposals. stdout if omitted.")
    args = ap.parse_args(argv)

    if args.product not in ADAPTERS:
        print(f"No adapter for {args.product!r}. Known: {sorted(ADAPTERS)}", file=sys.stderr)
        return 2
    try:
        pack = json.loads(args.bundle.read_text())
    except (OSError, json.JSONDecodeError) as ex:
        print(f"{args.bundle}: {ex}", file=sys.stderr)
        return 2

    metadata = json.loads(args.metadata.read_text()) if args.metadata else {}
    picklists = ({k: set(v) for k, v in json.loads(args.picklists.read_text()).items()}
                 if args.picklists else None)

    d.TASK_BUDGET = args.budget
    session = d.DesignSession(pack, ADAPTERS[args.product](), metadata=metadata,
                              documents=pack.get("documents", {}), picklists=picklists)

    brief = (f"{args.brief}\n\nBind every record to system {args.system!r} and product "
             f"{args.product!r}. Read the pack's registers and the documents' prose before you "
             f"author anything.")
    try:
        out = d.run(session, brief, max_turns=args.max_turns)
    except Exception as ex:                      # noqa: BLE001 — the reason matters, not the class
        print(f"The design pass failed: {type(ex).__name__}: {ex}", file=sys.stderr)
        return 1

    proposals = {
        "brief": args.brief, "system": args.system, "product": args.product,
        "accepted": [p.record for p in out.accepted],
        # Exactly the body of POST /engagements/{eid}/proposals, so this is `jq .proposals` away from
        # a person's screen. They are drafts: no signature, and none can be added by whoever wrote them.
        "proposals": {"records": [p.record for p in out.accepted],
                      "note": f"design pass: {args.brief}"},
        "refused": [p.as_dict() for p in out.refused],
        "decision_points": out.decisions,
        "traces": out.traces,
        "run": out.summary(),
        "metadata_gate": bool(metadata) or
            "SKIPPED — no tenant $metadata was given, so nothing checked these records against a "
            "real tenant's fields. They are a guess about a product until that runs.",
        "unsigned": ("Drafts, not intent. They carry no signature and cannot: a person signs each "
                     "one on the Proposals screen, under their own identity, and the refusals here "
                     "are part of what they are signing off on."),
    }
    text = json.dumps(proposals, indent=2, sort_keys=True, default=str)
    if args.out:
        args.out.write_text(text)
    else:
        print(text)

    print(f"\n{out.summary()['says']}", file=sys.stderr)
    for p in out.refused:
        print(f"  ! {p.record.get('object', '?')} "
              f"{p.record.get('external_code', '')}: {'; '.join(p.problems)}", file=sys.stderr)
    for dp in out.decisions:
        print(f"  ? {dp['dp_id']} ({dp['dp_type']}) {dp['question']}", file=sys.stderr)
    if not metadata:
        print("  * No tenant $metadata: the gate that decides whether these records will actually "
              "load did not run.", file=sys.stderr)
    broken = out.integrity.get("dangling") or out.integrity.get("cycles")
    for d in out.integrity.get("dangling", []):
        print(f"  ~ {d['record']} depends on {d['references']!r}, which nobody authored",
              file=sys.stderr)
    if out.integrity.get("cycles"):
        print(f"  ~ dependency cycle through {', '.join(out.integrity['cycles'])}", file=sys.stderr)
    if broken:
        print("  The planner would refuse this design. It is not finished.", file=sys.stderr)
    # A pass that refused everything, asked nothing and wrote nothing, or left a design the planner
    # would refuse, is not a success.
    return 0 if (out.accepted or out.decisions) and not broken else 1


if __name__ == "__main__":
    raise SystemExit(main())
