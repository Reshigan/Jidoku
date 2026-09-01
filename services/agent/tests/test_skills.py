"""Governed learning: loading a skill is not promoting it. Only an exam pass injects."""
import json, pytest

from jidoka_agent import skills
from jidoka_agent.skills import EVALS_DIR as EVALS, SKILLS_DIR as REAL_SKILLS


@pytest.fixture
def results_dir(tmp_path):
    d = tmp_path / "results"
    d.mkdir()
    return d


def _pass_file(results_dir, name, verdict="pass"):
    ids = [s["id"] for s in skills.load_scenarios(EVALS)]
    (results_dir / f"{name}.json").write_text(json.dumps({i: verdict for i in ids}))


def test_repo_skills_are_unpromoted_without_a_recorded_exam(results_dir):
    loaded = skills.load_skills(REAL_SKILLS, EVALS, results_dir)
    assert len(loaded) == 5
    assert all(not s.promoted and s.exam is None for s in loaded)
    assert skills.promoted_prompt(loaded) == ""   # nothing reaches SYSTEM


def test_exam_pass_promotes_and_injects(results_dir):
    _pass_file(results_dir, "sf-sequencing")
    loaded = skills.load_skills(REAL_SKILLS, EVALS, results_dir)
    promoted = [s for s in loaded if s.promoted]
    assert [s.name for s in promoted] == ["sf-sequencing"]
    prompt = skills.promoted_prompt(loaded)
    assert "SuccessFactors build sequencing" in prompt
    assert "Cutover discipline" not in prompt   # unpromoted stays out


def test_exam_fail_loads_but_never_injects(results_dir):
    _pass_file(results_dir, "cutover", verdict="fail")
    loaded = skills.load_skills(REAL_SKILLS, EVALS, results_dir)
    cutover = next(s for s in loaded if s.name == "cutover")
    assert cutover.text and cutover.exam is not None   # loaded and reviewable
    assert not cutover.promoted and not cutover.exam.passed
    assert "Cutover discipline" not in skills.promoted_prompt(loaded)


def test_partial_grading_does_not_promote(results_dir):
    ids = [s["id"] for s in skills.load_scenarios(EVALS)]
    (results_dir / "integration.json").write_text(json.dumps({ids[0]: "pass"}))
    loaded = skills.load_skills(REAL_SKILLS, EVALS, results_dir)
    assert not next(s for s in loaded if s.name == "integration").promoted


def test_consultant_system_prompt_uses_the_gate():
    from jidoka_agent import consultant
    p = consultant.system_prompt()
    assert p.startswith("You are JIDOKA's K5 senior SAP consultant")
    # no results recorded in-repo yet -> nothing is injected
    assert p == consultant.SYSTEM


def test_gate_status_names_what_is_withheld_and_why():
    """An empty promoted_prompt must be legible as a gate, not mistaken for an empty library."""
    from jidoka_agent.skills import gate_status, load_skills
    status = gate_status(load_skills())
    assert status["skills"], "the skill library should not be empty"
    # Nothing is promoted without a recorded exam pass, and every withholding states its reason.
    for s in status["skills"]:
        assert s["promoted"] or s["blocked_by"]
    assert set(status["promoted"]) | set(status["withheld"]) == {s["name"] for s in status["skills"]}
