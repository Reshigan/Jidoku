"""Gates that must hold: grounding, isolation, durable staleness, the scrubber."""
import pytest
from jidoka_core.ledger import Ledger
from jidoka_knowledge import (Claim, ProjectStore, SystemStore, evidence_hash, recheck,
                              sweep, supersede, promote, screen, PromotionRefused,
                              TRUSTED, STALE)


def _claim(text="four-digit numeric cost centres", ev=None, actor="agent"):
    ev = {"record": "CC-01"} if ev is None else ev
    return Claim("cost-centres", text, "ir:CC-01", evidence_hash(ev), actor)


def test_claim_without_source_is_unstorable():
    with pytest.raises(ValueError):
        Claim("x", "y", "", "hash", "agent")


def test_belief_write_lands_on_the_ledger():
    led = Ledger()
    ProjectStore("eng-1", ledger=led).add(_claim())
    assert [e["action"] for e in led.entries] == ["BELIEF"]
    assert led.verify_chain()


def test_engagements_cannot_reach_each_other():
    a, b = ProjectStore("eng-a"), ProjectStore("eng-b")
    a.add(_claim("shape A"))
    assert b.current() == []
    # The isolation is structural: no store method accepts another engagement's id.
    assert not [m for m in dir(a) if "engagement" in m and callable(getattr(a, m, None))]


def test_stale_claim_is_flagged_not_deleted():
    store = ProjectStore("eng-1")
    c = store.add(_claim())
    assert recheck(c, {"record": "CC-01"}) == TRUSTED
    assert recheck(c, {"record": "CC-02"}) == STALE   # evidence moved under it
    assert c in store.current() and store.stale() == [c]


def test_missing_evidence_is_stale_not_trusted():
    assert recheck(_claim(), None) == STALE


def test_supersession_closes_the_interval_and_keeps_history():
    store = ProjectStore("eng-1")
    old = store.add(_claim())
    recheck(old, {"record": "CC-99"})
    new = supersede(store, old, "five-digit numeric", {"record": "CC-99"}, "ir:CC-01", "agent")
    assert not old.open and new.open
    assert store.current() == [new]
    assert len(store.all()) == 2           # history survives the correction
    assert store.as_of(old.valid_from) == [old]


def test_sweep_counts_what_still_stands_up():
    store = ProjectStore("eng-1")
    good = store.add(_claim("shape one", ev={"a": 1}))
    bad = store.add(_claim("shape two", ev={"a": 2}))
    counts = sweep(store, lambda c: {"a": 1})
    assert counts[TRUSTED] == 1 and counts[STALE] == 1


def test_scrubber_refuses_client_values():
    assert screen("cost centre 1000 is the default")
    assert screen("contact fred@client.co.za")
    assert screen("BUKRS = ZA01")
    assert screen("go-live is 2026-03-01")
    assert not screen("cost centre codes are four-digit numeric")


def test_promotion_refuses_values_and_self_approval():
    sysmem, led = SystemStore(), Ledger()
    with pytest.raises(PromotionRefused):
        promote(_claim("cost centre 1000 is default"), sysmem, "human", "agent", led)
    with pytest.raises(PromotionRefused):
        promote(_claim(), sysmem, "agent", "agent", led)      # builder == approver
    with pytest.raises(PromotionRefused):
        promote(_claim(), sysmem, "", "agent", led)           # unapproved
    assert sysmem.current() == []


def test_promotion_carries_no_pointer_back_into_the_engagement():
    sysmem, led = SystemStore(), Ledger()
    src = _claim()
    got = promote(src, sysmem, "human", "agent", led)
    assert got.source_ref == f"promotion:{src.id}"
    assert "ir:" not in got.source_ref                # no reach back into client data
    assert got.actor == "human"
    assert [e["action"] for e in led.entries] == ["PROMOTED"]


def test_timestamps_are_parseable_and_sort_chronologically():
    """String comparison drives as_of(), so the stamp must be real ISO and fixed-width."""
    from datetime import datetime
    from jidoka_knowledge.claim import now
    stamps = [now() for _ in range(50)]
    for s in stamps:
        datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")      # malformed stamp raises here
    assert stamps == sorted(stamps)                        # lexical order == chronological order
    assert len({len(s) for s in stamps}) == 1              # fixed width, or sorting lies
