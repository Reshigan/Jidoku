"""The tenant-audit tool: a file in, a verdict out, no network."""
import importlib.util
import json
from pathlib import Path

from test_tenant_audit import metadata

TOOL = Path(__file__).parents[3] / "tools" / "jidoka-tenant-audit.py"
spec = importlib.util.spec_from_file_location("tenant_audit", TOOL)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def run(tmp_path, xml, *extra):
    src = tmp_path / "metadata.xml"
    src.write_text(xml)
    out = tmp_path / "audit.json"
    code = tool.main([str(src), "--out", str(out), *extra])
    return code, (json.loads(out.read_text()) if out.exists() else None)


def test_a_tenant_missing_tier_a_objects_fails_the_run_and_says_which(tmp_path):
    code, out = run(tmp_path, metadata(("FOCostCenter", ' sap:upsertable="true"')))
    assert code == 1 and "FODepartment" in out["not_published"]


def test_a_file_that_is_not_metadata_is_refused_by_name(tmp_path):
    assert run(tmp_path, "this is not xml")[0] == 2


def test_a_metadata_document_with_no_entity_sets_is_refused_rather_than_read_as_empty(tmp_path):
    assert run(tmp_path, metadata())[0] == 2


def test_an_unknown_product_is_refused(tmp_path):
    assert run(tmp_path, metadata(("X", "")), "--product", "Nope")[0] == 2


def test_only_successfactors_metadata_is_parsed_and_the_tool_says_so(tmp_path):
    assert run(tmp_path, metadata(("X", "")), "--product", "S4HANA")[0] == 2
