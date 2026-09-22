/* One writer, declared readers (ADR-0034).
   A customisation is never module-local: custom-string4 is written by EC and read by Time Off
   eligibility, EE reporting and the ECC payroll interface. As a field that is four surprises
   waiting for a release; as a contract it is one declaration every one of them is already in. */
import { useCallback, useEffect, useState } from "react";

import { ApiError, Contracts, TypeCheck, platform } from "./api";
import { Empty, Field, Section, useStillHere } from "./ui";

/* C1: the rule travels with the value. Every message below is the platform's own — a rejection
   that needed rewording before it could go in a report would be reworded by hand, once, and then
   drift away from what the type-checker actually enforces. */
export function TypesPanel(props: {
  eid: string | null;
  onRefusal: (title: string, text: string) => void;
}) {
  const { eid, onRefusal } = props;
  const [out, setOut] = useState<TypeCheck | null>(null);
  const stillHere = useStillHere(eid);

  useEffect(() => {
    setOut(null);
    if (!eid) return;
    platform.types(eid)
      .then((t) => { if (stillHere(eid)) setOut(t); })
      .catch((e) => { if (e instanceof ApiError && !e.notAvailable) onRefusal("The type-check", e.detail); });
  }, [eid, onRefusal]);

  if (!eid || !out) return null;
  const failures = [...out.disagrees, ...out.absent];

  return (
    <Section
      title="What the types say"
      note={out.method}
      lamp={out.holds ? "run" : "stop"}
      status={out.holds ? "signed intent type-checks" : `${failures.length} do not hold`}
    >
      {failures.length === 0 ? (
        <p className="mut">
          Every refinement in this design holds, and every field a type requires is set. Records
          without refinements are not checked and are not counted here — an untyped value is
          unconstrained, not approved.
        </p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {failures.map((f) => (
            <li key={`${f.key}${f.path}`} style={{ marginBottom: 10 }}>
              <span className="verbatim" style={{ display: "block" }}>{f.says}</span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

export function ContractsPanel(props: {
  eid: string | null;
  canSetPool: boolean;          // approve — the number is somebody's agreement, not the platform's
  onRefusal: (title: string, text: string) => void;
}) {
  const { eid, onRefusal } = props;
  const [out, setOut] = useState<Contracts | null>(null);
  const [pool, setPool] = useState("");
  const stillHere = useStillHere(eid);

  const load = useCallback(() => {
    if (!eid) return;
    platform.contracts(eid)
      .then((c) => { if (stillHere(eid)) setOut(c); })
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
      {/* The budget, above the list it is spent on. An empty pool is not a fault — it is a
          number somebody agreed to, reached. */}
      <p className={out.delta_pool.over ? "verbatim" : "mut"} style={{ marginBottom: 12 }}>
        {out.delta_pool.says}
      </p>

      {props.canSetPool && (
        <div className="row" style={{ gap: 12, alignItems: "flex-end", marginBottom: 14, flexWrap: "wrap" }}>
          <Field label="Customisations agreed" value={pool} placeholder={String(out.delta_pool.of)}
                 onChange={setPool} />
          <button className="btn" disabled={!pool.trim()} onClick={() => void (async () => {
            try {
              await platform.setDeltaPool(eid, Number(pool) || 0);
              setPool("");
              load();
            } catch (e) {
              if (e instanceof ApiError) onRefusal("That pool was not recorded", e.detail);
            }
          })()}>
            Record the pool
          </button>
        </div>
      )}

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
            <tr><th scope="col">Object</th><th scope="col">Written by</th><th scope="col">Read by</th><th scope="col">Feeds</th><th scope="col">Statutory</th></tr>
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
