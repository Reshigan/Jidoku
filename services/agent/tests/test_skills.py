"""Governed learning: loading a skill is not promoting it. Only an exam pass injects."""
import json, pytest

from jidoka_agent import skills
from jidoka_agent.skills import EVALS_DIR as EVALS, SKILLS_DIR as REAL_SKILLS


@pytest.fixture
def results_dir(tmp_path):
    d = tmp_path / "results"
    d.mkdir()
    return d


def _ids_for(name):
    """The scenarios that certify one skill. A scenario declares the skill it examines."""
    return [s["id"] for s in skills.load_scenarios(EVALS) if s.get("skill") == name]


def _pass_file(results_dir, name, verdict="pass"):
    (results_dir / f"{name}.json").write_text(json.dumps({i: verdict for i in _ids_for(name)}))


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
    ids = _ids_for("data-migration")
    (results_dir / "data-migration.json").write_text(json.dumps({ids[0]: "pass"}))
    loaded = skills.load_skills(REAL_SKILLS, EVALS, results_dir)
    assert not next(s for s in loaded if s.name == "data-migration").promoted


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


def test_a_skill_is_graded_only_on_the_scenarios_that_certify_it(results_dir):
    """Passing another skill's exam certifies nothing.

    Grading ran against the whole scenario bank, so a cutover result file answering integration
    questions promoted cutover. An exam that examines doctrine the skill does not teach is not a gate.
    """
    others = [s["id"] for s in skills.load_scenarios(EVALS) if s.get("skill") != "cutover"]
    (results_dir / "cutover.json").write_text(json.dumps({i: "pass" for i in others}))
    cutover = next(s for s in skills.load_skills(REAL_SKILLS, EVALS, results_dir) if s.name == "cutover")
    assert not cutover.promoted
    assert cutover.exam.total == len(_ids_for("cutover"))   # only its own questions counted


def test_a_skill_no_scenario_certifies_cannot_promote(results_dir, tmp_path):
    """An untested skill scores a vacuous 100% if nobody notices the bank is empty for it."""
    d = tmp_path / "skills" / "ghost"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("# Ghost\nNo scenario examines this.\n")
    (results_dir / "ghost.json").write_text("{}")
    ghost = skills.load_skills(tmp_path / "skills", EVALS, results_dir)[0]
    assert not ghost.promoted
    assert skills.gate_status([ghost])["skills"][0]["blocked_by"] == "no exam scenario certifies this skill"


def test_every_scenario_examines_a_skill_that_exists_and_teaches_its_rule():
    """The exam bank and the skill library drifted apart once; this is what noticed.

    A scenario naming a skill nobody wrote, or citing a rule that skill does not teach, is an exam
    question with no syllabus behind it — it can only ever be failed for the wrong reason.
    """
    import re
    taught = {}
    for s in skills.load_skills(REAL_SKILLS, EVALS, EVALS / "results"):
        rules = set()
        for a, b in re.findall(r"R-(\d+)\.\.R-(\d+)", s.text):
            rules |= {f"R-{n}" for n in range(int(a), int(b) + 1)}
        rules |= set(re.findall(r"R-\d+", s.text))
        taught[s.name] = rules
    for sc in skills.load_scenarios(EVALS):
        name = sc.get("skill")
        assert name in taught, f"{sc['id']} names unknown skill {name!r}"
        for rule in re.findall(r"R-\d+", sc.get("expected_behaviour", "")):
            assert rule in taught[name], f"{sc['id']} tests {rule}, which {name} does not teach"
