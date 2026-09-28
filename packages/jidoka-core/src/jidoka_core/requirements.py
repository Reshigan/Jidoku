"""What the client asked for, what controls it, and whether anything was configured for it.

A programme has a specification and it has a configuration, and on every engagement anybody has
worked on, nobody can answer the one question that joins them: *which requirements does this
configuration actually satisfy?* The specification lives in a Word document, the configuration in a
system, and the bridge between them is somebody's memory of a workshop in week three.

This is the bridge, and it is deliberately narrow. Three facts per requirement — the object it names,
the control that assures it, the evidence that control demands — and one derived answer:

  **CONFIGURED** — signed intent describes an object this requirement names.
  **NOT_CONFIGURED** — it names one and no signed record describes it.
  **NOT_TRACEABLE** — the requirement names no object at all, so the platform has nothing to look
  for. Reported as its own state and never counted as either of the others, because a specification
  full of untraceable requirements that reported 100% coverage would be the most convincing wrong
  number this platform could produce.

`Fit` is the design authority's word, kept and never derived: STD where standard content satisfies
the requirement, CFG where configuration does, GAP where neither does. A platform that recomputed
somebody's fit assessment would be overruling the design authority with a string match.

Pure stdlib, pure over its inputs.
"""
from dataclasses import dataclass, field

CONFIGURED = "CONFIGURED"
NOT_CONFIGURED = "NOT_CONFIGURED"
NOT_TRACEABLE = "NOT_TRACEABLE"

#: The fit assessments a design authority writes. Anything else is kept verbatim and reported as
#: unrecognised rather than mapped onto one of these — a pack may have its own vocabulary and
#: guessing at it would put a requirement in a bucket its author did not choose.
FITS = ("STD", "CFG", "GAP")


class RequirementError(Exception): ...


@dataclass(frozen=True)
class Requirement:
    """One line of a specification, as its author wrote it."""
    req_id: str
    requirement: str
    #: Why it exists. J-SOX asks for this and a requirement without one cannot be challenged.
    rationale: str = ""
    countries: str = ""
    wave: str = ""
    fit: str = ""
    #: The control objective that assures it, by id. Empty where the specification names none.
    control: str = ""
    #: The configuration objects that satisfy it. Declared by whoever absorbed or mapped the
    #: specification — never inferred from the requirement's words, which is how a platform ends up
    #: reporting a requirement as met because a sentence happened to contain an object's name.
    objects: tuple = ()

    def __post_init__(self):
        if not self.req_id.strip():
            raise RequirementError("A requirement with no identifier cannot be traced to anything.")
        if not self.requirement.strip():
            raise RequirementError(f"{self.req_id}: a requirement states what the solution must do.")


@dataclass(frozen=True)
class Control:
    """A control objective: what it assures, who owns it, how often, and what it leaves behind."""
    control_id: str
    objective: str
    owner: str = ""
    frequency: str = ""
    evidence: str = ""

    def __post_init__(self):
        if not self.owner.strip():
            raise RequirementError(
                f"{self.control_id}: a control objective names its owner. A control everybody owns "
                f"is a control nobody runs, and an auditor asks for the name first.")
        if not self.evidence.strip():
            raise RequirementError(
                f"{self.control_id}: a control objective names the evidence it produces. Without "
                f"one there is nothing to show an auditor and nothing for the platform to look for.")


@dataclass
class Specification:
    requirements: list = field(default_factory=list)
    controls: list = field(default_factory=list)


def _objects_in(records: list) -> set[str]:
    """Every object signed intent describes, by object name and by external code.

    Both, because a specification names an object type ("PicklistOption") where a design workbook
    names an instance ("MIBCO_FLAG"), and a requirement traced to either is traced.
    """
    out = set()
    for rec in records:
        get = rec.get if isinstance(rec, dict) else (lambda k, d=None: getattr(rec, k, d))
        for key in ("object", "external_code"):
            if value := get(key, ""):
                out.add(str(value))
    return out


def coverage(spec: Specification, records: list) -> list[dict]:
    """Each requirement against signed intent, and the control that assures it."""
    have = _objects_in(records)
    controls = {c.control_id: c for c in spec.controls}
    out = []
    for r in spec.requirements:
        found = sorted(o for o in r.objects if o in have)
        missing = sorted(o for o in r.objects if o not in have)
        state = (NOT_TRACEABLE if not r.objects
                 else CONFIGURED if not missing else NOT_CONFIGURED)
        control = controls.get(r.control)
        out.append({
            "req_id": r.req_id, "requirement": r.requirement, "rationale": r.rationale,
            "countries": r.countries, "wave": r.wave, "fit": r.fit,
            "fit_recognised": r.fit in FITS,
            "control": r.control,
            "control_named_but_absent": bool(r.control and control is None),
            "control_owner": control.owner if control else "",
            "control_evidence": control.evidence if control else "",
            "objects": list(r.objects), "configured": found, "not_configured": missing,
            "state": state,
            "says": (f"{r.req_id}: names no configuration object, so the platform cannot tell "
                     f"whether it is met. Somebody has to say which objects satisfy it."
                     if state == NOT_TRACEABLE
                     else f"{r.req_id}: signed intent describes {', '.join(found)}."
                     if state == CONFIGURED
                     else f"{r.req_id}: no signed record describes {', '.join(missing)}."),
        })
    return out


def uncontrolled(spec: Specification) -> list[dict]:
    """Requirements naming a control the specification never defines, and controls nothing cites.

    Both directions, because both are the same defect seen from opposite ends: a requirement whose
    control does not exist is unassured, and a control nothing cites is an assurance nobody asked
    for — and an auditor will ask about the second as readily as the first.
    """
    defined = {c.control_id for c in spec.controls}
    cited = {r.control for r in spec.requirements if r.control}
    return ([{"kind": "control_not_defined", "id": c,
              "says": f"requirements cite {c}, which this specification does not define. The "
                      f"requirements it assures are unassured until it does."}
             for c in sorted(cited - defined)]
            + [{"kind": "control_not_cited", "id": c.control_id,
                "says": f"{c.control_id} is defined and no requirement cites it. Either a "
                        f"requirement is missing its reference or the control assures nothing."}
               for c in spec.controls if c.control_id not in cited])


def account(spec: Specification, records: list) -> dict:
    """The specification against the configuration. No percentage, for the usual reason."""
    rows = coverage(spec, records)
    by_state = {s: [r["req_id"] for r in rows if r["state"] == s]
                for s in (CONFIGURED, NOT_CONFIGURED, NOT_TRACEABLE)}
    gaps = [r["req_id"] for r in rows if r["fit"] == "GAP"]
    unknown_fit = [r["req_id"] for r in rows if r["fit"] and not r["fit_recognised"]]
    return {
        "requirements": rows,
        "controls": [{"control_id": c.control_id, "objective": c.objective, "owner": c.owner,
                      "frequency": c.frequency, "evidence": c.evidence} for c in spec.controls],
        "uncontrolled": uncontrolled(spec),
        "configured": len(by_state[CONFIGURED]),
        "not_configured": by_state[NOT_CONFIGURED],
        "not_traceable": by_state[NOT_TRACEABLE],
        "declared_gaps": gaps,
        "unrecognised_fit": unknown_fit,
        "says": _says(rows, by_state, gaps),
        "method": ("Each requirement against the objects somebody declared satisfy it, checked "
                   "against signed intent. A requirement naming no object is NOT_TRACEABLE and is "
                   "never counted as covered: a specification of untraceable requirements would "
                   "otherwise report itself as fully met. Fit is the design authority's word, kept "
                   "and never recomputed. No percentage is published."),
    }


def _says(rows, by_state, gaps) -> str:
    n = len(rows)
    if not n:
        return "No specification has been absorbed for this engagement."
    parts = [f"{len(by_state[CONFIGURED])} of {n} requirements are described by signed intent"]
    if by_state[NOT_TRACEABLE]:
        parts.append(f"{len(by_state[NOT_TRACEABLE])} name no configuration object at all, so the "
                     f"platform cannot say whether they are met")
    if by_state[NOT_CONFIGURED]:
        parts.append(f"{len(by_state[NOT_CONFIGURED])} name objects no signed record describes")
    if gaps:
        parts.append(f"{len(gaps)} are declared GAP by the design authority: "
                     + ", ".join(gaps[:6]) + ("…" if len(gaps) > 6 else ""))
    return ". ".join(parts) + "."
