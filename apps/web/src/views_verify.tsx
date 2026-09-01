/* 12 · Verify — the platform reads the live system and compares it to signed intent.

   Verification here is not a test suite someone wrote: the test plan IS the signed IR (ADR-0013).
   The run only reads. A difference is never reconciled from this screen or any other — it becomes
   a blocking decision point owned by whoever signed the record, and planning stops until a person
   answers. The other half of the screen is number ranges (ADR-0014): codes as ledgered
   allocations, where a collision is a refusal with a name in it. */
import { useCallback, useEffect, useState } from "react";
import { ApiError, NumberingSnapshot, VerificationRun, platform } from "./api";
import { Empty, Field, Pill, Section } from "./ui";

export function VerifyView(props: {
  eid: string | null;
  canVerify: boolean;   // ledger_append — the run writes VERIFIED / DRIFT_DETECTED entries
  canAllocate: boolean; // write_ir — same permission that loads the IR the codes end up in
  onRefusal: (title: string, text: string) => void;
  onChanged: () => Promise<void>; // drift raises DPs and blocks planning; the rest of the console must learn
}) {
  const { eid, onRefusal } = props;
  const [run, setRun] = useState<VerificationRun | null>(null);
  const [numbering, setNumbering] = useState<NumberingSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [stamp, setStamp] = useState("");
  const [form, setForm] = useState({ range_id: "", object_type: "", prefix: "", start: "1", end: "9999" });

  const refreshNumbering = useCallback(() => {
    if (!eid) return;
    platform.numbering(eid)
      .then(setNumbering)
      .catch((e) => { if (e instanceof ApiError && !e.notAvailable) onRefusal("Number ranges", e.detail); });
  }, [eid, onRefusal]);

  useEffect(() => { setRun(null); setStamp(""); refreshNumbering(); }, [refreshNumbering]);

  if (!eid) return <Empty title="No engagement" body="Choose an engagement to verify it." />;

  const verify = async () => {
    setBusy(true);
    try {
      const out = await platform.verify(eid);
      setRun(out);
      setStamp(new Date().toLocaleTimeString());
      await props.onChanged();
    } catch (e) {
      if (e instanceof ApiError) onRefusal("Verification did not run", e.detail);
    } finally {
      setBusy(false);
    }
  };

  const register = async () => {
    try {
      await platform.registerRange(eid, {
        range_id: form.range_id, object_type: form.object_type, prefix: form.prefix,
        start: Number(form.start), end: Number(form.end),
      });
      setForm({ range_id: "", object_type: "", prefix: "", start: "1", end: "9999" });
      refreshNumbering();
    } catch (e) {
      if (e instanceof ApiError) onRefusal("The range was not registered", e.detail);
    }
  };

  const allocate = async (object_type: string) => {
    try {
      await platform.allocateCode(eid, object_type);
      refreshNumbering();
    } catch (e) {
      // A collision names its holder. That name is the point; it is quoted, never summarised.
      if (e instanceof ApiError) onRefusal("The code was not allocated", e.detail);
    }
  };

  const total = run ? run.verified.length + run.drift.length + run.skipped.length : 0;

  return (
    <>
      <Section
        title="Verification"
        note="Signed intent checked against live state. Reading only — a difference becomes a decision, never a silent fix."
        lamp={run ? (run.planning_blocked ? "stop" : "run") : undefined}
        status={run ? (run.planning_blocked ? "planning blocked" : "all checked records match") : undefined}
        actions={
          <button className="btn" disabled={!props.canVerify || busy} onClick={() => void verify()}>
            {busy ? "Reading the systems…" : run ? "Verify again" : "Run verification"}
          </button>
        }
      >
        {!run ? (
          <p className="mut">
            Nothing has been checked this session. The test plan is the signed IR itself — running
            verification reads every record's live system and compares field by field. Results are
            ledgered, and the Verification Report under Documents is projected from them.
          </p>
        ) : (
          <>
            <p className="mut">
              {run.verified.length} of {total} record{total === 1 ? "" : "s"} match{run.verified.length === 1 ? "es" : ""} the
              live system{stamp ? ` · checked ${stamp}` : ""}.
              {run.drift.length > 0 && " Each difference below is now a blocking decision point, owned by whoever signed the record."}
            </p>
            {run.drift.length > 0 && (
              <div className="tblwrap">
                <table className="tbl">
                  <thead>
                    <tr><th>Record</th><th>Found</th><th>System</th><th>Fields</th><th>Decision</th></tr>
                  </thead>
                  <tbody>
                    {run.drift.map((f) => (
                      <tr key={f.key}>
                        <td className="mono">{f.key}</td>
                        <td>
                          <Pill lamp="stop">{f.status === "MISSING" ? "Missing" : "Drifted"}</Pill>
                        </td>
                        <td className="mono">{f.system}</td>
                        <td>
                          {Object.keys(f.fields).length === 0
                            ? <span className="mut">absent from the live system</span>
                            : Object.entries(f.fields).map(([k, v]) => (
                                <div key={k} style={{ fontSize: 12.5 }}>
                                  <span className="mono">{k}</span>: signed <strong>{String(v.intent)}</strong>,
                                  live <strong>{String(v.live)}</strong>
                                </div>
                              ))}
                        </td>
                        <td className="mono">{f.decision_point}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {run.skipped.length > 0 && (
              <>
                <p className="mut" style={{ marginTop: 12 }}>
                  Not checked — a skipped record is a finding, not a pass:
                </p>
                <ul className="mut" style={{ fontSize: 12.5 }}>
                  {run.skipped.map((s) => (
                    <li key={s.key}><span className="mono">{s.key}</span> — {s.reason}</li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </Section>

      <Section
        title="Number ranges"
        note="Codes as governed allocations. A collision is refused with the holder's name; a code once used is never released."
        status={numbering ? `${Object.keys(numbering.allocated).length} allocated` : ""}
        className="grow scrolls"
      >
        {numbering && numbering.ranges.length > 0 && (
          <div className="tblwrap">
            <table className="tbl">
              <thead>
                <tr><th>Range</th><th>Governs</th><th>Codes</th><th>Next free</th><th /></tr>
              </thead>
              <tbody>
                {numbering.ranges.map((r) => (
                  <tr key={r.range_id}>
                    <td className="mono">{r.range_id}</td>
                    <td>{r.object_type}</td>
                    <td className="mono">
                      {r.prefix}{String(r.start).padStart(r.width, "0")}..{r.prefix}{String(r.end).padStart(r.width, "0")}
                    </td>
                    <td className="mono">
                      {r.next_free ?? <Pill lamp="stop">exhausted</Pill>}
                    </td>
                    <td>
                      <button className="btn" disabled={!props.canAllocate || r.next_free === null}
                              onClick={() => void allocate(r.object_type)}>
                        Allocate next
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {numbering && Object.keys(numbering.allocated).length > 0 && (
          <>
            <p className="mut" style={{ marginTop: 12 }}>Allocated — each entry is on the ledger:</p>
            <div className="tblwrap">
              <table className="tbl">
                <thead><tr><th>Code</th><th>Held by</th></tr></thead>
                <tbody>
                  {Object.entries(numbering.allocated).map(([code, holder]) => (
                    <tr key={code}><td className="mono">{code}</td><td>{holder}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        {numbering && numbering.ranges.length === 0 && (
          <p className="mut">
            No ranges yet. An object type without a range is unconstrained; register one and every
            IR load is checked against it before anything is kept.
          </p>
        )}
        {props.canAllocate && (
          <div className="row" style={{ gap: 12, alignItems: "flex-end", marginTop: 16, flexWrap: "wrap" }}>
            <Field label="Range id" value={form.range_id} placeholder="TT-ZA"
                   onChange={(v) => setForm({ ...form, range_id: v })} />
            <Field label="Object type" value={form.object_type} placeholder="TimeType"
                   onChange={(v) => setForm({ ...form, object_type: v })} />
            <Field label="Prefix" value={form.prefix} placeholder="TT_ZA_"
                   onChange={(v) => setForm({ ...form, prefix: v })} />
            <Field label="Start" value={form.start} onChange={(v) => setForm({ ...form, start: v })} />
            <Field label="End" value={form.end} onChange={(v) => setForm({ ...form, end: v })} />
            <button className="btn" disabled={!form.range_id || !form.object_type || !form.prefix}
                    onClick={() => void register()}>
              Register range
            </button>
          </div>
        )}
      </Section>
    </>
  );
}
