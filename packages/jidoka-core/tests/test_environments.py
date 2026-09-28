"""Two environments, compared, with neither one treated as the truth."""
from jidoka_core.environments import compare, roll_up

QA, PROD = "KOM-SF-QA", "KOM-SF-PROD"


def rows(*pairs):
    return [{"externalCode": k, **v} for k, v in pairs]


def test_the_comparison_has_no_baseline():
    """Reusing the adapters' directional diff would make one environment the baseline and the
    other a set of additions and deletions from it, which reads as a verdict nobody gave."""
    out = compare(rows(("A", {})), rows(("B", {})), "externalCode", QA, PROD)
    assert out["only_in_left"] == [{"key": "A"}] and out["only_in_right"] == [{"key": "B"}]
    assert "added" not in out and "removed" not in out
    assert f"1 only in {QA}" in out["says"] and f"1 only in {PROD}" in out["says"]


def test_two_environments_that_agree_say_so_plainly():
    same = rows(("A", {"v": "1"}), ("B", {"v": "2"}))
    out = compare(same, [dict(r) for r in same], "externalCode", QA, PROD)
    assert out["aligned"] is True and out["same"] == ["A", "B"]
    assert "field for field" in out["says"]


def test_a_difference_is_weighed_against_signed_intent_where_there_is_any():
    """"These two rows are not equal" is a far less useful sentence than "this one matches what
    was signed and that one does not"."""
    out = compare(rows(("A", {"v": "1"})), rows(("A", {"v": "9"})), "externalCode", QA, PROD,
                  intent={"A": {"v": "1"}})
    row = out["differs"][0]
    assert row["signed"] is True and row["matches"] == [QA]
    assert f"matches signed intent in {QA} and does not in {PROD}" in row["says"]


def test_neither_side_matching_the_design_is_its_own_finding():
    out = compare(rows(("A", {"v": "2"})), rows(("A", {"v": "9"})), "externalCode", QA, PROD,
                  intent={"A": {"v": "1"}})
    assert out["differs"][0]["matches"] == []
    assert "matches signed intent in neither" in out["differs"][0]["says"]


def test_an_object_nobody_designed_is_still_reported():
    """An undesigned object present in PROD and absent in DEV is exactly the thing somebody wants
    to find before a cutover."""
    out = compare(rows(("X", {"v": "1"})), rows(("X", {"v": "2"})), "externalCode", QA, PROD)
    row = out["differs"][0]
    assert row["signed"] is False
    assert "neither side is wrong by the design, and neither is right" in row["says"]


def test_tenant_generated_metadata_is_not_a_difference():
    """Comparing it would report every object as differing, on fields the tenant writes itself."""
    out = compare(rows(("A", {"v": "1", "lastModifiedDateTime": "t1", "lastModifiedBy": "x"})),
                  rows(("A", {"v": "1", "lastModifiedDateTime": "t2", "lastModifiedBy": "y"})),
                  "externalCode", QA, PROD)
    assert out["aligned"] is True


def test_a_row_with_no_key_is_not_compared_rather_than_compared_wrongly():
    out = compare([{"v": "1"}], rows(("A", {"v": "1"})), "externalCode", QA, PROD)
    assert out["only_in_right"] == [{"key": "A"}] and out["only_in_left"] == []


def test_the_roll_up_says_it_is_a_reading_and_not_a_verdict():
    out = roll_up([compare(rows(("A", {"v": "1"})), rows(("A", {"v": "2"})), "externalCode",
                           QA, PROD)])
    assert out["aligned"] is False and out["apart"] == 1
    assert "not a verdict on either" in out["says"]


def test_a_roll_up_over_nothing_does_not_claim_alignment_it_did_not_check():
    assert "no entity is readable in both systems" in roll_up([])["says"]
