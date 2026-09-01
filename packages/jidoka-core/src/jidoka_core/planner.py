"""Run-planner: topological sort of the IR dependency graph, tier split, DP hard-block.
The plan is derived from the work — cycles and open decisions stop the plan, loudly."""
from .ir import IRRecord

class PlanError(Exception): ...

def plan(records: list[IRRecord], open_dps: dict[str, list[str]]) -> dict:
    if open_dps:
        lines = [f"  {k}: {', '.join(v)}" for k, v in open_dps.items()]
        raise PlanError("PLAN BLOCKED — open Decision Points (JIDOKA will not invent values):\n" + "\n".join(lines))
    by_key = {r.key: r for r in records}
    # also index by short externalCode refs like "TimeAccountType:ANN_ACC_ZAF"
    short = {}
    for r in records:
        short[f"{r.object}:{r.external_code or r.intent.get('externalCode','?')}"] = r.key
    indeg = {r.key: 0 for r in records}
    edges: dict[str, list[str]] = {r.key: [] for r in records}
    for r in records:
        for dep in r.depends_on:
            dep_key = short.get(dep, dep)
            if dep_key not in by_key:
                raise PlanError(f"{r.key} depends on unknown object {dep!r} — referential gap in design.")
            edges[dep_key].append(r.key)
            indeg[r.key] += 1
    queue = sorted([k for k, d in indeg.items() if d == 0])
    ordered = []
    while queue:
        k = queue.pop(0)
        ordered.append(k)
        for nxt in sorted(edges[k]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    if len(ordered) != len(records):
        cyclic = [k for k, d in indeg.items() if d > 0]
        raise PlanError(f"Dependency cycle detected involving: {cyclic}")
    steps = []
    for i, key in enumerate(ordered, 1):
        r = by_key[key]
        # `product` rides along because completion is product-shaped: on the ABAP stack a
        # verified write is not done until its transport lands in PROD (ADR-0006), and a console
        # that cannot see the product cannot offer that step its next move.
        steps.append({"seq": i, "key": key, "tier": r.tier, "system": r.system_binding,
                      "product": r.product,
                      "action": {"A": "API_WRITE", "B": "FILE_IMPORT_HUMAN", "C": "UI_INSTRUCTION_HUMAN"}[r.tier]})
    # lanes: longest-path depth from a root. Same lane = no dependency between them,
    # so an executor may run a lane concurrently. Disconnected subgraphs share lane 0.
    depth = {k: 0 for k in ordered}
    for key in ordered:  # topological, so predecessors are already final
        for nxt in edges[key]:
            depth[nxt] = max(depth[nxt], depth[key] + 1)
    lanes: list[list[str]] = [[] for _ in range(max(depth.values(), default=-1) + 1)]
    for key in ordered:
        lanes[depth[key]].append(key)
    return {"steps": steps, "lanes": lanes,
            "tier_summary": {t: sum(1 for s in steps if s["tier"] == t) for t in "ABC"}}
