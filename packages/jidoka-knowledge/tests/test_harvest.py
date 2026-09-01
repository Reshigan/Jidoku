"""Harvest gates: read-only, grounded, structure-vs-setting, and the promotion queue.

Fixture-driven against the mock's real $metadata document, not against hand-written rows: a
harvester tested on dicts the test wrote is only testing the test.
"""
import pytest
from jidoka_adapters.mocksap import fixtures
from jidoka_knowledge import (ProjectStore, SystemStore, harvest, promotable, promote,
                              resolver, row_of, screen, sweep, PromotionRefused,
                              HarvestRefused, STALE, TRUSTED)
from jidoka_knowledge import metadata


class _System:
    """The registry's shape, as much of it as a harvest touches."""
    def __init__(self, system_id="SF-DEV", role="TARGET", product="SuccessFactors", credentials=None):
        self.system_id, self.role, self.product, self.credentials = system_id, role, product, credentials


class _Adapter:
    """A real adapter surface: extract() delegates to an injected fetcher, exactly as SF does."""
    product = "SuccessFactors"

    def __init__(self, fetch):
        self._fetch = fetch
        self.wrote = []

    def extract(self, system, entity):
        return self._fetch(system, entity)

    # Present so a mistake that calls one is a loud failure rather than a silent write.
    def build_apply(self, ir):
        self.wrote.append(ir)
        raise AssertionError("a harvest must never build a write")

    def verify(self, ir, live):
        raise AssertionError("a harvest must never verify")

    def tier_map(self):
        return {}


def _fetch():
    return metadata.read(fixtures.METADATA_XML, picklists=fixtures.PICKLISTV2)


def _harvest(store=None, system=None):
    store = store or ProjectStore("eng-1")
    return harvest(_Adapter(_fetch()), system or _System(), store, actor="agent"), store


def test_harvest_forms_grounded_claims_from_the_service_definition():
    claims, store = _harvest()
    assert claims and claims == store.current()
    # Every claim cites the system and the entity it was read from — that is what an auditor follows.
    assert all(c.source_ref.startswith("harvest:SF-DEV:") for c in claims)
    assert all(c.source_hash for c in claims)


def test_harvest_learns_the_tables_and_fields_the_service_publishes():
    claims, _ = _harvest()
    said = " | ".join(c.text for c in claims)
    assert "FOCostCenter holds" in said
    assert "FOCostCenter.externalCode is String of length 32" in said
    # A picklist annotation is a check table, and the harvester says so in those words.
    assert "FOCostCenter.status may only hold a value present in ACTIVE_STATUS" in said


def test_a_domain_carries_the_permitted_values_not_a_description_of_them():
    """The whole reason metadata beats documentation: the option set is this tenant's actual set."""
    claims, _ = _harvest()
    domain = next(c for c in claims if c.text.startswith("Domain ACTIVE_STATUS"))
    options = {r["externalCode"] for r in fixtures.PICKLISTV2
               if r.get("picklistId") == "ACTIVE_STATUS"}
    assert options, "fixture must actually carry this picklist for the test to mean anything"
    assert all(o in domain.text for o in options)


def test_harvest_never_calls_a_write_path():
    """Invariant 3 holds by construction: extract() is the only adapter method a harvest uses."""
    adapter = _Adapter(_fetch())
    harvest(adapter, _System(), ProjectStore("eng-1"), actor="agent")
    assert adapter.wrote == []


def test_harvest_refuses_a_source_system_holding_credentials():
    with pytest.raises(HarvestRefused):
        harvest(_Adapter(_fetch()),
                _System(role="SOURCE_LEGACY", credentials={"token": "x"}),
                ProjectStore("eng-1"), actor="agent")


def test_a_product_without_an_interface_is_skipped_not_fatal():
    """SuccessFactors has no IMG tree; asking for one must not abort the whole harvest."""
    claims, _ = _harvest()
    assert claims
    assert not any(":img_nodes" in c.source_ref for c in claims)


def test_harvest_is_ledgered_like_any_other_belief_write():
    from jidoka_core.ledger import Ledger
    led = Ledger()
    claims, _ = _harvest(store=ProjectStore("eng-1", ledger=led))
    assert len(led.entries) == len(claims)
    assert {e["action"] for e in led.entries} == {"BELIEF"}
    assert led.verify_chain()


def test_a_changed_service_definition_makes_the_claim_stale():
    """Re-reading through the same adapter is what makes staleness a comparison, not an opinion."""
    claims, store = _harvest()
    edmx = fixtures.METADATA_XML.replace('Name="name" Type="Edm.String" Nullable="false" MaxLength="255"',
                                         'Name="name" Type="Edm.String" Nullable="false" MaxLength="128"')
    assert edmx != fixtures.METADATA_XML
    system = _System()
    read = resolver({"SF-DEV": (_Adapter(metadata.read(edmx, picklists=fixtures.PICKLISTV2)), system)})
    counts = sweep(store, lambda c: row_of(c, read(c.source_ref)))
    assert counts[STALE] == 1 and counts[TRUSTED] == len(claims) - 1
    stale = store.stale()
    assert len(stale) == 1 and "FOCostCenter.name" in stale[0].text
    # Flagged, never deleted.
    assert stale[0] in store.current()


def test_an_unchanged_service_definition_leaves_everything_trusted():
    claims, store = _harvest()
    read = resolver({"SF-DEV": (_Adapter(_fetch()), _System())})
    counts = sweep(store, lambda c: row_of(c, read(c.source_ref)))
    assert counts[TRUSTED] == len(claims) and counts[STALE] == 0


def test_an_unregistered_system_is_unresolvable_not_stale():
    from jidoka_knowledge import Unresolvable
    claims, _ = _harvest()
    with pytest.raises(Unresolvable):
        resolver({})(claims[0].source_ref)


def test_only_structure_is_offered_for_promotion():
    claims, _ = _harvest()
    offered = promotable(claims)
    assert offered
    assert all(c.source_ref.rsplit(":", 1)[-1] in
               ("tables", "fields", "domains", "value_help", "check_tables") for c in offered)
    # And nothing the gate would refuse anyway reaches a reviewer's queue.
    assert not [c for c in offered if screen(c.text)]


def test_a_field_length_keeps_a_structural_fact_out_of_system_memory():
    """The scrubber cannot tell a length from a client code, and must not try.

    `MaxLength="255"` is genuinely general SAP truth, but it reads as a literal numeric code and
    the gate refuses rather than redacts. That is the gate working: a human rewrites it as a
    shape, and nothing crosses on a regex's opinion.
    """
    claims, _ = _harvest()
    sized = next(c for c in claims if "of length 255" in c.text)
    assert screen(sized.text)
    assert sized not in promotable(claims)
    with pytest.raises(PromotionRefused):
        promote(sized, SystemStore(), approver="lead", builder="agent")


def test_promotion_of_a_harvested_shape_still_needs_a_second_human():
    claims, _ = _harvest()
    shape = promotable(claims)[0]
    with pytest.raises(PromotionRefused):
        promote(shape, SystemStore(), approver="agent", builder="agent")
    system = SystemStore()
    out = promote(shape, system, approver="lead", builder="agent")
    assert out in system.current()
    # System memory holds no pointer back into the engagement.
    assert "SF-DEV" not in out.source_ref and out.source_ref.startswith("promotion:")


def test_harvests_of_two_engagements_do_not_mix():
    _, a = _harvest(store=ProjectStore("eng-a"))
    b = ProjectStore("eng-b")
    assert a.current() and b.current() == []


def test_the_tier_map_teaches_what_may_be_configured_by_machine():
    """The single most useful structural fact about an SAP product, and no manual states it."""
    from jidoka_adapters.s4hana import S4Adapter
    from jidoka_knowledge import from_tier_map
    store = ProjectStore("eng-1")
    claims = from_tier_map(S4Adapter(fetch=lambda s, e: []), _System(product="S4HANA"), store, "agent")
    said = " | ".join(c.text for c in claims)
    assert "A_CostCenter has a published write API" in said
    assert "T001 is transported customising with no write path" in said
    assert "ASSET_MASTER_LEGACY has no write API and is loaded from a file by a person" in said
    # Never the tier letter: a promoted claim must not read as an internal token.
    assert "tier A" not in said and "tier C" not in said


def test_tier_facts_are_promotable_general_truth():
    from jidoka_adapters.s4hana import S4Adapter
    from jidoka_knowledge import from_tier_map
    store = ProjectStore("eng-1")
    claims = from_tier_map(S4Adapter(fetch=lambda s, e: []), _System(product="S4HANA"), store, "agent")
    offered = promotable(claims)
    # Nearly all of it crosses: a tier declaration carries no client value. The exception is
    # TKA01, a real table name the value screen cannot distinguish from a client identifier —
    # the gate refusing a true fact is the gate working, and a human rewrites it to cross.
    assert len(offered) == len(claims) - 1
    assert [c for c in claims if c not in offered][0].text.startswith("TKA01")
    system = SystemStore()
    promote(offered[0], system, approver="lead", builder="agent")
    assert len(system.current()) == 1
