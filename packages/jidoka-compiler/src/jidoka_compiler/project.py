"""Documents projected from signed state, not authored beside it.

The compiler's other half. `compile_csv` turns a signed workbook into IR; this turns IR, decisions
and the ledger back into the documents a client, a partner and an auditor each ask for.

The direction matters. Everywhere else in this industry the document is written first and the
system drifts away from it — the blueprint describes what someone intended in March, the system
does what someone configured in July, and nobody can tell you which is authoritative without a
week of reconciliation. A document that *can* disagree with the system eventually does.

So nothing here is authored. Every sentence is a projection of state that is already true and
already signed, and regenerating is how you read the system rather than a report you run
afterwards. Three consequences follow, and they are the whole design:

  1. Nothing is invented. If IR does not say it, the document says it is not decided — never a
     plausible sentence in the gap. A generated document that guesses is worse than no document,
     because it reads with the same authority as the parts that are true.
  2. Provenance travels. Every configured value carries the workbook and cell it came from and the
     signature that made it loadable. An auditor's question is "says who", and the answer is on the
     same line as the value.
  3. Gaps are content. Open decision points are not omissions to be tidied away before sending;
     they are the most useful page in the pack. A design document with no open questions three
     weeks into a project is not finished, it is unexamined.

The three documents share one projection layer because they share one truth. A config book and a
solution design that disagree are two lies, and generating them from separate code is how that
happens.
"""
from __future__ import annotations

from collections import defaultdict

#: Documents that can be projected. Keyed by the name an API path asks for.
DOCUMENTS = {
    "config-rationale": "Configuration Rationale — every configured value, and who signed for it.",
    "solution-design": "Solution Design — scope, landscape, and object-by-object design.",
    "decision-register": "Decision Register — every decision point, its owner and its resolution.",
    "verification-report": "Verification Report — signed intent checked against live state, "
                           "with every unexplained difference and who must answer for it.",
}


class ProjectionError(Exception):
    """Asked for a document that does not exist. Not a gap in an engagement — a wrong name."""


# --- reading the state ---------------------------------------------------------------------------

def _records(engagement) -> list:
    return list(getattr(engagement, "ir", []) or [])


def _as_dict(record) -> dict:
    """IR arrives as an IRRecord or as the dict it was loaded from. Both are real: the API holds
    dataclasses, the repository holds rows."""
    if isinstance(record, dict):
        return record
    return {f: getattr(record, f, None) for f in
            ("object", "product", "system_binding", "intent", "tier", "source", "country",
             "depends_on", "external_code")}


def _code(rec: dict) -> str:
    return rec.get("external_code") or (rec.get("intent") or {}).get("externalCode") or "—"


def _open_dps(engagement) -> dict:
    return dict(getattr(engagement, "open_dps", {}) or {})


def _decisions(engagement):
    engine = getattr(engagement, "decisions", None)
    return list(getattr(engine, "dps", {}).values()) if engine else []


def _ledger_entries(engagement) -> list[dict]:
    ledger = getattr(engagement, "ledger", None)
    return list(getattr(ledger, "entries", []) or [])


def _approvals(engagement) -> dict[str, list[dict]]:
    """task -> the approvals recorded against it. The ledger is the only place an approval exists;
    an IR record cannot claim its own sign-off."""
    out = defaultdict(list)
    for e in _ledger_entries(engagement):
        if e.get("action") == "APPROVED":
            out[e.get("task")].append(e)
    return dict(out)


# --- rendering helpers ---------------------------------------------------------------------------

def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    return (["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
            + ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows])


def _provenance(rec: dict) -> str:
    """Where a value came from, in one cell. Unsigned IR cannot be loaded at all (invariant 1), so
    a record reaching this function has a signature — but say so explicitly rather than implying it
    by silence, because "no source shown" and "source not required" must never look the same."""
    src = rec.get("source") or {}
    workbook, cell = src.get("workbook"), src.get("cell_range")
    signed_by, date = src.get("signed_by"), src.get("date")
    where = f"{workbook} {cell}".strip() if workbook or cell else "—"
    who = f"{signed_by}" + (f", {date}" if date else "") if signed_by else "unsigned"
    return f"{where} (signed: {who})"


def _header(engagement, title: str, subtitle: str) -> list[str]:
    eid = getattr(engagement, "engagement_id", "—")
    return [
        f"# {title}",
        "",
        f"**{getattr(engagement, 'client', '—')} — {getattr(engagement, 'name', '—')}**  ",
        f"Engagement `{eid}` · phase {getattr(engagement, 'phase', '—')}",
        "",
        f"> {subtitle}",
        "",
    ]


def _footer(engagement) -> list[str]:
    """What makes this document trustworthy, stated rather than assumed.

    The chain verification is the load-bearing line. Every claim above is drawn from the ledger, so
    a document that renders while the chain is broken would be laundering tampered state into a
    clean-looking deliverable. Better to print the failure at the bottom of the document than to
    let it pass silently.
    """
    ledger = getattr(engagement, "ledger", None)
    try:
        intact = ledger.verify_chain() if ledger else False
    except Exception:                                  # noqa: BLE001 — a raising chain is a broken one
        intact = False
    n = len(_ledger_entries(engagement))
    state = (f"Ledger verified — {n} entries, hash chain intact."
             if intact else
             "**Ledger chain did not verify. Treat every statement in this document as unproven.**")
    return ["", "---", "",
            "*Generated from signed configuration intent. Nothing here is authored: every value is "
            "a projection of the engagement's own records, and regenerating this document is how "
            "the system is read.*",
            "",
            f"*{state}*", ""]


def _no_ir_yet(engagement, title: str, subtitle: str) -> str:
    """An engagement with no IR is a real state, not an error, and it must not render as an empty
    template that looks finished."""
    return "\n".join(_header(engagement, title, subtitle) + [
        "Nothing has been configured on this engagement yet.",
        "",
        "This document is a projection of signed configuration intent. Until intent is loaded there "
        "is nothing to project, and an empty document is the honest output — not a heading "
        "structure waiting to be filled in by hand.",
    ] + _footer(engagement))


# --- the documents -------------------------------------------------------------------------------

def config_rationale(engagement) -> str:
    """Every configured value, where it came from, and who signed for it.

    The document nobody can produce on demand. An auditor does not ask what the design was, they
    ask what the system is set to and on whose authority — and that question is normally answered
    by a consultant reading a screen and a spreadsheet six months out of date.
    """
    title, subtitle = "Configuration Rationale", DOCUMENTS["config-rationale"]
    records = [_as_dict(r) for r in _records(engagement)]
    if not records:
        return _no_ir_yet(engagement, title, subtitle)

    approvals, out = _approvals(engagement), _header(engagement, title, subtitle)
    by_product = defaultdict(list)
    for rec in records:
        by_product[rec.get("product") or "—"].append(rec)

    out += [f"{len(records)} configured object(s) across {len(by_product)} product(s).", ""]

    for product in sorted(by_product):
        out += [f"## {product}", ""]
        for rec in sorted(by_product[product], key=lambda r: (r.get("object") or "", _code(r))):
            code = _code(rec)
            out += [f"### {rec.get('object')} — `{code}`", "",
                    f"- **Tier** {rec.get('tier')} · **System** `{rec.get('system_binding')}`"
                    + (f" · **Country** {rec['country']}" if rec.get("country") else ""),
                    f"- **Source** {_provenance(rec)}"]

            if rec.get("depends_on"):
                out.append(f"- **Depends on** {', '.join(f'`{d}`' for d in rec['depends_on'])}")

            approved = approvals.get(code) or approvals.get(rec.get("object")) or []
            if approved:
                who = ", ".join(f"{a.get('actor')} ({a.get('ts')})" for a in approved)
                out.append(f"- **Approved by** {who}")
            else:
                # Said plainly. "No approval recorded" is a finding, and a document that omits it
                # is doing the reader's work for them in the wrong direction.
                out.append("- **Approved by** — no approval recorded on the ledger")
            out.append("")

            settled, pending = [], []
            for field_name, value in sorted((rec.get("intent") or {}).items()):
                if isinstance(value, dict) and "decision_point" in value:
                    if value.get("value") in (None, "", "TBD"):
                        pending.append([f"`{field_name}`", value["decision_point"]])
                        continue
                    settled.append([f"`{field_name}`", f"`{value['value']}`",
                                    f"resolved {value['decision_point']}"])
                    continue
                settled.append([f"`{field_name}`", f"`{value}`", "from workbook"])

            out += _table(["Field", "Value", "Basis"], settled) or ["*No field values recorded.*"]
            out.append("")
            if pending:
                out += ["**Not yet decided — these fields have no value and JIDOKA will not invent "
                        "one:**", ""]
                out += _table(["Field", "Decision point"], pending)
                out.append("")

    return "\n".join(out + _footer(engagement))


def solution_design(engagement) -> str:
    """Scope, landscape and object-by-object design — the BBP-shaped deliverable.

    The parts a machine can honestly write are the parts already decided: what is in scope, which
    systems, which objects, what each depends on. The parts that are genuine authorship — why this
    org structure, what the client's process should become — are not here and must not be faked.
    Where they belong, the document says a human has not written them yet.
    """
    title, subtitle = "Solution Design", DOCUMENTS["solution-design"]
    records = [_as_dict(r) for r in _records(engagement)]
    if not records:
        return _no_ir_yet(engagement, title, subtitle)

    out = _header(engagement, title, subtitle)

    out += ["## Scope", ""]
    by_product = defaultdict(list)
    for rec in records:
        by_product[rec.get("product") or "—"].append(rec)
    out += _table(["Product", "Objects", "Tiers"],
                  [[p, len(rs), ", ".join(sorted({str(r.get("tier")) for r in rs}))]
                   for p, rs in sorted(by_product.items())])
    out.append("")

    countries = sorted({r["country"] for r in records if r.get("country")})
    if countries:
        out += [f"In scope for {len(countries)} country/countries: "
                f"{', '.join(f'**{c}**' for c in countries)}.", "",
                "Country-specific values are statutory. They are not designed here — they enter "
                "the engagement as decision points resolved against signed client evidence.", ""]

    registry = getattr(engagement, "registry", None)
    systems = registry.landscape()["systems"] if registry else []
    if systems:
        out += ["## Landscape", ""]
        rows = []
        for s in systems:
            role = s.get("role", "—")
            # Worth stating in the design document rather than burying in a config: a source or
            # twin system that could hold write credentials would be a governance failure, and the
            # reader should be able to see that it cannot (invariant 3).
            note = "read-only by construction" if role in ("SOURCE_LEGACY", "TWIN") else ""
            rows.append([f"`{s.get('system_id', '—')}`", role, s.get("product", "—"), note])
        out += _table(["System", "Role", "Product", "Note"], rows)
        out.append("")

    out += ["## Design by object", ""]
    for product in sorted(by_product):
        out += [f"### {product}", ""]
        rows = []
        for rec in sorted(by_product[product], key=lambda r: (r.get("object") or "", _code(r))):
            intent = rec.get("intent") or {}
            undecided = sum(1 for v in intent.values()
                            if isinstance(v, dict) and v.get("value") in (None, "", "TBD"))
            rows.append([rec.get("object"), f"`{_code(rec)}`", rec.get("tier"),
                         ", ".join(f"`{d}`" for d in rec.get("depends_on", [])) or "—",
                         f"{len(intent) - undecided}/{len(intent)} decided"])
        out += _table(["Object", "Code", "Tier", "Depends on", "Fields"], rows)
        out.append("")

    tiers = {str(r.get("tier")) for r in records}
    if "C" in tiers:
        out += ["## Tier C — configured by hand, deliberately", "",
                "Some objects in scope have no published write API. JIDOKA declares those Tier C "
                "and produces a transportable change for a human to apply; it does not drive a "
                "screen to pretend otherwise. A fake write path is worse than an honest manual "
                "step, because it is a step nobody reviews (ADR-0003).", ""]

    open_dps = _open_dps(engagement)
    out += ["## Open questions", ""]
    if open_dps:
        out += [f"{len(open_dps)} decision point(s) are open. Planning is blocked until they are "
                "resolved — see the Decision Register.", ""]
        out += _table(["Decision point", "Blocks"],
                      [[f"`{k}`", str(v)] for k, v in sorted(open_dps.items())])
    else:
        out.append("No open decision points.")
    out.append("")

    out += ["## Process design", "",
            "*Not generated.* Why the client's processes should change, and what they should become, "
            "is authorship rather than projection. JIDOKA will not write it from configuration and "
            "then present the result with the same authority as the sections above.", ""]

    return "\n".join(out + _footer(engagement))


def decision_register(engagement) -> str:
    """Every decision point: the question, who owns it, how it was resolved, on what evidence.

    Type is not decoration. STATUTORY resolved without evidence and ONE_WAY resolved by one person
    cannot exist — `DecisionEngine.resolve` refuses both — so the register showing type and evidence
    together is the visible face of a gate that already held.
    """
    title, subtitle = "Decision Register", DOCUMENTS["decision-register"]
    dps = _decisions(engagement)
    out = _header(engagement, title, subtitle)

    if not dps:
        out += ["No decision points have been raised on this engagement.", "",
                "That is worth reading carefully rather than as good news. An engagement with real "
                "configuration and no decisions recorded means the questions were settled somewhere "
                "the ledger cannot see them."]
        return "\n".join(out + _footer(engagement))

    open_dps = [d for d in dps if getattr(d, "resolution", None) is None]
    closed = [d for d in dps if getattr(d, "resolution", None) is not None]
    out += [f"{len(dps)} decision point(s): **{len(open_dps)} open**, {len(closed)} resolved.", ""]

    if open_dps:
        out += ["## Open — planning is blocked", "",
                "JIDOKA does not plan around an open decision point and does not guess a value to "
                "get past one. Each of these needs its named owner.", ""]
        out += _table(["ID", "Type", "Question", "Owner", "Options"],
                      [[f"`{d.dp_id}`", d.dp_type, d.question, d.owner,
                        ", ".join(str(o) for o in (d.options or [])) or "—"]
                       for d in sorted(open_dps, key=lambda d: d.dp_id)])
        out.append("")

    if closed:
        out += ["## Resolved", ""]
        rows = []
        for d in sorted(closed, key=lambda d: d.dp_id):
            res = d.resolution or {}
            who = res.get("by", "—")
            if res.get("second_approver"):
                who = f"{who} + {res['second_approver']}"
            rows.append([f"`{d.dp_id}`", d.dp_type, d.question, f"`{res.get('value')}`", who,
                         res.get("evidence") or "—"])
        out += _table(["ID", "Type", "Question", "Value", "Decided by", "Evidence"], rows)
        out += ["",
                "ONE_WAY decisions carry two distinct approvers and STATUTORY decisions carry a "
                "signed client evidence reference. Neither can be recorded without them.", ""]

    return "\n".join(out + _footer(engagement))


def verification_report(engagement) -> str:
    """What was checked, what matched, what drifted, and what has never been looked at.

    Nobody writes this test plan. The expected result for every object IS its signed intent, so
    the plan cannot test the wrong thing and cannot go stale — and the results column is read off
    the ledger, where verification runs already wrote it. A difference is not a red cell here: it
    is an open decision point with a named owner, listed below, blocking the plan (ADR-0013).
    """
    title, subtitle = "Verification Report", DOCUMENTS["verification-report"]
    records = [_as_dict(r) for r in _records(engagement)]
    if not records:
        return _no_ir_yet(engagement, title, subtitle)

    def _key(rec):
        return f"{rec.get('product')}:{rec.get('object')}:{_code(rec)}"

    # Latest verification verdict per record, straight off the ledger.
    last: dict[str, dict] = {}
    for e in _ledger_entries(engagement):
        if e.get("action") in ("VERIFIED", "DRIFT_DETECTED"):
            last[e.get("task")] = e

    out = _header(engagement, title, subtitle)
    out += ["## What is checked", "",
            "The expected state below is not authored by a tester — it is the engagement's signed "
            "intent, per object. Settled fields are asserted verbatim against the live system; "
            "fields still behind an open decision point are not asserted, because JIDOKA does not "
            "test a value nobody has decided.", ""]
    rows = []
    for rec in sorted(records, key=_key):
        intent = rec.get("intent") or {}
        settled = [f for f, v in sorted(intent.items()) if not isinstance(v, dict)]
        rows.append([rec.get("object"), f"`{_code(rec)}`", f"`{rec.get('system_binding')}`",
                     ", ".join(f"`{f}`" for f in settled) or "—"])
    out += _table(["Object", "Code", "System", "Asserted fields"], rows)
    out.append("")

    out += ["## Last verification", ""]
    rows, never = [], []
    for rec in sorted(records, key=_key):
        e = last.get(_key(rec))
        if e is None:
            never.append(rec)
            continue
        verdict = "match" if e.get("action") == "VERIFIED" else f"**{e.get('status', 'DRIFT')}**"
        rows.append([rec.get("object"), f"`{_code(rec)}`", verdict, e.get("ts", "—"),
                     e.get("detail", "")])
    out += _table(["Object", "Code", "Result", "When", "Detail"], rows) or            ["*No verification has been run on this engagement.*"]
    out.append("")
    if never and rows:
        out += ["**Never verified** — these objects have signed intent but no verification entry "
                "on the ledger. Absence of a check is a finding, not a pass:", ""]
        out += _table(["Object", "Code"], [[r.get("object"), f"`{_code(r)}`"] for r in never])
        out.append("")

    drift_dps = [d for d in _decisions(engagement)
                 if d.dp_id.startswith("DP-DRIFT-") and getattr(d, "resolution", None) is None]
    out += ["## Unexplained differences", ""]
    if drift_dps:
        out += [f"{len(drift_dps)} drift decision point(s) are open. JIDOKA neither re-applies "
                "over an ununderstood change nor adopts an unsigned one; each difference below "
                "waits for its named owner to choose.", ""]
        out += _table(["Decision point", "Question", "Owner"],
                      [[f"`{d.dp_id}`", d.question, d.owner]
                       for d in sorted(drift_dps, key=lambda d: d.dp_id)])
    else:
        out.append("No unexplained differences are open.")
    out.append("")

    return "\n".join(out + _footer(engagement))


RENDERERS = {
    "config-rationale": config_rationale,
    "solution-design": solution_design,
    "decision-register": decision_register,
    "verification-report": verification_report,
}


def render(engagement, document: str) -> str:
    """Project one document from an engagement's signed state."""
    if document not in RENDERERS:
        raise ProjectionError(
            f"Unknown document {document!r}. Available: {', '.join(sorted(RENDERERS))}.")
    return RENDERERS[document](engagement)
