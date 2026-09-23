/* Is QA the same as PROD, and what is in DEV that never made it across?
   The question a consultant answers by hand before every cutover, asked of two systems the
   registry already knows. Neither side is a baseline: the screen says what differs and, where
   signed intent describes the object, which side matches it — and stops there, because which one
   is right is a question about why they differ. */
import { useCallback, useEffect, useState } from "react";

import { ApiError, EnvironmentDiff, Landscape, platform } from "./api";
import { Empty, Section, useStillHere } from "./ui";

export function EnvironmentsPanel(props: {
  eid: string | null;
  landscape: Landscape | null;
  onRefusal: (title: string, text: string) => void;
}) {
  const { eid, onRefusal } = props;
  const systems = props.landscape?.systems ?? [];
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [out, setOut] = useState<EnvironmentDiff | null>(null);
  const [busy, setBusy] = useState(false);
  const [bound, setBound] = useState<string[]>([]);
  const stillHere = useStillHere(eid);

  /* What has a binding. Without it the panel refuses with a 409 and leaves the operator to go
     and find the harvest dialog, which is where the only other reader button lives. */
  const refreshBound = useCallback(() => {
    if (!eid) return;
    platform.connectors(eid)
      .then((cs) => { if (stillHere(eid)) setBound(cs.connectors.map((x) => x.system_id)); })
      .catch(() => undefined);   // unknown is shown as unbound; the server refuses anyway
  }, [eid, stillHere]);

  useEffect(() => { setOut(null); setLeft(""); setRight(""); refreshBound(); }, [eid, refreshBound]);

  const run = useCallback(async () => {
    if (!eid || !left || !right) return;
    setBusy(true);
    try {
      const d = await platform.compareEnvironments(eid, left, right);
      if (stillHere(eid)) setOut(d);
    } catch (e) {
      if (e instanceof ApiError) onRefusal("Those two could not be compared", e.detail);
    } finally {
      setBusy(false);
    }
  }, [eid, left, right, onRefusal, stillHere]);

  if (!eid) return null;

  const picker = (value: string, set: (v: string) => void, label: string) => (
    <label className="field">
      <span className="eyebrow">{label}</span>
      <select value={value} onChange={(ev) => set(ev.target.value)} aria-label={label}>
        <option value="">—</option>
        {systems.map((s) => (
          <option key={s.system_id} value={s.system_id}>{s.system_id} ({s.role})</option>
        ))}
      </select>
    </label>
  );

  return (
    <Section
      title="Two environments, compared"
      note="Only the objects this engagement designed, read from both systems through bindings that cannot write. Neither side is the baseline."
      lamp={out ? (out.aligned ? "run" : "call") : undefined}
      status={out ? (out.aligned ? "they agree" : `${out.apart} apart`) : undefined}
      actions={
        <button className="btn" disabled={!left || !right || left === right || busy}
                onClick={() => void run()}>
          {busy ? "Reading both…" : "Compare"}
        </button>
      }
    >
      <div className="row" style={{ gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
        {picker(left, setLeft, "Compare this system")}
        {picker(right, setRight, "With this system")}
      </div>

      {/* A reader, offered where the question is asked. The system worth comparing is usually one
          no IR record binds to, so the writer path cannot even name its product — and a reader is
          what this needs anyway: a binding with no write half at all. */}
      {[left, right].filter((s) => s && !bound.includes(s)).map((s) => (
        <div key={s} className="verbatim calm" style={{ marginTop: 12 }}>
          {s} has nothing bound to it, so nothing can read it.
          <div className="row" style={{ marginTop: 10 }}>
            <button className="btn sm" onClick={() => void (async () => {
              try {
                await platform.bindReader(eid, s);
                refreshBound();
              } catch (err) {
                if (err instanceof ApiError) onRefusal(`${s} could not be read`, err.detail);
              }
            })()}>
              Bind a read-only connector to {s}
            </button>
          </div>
        </div>
      ))}

      {!out ? (
        <Empty
          title="Nothing compared yet"
          body="Pick two registered systems of the same product. The comparison reads both and writes to neither — which is why it needs only read access, and why a system bound read-only is exactly the right thing to point it at."
        />
      ) : (
        <>
          <p className={out.aligned ? "mut" : "verbatim"} style={{ margin: "12px 0" }}>
            {out.says}
          </p>

          {out.entities.filter((en) => !en.aligned).map((en) => (
            <div key={en.entity} style={{ marginBottom: 14 }}>
              <p className="mono mut" style={{ fontSize: 12.5, marginBottom: 6 }}>{en.entity}</p>
              <table className="tbl">
                <thead>
                  <tr><th scope="col">Object</th><th scope="col">Where</th>
                    <th scope="col">What the platform can say</th></tr>
                </thead>
                <tbody>
                  {en.only_in_left.map((r) => (
                    <tr key={`l${r.key}`}><td className="mono">{r.key}</td>
                      <td>only in {out.entities[0]?.left ?? left}</td>
                      <td className="mut">not present in the other system at all</td></tr>
                  ))}
                  {en.only_in_right.map((r) => (
                    <tr key={`r${r.key}`}><td className="mono">{r.key}</td>
                      <td>only in {out.entities[0]?.right ?? right}</td>
                      <td className="mut">not present in the other system at all</td></tr>
                  ))}
                  {en.differs.map((r) => (
                    <tr key={`d${r.key}`}><td className="mono">{r.key}</td>
                      <td>both, differing</td>
                      <td>{r.says}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}

          {out.unreadable.length > 0 && (
            /* A comparison that quietly dropped what it could not read would report alignment it
               never checked. */
            <ul className="mut" style={{ fontSize: 12.5, marginTop: 12 }}>
              {out.unreadable.map((u) => (
                <li key={u.entity} style={{ marginBottom: 4 }}>
                  {u.entity} was not compared — {u.reason}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Section>
  );
}
