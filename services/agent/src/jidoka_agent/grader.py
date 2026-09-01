"""The senior's side of the K5 exam: sit the papers, mark them, sign the verdict.

`exam.py` ingests verdicts and computes a gate. `skills.py` reads that gate and refuses to promote
without it. Neither of them gives a human a way to actually *do* the marking, which is why every
skill in the library has sat at `blocked_by: never sat the K5 exam` since the day it was written.
A gate nobody can open is not governance, it is a locked door with the key thrown away.

This module is the workbench. Three verbs, and the order is the point:

    sit    — put the scenarios to the agent, capture the transcripts, write an unmarked paper.
    mark   — a named senior reads each answer and records pass or fail, with a reason.
    sign   — the marked paper becomes evals/results/<skill>.json, which is what promotes.

Grading stays human because a model marking its own exam is not governance (ADR-0010's argument,
applied to skills instead of claims: the party proposing a belief must not be the party ratifying
it). The autocheck in exam.py can overturn a pass but never grant one, and nothing here changes
that — a senior who marks a paper pass on an answer that claims approval authority still fails it,
because `grade()` applies the autocheck afterwards.

The grader records a signature, not a login. JIDOKA has no notion of a senior's identity beyond a
name they type, and pretending otherwise would be worse than the honest version: the name is on
the paper, in the ledger, and in git history, and that is the accountability on offer.
"""
from __future__ import annotations

import getpass
import json
import pathlib
from datetime import datetime, timezone

from .exam import autocheck, grade, load_results, load_scenarios


class GradingRefused(Exception):
    """The workbench declining. Not a failure — a gate holding."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sit(skill: str, evals_dir, out_path, answer) -> dict:
    """Put every scenario certifying `skill` to the agent and capture what it says.

    `answer` is a callable(scenario) -> transcript. Injected rather than imported so a sitting can
    be run against a live agent, a recorded one, or a fixture without this module knowing which —
    and so the exam is model-agnostic, which services/agent/CLAUDE.md requires.

    The paper comes out unmarked. There is deliberately no mode where sitting also grades: a
    transcript that arrives pre-marked has been marked by the thing that wrote it.
    """
    scenarios = [s for s in load_scenarios(evals_dir) if s.get("skill") == skill]
    if not scenarios:
        raise GradingRefused(
            f"No exam scenario certifies {skill!r}. A skill with no scenarios cannot be examined, "
            f"and must not promote on a vacuous pass — write scenarios into evals/ first, drawn "
            f"from real engagement failures.")

    paper = {"skill": skill, "sat_at": _now(), "answers": {}}
    for s in scenarios:
        transcript = answer(s)
        auto = autocheck(s, transcript)
        paper["answers"][s["id"]] = {
            "scenario": s.get("scenario", ""),
            "expected_behaviour": s.get("expected_behaviour", ""),
            "fail_if": s.get("fail_if", ""),
            "transcript": transcript,
            # Surfaced to the marker as a flag, never as a verdict. A clean autocheck means the
            # answer is eligible for human attention, nothing more.
            "autocheck": auto,
            "verdict": None,
            "grader": None,
            "notes": "",
        }
    pathlib.Path(out_path).write_text(json.dumps(paper, indent=2) + "\n")
    return paper


def load_paper(path) -> dict:
    p = pathlib.Path(path)
    if not p.is_file():
        raise GradingRefused(f"No paper at {p}. Sit the exam before marking it.")
    return json.loads(p.read_text())


def mark(paper: dict, scenario_id: str, verdict: str, grader: str, notes: str = "") -> dict:
    """Record one verdict against one answer.

    A fail with no note is refused. "Why" is the entire value of a human grader — a bare fail
    teaches the skill's author nothing, and the next person to sit the exam repeats it.
    """
    if scenario_id not in paper["answers"]:
        raise GradingRefused(f"{scenario_id} is not on this paper.")
    if verdict not in ("pass", "fail"):
        raise GradingRefused(f"Verdict must be 'pass' or 'fail', not {verdict!r}.")
    if not grader.strip():
        raise GradingRefused("A verdict needs a named grader. Anonymous marking is not marking.")
    if verdict == "fail" and not notes.strip():
        raise GradingRefused(
            f"{scenario_id}: a fail needs a reason. The note is what the skill's author acts on.")

    answer = paper["answers"][scenario_id]
    answer.update(verdict=verdict, grader=grader.strip(), notes=notes.strip(), marked_at=_now())
    return paper


def unmarked(paper: dict) -> list[str]:
    return [i for i, a in paper["answers"].items() if a.get("verdict") is None]


def sign(paper: dict, results_dir) -> pathlib.Path:
    """Write the marked paper as the results file `skills.py` reads.

    Refuses a partial paper. An unmarked scenario already counts as a failure in `grade()`, so
    signing an incomplete paper would not promote anything — but it would put a file on disk that
    looks like a completed sitting, and a misleading artefact is worse than a missing one.
    """
    left = unmarked(paper)
    if left:
        raise GradingRefused(
            f"{len(left)} scenario(s) still unmarked: {', '.join(sorted(left))}. "
            f"An unmarked paper does not promote a skill.")

    graders = {a["grader"] for a in paper["answers"].values()}
    results_dir = pathlib.Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    out = results_dir / f"{paper['skill']}.json"
    out.write_text(json.dumps(
        {i: {"verdict": a["verdict"], "grader": a["grader"], "notes": a["notes"],
             "transcript": a["transcript"], "marked_at": a.get("marked_at")}
         for i, a in paper["answers"].items()}, indent=2) + "\n")
    paper["signed_at"] = _now()
    paper["signed_by"] = sorted(graders)
    return out


def verdict_of(skill: str, evals_dir, results_dir):
    """What the gate says about this skill right now, after the autocheck has had its say."""
    results_path = pathlib.Path(results_dir) / f"{skill}.json"
    if not results_path.is_file():
        return None
    mine = [s for s in load_scenarios(evals_dir) if s.get("skill") == skill]
    return grade(mine, load_results(results_path))


# --- the terminal workbench ---------------------------------------------------------------------

def _render(answer: dict, scenario_id: str, n: int, total: int) -> str:
    lines = [
        "", "=" * 78,
        f"  {scenario_id}   ({n} of {total})",
        "=" * 78, "",
        "SCENARIO", "  " + answer["scenario"], "",
        "EXPECTED", "  " + answer["expected_behaviour"], "",
    ]
    if answer.get("fail_if"):
        lines += ["FAIL IF", "  " + answer["fail_if"], ""]
    if answer.get("autocheck"):
        # Named as a flag for the marker's attention. It does not decide the verdict here, but it
        # will overturn a pass in grade(), so a marker should know before typing one.
        lines += ["AUTOCHECK FLAGGED THIS ANSWER", "  " + answer["autocheck"],
                  "  (a pass here will be overturned by the gate)", ""]
    lines += ["-" * 78, "THE AGENT'S ANSWER", "-" * 78, "",
              answer["transcript"].strip() or "  (empty)", ""]
    return "\n".join(lines)


def review(paper: dict, grader: str, ask=input, show=print) -> dict:
    """Walk a senior through the unmarked answers on a paper.

    `ask` and `show` are injected so this is testable without a terminal, which matters: the thing
    standing between an unpromoted library and a promoted one should itself be under test.
    """
    todo = unmarked(paper)
    if not todo:
        show("Every answer on this paper is marked.")
        return paper

    for n, sid in enumerate(todo, 1):
        answer = paper["answers"][sid]
        show(_render(answer, sid, n, len(todo)))
        while True:
            got = ask("  pass / fail / skip > ").strip().lower()
            if got in ("s", "skip"):
                break
            if got in ("p", "pass", "f", "fail"):
                verdict = "pass" if got.startswith("p") else "fail"
                notes = ask("  why (required on a fail) > ").strip()
                try:
                    mark(paper, sid, verdict, grader, notes)
                except GradingRefused as ex:
                    show(f"  {ex}")
                    continue
                break
            show("  Answer pass, fail, or skip.")
    return paper


def main(argv=None) -> int:
    """`python -m jidoka_agent.grader <sit|mark|status> ...`"""
    import argparse

    from .skills import EVALS_DIR, RESULTS_DIR, SKILLS_DIR, gate_status, load_skills

    p = argparse.ArgumentParser(prog="jidoka-grade", description=__doc__.split("\n")[0])
    p.add_argument("--evals", default=str(EVALS_DIR))
    p.add_argument("--results", default=str(RESULTS_DIR))
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sit", help="put the scenarios to the agent and write an unmarked paper")
    s.add_argument("skill")
    s.add_argument("--paper", default="", help="where to write the paper")

    m = sub.add_parser("mark", help="mark a paper as a named senior, then sign it")
    m.add_argument("paper")
    m.add_argument("--grader", default="", help="your name; goes on every verdict")

    sub.add_parser("status", help="what the promotion gate is withholding, and why")

    a = p.parse_args(argv)
    evals, results = pathlib.Path(a.evals), pathlib.Path(a.results)

    if a.cmd == "status":
        st = gate_status(load_skills(SKILLS_DIR, evals, results))
        for row in st["skills"]:
            mark_ = "promoted" if row["promoted"] else f"withheld — {row['blocked_by']}"
            score = f"{row['score']:.0%}" if row["score"] is not None else "  — "
            print(f"  {row['name']:<24} {score:>5}   {mark_}")
        print(f"\n  {len(st['promoted'])} promoted, {len(st['withheld'])} withheld.")
        if st["withheld"]:
            print("  Nothing withheld reaches the agent's system prompt. That is the gate working.")
        return 0

    if a.cmd == "sit":
        # Sitting needs a live agent, and wiring one here would make this module depend on a
        # model. It takes the answer function instead; the CLI's job is to say so clearly rather
        # than to invent a default that quietly examines the wrong thing.
        print(f"Sitting {a.skill!r} needs an answer function bound to a running agent.\n"
              f"  from jidoka_agent.grader import sit\n"
              f"  sit({a.skill!r}, {str(evals)!r}, 'paper.json', answer=my_agent_answer)\n"
              f"An exam sat by anything other than the agent being certified proves nothing.")
        return 2

    paper = load_paper(a.paper)
    grader = a.grader.strip() or getpass.getuser()
    print(f"Marking {paper['skill']!r} as {grader!r}. Your name goes on every verdict.")
    review(paper, grader)
    left = unmarked(paper)
    pathlib.Path(a.paper).write_text(json.dumps(paper, indent=2) + "\n")
    if left:
        print(f"\n{len(left)} left unmarked — paper saved, not signed. Nothing promotes yet.")
        return 1
    out = sign(paper, results)
    res = verdict_of(paper["skill"], evals, results)
    print(f"\nSigned to {out}.")
    print(f"  {res.scored}/{res.total} — {'PROMOTES' if res.passed else 'does not promote'}.")
    if res.autofailed:
        print(f"  Autocheck overturned: {', '.join(res.autofailed)}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
