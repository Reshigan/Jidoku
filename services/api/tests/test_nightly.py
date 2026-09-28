"""The night's entry point: one call, every engagement, and an exit code a scheduler can read."""
import json
import pathlib

import pytest
from fastapi.testclient import TestClient
from jidoka_api.main import app
from jidoka_api.nightly import NIGHT_ACTOR, main, work_the_night
from jidoka_api.routers.engagements import STORE

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))


@pytest.fixture(autouse=True)
def _clean():
    STORE.reset()
    yield
    STORE.reset()


def _eng(name, bind=True):
    eid = c.post("/engagements", json={"name": name, "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=IR)
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": IR[0]["system_binding"], "product": "SuccessFactors", "role": "TARGET",
        "environment": "DEV", "connectivity": {"write_credentials": "vault:sf"}})
    if bind:
        c.post(f"/engagements/{eid}/execution/connector",
               json={"system_id": IR[0]["system_binding"], "kind": "mock"})
    return eid


def test_every_engagement_gets_its_own_night():
    _eng("ZA payroll"), _eng("CO rollout")
    out = work_the_night()
    assert len(out["worked"]) == 2 and out["failed"] == []
    assert {n["name"] for n in out["worked"]} == {"ZA payroll", "CO rollout"}
    assert all(n["handover"].startswith("Handover — Komatsu") for n in out["worked"])


def test_one_bad_engagement_does_not_abandon_the_others():
    """A night that stopped at the first failure would leave twelve engagements unworked."""
    good = _eng("ZA payroll")
    STORE.get(good)  # keep it in the cache
    broken = _eng("Broken")
    STORE.get(broken).ir = None          # a shape nothing downstream can walk

    out = work_the_night()
    assert [n["name"] for n in out["worked"]] == ["ZA payroll"]
    assert [f["name"] for f in out["failed"]] == ["Broken"]


def test_the_night_runs_as_the_platform_and_says_so_on_the_chain():
    """Not a person, and never pretending to be one."""
    eid = _eng("ZA payroll")
    work_the_night()
    entry = next(e for e in c.get(f"/engagements/{eid}/ledger").json()["entries"]
                 if e["action"] == "HANDOVER")
    assert entry["actor"] == NIGHT_ACTOR


def test_the_budget_carries_through_to_every_engagement():
    eid = _eng("ZA payroll")
    STORE.get(eid).ledger.append("t", "PARTIAL", "a.builder", "half-landed")
    STORE.get(eid).ledger.append("t2", "PARTIAL", "a.builder", "half-landed")
    out = work_the_night(budget=1)
    assert out["worked"][0]["interrupted"] == 1


def test_the_exit_code_tells_a_scheduler_whether_the_night_ran(capsys):
    _eng("ZA payroll")
    assert main(["--quiet"]) == 0
    assert json.loads(capsys.readouterr().out) == {"worked": 1, "failed": 0}


def test_a_failed_engagement_makes_the_exit_code_non_zero(capsys):
    """A night that half-ran and reported success is worse than one that reported failure."""
    _eng("ZA payroll")
    STORE.get(_eng("Broken")).ir = None
    assert main(["--quiet"]) == 1
    assert json.loads(capsys.readouterr().out) == {"worked": 1, "failed": 1}


def test_with_nothing_to_work_it_succeeds_quietly(capsys):
    assert main(["--quiet"]) == 0
    assert json.loads(capsys.readouterr().out) == {"worked": 0, "failed": 0}


def test_it_prints_the_handovers_when_not_quiet(capsys):
    _eng("ZA payroll")
    main([])
    assert "**What I need from you today**" in capsys.readouterr().out
