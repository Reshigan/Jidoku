/* 13 · Insight — the brownfield door.

   Every other screen starts from signed intent. This one starts from a system nobody designed:
   a tenant configured over years by people who have left, whose design document either never
   existed or stopped being true long ago. Archaeology reads it into drafts that are unsigned by
   construction, so nothing recovered can execute and nothing recovered is mistaken for a
   decision. The backlog is the work: each object is one question — why does this exist, and is
   it still wanted?

   Signing is the whole connection to the rest of the console. A signed draft stops being
   archaeology and becomes ordinary IR, which the planner sequences, the documents project and
   verification checks — with nothing on this screen doing any of it. The signature is the
   server's view of who is calling (ADR-0015): there is no name field here, on purpose. */
import { useCallback, useEffect, useState } from "react";
import { ApiError, Backlog, Blast, Landscape, TimeTravel, platform } from "./api";
import { Empty, Field, Pill, Section } from "./ui";

/** A grade is a lamp: D is a stop, A is a running line. */
const GRADE_LAMP: Record<string, string> = { A: "run", B: "run", C: "call", D: "stop" };

export function InsightView(props: {
  eid: string | null;
  landscape: Landscape | null;
  canDig: boolean;    // write_ir — archaeology and signing are both builder acts
  onRefusal: (title: string, text: string) => void;
  onChanged: () => Promise<void>;  // signing adds IR; the plan, documents and verify must learn
}) {
  const { eid, onRefusal } = props;
  const [backlog, setBacklog] = useState<Backlog | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [dig, setDig] = useState({ system_id: "", entities: "" });
  const [workbook, setWorkbook] = useState("");
  const [at, setAt] = useState("");
  const [moment, setMoment] = useState<TimeTravel | null>(null);
  const [blastForm, setBlastForm] = useState({ system_id: "", entity: "", id_field: "externalCode",
                                               field: "", value: "", delta: "" });
  const [blast, setBlast] = useState<Blast | null>(null);

  const refresh = useCallback(() => {
    if (!eid) return;
    platform.backlog(eid)
      .then(setBacklog)
      .catch((e) => { if (e instanceof ApiError && !e.notAvailable) onRefusal("Backlog", e.detail); });
  }, [eid, onRefusal]);

  useEffect(() => { setBacklog(null); setPicked(new Set()); setMoment(null); setBlast(null); refresh(); },
            [refresh]);

  if (!eid) return <Empty title="No engagement" body="Choose an engagement to read its systems." />;

  const systems = props.landscape?.systems ?? [];
  const unsigned = backlog ? backlog.drafts.filter((d) => !d.signed) : [];

  const run = async (label: string, fn: () => Promise<unknown>, title: string) => {
    setBusy(label);
    try { await fn(); } catch (e) { if (e instanceof ApiError) onRefusal(title, e.detail); }
    finally { setBusy(null); }
  };

  const excavate = () =>
    run("dig", async () => {
      const entities = dig.entities.split(/[,\s]+/).filter(Boolean);
      setBacklog(await platform.dig(eid, dig.system_id, entities));
      setPicked(new Set());
    }, "The system was not read");

  const sign = () =>
    run("sign", async () => {
      const out = await platform.signDrafts(eid, [...picked], workbook);
      setBacklog(out.backlog);
      setPicked(new Set());
      setWorkbook("");
      await props.onChanged();
    }, "Nothing was signed");

  const replay = () =>
    run("time", async () => setMoment(await platform.timetravel(eid, at)), "That moment could not be read");

  const radius = () =>
    run("blast", async () => setBlast(await platform.blast(eid, {
      system_id: blastForm.system_id, entity: blastForm.entity, id_field: blastForm.id_field,
      selector: blastForm.field ? { [blastForm.field]: blastForm.value } : {},
      delta: blastForm.delta,
    })), "The blast radius was not computed");

  const toggle = (key: string) =>
    setPicked((p) => { const n = new Set(p); n.has(key) ? n.delete(key) : n.add(key); return n; });

  return (
    <>
      <Section
        title="Archaeology"
        note="Read a live system into draft records. Unsigned by construction — nothing recovered here can execute."
        lamp={backlog && unsigned.length > 0 ? "call" : backlog ? "run" : undefined}
        status={backlog ? `${unsigned.length} unexplained` : undefined}
      >
        {props.canDig && (
          <div className="row" style={{ gap: 12, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 14 }}>
            <label className="field">
              <span className="eyebrow">System to read</span>
              <select value={dig.system_id}
                      onChange={(e) => setDig({ ...dig, system_id: e.target.value })}>
                <option value="">Choose a bound system…</option>
                {systems.map((s) => (
                  <option key={s.system_id} value={s.system_id}>{s.system_id} · {s.role}</option>
                ))}
              </select>
            </label>
            <Field label="Entities" value={dig.entities} placeholder="FOCostCenter, TimeType"
                   onChange={(v) => setDig({ ...dig, entities: v })} />
            <button className="btn" disabled={!dig.system_id || !dig.entities || busy !== null}
                    onClick={() => void excavate()}>
              {busy === "dig" ? "Reading the system…" : "Read the system"}
            </button>
          </div>
        )}

        {!backlog || backlog.drafts.length === 0 ? (
          <p className="mut">
            No live system has been read on this engagement. Archaeology reverses a running tenant
            into draft records so the objects nobody can account for become visible work. An empty
            backlog is not a claim that the system is clean — it means nothing has been looked at.
          </p>
        ) : (
          <>
            <p className="mut">
              {backlog.drafts.length} object{backlog.drafts.length === 1 ? "" : "s"} recovered from{" "}
              {backlog.systems.join(", ")}. {unsigned.length} still carr{unsigned.length === 1 ? "ies" : "y"} no
              rationale. Signing one is an assertion that somebody understands why it exists — it
              becomes intent the platform will plan, document and verify like any other record.
            </p>
            <div className="tblwrap">
              <table className="tbl">
                <thead>
                  <tr><th /><th>Object</th><th>Code</th><th>System</th><th>Recovered as</th><th>Rationale</th></tr>
                </thead>
                <tbody>
                  {unsigned.map((d) => (
                    <tr key={d.key}>
                      <td>
                        <input type="checkbox" checked={picked.has(d.key)} disabled={!props.canDig}
                               aria-label={`Select ${d.key}`} onChange={() => toggle(d.key)} />
                      </td>
                      <td>{d.object}</td>
                      <td className="mono">{d.external_code}</td>
                      <td className="mono">{d.system_binding}</td>
                      <td><Pill lamp="call">{d.provenance_status}</Pill></td>
                      <td>{d.rationale ?? <span className="mut">unexplained</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {props.canDig && (
              <div className="row" style={{ gap: 12, alignItems: "flex-end", marginTop: 14, flexWrap: "wrap" }}>
                <Field label="Workbook" value={workbook} placeholder="brownfield-review-2026"
                       onChange={setWorkbook} />
                <button className="btn" disabled={picked.size === 0 || busy !== null}
                        onClick={() => void sign()}>
                  {busy === "sign" ? "Signing…" : `Sign ${picked.size || ""} into intent`.trim()}
                </button>
                <span className="mut" style={{ fontSize: 12.5 }}>
                  Signed in your name by the server — there is no field here to sign as someone else.
                </span>
              </div>
            )}
          </>
        )}
      </Section>

      {backlog && (
        <Section
          title="Debt index"
          note="Published weights, reproducible from the same extract — and an honest list of what was never measured."
          lamp={GRADE_LAMP[backlog.debt.grade]}
          status={`score ${backlog.debt.score} · grade ${backlog.debt.grade}`}
        >
          <div className="tblwrap">
            <table className="tbl">
              <thead><tr><th>Counter</th><th>Count</th><th>Weight</th><th>Contribution</th><th>Measured from</th></tr></thead>
              <tbody>
                {Object.keys(backlog.debt.items).sort().map((k) => (
                  <tr key={k}>
                    <td className="mono">{k}</td>
                    <td>{backlog.debt.counts[k] ?? 0}</td>
                    <td>{backlog.debt.weights[k]}</td>
                    <td>{backlog.debt.items[k]}</td>
                    <td className="mut" style={{ fontSize: 12.5 }}>
                      {backlog.debt.measured[k] ?? <em>not measured</em>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {backlog.debt.unmeasured.length > 0 && (
            <p className="mut" style={{ marginTop: 12, fontSize: 12.5 }}>
              Not measured, and therefore contributing nothing rather than assumed to be zero:{" "}
              {backlog.debt.unmeasured.join(", ")}. A number nobody can trace is an opinion.
            </p>
          )}
        </Section>
      )}

      <Section
        title="Time travel"
        note="The ledger is the record; 'now' is only its last frame. Replay the programme to any moment."
      >
        <div className="row" style={{ gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
          <Field label="As of" value={at} placeholder="2026-09-01T12:00:00Z" onChange={setAt} />
          <button className="btn" disabled={!at || busy !== null} onClick={() => void replay()}>
            {busy === "time" ? "Replaying…" : "Replay to this moment"}
          </button>
        </div>
        {moment && (
          <p className="mut" style={{ marginTop: 12 }}>
            At {moment.at}: {moment.entries} ledger entr{moment.entries === 1 ? "y" : "ies"} had been
            written, {moment.approved.length} task{moment.approved.length === 1 ? "" : "s"} stood approved,
            {" "}{moment.rolled_back.length} had been rolled back, {moment.open_dps.length} decision
            point{moment.open_dps.length === 1 ? " was" : "s were"} open, and the line was{" "}
            {moment.halted ? <Pill lamp="stop">halted</Pill> : "running"}.
          </p>
        )}
      </Section>

      <Section
        title="Blast radius"
        note="Counted in people, read from the live system. A radius computed from a design document counts the people somebody meant to have."
        className="grow scrolls"
      >
        <div className="row" style={{ gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
          <label className="field">
            <span className="eyebrow">Population system</span>
            <select value={blastForm.system_id}
                    onChange={(e) => setBlastForm({ ...blastForm, system_id: e.target.value })}>
              <option value="">Choose…</option>
              {systems.map((s) => <option key={s.system_id} value={s.system_id}>{s.system_id}</option>)}
            </select>
          </label>
          <Field label="Entity" value={blastForm.entity} placeholder="FOCostCenter"
                 onChange={(v) => setBlastForm({ ...blastForm, entity: v })} />
          <Field label="Identified by" value={blastForm.id_field}
                 onChange={(v) => setBlastForm({ ...blastForm, id_field: v })} />
          <Field label="Where field" value={blastForm.field} placeholder="cust_region"
                 onChange={(v) => setBlastForm({ ...blastForm, field: v })} />
          <Field label="equals" value={blastForm.value} placeholder="EMEA"
                 onChange={(v) => setBlastForm({ ...blastForm, value: v })} />
          <Field label="Change" value={blastForm.delta} placeholder="accrual basis corrected"
                 onChange={(v) => setBlastForm({ ...blastForm, delta: v })} />
          <button className="btn" disabled={!blastForm.system_id || !blastForm.entity || busy !== null}
                  onClick={() => void radius()}>
            {busy === "blast" ? "Counting…" : "Count the people"}
          </button>
        </div>
        {blast && (
          <p style={{ marginTop: 14 }}>
            {blast.statement}
            {blast.affected_ids.length > 0 && (
              <span className="mut" style={{ display: "block", marginTop: 6, fontSize: 12.5 }}>
                Affected: {blast.affected_ids.slice(0, 20).map(String).join(", ")}
                {blast.affected_ids.length > 20 ? ` … and ${blast.affected - 20} more` : ""}
              </span>
            )}
          </p>
        )}
      </Section>
    </>
  );
}
