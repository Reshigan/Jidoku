"""Reading a Word document's tables.

The fixture is built by `fixtures/make_fixtures.py` with zipfile and no dependency, and it
reproduces the two things a real pack does that break a naive reader: a sentence split across runs,
and the same register written as several tables under one heading each.
"""
from pathlib import Path

import pytest
from jidoka_compiler.docx import DocxError, headings, paragraphs, rows, tables, unread

DOC = Path(__file__).parent / "fixtures" / "design_document.docx"
REQ = ("ID", "Requirement", "Rationale")


def test_a_sentence_split_across_runs_comes_back_whole():
    # Word starts a new run wherever formatting changes. Reading the first w:t returns half a
    # requirement, and half a requirement reads like a complete one.
    first = rows(DOC, REQ)[0]
    assert first["Requirement"] == "Single instance, four country layers"
    assert first["Rationale"].startswith("The baseline extract establishes")


def test_every_table_under_a_header_is_read_not_only_the_first():
    # A real BRS writes sixty-two requirements as seventeen tables. Taking the first would report a
    # seventeenth of a specification as the whole of it.
    ids = [r["ID"] for r in rows(DOC, REQ)]
    assert ids == ["BRS-EC-001", "BRS-EC-002", "BRS-TIM-001"]


def test_a_row_is_keyed_by_its_own_headers():
    r = rows(DOC, REQ)[0]
    assert r["Fit"] == "STD" and r["Ctrl"] == "C01" and r["Wave/Wk"] == "W1"


def test_a_header_that_matches_nothing_returns_nothing_rather_than_guessing():
    assert rows(DOC, ("Sprint", "Velocity")) == []


def test_the_tables_no_header_matched_are_named_with_their_size():
    left = unread(DOC, [REQ, ("ID", "Control objective", "Owner")])
    labels = {first for first, _ in left}
    assert "Document ID" in labels
    assert "Item" in labels                 # the scope catalogue, unread by this caller's headers
    assert all(n >= 0 for _, n in left)


def test_a_table_every_header_matched_is_not_reported_as_unread():
    every = [tuple(t[0][:3]) for t in tables(DOC) if t and len(t[0]) >= 3]
    assert ("Document ID", "FIXTURE-SDD-001") not in every    # two columns, so not in this set
    left = unread(DOC, every)
    assert all(first in ("Document ID",) for first, _ in left)


def test_the_documents_own_outline_is_available_to_say_what_was_not_read():
    heads = headings(DOC)
    assert "What This Document Governs" in heads
    assert "Ordering Constraints" in heads


def test_the_prose_is_returned_as_prose_and_nothing_interprets_it():
    text = " ".join(paragraphs(DOC))
    assert "Most of its reasoning is in sentences" in text


def test_something_that_is_not_a_docx_is_refused_by_name():
    with pytest.raises(DocxError) as ex:
        rows(Path(__file__), REQ)
    assert "not a readable .docx" in str(ex.value)
