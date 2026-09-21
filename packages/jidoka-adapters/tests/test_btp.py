"""BTP: declarative by nature, and tier-honest about what that means."""
import pytest

from jidoka_adapters.base import audit_tier_map
from jidoka_adapters.btp import BTPAdapter, BTPError, TerraformRefused, declaration
from jidoka_core.ir import validate_record

SIGNED = {"workbook": "btp-landscape-v2.xlsx", "signed_by": "T. Mabaso", "date": "2026-09-01"}


def rec(object_, code, tier, intent=None):
    return validate_record({"object": object_, "product": "BTP", "system_binding": "KOM-BTP-DEV",
                            "tier": tier, "external_code": code, "source": dict(SIGNED),
                            "intent": {"externalCode": code, **(intent or {})}})[0]


def test_the_tier_map_does_not_lie():
    """Nothing is tier A because it ought to be. The bar is a write path this adapter can name."""
    assert audit_tier_map(BTPAdapter())["lying"] == []


def test_terraform_declared_objects_are_not_claimed_as_tier_a():
    """Applying the plan would mean owning the customer's state file or destroying what it did not
    know about. Neither is a thing to do to somebody's platform tenant."""
    tiers = BTPAdapter().tier_map()
    assert tiers["SUBACCOUNT"] == "B" and tiers["ENTITLEMENT"] == "B"
    assert tiers["ROLE_COLLECTION_MEMBER"] == "A", "this one really is a write API"


def test_a_tier_b_object_is_still_verifiable_because_the_provider_reads_the_same_apis():
    """Tier B here is a hand-off, not a hand-off into the dark."""
    a = BTPAdapter()
    assert a.verifiable("SUBACCOUNT") and a.verifiable("ENTITLEMENT")
    assert not a.verifiable("CUSTOM_IDP_BRANDING")


def test_the_plan_comes_before_the_apply():
    """The value of a declarative tool is that somebody sees the diff first."""
    out = BTPAdapter().build_apply(rec("ENTITLEMENT", "kom-ml", "B",
                                       {"service_name": "hana-cloud", "plan_name": "hana",
                                        "amount": 2}))
    assert out["kind"] == "import_file"
    assert "terraform plan" in out["human_step"]
    assert out["human_step"].index("terraform plan") < out["human_step"].index("terraform apply")
    assert "has not seen your state file" in out["human_step"]


def test_the_hcl_is_plain_enough_to_review():
    hcl = declaration(rec("ENTITLEMENT", "kom-ml", "B",
                          {"service_name": "hana-cloud", "amount": 2, "auto_assign": True}))
    assert hcl.startswith('resource "btp_subaccount_entitlement" "kom-ml" {')
    assert '  amount = 2' in hcl and '  auto_assign = true' in hcl
    assert '  service_name = "hana-cloud"' in hcl
    assert "module" not in hcl and "var." not in hcl


def test_an_object_with_no_provider_resource_is_refused_not_guessed():
    """Guessing a resource type would put a plausible-looking block in front of a reviewer who
    would have no way to tell."""
    with pytest.raises(TerraformRefused, match="no declared BTP provider resource"):
        declaration(rec("SOME_NEW_THING", "x", "B"))


def test_a_tier_the_ir_and_the_adapter_disagree_about_is_refused():
    """Guessing which is right would be the platform deciding what a product permits."""
    with pytest.raises(BTPError, match="One of the two is wrong"):
        BTPAdapter().build_apply(rec("SUBACCOUNT", "kom-dev", "A", {"subdomain": "kom-dev"}))


def test_a_cockpit_only_object_gets_a_person_and_an_attestation():
    out = BTPAdapter().build_apply(rec("CUSTOM_IDP_BRANDING", "kom", "C", {"logo": "kom.png"}))
    assert out["kind"] == "instruction_sheet"
    assert "a person's word, not a check" in out["steps"][-1]


def test_a_tier_a_write_names_its_api_and_rehearses_first():
    out = BTPAdapter().build_apply(rec("ROLE_COLLECTION_MEMBER", "admins", "A",
                                       {"role_collection_name": "admins", "user_name": "a@b.c"}))
    assert out["dry_run"] is True and "XSUAA" in out["api"]
    assert out["key_field"] == "role_collection_name"


def test_verification_reads_the_key_the_entity_actually_answers_to():
    """BTP has no universal external code either, and a diff keyed on the wrong field reports
    every object as missing."""
    a = BTPAdapter()
    ir = rec("SUBACCOUNT", "kom-dev", "B", {"subdomain": "kom-dev", "region": "eu10"})
    assert a.verify(ir, [{"subdomain": "kom-dev", "region": "eu10"}])["status"] == "MATCH"
    assert a.verify(ir, [{"subdomain": "kom-dev", "region": "us10"}])["status"] == "DRIFT"
    assert a.verify(ir, [])["status"] == "MISSING"


def test_extraction_without_a_fetcher_says_so_rather_than_returning_nothing():
    """An empty list would read as "the tenant has none of these", which is a different fact."""
    with pytest.raises(RuntimeError, match="No fetcher configured"):
        BTPAdapter().extract("KOM-BTP-DEV", "SUBACCOUNT")


def test_btp_is_registered_so_an_ir_record_can_name_it():
    """A product the registry does not know is a product the platform refuses to touch, which is
    the right default — and an adapter nothing can reach is a diagram."""
    from jidoka_adapters import ADAPTERS

    assert ADAPTERS["BTP"] is BTPAdapter


def test_there_is_no_live_btp_connector_and_that_is_said_rather_than_faked():
    """No tenant has been bound from this codebase. A connector written against an API nobody has
    called would be a plausible-looking write path into a customer's control plane."""
    from jidoka_api.connectors import ConnectorError, _live

    with pytest.raises(ConnectorError, match="No live connector implemented for product 'BTP'"):
        _live("KOM-BTP-DEV", "BTP", "https://api.cf.eu10.hana.ondemand.com", "BTP")
