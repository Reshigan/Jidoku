"""K5 exam runner: YAML scenarios in, human-graded verdicts in, a pass-gate out.

The exam is human-graded by named seniors — this module does not score behaviour itself, it
ingests verdicts and computes the gate skills.py uses to promote. Grading stays human because
a model marking its own exam is not governance."""
import json, pathlib
from dataclasses import dataclass

PASS_THRESHOLD = 0.9      # a K5 exam is near-perfect or it is not a K5 exam
PASS_VERDICTS = {"pass", "PASS", True}


def _parse_scenarios(text: str) -> list[dict]:
    """Parse the evals/*.yaml subset: a flat list of one-level `key: "value"` mappings.

    ponytail: deliberate 20-line parser over a pyyaml dep — the exam files are a fixed shape
    and jidoka keeps deps honest. If evals ever need nesting or anchors, add pyyaml here."""
    items: list[dict] = []
    for raw in text.splitlines():
        line = raw.split(" #")[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        stripped = line.lstrip("- ").strip() if line.lstrip().startswith("- ") else line.strip()
        if line.lstrip().startswith("- "):
            items.append({})
        if not items or ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        val = val.strip()
        if val[:1] in ('"', "'") and val[-1:] == val[:1]:
            val = val[1:-1]
        items[-1][key.strip()] = val
    return [i for i in items if i]


def load_scenarios(path: str | pathlib.Path) -> list[dict]:
    """Load one exam file, or every evals/*.yaml if given a directory."""
    p = pathlib.Path(path)
    files = sorted(p.glob("*.yaml")) if p.is_dir() else [p]
    return [s for f in files for s in _parse_scenarios(f.read_text())]


def load_results(path: str | pathlib.Path) -> dict[str, dict]:
    """Human rubric ingestion: {scenario_id: {verdict|score, grader, notes}} as JSON."""
    return json.loads(pathlib.Path(path).read_text())


@dataclass(frozen=True)
class ExamResult:
    scored: int
    total: int
    ungraded: tuple[str, ...]
    failed: tuple[str, ...]

    @property
    def score(self) -> float:
        return self.scored / self.total if self.total else 0.0

    @property
    def passed(self) -> bool:
        # Ungraded scenarios are failures, not absences: an unmarked paper does not promote a skill.
        return bool(self.total) and not self.ungraded and self.score >= PASS_THRESHOLD


def _is_pass(entry: dict | str | bool) -> bool:
    if isinstance(entry, (str, bool)):
        return entry in PASS_VERDICTS
    if "verdict" in entry:
        return entry["verdict"] in PASS_VERDICTS
    return float(entry.get("score", 0)) >= 1.0


def grade(scenarios: list[dict], results: dict) -> ExamResult:
    ids = [s["id"] for s in scenarios]
    ungraded = tuple(i for i in ids if i not in results)
    failed = tuple(i for i in ids if i in results and not _is_pass(results[i]))
    return ExamResult(len(ids) - len(ungraded) - len(failed), len(ids), ungraded, failed)


def run(evals_dir: str | pathlib.Path, results_path: str | pathlib.Path) -> ExamResult:
    return grade(load_scenarios(evals_dir), load_results(results_path))
