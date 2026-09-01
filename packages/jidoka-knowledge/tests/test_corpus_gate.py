"""DP-K01 holds: no gated corpus can be ingested while the decision is open.

These tests are the enforcement, not a description of it. The decision lives in source, so a test
run proves the gate is shut for every tenant at once — which is what "platform-wide legal
position" has to mean if it means anything.
"""
import pytest

from jidoka_knowledge import DP_K01, GATED, CorpusRefused, brief, require_open


def test_the_decision_is_open_until_counsel_answers():
    """The gate's whole premise. If this ever fails without a reviewed commit resolving DP-K01
    with a named authority, something has quietly asserted a legal position on its own."""
    assert DP_K01.open
    assert DP_K01.resolution is None


@pytest.mark.parametrize("corpus", sorted(GATED))
def test_no_gated_corpus_can_be_ingested(corpus):
    with pytest.raises(CorpusRefused):
        require_open(corpus)


def test_the_refusal_names_the_decision_and_its_owner():
    """An operator hitting this must learn what to do about it, not just that it stopped."""
    with pytest.raises(CorpusRefused) as ex:
        require_open("sap_notes")
    said = str(ex.value)
    assert "DP-K01" in said
    assert DP_K01.owner in said
    # It says what happens instead, so the refusal does not read as an outage.
    assert "metadata" in said


def test_the_gate_has_no_override():
    """A gate with a bypass is not a gate. require_open takes the corpus name and nothing else —
    no force flag, no environment escape hatch, nothing an engineer in a hurry can reach for."""
    import inspect

    from jidoka_knowledge import corpus

    assert list(inspect.signature(require_open).parameters) == ["corpus"]
    src = inspect.getsource(corpus)
    assert "os.environ" not in src and "getenv" not in src


def test_a_tenants_own_metadata_is_not_gated_by_this():
    """K1 is the client's own data under the client's own entitlement, and ADR-0012 is built on
    exactly that distinction. If this ever raises, the gate has grown past its question."""
    require_open("tenant_metadata")
    require_open("engagement_shapes")


def test_an_unknown_corpus_name_does_not_read_as_permission():
    """Passing through is correct for a genuinely ungated corpus, so the risk is the opposite one:
    a typo silently becoming an allowance. Pin that gated names are matched exactly."""
    for typo in ("sap_note", "SAP_NOTES", "sap-notes"):
        assert typo not in GATED
    # And that the real names are still caught, so the exact-match is doing work.
    with pytest.raises(CorpusRefused):
        require_open("sap_notes")


def test_the_brief_asks_counsel_the_same_question_the_code_is_holding_out_for():
    """The document that goes to a lawyer is generated from the record. A brief that drifted from
    the gate would get an answer to the wrong question."""
    doc = brief()
    assert DP_K01.question in doc
    assert DP_K01.if_refused in doc
    for requirement in DP_K01.requires:
        assert requirement in doc
    assert "OPEN — blocking" in doc


def test_the_decision_says_what_happens_if_the_answer_is_no():
    """A decision with no answer for 'no' is a plan with a hope in it."""
    assert DP_K01.if_refused
    assert "not blocked" in DP_K01.if_refused
