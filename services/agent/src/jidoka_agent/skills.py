"""Governed learning: skills load always, but only PROMOTED skills reach the system prompt.

A skill is promoted only when a recorded K5 exam pass exists for it (evals/results/<name>.json).
Loading is not promotion — an unpromoted skill is visible for review and refused injection, which
is what stops the agent teaching itself from an unsigned draft."""
import pathlib
from dataclasses import dataclass

from .exam import ExamResult, grade, load_results, load_scenarios  # re-exported for callers

AGENT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS_DIR = AGENT_ROOT / "skills"
EVALS_DIR = AGENT_ROOT / "evals"
RESULTS_DIR = EVALS_DIR / "results"


@dataclass(frozen=True)
class Skill:
    name: str
    text: str
    promoted: bool
    exam: ExamResult | None  # None = never sat the exam


def _exam_for(name: str, evals_dir: pathlib.Path, results_dir: pathlib.Path) -> ExamResult | None:
    results = results_dir / f"{name}.json"
    if not results.is_file() or not evals_dir.is_dir():
        return None
    return grade(load_scenarios(evals_dir), load_results(results))


def load_skills(skills_dir: pathlib.Path | str = SKILLS_DIR,
                evals_dir: pathlib.Path | str = EVALS_DIR,
                results_dir: pathlib.Path | str = RESULTS_DIR) -> list[Skill]:
    skills_dir, evals_dir, results_dir = map(pathlib.Path, (skills_dir, evals_dir, results_dir))
    out = []
    for md in sorted(skills_dir.glob("*/SKILL.md")):
        exam = _exam_for(md.parent.name, evals_dir, results_dir)
        out.append(Skill(md.parent.name, md.read_text().strip(), bool(exam and exam.passed), exam))
    return out


def promoted_prompt(skills: list[Skill]) -> str:
    """The only path from a skill file into SYSTEM. Unpromoted skills contribute nothing."""
    return "\n\n".join(s.text for s in skills if s.promoted)
