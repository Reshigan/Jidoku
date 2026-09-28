"""Reading the workbook a programme actually wrote.

The shape here is the shape of a real design authority pack: a title block, a rule statement, a
wordmark, and then the header row. `compile_xlsx` requires the header in row 1, so asked to compile
one of these it read every sheet as zero records — and said nothing, because skipping is what it
does when the convention is absent. The client pack that found this is not in the repository; this
fixture reproduces its shape.
"""
import dataclasses
import pathlib

import pytest

from jidoka_compiler.profile import (Profile, ProfileError, compile_decisions, compile_profiled)

WB = pathlib.Path(__file__).parent / "fixtures/design_authority_workbook.xlsx"

VALUES = Profile(
    name="test/option-sets", header_contains="Picklist ID", object="PicklistOption",
    code_column="External code",
    intent={"picklist": "Picklist ID", "label_en_GB": "Label en_GB", "country": "Country"},
    skip_sheets=("Design Rules", "Inventory", "Decision Points"), tier="B",
)
INVENTORY = Profile(
    name="test/inventory", header_contains="Ref", object="Picklist", code_column="Ref",
    intent={"concept": "Business concept"}, sheets=("Inventory",),
    origin_column="Origin", designed_prefix="CLIENT",
    not_a_record=("MDF OBJECT, not a picklist",),
    owner_column="Owner (approves values)", tier="C",
)


def compile_values(**over):
    return compile_profiled(WB, dataclasses.replace(VALUES, **over), "SuccessFactors", "S1",
                            "design_authority_workbook.xlsx", "T. Mabaso", "2026-09-28")


def test_a_header_below_a_title_block_is_found_rather_than_missed():
    """Row 5, under a title, a rule and a wordmark. The old compiler read this as no records."""
    records, notes = compile_values()
    assert len(records) == 3
    assert any("Core HR: 3 record(s) from row 6" in n for n in notes)


def test_provenance_is_a_cell_range_in_the_sheet_the_value_came_from():
    records, _ = compile_values()
    src = records[0]["source"]
    assert src["sheet"] == "Core HR" and src["cell_range"].startswith("Core HR!A6:")
    assert src["signed_by"] == "T. Mabaso"


def test_a_blank_cell_the_profile_named_becomes_a_decision_not_a_value():
    """The compiler never guesses. It did not before and a declared mapping does not change it."""
    records, _ = compile_values()
    blank = next(r for r in records if r["external_code"] == "EC_EMPLOYEE_CLASS_BLANK")
    gap = blank["intent"]["label_en_GB"]
    assert gap["value"] is None
    assert gap["decision_point"] == "DP-GAP-CORE_HR-LABEL_EN_GB-8"


def test_every_sheet_not_read_is_named_and_why():
    """A compiler that read three of eleven sheets and said nothing would report a third of a
    design as the whole of it."""
    _, notes = compile_values()
    assert any("Design Rules: skipped by profile" in n for n in notes)
    assert any("Decision Points: skipped by profile" in n for n in notes)


def test_a_design_authority_qualifies_its_own_answers_so_the_origin_is_a_prefix():
    """"CLIENT" and "CLIENT (statutory codes)" are both designed here. Demanding one spelling
    would silently drop the statutory lists from the delta pool."""
    records, _ = compile_profiled(WB, INVENTORY, "SuccessFactors", "S1", "wb.xlsx", "T", "2026-09-28")
    contracted = [r for r in records if r.get("contract")]
    assert [r["external_code"] for r in contracted] == ["PL-02", "PL-03"]
    assert contracted[1]["contract"]["owner"] == "Client HR + EE Committee"


def test_a_row_the_workbook_disowns_is_not_compiled_as_one():
    """"MDF OBJECT, not a picklist" is the document telling the compiler this is not the thing.
    Compiling it anyway would be the platform overruling the design authority about its own
    design."""
    records, notes = compile_profiled(WB, INVENTORY, "SuccessFactors", "S1", "wb.xlsx", "T", "2026-09-28")
    assert "PL-04" not in [r["external_code"] for r in records]
    assert any("not compiled as a Picklist" in n for n in notes)


def test_a_profile_naming_a_column_the_sheet_does_not_have_is_refused():
    """Guessing which column held the key would produce records nobody can trace to a cell."""
    with pytest.raises(ProfileError, match="names 'Nope' as the code column"):
        compile_values(code_column="Nope")


# --- the decisions a design records ------------------------------------------------------------

DECISIONS = dataclasses.replace(
    __import__("jidoka_compiler.profile", fromlist=["KOMATSU_DECISIONS"]).KOMATSU_DECISIONS,
    name="test/decisions", due_column="Required by", recommendation_column="")


def test_the_decisions_a_workbook_is_waiting_on_are_not_left_on_the_page():
    """The worst result of compiling a real pack: nine decisions with owners and dates on the
    sheet, and a platform reporting a design with nothing blocking it. A false clean is the one
    failure mode this platform exists to prevent."""
    dps, notes = compile_decisions(WB, DECISIONS)
    assert [d["dp_id"] for d in dps] == ["DP-P01", "DP-P03"]
    assert dps[1]["owner"] == "Client HR + EE Committee"
    assert dps[1]["required_by"] == "End W2"


def test_the_type_is_not_guessed_and_the_gap_is_named():
    """A STATUTORY decision needs a signed evidence reference to resolve and one registered as
    DESIGN does not. Guessing from the wording would be the platform deciding which of a client's
    decisions are statutory."""
    dps, notes = compile_decisions(WB, DECISIONS)
    assert {d["dp_type"] for d in dps} == {"DESIGN"}
    assert "the workbook states no type" in notes[0]
    assert "has to be re-typed by a person" in notes[0]
    assert "DP-P01, DP-P03" in notes[0]
