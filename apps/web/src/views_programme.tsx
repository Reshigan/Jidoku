/* The programme: the plan of record, against what the chain says.

   This is the screen a delivery lead opens instead of the plan workbook, and the one design decision
   in it is what it refuses to show. There is no percentage complete and no progress bar, because
   most of a programme's tasks are workshops the platform cannot see, and a number made partly of
   those would be read as progress and quoted in a steering meeting. So each row says what it is: on
   the chain, or the register's claim.

   The three registers are shown in the order they can stop the programme. A breached boundary
   condition is the loudest thing on the page — its consequence was written down before the work
   started, which is the whole reason to keep it. */
import { useCallback, useEffect, useState } from "react";

import { ApiError, Programme, ProgrammeGate, platform } from "./api";
import { Empty, Field, Modal, Pill, Section, Skeleton, useStillHere } from "./ui";
import "./views_programme.css";

/** The caller's day, so lateness is measured on the reader's clock rather than the server's. */
function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ProgrammeView(props: {
  eid: string;
  onRefusal: (title: string, text: string) => void;
}) {
  const { eid, onRefusal } = props;
  const [out, setOut] = useState<Programme | null>(null);
  const [missing, setMissing] = useState(false);
  const [gate, setGate] = useState<ProgrammeGate | null>(null);
  const [evidence, setEvidence] = useState("");
  const [behalf, setBehalf] = useState("");
  /* Everything on this screen is recorded against a name, so everything on it asks for what was
     checked. One dialog rather than three, and never a browser prompt: a prompt's text is not on
     the page, so what somebody was told before they answered is not in the record either. */
  const [ask, setAsk] = useState<{ title: string; hint: string; label: string;
                                   run: (evidence: string) => Promise<Programme>; } | null>(null);
  const stillHere = useStillHere(eid);

  const load = useCallback(() => {
    const was = eid;
    platform.programme(eid, today())
      .then((p) => { if (stillHere(was)) { setOut(p); setMissing(false); } })
      .catch((e) => {
        if (!stillHere(was)) return;
        if (e instanceof ApiError && e.status === 404) { setMissing(true); return; }
        if (e instanceof ApiError && !e.notAvailable) onRefusal("The programme", e.detail);
      });
  }, [eid, onRefusal, stillHere]);

  useEffect(load, [load]);

  const act = (p: Promise<Programme>, title: string) => {
    p.then(setOut).catch((e) => {
      if (e instanceof ApiError) onRefusal(title, e.detail);
    });
  };

  if (missing) {
    return (
      <Empty
        title="No plan has been absorbed for this engagement"
        body="A mobilisation pack becomes a programme through tools/jidoka-absorb.py, and a person signs the bundle before it is registered. A programme the platform has not been given is not a programme with nothing in it."
      />
    );
  }
  if (!out) return <Skeleton rows={6} tall />;

  const worst = out.breached_conditions ? "stop"
    : out.gates_late.length || out.unspoken_conditions ? "call" : "run";

  return (
    <>
      <Section
        title="The plan of record"
        note={out.method}
        lamp={worst}
        status={`${out.gates_passed} of ${out.gates.length} gates passed on evidence`}
      >
        <p className="mut" style={{ marginBottom: 12 }}>{out.says}</p>
      </Section>

      <Section
        title="Boundary conditions"
        note="What the programme said had to be true, and the consequence it wrote down for each one failing. Silence is shown as silence: a condition nobody has spoken about is not a condition that holds."
        lamp={out.breached_conditions ? "stop" : out.unspoken_conditions ? "call" : "run"}
        status={out.breached_conditions ? `${out.breached_conditions} breached`
          : out.unspoken_conditions ? `${out.unspoken_conditions} unconfirmed` : "all confirmed"}
      >
        {out.conditions.length === 0 ? (
          <p className="mut">This plan declared no boundary conditions.</p>
        ) : (
          <ul className="pg-list">
            {out.conditions.map((c) => (
              <li key={c.what}
                  className={c.holding === false ? "pg-breached" : c.holding ? "pg-held" : ""}>
                <div className="pg-head">
                  <span>{c.what}</span>
                  <Pill lamp={c.holding === false ? "stop" : c.holding ? "run" : "call"}>
                    {c.holding === false ? "breached" : c.holding ? "confirmed" : "nobody has said"}
                  </Pill>
                </div>
                <p className="mut">{c.says}</p>
                {c.holding === null && (
                  <div className="pg-actions">
                    <button onClick={() => { setEvidence(""); setAsk({
                      title: `${c.what} — it holds`,
                      hint: "What did you check? A condition confirmed against nothing is somebody's impression, and the consequence of it failing is already written down.",
                      label: "Confirm it",
                      run: (ev) => platform.confirmCondition(eid, c.what, ev) }); }}>
                      It holds
                    </button>
                    <button className="danger" onClick={() => { setEvidence(""); setAsk({
                      title: `${c.what} — it has failed`,
                      hint: `What happened? The plan says the consequence is: ${c.consequence}`,
                      label: "Record the breach",
                      run: (ev) => platform.breachCondition(eid, c.what, ev) }); }}>
                      It has failed
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section
        title="Gates"
        note="A gate passes on evidence, by somebody who did not do the work. The date is when it is due; passing is what the chain records."
        lamp={out.gates_late.length ? "call" : "run"}
        status={out.gates_late.length ? `${out.gates_late.length} past their date` : undefined}
      >
        <table className="tbl">
          <thead>
            <tr><th scope="col">Gate</th><th scope="col">Due</th><th scope="col">Approver</th>
              <th scope="col">State</th><th scope="col" /></tr>
          </thead>
          <tbody>
            {out.gates.map((g) => (
              <tr key={g.gate_id}>
                <td>{g.gate_id} · {g.name}</td>
                {/* The pack's own words, because that is what the approver reads. The absence of a
                    resolvable day is said rather than hidden: it is why no lateness is claimed. */}
                <td title={g.date_understood ? g.due_on : "no day was resolved from this"}>
                  {g.date || "unscheduled"}
                  {!g.date_understood && <span className="mut"> (not a day)</span>}
                </td>
                <td>{g.approver}</td>
                <td>
                  <Pill lamp={g.passed ? "run" : g.late ? "call" : "idle"}>
                    {g.passed ? `passed by ${g.passed_by}` : g.late ? "late" : "not yet"}
                  </Pill>
                </td>
                <td>
                  {!g.passed && (
                    <button onClick={() => { setGate(g); setEvidence(""); setBehalf(g.approver); }}>
                      Pass on evidence
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section
        title="Tasks"
        note="What the chain shows, kept apart from what the register claims. A task that watches nothing is invisible to the platform, and its status is whatever somebody typed."
        lamp={out.blocked.length ? "call" : "run"}
        status={`${out.tasks_the_platform_cannot_see} of ${out.tasks.length} invisible to the platform`}
      >
        {out.blocked.length > 0 && (
          <p className="mut" style={{ marginBottom: 10 }}>
            {out.blocked.length} task(s) are waiting on work the plan puts before them:{" "}
            {out.blocked.map((t) => `${t.task_id} on ${t.waiting_on?.join(", ")}`).join("; ")}.
          </p>
        )}
        <table className="tbl">
          <thead>
            <tr><th scope="col">Task</th><th scope="col">Week</th><th scope="col">Owner</th>
              <th scope="col">Gate</th><th scope="col">The register says</th>
              <th scope="col">The chain says</th><th scope="col" /></tr>
          </thead>
          <tbody>
            {out.tasks.map((t) => (
              <tr key={t.task_id}>
                <td title={t.task}>{t.task_id}</td>
                <td>{t.week}</td>
                <td>{t.owner}</td>
                <td>{t.gate}</td>
                <td className="mut">{t.declared_status || "—"}</td>
                <td>
                  <Pill lamp={t.done ? "run" : t.visible_to_platform ? "idle" : "call"}>
                    {t.done ? "done" : t.visible_to_platform ? "not done" : "cannot see it"}
                  </Pill>
                </td>
                <td>
                  {!t.done && !t.visible_to_platform && (
                    <button onClick={() => { setEvidence(""); setAsk({
                      title: `${t.task_id} — report it done`,
                      hint: `${t.task}. The platform cannot see this one, so what goes on the chain is your account of it, under your name.`,
                      label: "Report it done",
                      run: (ev) => platform.reportTaskDone(eid, t.task_id, ev) }); }}>
                      Report it done
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      {ask && (
        <Modal title={ask.title} onClose={() => setAsk(null)}>
          <Field label="What happened" value={evidence} onChange={setEvidence} required
                 hint={ask.hint} textarea />
          <div className="pg-actions">
            <button className="primary" onClick={() => {
              act(ask.run(evidence), ask.title);
              setAsk(null);
            }}>
              {ask.label}
            </button>
            <button onClick={() => setAsk(null)}>Cancel</button>
          </div>
        </Modal>
      )}

      {gate && (
        <Modal title={`Pass ${gate.gate_id} — ${gate.name}`} onClose={() => setGate(null)}>
          <p className="mut">{gate.criteria}</p>
          {/* Not just "Evidence": the andon rail already has a view by that name, so a reader
              hearing the label alone would not know which one they were on. */}
          <Field label="Evidence for this gate" value={evidence} onChange={setEvidence} required
                 hint={`The pack asks for: ${gate.evidence_required}`} textarea />
          <Field label="On behalf of" value={behalf} onChange={setBehalf}
                 hint="Who the plan names as this gate's approver. Recorded beside your own name, because a plan names a person and a token proves who pressed the button." />
          <div className="pg-actions">
            <button className="primary" onClick={() => {
              act(platform.passGate(eid, gate.gate_id, evidence, behalf), `Passing ${gate.gate_id}`);
              setGate(null);
            }}>
              Pass it
            </button>
            <button onClick={() => setGate(null)}>Not yet</button>
          </div>
        </Modal>
      )}
    </>
  );
}
