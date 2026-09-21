/* The platform's account of itself, and every engagement at once.
   Two screens that report on JIDOKA rather than on the configuration — the first because a
   governance tool that publishes only its successes is asking to be trusted on its own account,
   the second because a partner running eleven programmes asks one question and had to open eleven
   screens to answer it. */
import { useCallback, useEffect, useState } from "react";

import { Accountability, ApiError, Portfolio, platform } from "./api";
import { Empty, Section } from "./ui";

export function PortfolioView(props: { onRefusal: (title: string, text: string) => void }) {
  const { onRefusal } = props;
  const [out, setOut] = useState<Portfolio | null>(null);

  useEffect(() => {
    platform.portfolio()
      .then(setOut)
      .catch((e) => { if (e instanceof ApiError && !e.notAvailable) onRefusal("The portfolio", e.detail); });
  }, [onRefusal]);

  if (!out) return <Empty title="Reading every engagement" body="One line each, worst first." />;

  return (
    <Section
      title="Every engagement"
      note="The same numbers each engagement's own screen shows, run across the store. A roll-up that computed anything differently would be a second opinion, and the first argument in every steering meeting would be about which one is right."
      lamp={out.need_a_person ? "call" : out.total ? "run" : undefined}
      status={out.total ? `${out.need_a_person} of ${out.total} need a person` : undefined}
    >
      <p className="mut" style={{ marginBottom: 12 }}>{out.says}</p>
      {out.engagements.length === 0 ? (
        <p className="mut">No engagements on this kernel yet.</p>
      ) : (
        <table className="tbl">
          <thead>
            <tr><th>Engagement</th><th>Client</th><th>Phase</th><th className="num">Records</th>
              <th className="num">Proven</th><th>Needs a person</th></tr>
          </thead>
          <tbody>
            {out.engagements.map((e) => (
              /* No row highlight: the list is already worst-first and the last column says what
                 is wrong in words. A colour somebody has to decode, on a row whose sentence
                 already says it, is decoration. */
              <tr key={e.engagement_id}>
                <td>{e.name}</td>
                <td>{e.client}</td>
                <td>{e.phase}</td>
                <td className="num">{e.records}</td>
                {/* Never 0% for "nothing claimed yet": a fraction of nothing reads as a failure
                    and it is the absence of a claim. */}
                <td className="num">{e.proven === null ? "—" : `${Math.round(e.proven * 100)}%`}</td>
                <td>{e.needs_a_person || <span className="mut">nothing</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Section>
  );
}

export function AccountabilityPanel(props: {
  eid: string | null;
  onRefusal: (title: string, text: string) => void;
}) {
  const { eid, onRefusal } = props;
  const [out, setOut] = useState<Accountability | null>(null);

  const load = useCallback(() => {
    if (!eid) return;
    platform.accountability(eid)
      .then(setOut)
      .catch((e) => { if (e instanceof ApiError && !e.notAvailable) onRefusal("The account", e.detail); });
  }, [eid, onRefusal]);

  useEffect(() => { setOut(null); load(); }, [load]);

  if (!out) return null;

  return (
    <Section
      title="What I got wrong"
      note="Where this platform was wrong, and where its gates stopped work that was fine. Nothing here is scored: a single number would be quoted, and the questions are the product."
      status={out.refusals.fired ? `${out.refusals.fired} refusal(s), ${out.refusals.still_standing} still standing` : "no refusals yet"}
    >
      <p className="verbatim calm" style={{ marginBottom: 12 }}>{out.says}</p>

      {out.refusals.gates.length > 0 && (
        <table className="tbl">
          <thead>
            <tr><th>Gate</th><th className="num">Fired</th><th className="num">Cleared</th>
              <th className="num">Standing</th><th>Reads as</th></tr>
          </thead>
          <tbody>
            {out.refusals.gates.map((g) => (
              <tr key={g.gate}>
                <td className="mono">{g.gate}</td>
                <td className="num">{g.fired}</td>
                <td className="num">{g.cleared}</td>
                <td className="num">{g.standing}</td>
                <td>{g.reads_as}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {out.mistakes.drift_after_verified.length > 0 && (
        <p className="mut" style={{ marginTop: 12, fontSize: 12.5 }}>
          I called these verified and the system has since disagreed:{" "}
          {out.mistakes.drift_after_verified.join(", ")}. That is being wrong, not the system
          changing under a correct reading.
        </p>
      )}

      {/* Published beside the numbers rather than in a footnote: the gap between what a metric
          covers and what a reader assumes it covers is where every dishonest dashboard lives. */}
      <details style={{ marginTop: 12 }}>
        <summary className="mut" style={{ fontSize: 12.5, cursor: "pointer" }}>
          What these numbers cannot tell you
        </summary>
        <ul className="mut" style={{ fontSize: 12.5, marginTop: 8 }}>
          {out.unmeasurable.map((u) => <li key={u} style={{ marginBottom: 6 }}>{u}</li>)}
        </ul>
      </details>
    </Section>
  );
}
