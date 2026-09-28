/* What the client asked for, against what has been signed.

   Every engagement has a specification and a configuration and nobody can join them: the
   requirements are in a Word document, the configuration is in a system, and the answer lives in
   somebody's memory of a workshop in week three. This screen is that join, and its most important
   column is the one that says the platform cannot answer.

   A requirement traced to nothing is NOT_TRACEABLE and is never counted as covered. It is shown
   first, because an untraced specification quietly reporting a high number is the most convincing
   wrong answer this platform could give. */
import { useCallback, useEffect, useState } from "react";

import { ApiError, RequirementRow, SpecificationView, platform } from "./api";
import { Empty, Field, Modal, Pill, Section, Skeleton, useStillHere } from "./ui";
import "./views_specification.css";

const LAMP: Record<string, string> = {
  CONFIGURED: "run", NOT_CONFIGURED: "idle", NOT_TRACEABLE: "call",
};
const STATE: Record<string, string> = {
  CONFIGURED: "signed", NOT_CONFIGURED: "not signed", NOT_TRACEABLE: "cannot tell",
};

export function SpecificationView_(props: {
  eid: string;
  onRefusal: (title: string, text: string) => void;
}) {
  const { eid, onRefusal } = props;
  const [out, setOut] = useState<SpecificationView | null>(null);
  const [missing, setMissing] = useState(false);
  const [tracing, setTracing] = useState<RequirementRow | null>(null);
  const [objects, setObjects] = useState("");
  const [why, setWhy] = useState("");
  const stillHere = useStillHere(eid);

  const load = useCallback(() => {
    const was = eid;
    platform.specification(eid)
      .then((s) => { if (stillHere(was)) { setOut(s); setMissing(false); } })
      .catch((e) => {
        if (!stillHere(was)) return;
        if (e instanceof ApiError && e.status === 404) { setMissing(true); return; }
        if (e instanceof ApiError && !e.notAvailable) onRefusal("The specification", e.detail);
      });
  }, [eid, onRefusal, stillHere]);

  useEffect(load, [load]);

  if (missing) {
    return (
      <Empty
        title="No specification has been absorbed for this engagement"
        body="A requirements document becomes a specification through tools/jidoka-absorb.py. An unanswered specification is not the same as one with no requirements in it, so nothing is shown rather than an empty table."
      />
    );
  }
  if (!out) return <Skeleton rows={6} tall />;

  /* Worst first, and within a state by identifier: the order is the reading order, and a screen
     that sorted by id alone would bury the requirements nobody can answer for. */
  const order = ["NOT_TRACEABLE", "NOT_CONFIGURED", "CONFIGURED"];
  const rows = [...out.requirements].sort((a, b) =>
    order.indexOf(a.state) - order.indexOf(b.state) || a.req_id.localeCompare(b.req_id));

  return (
    <>
      <Section
        title="The specification"
        note={out.method}
        lamp={out.not_traceable.length ? "call" : out.not_configured.length ? "idle" : "run"}
        status={`${out.configured} of ${out.requirements.length} described by signed intent`}
      >
        <p className="mut" style={{ marginBottom: 12 }}>{out.says}</p>
        {out.declared_gaps.length > 0 && (
          <p className="mut">
            The design authority declared {out.declared_gaps.length} of these a GAP:{" "}
            {out.declared_gaps.join(", ")}. That is its assessment, kept as written and never
            recomputed here.
          </p>
        )}
        {out.unrecognised_fit.length > 0 && (
          <p className="mut">
            {out.unrecognised_fit.length} carry a fit assessment this platform does not recognise,
            so they are reported rather than sorted into one it does: {out.unrecognised_fit.join(", ")}.
          </p>
        )}
      </Section>

      <Section
        title="Requirements"
        note="Worst first. A requirement nobody has traced to a configuration object is shown at the top, because it is the one the platform cannot answer for — not the one that is fine."
        lamp={out.not_traceable.length ? "call" : "run"}
        status={out.not_traceable.length
          ? `${out.not_traceable.length} traced to nothing` : "all traced"}
      >
        <table className="tbl">
          <thead>
            <tr><th scope="col">Requirement</th><th scope="col">Fit</th><th scope="col">Control</th>
              <th scope="col">Objects</th><th scope="col">State</th><th scope="col" /></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.req_id}>
                <td title={r.rationale}>
                  <span className="mono">{r.req_id}</span>
                  <div className="mut spec-req">{r.requirement}</div>
                </td>
                <td>{r.fit_recognised ? r.fit : <em>{r.fit || "—"}</em>}</td>
                <td title={r.control_evidence}>
                  {r.control || "—"}
                  {r.control_named_but_absent && <span className="mut"> (not defined)</span>}
                </td>
                <td className="mono">{r.objects.join(", ") || "—"}</td>
                <td><Pill lamp={LAMP[r.state]}>{STATE[r.state]}</Pill></td>
                <td>
                  <button onClick={() => {
                    setTracing(r); setObjects(r.objects.join(", ")); setWhy("");
                  }}>
                    {r.objects.length ? "Re-trace" : "Trace it"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section
        title="Control objectives"
        note="What each control assures, who owns it, how often it runs and what it leaves behind. A control nothing cites and a control nothing defines are both named — an auditor asks about the second as readily as the first."
        lamp={out.uncontrolled.length ? "call" : "run"}
        status={out.uncontrolled.length ? `${out.uncontrolled.length} to answer for` : undefined}
      >
        {out.uncontrolled.length > 0 && (
          <ul className="spec-gaps">
            {out.uncontrolled.map((u) => <li key={u.kind + u.id}>{u.says}</li>)}
          </ul>
        )}
        <table className="tbl">
          <thead>
            <tr><th scope="col">Control</th><th scope="col">Objective</th><th scope="col">Owner</th>
              <th scope="col">Frequency</th><th scope="col">Evidence</th></tr>
          </thead>
          <tbody>
            {out.controls.map((c) => (
              <tr key={c.control_id}>
                <td className="mono">{c.control_id}</td>
                <td>{c.objective}</td>
                <td>{c.owner}</td>
                <td>{c.frequency}</td>
                <td className="mut">{c.evidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      {tracing && (
        <Modal title={`Trace ${tracing.req_id}`} onClose={() => setTracing(null)}>
          <p className="mut">{tracing.requirement}</p>
          <Field label="Objects that satisfy it" value={objects} onChange={setObjects} required
                 hint="Object names or external codes, comma separated. They need not exist yet — a requirement traced to something nothing describes reads as not signed, which is a true answer." />
          {/* Not "Why": a field's accessible name here is its label plus its hint, and the field
              above ends with "…which is why the platform will not make it". */}
          <Field label="Why this satisfies it" value={why} onChange={setWhy}
                 hint="Recorded against your name. This is a judgement about the client's design, which is why the platform will not make it." />
          <div className="spec-actions">
            <button className="primary" onClick={() => {
              const list = objects.split(",").map((o) => o.trim()).filter(Boolean);
              platform.traceRequirement(eid, tracing.req_id, list, why)
                .then(setOut)
                .catch((e) => {
                  if (e instanceof ApiError) onRefusal(`Tracing ${tracing.req_id}`, e.detail);
                });
              setTracing(null);
            }}>
              Record the trace
            </button>
            <button onClick={() => setTracing(null)}>Cancel</button>
          </div>
        </Modal>
      )}
    </>
  );
}
