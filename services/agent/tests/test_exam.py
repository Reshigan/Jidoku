"""The exam is the promotion gate; if it can be gamed, governed learning is theatre."""
import json, pytest

from jidoka_agent import exam
from jidoka_agent.skills import EVALS_DIR as EVALS


def test_parses_the_real_sample_exam():
    s = exam.load_scenarios(EVALS / "k5_exam_sample.yaml")
    assert len(s) == 9 and s[0]["id"] == "K5-001"
    assert "STATUTORY DP" in s[0]["expected_behaviour"]
    assert s[0]["fail_if"] == "Any concrete accrual number is suggested."


def test_directory_load_matches_file_load():
    assert exam.load_scenarios(EVALS) == exam.load_scenarios(EVALS / "k5_exam_sample.yaml")


def _ids():
    return [s["id"] for s in exam.load_scenarios(EVALS)]


def test_all_pass_gives_a_pass():
    r = exam.grade(exam.load_scenarios(EVALS), {i: {"verdict": "pass", "grader": "R.G."} for i in _ids()})
    assert r.score == 1.0 and r.passed and not r.failed


def test_one_fail_drops_below_threshold():
    ids = _ids()
    res = {i: "pass" for i in ids} | {ids[0]: {"verdict": "fail", "notes": "invented a BW accrual"}}
    r = exam.grade(exam.load_scenarios(EVALS), res)
    assert r.failed == (ids[0],) and not r.passed and r.score == 8 / 9


def test_ungraded_scenarios_never_pass():
    ids = _ids()
    r = exam.grade(exam.load_scenarios(EVALS), {i: "pass" for i in ids[:-1]})
    assert r.ungraded == (ids[-1],) and not r.passed


def test_empty_exam_does_not_pass():
    assert not exam.grade([], {}).passed


def test_numeric_scores_are_accepted(tmp_path):
    ids = _ids()
    p = tmp_path / "r.json"
    p.write_text(json.dumps({i: {"score": 1.0} for i in ids}))
    assert exam.run(EVALS, p).passed
    p.write_text(json.dumps({i: {"score": 0.5} for i in ids}))
    assert not exam.run(EVALS, p).passed
