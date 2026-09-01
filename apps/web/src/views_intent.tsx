/* Intent + Ledger — signed design in, hash-chained record out.
   Split out of views.tsx: nine screens in one file meant every rebuild collided. views.tsx is now
   the barrel App.tsx imports from. */
import { Fragment, useMemo, useState } from "react";
import type { IRRecordView, LedgerEntry } from "./api";
import { Empty, Pill, Seal, Section, Skeleton } from "./ui";
import { Chain, Facts, Hash, Meter, Track } from "./viz";
import type { ChainNode, TrackStop } from "./viz";
import { fmt, humanAction } from "./viewkit";
import "./views_intent.css";

/* ---------------- 5 · Intent ---------------- */

/**
 * The invariant this screen exists to make visible: a record without a signed source is unloadable,
 * and no code path executes unsigned intent. v1 rendered that as a grey column of workbook names —
 * the operator had to read the whole table to answer "is any of this unsigned?". The signature is
 * now the spine: counted in the strip, drawn on the track, and lamped on every row.
 */
export function IntentView(props: {
  records: IRRecordView[] | null;
  gaps: Record<string, string[]>;
  schemaVersion: string;
  writable: boolean;
  onLoad: () => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const records = props.records ?? [];

  /* A source counts as signed when it names a signer AND the workbook it came from. Either half
     missing and the provenance cannot be walked back to a person, which is the whole point. */
  const signed = useMemo(
    () => records.filter((r) => r.source?.signed_by && r.source?.workbook),
    [records],
  );
  const gapCount = useMemo(
    () => records.filter((r) => props.gaps[r.key]?.length).length,
    [records, props.gaps],
  );
  const workbooks = useMemo(
    () => new Set(records.map((r) => r.source?.workbook).filter(Boolean)).size,
    [records],
  );
  const tierA = useMemo(() => records.filter((r) => r.tier === "A").length, [records]);

  if (!props.records) return <Skeleton rows={5} />;

  /* Check → load → plan is a gate run, not three unrelated buttons: nothing plans until every
     record is signed and every gap is answered, so the track states are derived, never asserted. */
  const stops: TrackStop[] = [
    {
      id: "signed", label: "Signed", state: records.length === 0 ? "todo"
        : signed.length === records.length ? "done" : "blocked",
      sub: records.length === 0 ? "nothing loaded" : `${signed.length} of ${records.length} records`,
      badge: records.length ? <Meter value={signed.length} of={records.length}
                                     tone={signed.length === records.length ? "run" : "stop"}
                                     label="Signed records" /> : undefined,
    },
    {
      id: "loaded", label: "Loaded", state: records.length === 0 ? "current" : "done",
      sub: records.length === 0 ? "waiting on a record set" : `${records.length} records held`,
    },
    {
      id: "answered", label: "Answered", state: records.length === 0 ? "todo"
        : gapCount ? "blocked" : "done",
      sub: gapCount ? `${gapCount} waiting on a decision` : "no open questions",
      badge: records.length ? <Meter value={records.length - gapCount} of={records.length}
                                     tone={gapCount ? "call" : "run"} label="Answered" /> : undefined,
    },
    {
      id: "plans", label: "Plans", state: records.length === 0 || gapCount || signed.length !== records.length
        ? "todo" : "current",
      sub: gapCount ? "held until the questions are taken" : "the plan builds from here",
    },
  ];

  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">Signed intent · schema {props.schemaVersion || "—"}</div>
          <h1>What was asked for</h1>
        </div>
        <button className="btn primary" onClick={props.onLoad} disabled={!props.writable}>
          Load intent
        </button>
      </div>

      {/* The constants of the screen in one dense strip, so the answer to "how much, from where,
          signed by how many" costs a glance rather than a scroll through the table. */}
      <Facts items={[
        { k: "Records held", v: records.length },
        { k: "Signed", v: <Meter value={signed.length} of={records.length}
                                 tone={records.length && signed.length === records.length ? "run" : "stop"}
                                 label="Signed records" /> },
        { k: "Workbooks", v: workbooks || "—" },
        { k: "Tier A", v: tierA },
        { k: "Waiting on a decision", v: gapCount },
        { k: "Schema", v: props.schemaVersion || "—", mono: true },
      ]} />

      <Track stops={stops} note="From signature to plan" />

      {records.length === 0 ? (
        <Empty title="No signed intent yet"
               body="JIDOKA does not execute unsigned intent. Load a signed configuration record set — every record names the workbook it came from, who signed it and when — and the plan builds itself from there." />
      ) : (
        <Section title="Every record and who stands behind it" className="grow scrolls"
                 note={signed.length === records.length
                   ? "Every record names a signer and a workbook."
                   : `${records.length - signed.length} records name no signer. Those cannot be executed.`}
                 lamp={signed.length === records.length ? "run" : "stop"}
                 status={signed.length === records.length ? "All signed" : "Unsigned held"}>
          <div className="scroll-x">
            <table className="tbl intent-tbl">
              <thead>
                <tr>
                  <th>Object</th><th>Product</th><th>Tier</th><th>Binds to</th>
                  <th>Source</th><th>Signed by</th><th></th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => {
                  const ok = Boolean(r.source?.signed_by && r.source?.workbook);
                  return (
                    <Fragment key={r.key}>
                      {/* data-signed drives the left edge: a row that cannot execute is marked on the
                          row itself, not only in a column the eye has to travel to. */}
                      <tr data-signed={ok}>
                        <td>
                          <strong>{r.object}</strong>
                          {props.gaps[r.key] && (
                            <span className="pill" data-lamp="call" style={{ marginLeft: 8 }}>gap</span>
                          )}
                          <div className="mono dim" style={{ fontSize: 10.5 }}>{r.key}</div>
                        </td>
                        <td>{r.product}</td>
                        <td><span className="tier" data-t={r.tier}>{r.tier}</span></td>
                        <td className="mono">{r.system_binding}</td>
                        <td className="mono dim" title={String(r.source.workbook ?? "")}>
                          {String(r.source.workbook ?? "—")}
                        </td>
                        <td>
                          {ok ? <Seal name={String(r.source.signed_by)} /> : <span className="unsigned">Not signed</span>}
                          <div style={{ fontSize: 10 }}>{String(r.source.date ?? "")}</div>
                        </td>
                        <td>
                          <button className="btn ghost sm" onClick={() => setOpen(open === r.key ? null : r.key)}>
                            {open === r.key ? "Hide" : "What it asks for"}
                          </button>
                        </td>
                      </tr>
                      {open === r.key && (
                        <tr>
                          <td colSpan={7}>
                            {/* Opened detail answers the two questions the row raises: what this record
                                will do, and where the authority to do it comes from. */}
                            <Facts items={[
                              { k: "Workbook", v: String(r.source.workbook ?? "—"), mono: true },
                              { k: "Signed by", v: String(r.source.signed_by ?? "Not signed"), mono: true },
                              { k: "Signed on", v: String(r.source.date ?? "—"), mono: true },
                              { k: "Writes into", v: r.system_binding, mono: true },
                              { k: "External code", v: r.external_code || "none yet", mono: true },
                              { k: "Waits on", v: r.depends_on?.length ? r.depends_on.join(", ") : "nothing", mono: true },
                            ]} />
                            {props.gaps[r.key]?.length ? (
                              <div className="mut intent-gap">
                                Waiting on a decision: {props.gaps[r.key].join(", ")}
                              </div>
                            ) : null}
                            <div className="verbatim calm">{JSON.stringify(r.intent, null, 2)}</div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </>
  );
}

/* ---------------- 6 · Ledger ---------------- */

/**
 * The table was the best thing in v1 and keeps its columns and its monospace exactly. What it could
 * not do was carry its own claim: "16 links verified" beside a column of unrelated-looking hashes is
 * an assertion, and this platform exists so that nothing has to be taken on assertion. The chain
 * panel draws the linkage — each entry's hash beside the prior hash it claims to follow, on a drawn
 * line that breaks at the first pair that does not reconcile.
 */
export function LedgerView(props: {
  entries: LedgerEntry[] | null;
  chainBroken: string | null;
  genesis?: string;
}) {
  const [q, setQ] = useState("");
  const rows = useMemo(() => {
    const all = props.entries ?? [];
    if (!q.trim()) return all;
    const n = q.toLowerCase();
    return all.filter((e) =>
      [e.task, e.action, e.actor, e.detail].some((v) => String(v).toLowerCase().includes(n)));
  }, [props.entries, q]);

  /* Reconciliation is done here, in the browser, against what the server sent — that is the point.
     Entry n links if its `prev` is the hash of entry n-1; the first entry links to the genesis. The
     first failure is marked and everything after it is downstream of a break, so it is marked too. */
  const links = useMemo(() => {
    const all = props.entries ?? [];
    const genesis = props.genesis ?? "0".repeat(64);
    let seenBreak = false;
    return all.map((e, i) => {
      const expected = i === 0 ? genesis : all[i - 1].hash;
      const ok = !seenBreak && e.prev === expected;
      if (!ok) seenBreak = true;
      return { entry: e, expected, ok, index: i };
    });
  }, [props.entries, props.genesis]);

  const firstBreak = links.find((l) => !l.ok);
  const verified = links.filter((l) => l.ok).length;

  if (!props.entries) return <Skeleton rows={6} />;

  const nodes: ChainNode[] = links.map((l) => ({
    id: l.entry.hash || `entry-${l.index}`,
    lamp: l.ok ? "run" : "stop",
    broken: !l.ok,
    title: (
      <>
        <span className="mono dim">{String(l.index + 1).padStart(3, "0")}</span>
        {humanAction(l.entry.action)}
      </>
    ),
    /* Actor and time only. The task key and the detail stay off this panel: the table beside it is
       the auditor's raw copy and already carries both, and this panel's job is the hash comparison. */
    meta: `${l.entry.actor} · ${fmt(l.entry.ts)}`,
    /* The two hashes sit side by side because that is the comparison being claimed. Hovering either
       gives the full value, so an operator can check the link by eye without leaving the screen. */
    body: (
      <div className="link-pair">
        <span className="link-leg">
          <span className="link-k">follows</span>
          <Hash value={l.entry.prev} />
        </span>
        <span className={l.ok ? "link-arrow ok" : "link-arrow bad"} aria-hidden>→</span>
        <span className="link-leg">
          <span className="link-k">this entry</span>
          <Hash value={l.entry.hash} prev={l.entry.prev} />
        </span>
        {!l.ok && (
          <span className="link-note">
            expected <Hash value={l.expected} />
          </span>
        )}
      </div>
    ),
  }));

  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">Ledger · hash-chained, append only</div>
          <h1>Everything that happened</h1>
        </div>
        <div className="row">
          <input type="search" placeholder="Filter by task, actor or action"
                 value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 260 }}
                 aria-label="Filter the ledger" />
          <Pill lamp={props.chainBroken ? "stop" : "run"}>
            {props.chainBroken ? "Broken" : `${props.entries.length} links verified`}
          </Pill>
        </div>
      </div>

      {props.chainBroken && (
        <div className="banner" data-lamp="stop">
          <span className="bar" />
          <div>
            <strong>The chain does not verify. Approvals are suspended.</strong>
            <div className="verbatim" style={{ marginTop: 8 }}>{props.chainBroken}</div>
          </div>
        </div>
      )}

      <Facts items={[
        { k: "Entries", v: props.entries.length },
        { k: "Links reconciled", v: <Meter value={verified} of={links.length}
                                           tone={firstBreak ? "stop" : "run"} label="Links reconciled" /> },
        { k: "Head", v: <Hash value={props.entries[props.entries.length - 1]?.hash ?? ""} />, mono: true },
        {
          k: "First break",
          v: firstBreak ? `entry ${firstBreak.index + 1}` : "none",
          mono: true,
        },
        { k: "Showing", v: `${rows.length} of ${props.entries.length}`, mono: true },
      ]} />

      <div className="board fill ledger-board">
        <Section title="Everything that happened" className="grow scrolls span2"
                 note="Newest last. Filter narrows this table, never the chain.">
          <div className="scroll-x">
            <table className="tbl">
              <thead>
                <tr><th>#</th><th>When</th><th>Task</th><th>What happened</th><th>Who</th><th>Detail</th><th>Hash</th></tr>
              </thead>
              <tbody>
                {rows.map((e, i) => (
                  <tr key={e.hash}>
                    <td className="num dim">{i + 1}</td>
                    <td className="num">{fmt(e.ts)}</td>
                    <td className="mono">{e.task}</td>
                    <td>{humanAction(e.action)}</td>
                    <td>{e.actor}</td>
                    <td className="mut">{e.detail}</td>
                    {/* Head-and-tail, not the full 64 characters: rendered raw it overran the column
                        and clipped under the panel edge, which reads as data loss. The whole value is
                        on the title, and the chain panel beside this one carries the comparison. */}
                    <td><Hash value={e.hash} prev={e.prev} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <div className="mut" style={{ padding: 14 }}>Nothing matches that filter.</div>}
          </div>
        </Section>

        <Section title="The chain, link by link" className="grow scrolls"
                 note={firstBreak
                   ? `Entry ${firstBreak.index + 1} does not follow the entry before it.`
                   : "Each entry names the hash before it, and each one matches."}
                 lamp={firstBreak ? "stop" : "run"}
                 status={firstBreak ? "Break at " + (firstBreak.index + 1) : `${verified} links hold`}>
          {links.length === 0
            ? <div className="mut">Nothing has happened yet.</div>
            : <Chain nodes={nodes} dense />}
        </Section>
      </div>
    </>
  );
}
