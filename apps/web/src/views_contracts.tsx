/* One writer, declared readers (ADR-0034).
   A customisation is never module-local: custom-string4 is written by EC and read by Time Off
   eligibility, EE reporting and the ECC payroll interface. As a field that is four surprises
   waiting for a release; as a contract it is one declaration every one of them is already in. */
import { useCallback, useEffect, useState } from "react";

import { ApiError, Contracts, platform } from "./api";
import { Empty, Section } from "./ui";

export function ContractsPanel(props: {
  eid: string | null;
  onRefusal: (title: string, text: string) => void;
}) {
  const { eid, onRefusal } = props;
  const [out, setOut] = useState<Contracts | null>(null);

  const load = useCallback(() => {
    if (!eid) return;
    platform.contracts(eid)
      .then(setOut)
      .catch((e) => { if (e instanceof ApiError && !e.notAvailable) onRefusal("The contracts", e.detail); });
  }, [eid, onRefusal]);

  useEffect(() => { setOut(null); load(); }, [load]);

  if (!eid || !out) return null;

  return (
    <Section
      title="Cross-module contracts"
      note={out.rule}
      lamp={out.conflicts.length ? "stop" : out.undeclared_readers.length ? "call" : out.contracts.length ? "run" : undefined}
      status={out.conflicts.length ? `${out.conflicts.length} object(s) claimed by two modules`
        : out.undeclared_readers.length ? `${out.undeclared_readers.length} undeclared reader(s)`
          : out.contracts.length ? `${out.contracts.length} contracted` : undefined}
    >
      {out.conflicts.map((c) => (
        /* The platform's own words: a conflict is a refusal, and a refusal is quoted. */
        <p key={c.key} className="verbatim" style={{ marginBottom: 12 }}>{c.says}</p>
      ))}

      {out.contracts.length === 0 ? (
        <Empty
          title="Nothing is contracted here"
          body="Delivered standard configuration needs no contract. This is for the objects a programme builds — which are exactly the objects that later surprise it."
        />
      ) : (
        <table className="tbl">
          <thead>
            <tr><th>Object</th><th>Written by</th><th>Read by</th><th>Feeds</th><th>Statutory</th></tr>
          </thead>
          <tbody>
            {out.contracts.map((c) => (
              <tr key={c.key}>
                <td className="mono">{c.key}</td>
                <td>{c.owner}</td>
                <td>{c.consumers.join(", ") || <span className="mut">nobody registered</span>}</td>
                <td>{c.feeds.join(", ") || <span className="mut">—</span>}</td>
                <td>{c.statutory || <span className="mut">—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {out.undeclared_readers.length > 0 && (
        <ul className="mut" style={{ fontSize: 12.5, marginTop: 12 }}>
          {out.undeclared_readers.map((r) => (
            <li key={`${r.reader}->${r.reads}`} style={{ marginBottom: 6 }}>{r.says}</li>
          ))}
        </ul>
      )}
    </Section>
  );
}
