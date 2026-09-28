"""Whether the tier map is true *here*, against one tenant's own `$metadata`.

The map is a statement about a product. A tenant is a different thing: SF creates an entity set per
MDF object definition, so Tier-A coverage varies by customer. What these pin is the refusal to treat
silence as permission — an entity set with no write annotation is unconfirmed, never writable.
"""
from jidoka_adapters.base import audit_tenant
from jidoka_adapters.successfactors import SFAdapter
from jidoka_adapters.successfactors.odata import parse_entity_sets

SAP = 'xmlns:sap="http://www.sap.com/Protocols/SAPData"'


def metadata(*sets):
    body = "".join(f'<EntitySet Name="{n}" EntityType="SFOData.{n}"{a}/>' for n, a in sets)
    return (f'<edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx" {SAP}>'
            f'<edmx:DataServices><Schema xmlns="http://schemas.microsoft.com/ado/2008/09/edm">'
            f'<EntityContainer Name="C">{body}</EntityContainer></Schema></edmx:DataServices>'
            f'</edmx:Edmx>')


def sets(*pairs):
    return parse_entity_sets(metadata(*pairs))


def test_an_annotation_the_tenant_published_is_read_and_one_it_did_not_is_none_not_true():
    got = sets(("FOCostCenter", ' sap:upsertable="true" sap:creatable="true"'),
               ("FODepartment", ' sap:upsertable="false"'),
               ("FOLocation", ""))
    assert got["FOCostCenter"]["upsertable"] is True and got["FOCostCenter"]["updatable"] is None
    assert got["FODepartment"]["upsertable"] is False
    assert got["FOLocation"] == {"entity_type": "SFOData.FOLocation", "upsertable": None,
                                "creatable": None, "updatable": None}


def test_a_tier_a_object_the_tenant_does_not_publish_is_a_claim_that_is_false_here():
    out = audit_tenant(SFAdapter(), sets(("FOCostCenter", ' sap:upsertable="true"')))
    assert "FOCostCenter" not in out["not_published"]
    assert "FODepartment" in out["not_published"]
    assert "the tier-A claim is false here" in out["says"]


def test_published_and_marked_not_upsertable_is_reported_apart_from_not_published():
    out = audit_tenant(SFAdapter(), sets(("FOCostCenter", ' sap:upsertable="false"')))
    assert out["not_writable"] == ["FOCostCenter"]
    assert "FOCostCenter" not in out["not_published"]


def test_silence_is_unconfirmed_and_never_counted_as_writable():
    out = audit_tenant(SFAdapter(), sets(("FOCostCenter", ""),
                                         ("FODepartment", ' sap:upsertable="true"')))
    assert out["writability_unknown"] == ["FOCostCenter"]
    assert out["tier_a_confirmed_writable"] == 1
    assert "unconfirmed rather than assumed" in out["says"]


def test_an_entity_set_in_no_tier_map_is_named_and_only_a_tenant_marked_one_is_a_candidate():
    # MDF generic objects are the case that matters: they exist per customer and no product-level
    # map can list them. A candidate is a *question for the adapter*, never a promotion.
    out = audit_tenant(SFAdapter(), sets(("cust_Grievance", ' sap:upsertable="true"'),
                                         ("cust_Audit", ' sap:upsertable="false"'),
                                         ("cust_Quiet", "")))
    assert out["uncatalogued"] == ["cust_Audit", "cust_Grievance", "cust_Quiet"]
    assert out["candidates"] == ["cust_Grievance"]


def test_the_audit_reports_and_never_edits_the_tier_map():
    adapter = SFAdapter()
    before = dict(adapter.tier_map())
    audit_tenant(adapter, sets(("cust_Grievance", ' sap:upsertable="true"')))
    assert adapter.tier_map() == before


def test_an_empty_tenant_says_so_rather_than_reporting_a_clean_map():
    out = audit_tenant(SFAdapter(), {})
    assert out["tier_a_confirmed_writable"] == 0
    assert len(out["not_published"]) == out["tier_a_claimed"] > 0
