"""The pack absorber, end to end: a folder in, a bundle out, and everything it did not read named.

The tool's whole reason to exist is the last part. A person signs the bundle and the signature is
what makes the design executable, so a reader that silently skipped a file would be handing somebody
part of a design to sign as the whole of it. The exit status is how that reaches a pipeline.
"""
import importlib.util
import json
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"
TOOL = Path(__file__).parents[3] / "tools" / "jidoka-absorb.py"

spec = importlib.util.spec_from_file_location("jidoka_absorb", TOOL)
absorber = importlib.util.module_from_spec(spec)
spec.loader.exec_module(absorber)


def run(tmp_path, folder, *extra):
    out = tmp_path / "bundle.json"
    code = absorber.main([str(folder), "--term", "2026-10", "--system", "ACME-QAL",
                          "--out", str(out), *extra])
    return code, json.loads(out.read_text())


def pack(tmp_path):
    """A pack is a folder. The fixtures are copied under the names the profiles match on."""
    folder = tmp_path / "pack"
    (folder / "01_Plan_of_Record").mkdir(parents=True)
    (folder / "03_Design_Authority").mkdir(parents=True)
    (folder / "01_Plan_of_Record" / "Integrated Plan Workbook v1.0.xlsx").write_bytes(
        (FIX / "mobilisation_plan.xlsx").read_bytes())
    (folder / "03_Design_Authority" / "Cross-Module Alignment Matrix v1.0.xlsx").write_bytes(
        (FIX / "alignment_matrix.xlsx").read_bytes())
    return folder


def test_a_pack_folder_yields_the_programme_the_design_and_the_decisions(tmp_path):
    code, bundle = run(tmp_path, pack(tmp_path))
    assert code == 0
    prog = bundle["programme"]
    assert [g["gate_id"] for g in prog["gates"]] == ["G1", "G2", "G3", "DEL-D1", "DEL-D2"]
    assert [t["task_id"] for t in prog["tasks"]][:3] == ["T-001", "T-002", "T-003"]
    assert len(prog["conditions"]) == 2
    assert bundle["contracts"]["Pay components"]["owner"] == "EC Payroll"


def test_the_bundle_says_it_is_not_intent(tmp_path):
    _, bundle = run(tmp_path, pack(tmp_path))
    assert "not intent" in bundle["unsigned"]
    assert "until a person signs it" in bundle["unsigned"]
    assert "signature" not in json.dumps(bundle["records"])


def test_a_file_no_profile_matches_is_named_and_fails_the_run(tmp_path):
    folder = pack(tmp_path)
    (folder / "99_Extra" ).mkdir()
    (folder / "99_Extra" / "Payroll Rules Something.xlsx").write_bytes(
        (FIX / "alignment_matrix.xlsx").read_bytes())
    code, bundle = run(tmp_path, folder)
    # The bundle is still written — a person needs to see what was read — but the run is not clean.
    assert code == 1
    assert bundle["programme"]["gates"]


def test_the_term_is_declared_and_a_malformed_one_is_refused(tmp_path):
    out = tmp_path / "b.json"
    assert absorber.main([str(pack(tmp_path)), "--term", "October", "--system", "A",
                          "--out", str(out)]) == 2
    assert not out.exists()


def test_a_folder_that_is_not_a_folder_is_refused(tmp_path):
    assert absorber.main([str(FIX / "mobilisation_plan.xlsx"), "--term", "2026-10",
                          "--system", "A"]) == 2


def test_one_way_doors_arrive_as_one_way_decisions(tmp_path):
    _, bundle = run(tmp_path, pack(tmp_path))
    kinds = {d["dp_id"]: d["dp_type"] for d in bundle["decision_points"]}
    assert kinds["DOOR-D1"] == "ONE_WAY" and kinds["DOOR-D2"] == "ONE_WAY"
    assert kinds["DP-B01"] == "DESIGN"


def test_an_unmatched_data_domain_becomes_a_decision_rather_than_a_silent_zero(tmp_path):
    _, bundle = run(tmp_path, pack(tmp_path))
    mapping = [d for d in bundle["decision_points"] if d["dp_id"].startswith("DP-MAP-")]
    assert len(mapping) == len(bundle["contracts"])
    assert "cannot tell who a change to them breaks" in mapping[0]["question"]
    assert "will report no undeclared readers because it was given none" in " ".join(bundle["notes"])


def pack_with_documents(tmp_path):
    folder = pack(tmp_path)
    (folder / "03_Design_Authority" / "Solution Design Document v1.0.docx").write_bytes(
        (FIX / "design_document.docx").read_bytes())
    (folder / "03_Design_Authority" / "Licensing Position v1.0.docx").write_bytes(
        (FIX / "licensing_position.docx").read_bytes())
    return folder


def test_the_documents_are_read_as_well_as_the_workbooks(tmp_path):
    code, bundle = run(tmp_path, pack_with_documents(tmp_path))
    assert code == 0
    spec = bundle["specification"]
    assert [r["req_id"] for r in spec["requirements"]] == \
        ["BRS-EC-001", "BRS-EC-002", "BRS-TIM-001"]
    assert [c["control_id"] for c in spec["controls"]] == ["C01"]
    assert bundle["ordering"][0]["by"] == "Week 1"
    assert {r["rule_id"] for r in bundle["rules"]} == {"P1", "A1"}


def test_a_decision_stated_two_ways_across_the_pack_reaches_the_bundles_notes(tmp_path):
    _, bundle = run(tmp_path, pack_with_documents(tmp_path))
    notes = " ".join(bundle["notes"])
    assert "DP-C04 is stated 2 different ways" in notes
    assert len([d for d in bundle["decision_points"] if d["dp_id"] == "DP-C04"]) == 2


def test_a_document_no_workbook_duplicates_still_reports_its_unread_prose(tmp_path):
    _, bundle = run(tmp_path, pack_with_documents(tmp_path))
    assert "section(s) of prose were not read at all" in " ".join(bundle["notes"])


def test_the_one_way_doors_survive_the_merge_into_the_bundle(tmp_path):
    # They were dropped once, by a field-by-field copy that forgot them.
    _, bundle = run(tmp_path, pack_with_documents(tmp_path))
    doors = [d for d in bundle["decision_points"] if d["dp_type"] == "ONE_WAY"]
    assert {d["dp_id"] for d in doors} == {"DOOR-D1", "DOOR-D2"}
