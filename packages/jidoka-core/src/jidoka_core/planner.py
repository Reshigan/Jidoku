"""Run-planner: topological sort of the IR dependency graph, tier split, DP hard-block.
The plan is derived from the work — cycles and open decisions stop the plan, loudly."""
from .contracts import conflicts as write_conflicts
from .ir import IRRecord
from .refinements import check as type_check, missing_required

class PlanError(Exception): ...

def alias_of(obj: str, code: str | None, intent: dict | None = None) -> str:
    """The short reference a design uses for a record — `TimeAccountType:ANN_ACC_ZAF` — as `plan`
    indexes it. One definition, because a drafter and the planner disagreeing about what a reference
    resolves to is a dependency that looks fine until the plan is built."""
    return f"{obj}:{code or (intent or {}).get('externalCode', '?')}"


def dependency_problems(deps: dict[str, list[str]], aliases: dict[str, str]) -> dict:
    """What `plan` would refuse about a dependency graph, without building a plan.

    `deps` maps a record's key to what it depends on; `aliases` maps a short reference to a key.
    Returns `dangling` — (record, reference) pairs naming something not in the design — and `cyclic`,
    the records left after every record with all its dependencies met has been removed. Pure over
    keys, so it works on drafts nobody has signed: a design pass finds these while the model can
    still fix them, instead of at plan time after a person has signed.

    `plan` remains the authority and this is tied to it by a test that builds graphs both ways: a
    second implementation of a rule is only safe while something fails when the two disagree.
    """
    dangling, indeg, edges = [], {k: 0 for k in deps}, {k: [] for k in deps}
    for key, refs in deps.items():
        for ref in refs:
            target = aliases.get(ref, ref)
            if target not in deps:
                dangling.append((key, ref))
                continue
            edges[target].append(key)
            indeg[key] += 1
    queue, seen = [k for k, d in indeg.items() if d == 0], 0
    while queue:
        k = queue.pop()
        seen += 1
        for nxt in edges[k]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    return {"dangling": dangling,
            "cyclic": sorted(k for k, d in indeg.items() if d > 0) if seen != len(deps) else []}


def plan(records: list[IRRecord], open_dps: dict[str, list[str]]) -> dict:
    # One writer, declared readers. Two modules claiming to write the same object is a design
    # decision nobody has made, and it blocks for the same reason an open decision point does:
    # JIDOKA refuses to answer it by picking one. Checked before the decision points so the
    # message names the rule rather than arriving as a mysterious ordering problem later.
    clash = write_conflicts(records)
    if clash:
        lines = [f"  {k}: {v[0]}" for k, v in sorted(clash.items())]
        raise PlanError("PLAN BLOCKED — two modules claim to write the same object:\n"
                        + "\n".join(lines))
    if open_dps:
        lines = [f"  {k}: {', '.join(v)}" for k, v in open_dps.items()]
        raise PlanError("PLAN BLOCKED — open Decision Points (JIDOKA will not invent values):\n" + "\n".join(lines))

    # Type-check, after the decisions: a refinement over a value nobody has decided would report
    # the absence of a decision as a type error, and the gate above says that better. The message
    # is the auditor's control narrative verbatim — a rejection that needed translating before it
    # could go in a report would be translated by hand once, and then drift (ADR-0036).
    failures = type_check(records) + missing_required(records)
    if failures:
        raise PlanError("PLAN BLOCKED — signed intent does not type-check:\n"
                        + "\n".join(f"  {f['says']}" for f in failures))
    by_key = {r.key: r for r in records}
    # also index by short externalCode refs like "TimeAccountType:ANN_ACC_ZAF"
    short = {}
    for r in records:
        short[alias_of(r.object, r.external_code, r.intent)] = r.key
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
