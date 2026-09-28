#!/usr/bin/env python3
"""Is the tier map true on *this* tenant?

    python tools/jidoka-tenant-audit.py metadata.xml [--product SuccessFactors] [--out audit.json]

`metadata.xml` is a saved `GET /odata/v2/$metadata`. This reads a file and touches no network, so it
runs on a laptop against something a client emailed, before anybody holds a credential.

The tier map is a statement about a product; write surface is a property of a tenant — SF creates an
entity set per MDF object, so Tier-A coverage varies by customer. This reports which Tier-A claims
are false here, which are published-but-read-only, which are unconfirmed, and which entity sets the
tenant publishes that no map lists. It reports and never edits: `$metadata` says what a tenant
publishes, and a published entity set can be read-only.

Exit status is 1 when any Tier-A claim is false or unconfirmed on this tenant.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for pkg in ("jidoka-core", "jidoka-adapters"):
    sys.path.insert(0, str(ROOT / "packages" / pkg / "src"))

from jidoka_adapters import ADAPTERS  # noqa: E402
from jidoka_adapters.base import audit_tenant  # noqa: E402
from jidoka_adapters.successfactors.odata import parse_entity_sets  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("metadata", type=Path, help="a saved $metadata document")
    ap.add_argument("--product", default="SuccessFactors")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    if args.product not in ADAPTERS:
        print(f"No adapter for {args.product!r}. Known: {sorted(ADAPTERS)}", file=sys.stderr)
        return 2
    if args.product != "SuccessFactors":
        print(f"Only SuccessFactors $metadata is parsed today; {args.product} has no entity-set "
              f"reader, and guessing one would report a tenant this has not read.", file=sys.stderr)
        return 2
    try:
        entity_sets = parse_entity_sets(args.metadata.read_bytes())
    except Exception as ex:                      # noqa: BLE001 — the reason matters, not the class
        print(f"{args.metadata}: not a readable $metadata document ({type(ex).__name__}: {ex}).",
              file=sys.stderr)
        return 2
    if not entity_sets:
        print(f"{args.metadata} parsed and holds no entity sets. A truncated download and a "
              f"non-OData file both look like this.", file=sys.stderr)
        return 2

    out = audit_tenant(ADAPTERS[args.product](), entity_sets)
    text = json.dumps(out, indent=2, sort_keys=True)
    (args.out.write_text(text) if args.out else print(text))

    print(f"\n{out['says']}", file=sys.stderr)
    for name in out["not_published"]:
        print(f"  ! {name}: tier A, and this tenant does not publish it", file=sys.stderr)
    for name in out["candidates"][:20]:
        print(f"  ? {name}: published and upsertable, in no tier map", file=sys.stderr)
    return 1 if out["not_published"] or out["not_writable"] or out["writability_unknown"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
