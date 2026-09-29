"""`dependency_problems` is a second implementation of a rule `plan` already enforces, so the only
thing that makes it safe is a test that fails when the two disagree. That is most of this file."""
import itertools

import pytest
from jidoka_core.ir import IRRecord
from jidoka_core.planner import PlanError, alias_of, dependency_problems, plan


def rec(code, deps=()):
    return IRRecord(object="FOCostCenter", product="SuccessFactors", system_binding="X",
                    intent={"externalCode": code}, tier="A",
                    source={"workbook": "w", "signed_by": "s", "date": "d"},
                    depends_on=list(deps), external_code=code)


def graph(records):
    aliases = {alias_of(r.object, r.external_code, r.intent): r.key for r in records}
    return {r.key: list(r.depends_on) for r in records}, aliases


def test_a_clean_graph_has_no_problems():
    d, a = graph([rec("A"), rec("B", ["FOCostCenter:A"])])
    assert dependency_problems(d, a) == {"dangling": [], "cyclic": []}


def test_a_dependency_on_something_not_in_the_design_is_dangling_and_named():
    d, a = graph([rec("A", ["FOCostCenter:NOPE"])])
    got = dependency_problems(d, a)
    assert got["dangling"] == [("SuccessFactors:FOCostCenter:A", "FOCostCenter:NOPE")]


def test_a_cycle_names_every_record_it_involves_and_not_the_innocent_ones():
    d, a = graph([rec("A", ["FOCostCenter:B"]), rec("B", ["FOCostCenter:A"]), rec("C")])
    assert dependency_problems(d, a)["cyclic"] == ["SuccessFactors:FOCostCenter:A",
                                                   "SuccessFactors:FOCostCenter:B"]


def test_a_self_dependency_is_a_cycle():
    d, a = graph([rec("A", ["FOCostCenter:A"])])
    assert dependency_problems(d, a)["cyclic"] == ["SuccessFactors:FOCostCenter:A"]


def test_a_full_key_resolves_as_well_as_a_short_reference():
    d, a = graph([rec("A"), rec("B", ["SuccessFactors:FOCostCenter:A"])])
    assert dependency_problems(d, a) == {"dangling": [], "cyclic": []}


#: Every graph on three nodes with up to four edges, self-loops included: 256 of them. Small enough to
#: run every time, large enough to contain each shape that matters — clean, dangling-free chains,
#: two-cycles, three-cycles, self-loops, and a cycle with an innocent bystander.
ALL_EDGES = [(i, j) for i in range(3) for j in range(3)]
SMALL_GRAPHS = [e for n in range(5) for e in itertools.combinations(ALL_EDGES, n)]


@pytest.mark.parametrize("edges", SMALL_GRAPHS)
def test_the_pure_check_and_the_planner_agree_on_every_small_graph(edges):
    assert len(SMALL_GRAPHS) == 256
    codes = ["A", "B", "C"]
    deps = {c: [f"FOCostCenter:{codes[j]}" for (i, j) in edges if codes[i] == c] for c in codes}
    records = [rec(c, deps[c]) for c in codes]
    d, a = graph(records)
    found = dependency_problems(d, a)
    refused = False
    try:
        plan(records, {})
    except PlanError as ex:
        refused = "cycle" in str(ex) or "unknown object" in str(ex)
    assert refused == bool(found["dangling"] or found["cyclic"]), edges


def test_the_planner_and_the_drafter_resolve_a_reference_the_same_way():
    assert alias_of("FOCostCenter", "CC1") == "FOCostCenter:CC1"
    assert alias_of("FOCostCenter", None, {"externalCode": "CC1"}) == "FOCostCenter:CC1"
