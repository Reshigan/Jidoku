"""Measuring the design pass against configuration that was actually built.

The K5 exam in `exam.py` is human-graded on purpose: a model marking its own answers is not
governance. This is a different kind of measurement and it is allowed to be automatic, because it
does not ask the model's opinion of itself — it compares what the pass authored against **the
configuration real consultants really built** from the same documents. There is a right answer, it
was written by people, and it is not ours to adjudicate.

The method is to take something away. A pack carries both the design documents *and* the workbooks
that were compiled from them; hide the workbooks, give the pass only the prose and the requirements,
and see whether it arrives at the same objects. On the Komatsu pack that is 159 picklist options
derived from a Solution Design Document and a Business Requirements Specification — a real exam with
a real marking scheme, taken from work that shipped.

Three results, and the third is the one that matters:

  **matched** — the pass authored a record the consultants built. Field-level agreement is reported
  separately, because the right object with the wrong value is not a pass.

  **missed** — the consultants built it and the pass did not. Unambiguously a gap.

  **extra** — the pass authored something the consultants did not build. **Not counted as wrong.**
  Sometimes it is a hallucination and sometimes it is the thing the project forgot; a benchmark that
  scored these as errors would train the pass to author less, which is the opposite of what is
  wanted. They go to a person.

No single score is published. A percentage over a benchmark whose `extra` column needs human reading
would be quoted as accuracy, and the first thing anybody would do is optimise it.
"""
from dataclasses import dataclass, field

#: Registers a case can withhold from the pack before the pass reads it. Each one is a real
#: experiment: hide `records` and the pass must derive the objects from prose, hide `specification`
#: and it must work from the design documents alone.
WITHHOLDABLE = ("records", "specification", "documents", "contracts", "interlocks", "scope",
                "ordering", "rules", "decision_points")


class BenchError(Exception): ...


@dataclass(frozen=True)
class Case:
    """One exam paper: what the pass is told, what it is not shown, and what it should reach."""
    case_id: str
    brief: str
    #: Registers removed from the pack. Withholding nothing measures nothing — the answer would be
    #: sitting in the input — so a case that hides nothing is a declaration error.
    hide: tuple = ()
    #: The records the consultants actually built, keyed as `key_of` keys them.
    expected: tuple = ()
    #: Fields whose value is compared where a record matches. Empty compares nothing and reports it.
    compare: tuple = ()

    def __post_init__(self):
        if not self.hide:
            raise BenchError(
                f"{self.case_id}: a case that withholds nothing measures nothing — the answer is "
                f"in the input. Name the register the pass has to do without.")
        for register in self.hide:
            if register not in WITHHOLDABLE:
                raise BenchError(f"{self.case_id}: {register!r} is not a register of a pack.")
        if not self.expected:
            raise BenchError(f"{self.case_id}: there is no exam without a right answer.")


def key_of(record: dict) -> str:
    """How a record is identified for comparison: object plus its external code where it has one.

    Not `jidoka_core.record_key`, which includes the system binding — two runs against different
    tenants would then never match, and the question here is about the design, not the target.
    """
    code = record.get("external_code") or record.get("intent", {}).get("externalCode", "")
    return f"{record.get('object', '?')}/{code}" if code else str(record.get("object", "?"))


def withhold(pack: dict, hide: tuple) -> dict:
    """The pack as the pass will see it. A shallow copy: nothing here mutates the real bundle."""
    out = dict(pack)
    for register in hide:
        out.pop(register, None)
    return out


def score(case: Case, authored: list) -> dict:
    """One paper, marked. `authored` is the accepted records of a design pass."""
    want = {key_of(r): r for r in case.expected}
    got = {key_of(r): r for r in authored}

    matched = sorted(set(want) & set(got))
    missed = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))

    disagreements = []
    agreed = 0
    compared = 0
    for k in matched:
        for f in case.compare:
            compared += 1
            theirs = want[k].get("intent", {}).get(f, want[k].get(f))
            ours = got[k].get("intent", {}).get(f, got[k].get(f))
            if theirs == ours:
                agreed += 1
            else:
                disagreements.append({"key": k, "field": f, "built": theirs, "authored": ours})

    return {
        "case_id": case.case_id,
        "withheld": list(case.hide),
        "matched": matched, "missed": missed, "extra": extra,
        "fields_compared": compared, "fields_agreed": agreed,
        "disagreements": disagreements,
        "says": _says(case, matched, missed, extra, compared, agreed),
        "method": ("The pass was given the pack with " + ", ".join(case.hide) + " withheld, and its "
                   "output compared against configuration people really built from the same "
                   "documents. `extra` is not counted as wrong: sometimes it is invention and "
                   "sometimes it is what the project forgot, and a benchmark that scored it as an "
                   "error would train the pass to author less. No single score is published."),
    }


def _says(case, matched, missed, extra, compared, agreed) -> str:
    parts = [f"{len(matched)} of {len(case.expected)} objects the consultants built were authored "
             f"from the documents alone"]
    if compared:
        parts.append(f"{agreed} of {compared} compared field values agree")
    elif matched:
        parts.append("no fields were compared, so this says nothing about the values")
    if missed:
        parts.append(f"{len(missed)} were missed: " + ", ".join(missed[:8])
                     + ("…" if len(missed) > 8 else ""))
    if extra:
        parts.append(f"{len(extra)} were authored that nobody built — read them, they are either "
                     f"invention or something the project forgot: " + ", ".join(extra[:8])
                     + ("…" if len(extra) > 8 else ""))
    return ". ".join(parts) + "."


def ground_truth(pack: dict, object_name: str = "") -> tuple:
    """The pack's own compiled records, as the right answer. Optionally one object type.

    This is what makes the benchmark honest and also what limits it: the right answer is whatever a
    real project compiled, defects included. A record the consultants got wrong is scored as the
    target, and the only defence against that is reading the disagreements.
    """
    records = pack.get("records", [])
    if object_name:
        records = [r for r in records if r.get("object") == object_name]
    return tuple(records)


@dataclass
class Bench:
    """A set of papers and their results. Nothing here runs a pass — the caller does, because a
    benchmark that owns the API call is a benchmark nobody can run against a recorded transcript."""
    cases: list = field(default_factory=list)
    results: list = field(default_factory=list)

    def mark(self, case: Case, authored: list) -> dict:
        got = score(case, authored)
        self.results.append(got)
        return got

    def report(self) -> dict:
        if not self.results:
            return {"cases": 0, "says": "No papers have been marked."}
        return {
            "cases": len(self.results),
            "results": self.results,
            "matched": sum(len(r["matched"]) for r in self.results),
            "missed": sum(len(r["missed"]) for r in self.results),
            "extra": sum(len(r["extra"]) for r in self.results),
            "fields_agreed": sum(r["fields_agreed"] for r in self.results),
            "fields_compared": sum(r["fields_compared"] for r in self.results),
            # Two kinds of thing a person has to read, discriminated rather than flattened: a value
            # the pass and the project disagree on, and an object the pass authored that nobody
            # built. Both need judgement; they need different judgement.
            "needs_a_person": [{"kind": "disagreement", **d}
                               for r in self.results for d in r["disagreements"]]
                              + [{"kind": "authored_but_never_built", "key": k,
                                  "case_id": r["case_id"]}
                                 for r in self.results for k in r["extra"]],
            "says": "; ".join(r["says"] for r in self.results),
        }
