/* The platform's position, and the loop that closes it (M6, ADR-0033).
   An objection is not a gate — nothing here blocks anything, and it must not look as though it
   does. It is the platform disagreeing with a decision it has no standing to prevent, saying so
   once with the consequence and the recommendation, and coming back at the phase where the thing
   it predicted becomes observable. */
import { useCallback, useEffect, useState } from "react";

import { ApiError, ObjectionRow, platform } from "./api";
import { Empty, Field, Section } from "./ui";

export function ObjectionsPanel(props: {
  eid: string | null;
  canOverride: boolean;          // approve — the platform is never the one who sets its own position aside
  onRefusal: (title: string, text: string) => void;
}) {
  const { eid, onRefusal } = props;
  const [rows, setRows] = useState<ObjectionRow[] | null>(null);
  const [due, setDue] = useState<ObjectionRow[]>([]);
  const [phase, setPhase] = useState("");
  const [who, setWho] = useState("");
  const [why, setWhy] = useState("");
  const [on, setOn] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!eid) return;
    platform.objections(eid)
      .then((o) => { setRows(o.objections); setDue(o.due_for_revisit); setPhase(o.phase); })
      .catch((e) => { if (e instanceof ApiError && !e.notAvailable) onRefusal("The objections", e.detail); });
  }, [eid, onRefusal]);

  useEffect(() => { setRows(null); setOn(null); load(); }, [load]);

  if (!eid) return null;

  const override = async (oid: string) => {
    try {
      await platform.overrideObjection(eid, oid, who.trim(), why.trim());
      setOn(null); setWho(""); setWhy("");
      load();
    } catch (e) {
      if (e instanceof ApiError) onRefusal("That override was not recorded", e.detail);
    }
  };

  const revisit = async (oid: string) => {
    try {
      const out = await platform.revisitObjection(eid, oid);
      onRefusal("What happened since", `It said: ${out.objection_said}\n\nSet aside by ${out.overridden_by}.\n\n${out.says}`);
      load();
    } catch (e) {
      if (e instanceof ApiError) onRefusal("That revisit was not recorded", e.detail);
    }
  };

  const open = (rows ?? []).filter((o) => o.status === "open");

  return (
    <Section
      title="Where I disagree"
      note="Stated once, with the consequence and what I would do instead — then I defer. This blocks nothing: the gates are the invariants, and they refuse. Overriding one takes a name."
      lamp={due.length ? "call" : open.length ? "idle" : undefined}
      status={due.length ? `${due.length} due a revisit` : open.length ? `${open.length} open` : undefined}
    >
      {rows === null ? (
        <p className="mut">Reading the chain.</p>
      ) : rows.length === 0 ? (
        <Empty title="No objections" body="I have nothing to disagree with on this engagement yet. Run the crew and I will say so if I do." />
      ) : (
        <>
          {due.length > 0 && (
            <p className="verbatim" style={{ marginBottom: 12 }}>
              {due.length} objection(s) were set aside and the engagement is now at {phase}, which
              is where what they predicted becomes observable. Revisiting is not me asking to be
              told I was right — it is the loop closing, which is what makes the next one worth
              hearing.
            </p>
          )}
          <table className="tbl">
            <thead>
              <tr><th>About</th><th>What I found</th><th>If it goes ahead</th><th>I would</th>
                <th>Where it stands</th><th /></tr>
            </thead>
            <tbody>
              {rows.map((o) => (
                <tr key={o.objection_id}>
                  <td className="mono">{o.about}</td>
                  <td>{o.finding}</td>
                  <td>{o.consequence}</td>
                  <td>{o.recommendation}</td>
                  <td>
                    {o.status === "open" ? <span className="mut">open</span>
                      : o.status === "overridden"
                        ? <>set aside by <strong>{o.overridden_by}</strong>{o.override_reason ? ` — ${o.override_reason}` : ""}</>
                        : o.status === "withdrawn" ? <span className="mut">I withdrew it</span>
                          : <>revisited — {o.what_happened}</>}
                  </td>
                  <td>
                    {o.status === "open" && props.canOverride && (
                      <button className="btn" onClick={() => setOn(o.objection_id)}>Override</button>
                    )}
                    {due.some((d) => d.objection_id === o.objection_id) && (
                      <button className="btn" onClick={() => void revisit(o.objection_id)}>
                        Revisit
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {on && (
            <div className="row" style={{ gap: 12, alignItems: "flex-end", marginTop: 14, flexWrap: "wrap" }}>
              {/* A person, never a role and never "the client". */}
              <Field label="Overridden by" value={who} placeholder="T. Mabaso" onChange={setWho} />
              <Field label="Because" value={why} placeholder="the vendor confirmed it in writing"
                     onChange={setWhy} />
              <button className="btn" disabled={!who.trim() || !why.trim()}
                      onClick={() => void override(on)}>
                Record the override
              </button>
              <button className="btn" onClick={() => setOn(null)}>Cancel</button>
            </div>
          )}
        </>
      )}
    </Section>
  );
}
