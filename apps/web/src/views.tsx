/* The working views. Every value shown is read back from the platform; nothing is asserted locally. */
import { Fragment, useMemo, useState } from "react";
import type {
  ArmedTarget, Connector, DecisionPoint, EngagementDetail, Evidence, ExecutionResult, IRRecordView,
  Landscape, LedgerEntry, Plan, StepTransport,
} from "./api";
import { STAGE_WORDS, dpRelease, type Lane, type Milestone, type Station } from "./derive";
import { Empty, Pill, Section, Skeleton } from "./ui";

const fmt = (ts: string) => (ts || "").replace("T", " ").replace("Z", "");

/* ---------------- 1 · Line: the state of the whole engagement at a glance ---------------- */
export function LineView(props: {
  detail: EngagementDetail | null;
  lanes: Lane[];
  plan: Plan | null;
  planBlock: string | null;
  entries: LedgerEntry[] | null;
  dps: DecisionPoint[];
  chainBroken: string | null;
  onAdvance: (to: string) => void;
  canAdvance: boolean;
}) {
  const d = props.detail;
  if (!d) return <Skeleton rows={4} tall />;

  const approved = props.lanes.flatMap((l) => l.stations).filter((s) => s.stage === "approved").length;
  const total = props.lanes.flatMap((l) => l.stations).length;
  const waiting = props.dps.filter((x) => !x.resolution).length;

  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">{d.client} · engagement {d.engagement_id}</div>
          <h1>{d.name}</h1>
        </div>
        <div className="row">
          <Pill lamp={props.chainBroken ? "stop" : "run"}>
            {props.chainBroken ? "Chain broken" : "Ledger verified"}
          </Pill>
        </div>
      </div>

      <div className="counters">
        <Counter label="Signed intent records" value={d.ir_records} sub="loaded from a signed source" />
        <Counter label="Stations approved" value={`${approved}/${total || 0}`}
                 sub={total ? "checkpoints on the plan" : "no plan built yet"} />
        <Counter label="Waiting on a person" value={waiting}
                 sub={waiting ? "decisions nobody has taken" : "nothing is blocked on a human"} lamp={waiting ? "call" : "run"} />
        <Counter label="Ledger entries" value={d.ledger_entries} sub="hash-chained, append only" />
      </div>

      {props.planBlock && (
        <div className="banner" data-lamp="call" style={{ marginTop: 8 }}>
          <span className="bar" />
          <div>
            <strong>The plan is blocked.</strong>
            <div className="verbatim calm" style={{ marginTop: 8 }}>{props.planBlock}</div>
            <div className="mut" style={{ marginTop: 8 }}>
              Resolve the open decisions and the plan builds itself.
            </div>
          </div>
        </div>
      )}

      <div className="board" style={{ marginTop: 8 }}>
      {/* The phase rail: where this engagement has got to, and what advancing costs. */}
      <Section title="Phase" note="Forward only. A phase advance declares work complete, so it is an approval-grade act.">
        <div className="phases">
          {d.phases.map((p, i) => {
            const at = d.phases.indexOf(d.phase);
            const state = i < at ? "done" : i === at ? "now" : "next";
            return (
              <div className="phase" key={p} data-state={state}>
                <div className="n">{String(i + 1).padStart(2, "0")}</div>
                <div className="t">{p}</div>
                <div className="mono dim" style={{ fontSize: 10, marginTop: 4 }}>
                  {state === "done" ? "complete" : state === "now" ? "current" : "not started"}
                </div>
              </div>
            );
          })}
        </div>
        <div className="row" style={{ marginTop: 14 }}>
          {d.next_phases.length === 0 ? (
            <span className="mut">This is the final phase.</span>
          ) : (
            d.next_phases.map((n) => (
              <button key={n} className="btn primary" disabled={!props.canAdvance}
                      onClick={() => props.onAdvance(n)}>
                Advance to {n}
              </button>
            ))
          )}
          {!props.canAdvance && d.next_phases.length > 0 && (
            <span className="mut">Waiting on someone who may approve.</span>
          )}
        </div>
      </Section>

      <Section title="Recent activity" note="The last of the ledger, newest first.">
        {!props.entries ? <Skeleton /> : props.entries.length === 0 ? (
          <span className="mut">Nothing has happened on this engagement yet.</span>
        ) : (
          <div className="chain">
            {[...props.entries].reverse().slice(0, 12).map((e) => (
              <div className="link" key={e.hash} data-lamp={lampForAction(e.action)}>
                <div className="spine"><span className="node" /></div>
                <div>
                  <div className="row" style={{ gap: 8 }}>
                    <strong>{humanAction(e.action)}</strong>
                    <span className="mono dim">{e.task}</span>
                  </div>
                  <div className="mut" style={{ fontSize: 12.5 }}>
                    {e.actor}{e.detail ? ` · ${e.detail}` : ""}
                  </div>
                  <div className="mono dim" style={{ fontSize: 10.5, marginTop: 2 }}>{fmt(e.ts)}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
      </div>
    </>
  );
}

function Counter(props: { label: string; value: string | number; sub: string; lamp?: string }) {
  return (
    <div style={{ padding: "10px 12px" }}>
      <div className="eyebrow">{props.label}</div>
      <div className="figure" style={{ marginTop: 4, color: props.lamp === "call" ? "var(--call)" : undefined }}>
        {props.value}
      </div>
      <div className="mut" style={{ fontSize: 11, marginTop: 4 }}>{props.sub}</div>
    </div>
  );
}

export function humanAction(a: string) {
  const words: Record<string, string> = {
    CREATED: "Engagement opened", LOADED: "Signed intent loaded", BUILT: "Plan built",
    SNAPSHOT: "Before-snapshot taken", EXECUTED: "Change executed", VALIDATED: "Change validated",
    APPROVED: "Approved", ROLLED_BACK: "Rolled back", LINE_STOP: "Line stopped",
    LINE_RESUME: "Line released", PHASE_ADVANCED: "Phase advanced",
    SYSTEM_REGISTERED: "System registered", DP_RAISED: "Decision raised", DP_RESOLVED: "Decision taken",
  };
  return words[a] ?? a.replace(/_/g, " ").toLowerCase();
}

function lampForAction(a: string) {
  if (a === "APPROVED" || a === "VALIDATED") return "run";
  if (a === "LINE_STOP" || a === "ROLLED_BACK") return "stop";
  if (a === "DP_RAISED") return "call";
  return "blue";
}

/* ---------------- 2 · Work: the execution floor ---------------- */
export function WorkView(props: {
  lanes: Lane[];
  planBlock: string | null;
  writable: boolean;
  busy: string | null;
  onStage: (s: Station, action: string, detail?: string) => void;
  onApprove: (s: Station) => void;
  onRollback: (s: Station) => void;
}) {
  if (props.planBlock) {
    return (
      <Empty title="No plan to work"
             body="The plan is blocked, so there are no checkpoints to run yet."
             verbatim={props.planBlock} />
    );
  }
  if (!props.lanes.length) return <Skeleton rows={5} tall />;

  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">Execution</div>
          <h1>The floor</h1>
        </div>
        <span className="mut">A station opens when the one before it is approved.</span>
      </div>

      {/* One panel per phase, side by side — a lane is a column on the floor, not a full-width band. */}
      <div className="board">
      {props.lanes.map((lane, i) => (
        <Section key={i} title={`Phase ${i + 1}`}
                 note={`${lane.stations.filter((s) => s.stage === "approved").length} of ${lane.stations.length} approved`}
                 lamp={lane.lamp} status={laneWord(lane.lamp)}>
          <div className="grid">
            {lane.stations.map((s) => (
              <StationCard key={s.step.key} s={s} {...props} />
            ))}
          </div>
        </Section>
      ))}
      </div>
    </>
  );
}

function stationLamp(s: Station) {
  if (s.stage === "rolledback") return "stop";
  if (s.stage === "approved") return "run";
  if (s.stage === "validated") return "call";
  if (s.locked) return "idle";
  return s.stage === "waiting" ? "idle" : "blue";
}

/** The plan speaks in substrate verbs. A person reads what actually happens. */
function stepWords(step: { action: string; system: string; key: string }) {
  // key is product:object:code, and "?" is the platform's word for "no external code yet".
  const [, object = step.key, code = ""] = step.key.split(":");
  const what = code && code !== "?" ? `${object} ${code}` : `a new ${object}`;
  switch (step.action) {
    case "API_WRITE": return `Write ${what} into ${step.system}`;
    case "FILE_IMPORT_HUMAN": return `Import ${what} into ${step.system} — by hand`;
    case "UI_INSTRUCTION_HUMAN": return `Configure ${what} by hand in ${step.system}`;
    default: return `${step.action} ${what}`;
  }
}

function laneWord(l: string) {
  return l === "run" ? "Complete" : l === "stop" ? "Rolled back" : l === "call" ? "In progress" : "Not started";
}

function StationCard(props: {
  s: Station; writable: boolean; busy: string | null;
  onStage: (s: Station, action: string, detail?: string) => void;
  onApprove: (s: Station) => void;
  onRollback: (s: Station) => void;
}) {
  const { s } = props;
  const off = !props.writable || s.locked || props.busy === s.step.key;
  return (
    <div className="station" data-lamp={stationLamp(s)} data-locked={s.locked}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <div className="row" style={{ gap: 8 }}>
            <span className="title">{stepWords(s.step)}</span>
            <span className="tier" data-t={s.step.tier}>Tier {s.step.tier}</span>
          </div>
          <div className="key">{s.step.key} · {s.step.system}</div>
        </div>
        <Pill lamp={stationLamp(s)}>{STAGE_WORDS[s.stage]}</Pill>
      </div>

      {s.locked && (
        <div className="mut" style={{ fontSize: 12.5 }}>
          Locked until the station before it is approved.
        </div>
      )}

      {!s.locked && (
        <div className="row">
          {s.stage === "waiting" && (
            <button className="btn" disabled={off}
                    onClick={() => props.onStage(s, "SNAPSHOT", "before-snapshot captured")}>
              Take before-snapshot
            </button>
          )}
          {/* Execution is refused without a snapshot, so the control does not exist until there is one. */}
          {s.stage === "snapshot" && (
            <button className="btn primary" disabled={off}
                    onClick={() => props.onStage(s, "EXECUTED", s.step.action)}>
              Execute
            </button>
          )}
          {s.stage === "executed" && (
            <button className="btn" disabled={off}
                    onClick={() => props.onStage(s, "VALIDATED", "read back and compared")}>
              Validate
            </button>
          )}
          {s.stage === "validated" && (
            <button className="btn primary" disabled={off} onClick={() => props.onApprove(s)}>
              Approve
            </button>
          )}
          {s.stage === "approved" && <span className="mut">Approved and closed.</span>}
          {s.stage === "rolledback" && (
            <span className="mut">Rolled back. A fresh snapshot is needed before re-running.</span>
          )}
          {(s.stage === "executed" || s.stage === "validated") && (
            <button className="btn danger sm" disabled={off} onClick={() => props.onRollback(s)}>
              Roll back
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/* ---------------- 3 · Decisions ---------------- */
export function DecisionsView(props: {
  dps: DecisionPoint[] | null;
  irGaps: Record<string, string[]>;
  writable: boolean;
  onResolve: (dp: DecisionPoint) => void;
  onRaise: () => void;
}) {
  const open = (props.dps ?? []).filter((d) => !d.resolution);
  const done = (props.dps ?? []).filter((d) => d.resolution);
  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">Decisions</div>
          <h1>Waiting on a person</h1>
        </div>
        <button className="btn" onClick={props.onRaise} disabled={!props.writable}>Raise a decision</button>
      </div>

      {Object.keys(props.irGaps).length > 0 && (
        <div className="banner" data-lamp="call">
          <span className="bar" />
          <div>
            <strong>{Object.keys(props.irGaps).length} record(s) of signed intent have gaps.</strong>
            <div className="mut" style={{ marginTop: 4 }}>
              A blank value in a signed workbook is a question nobody answered. Until it is answered the
              plan will not build.
            </div>
            <div className="mono dim" style={{ marginTop: 8, fontSize: 11 }}>
              {Object.entries(props.irGaps).map(([k, v]) => `${k} → ${v.join(", ")}`).join(" · ")}
            </div>
          </div>
        </div>
      )}

      {!props.dps ? <Skeleton rows={4} tall /> : (
        <div className="board">
          <Section title="Open" note={`${open.length} unresolved`} lamp={open.length ? "call" : "run"}
                   status={open.length ? "Waiting on a person" : "Nothing open"}>
            {open.length === 0 ? <span className="mut">Nothing is blocked on a human right now.</span> : (
              <div className="grid">{open.map((d) => <DPCard key={d.dp_id} dp={d} {...props} />)}</div>
            )}
          </Section>
          {done.length > 0 && (
            <Section title="Taken" note={`${done.length} decided`} lamp="run" status="Decided">
              <div className="grid">{done.map((d) => <DPCard key={d.dp_id} dp={d} {...props} />)}</div>
            </Section>
          )}
        </div>
      )}
    </>
  );
}

function DPCard(props: { dp: DecisionPoint; writable: boolean; onResolve: (dp: DecisionPoint) => void }) {
  const { dp } = props;
  const resolved = !!dp.resolution;
  return (
    <div className="station" data-lamp={resolved ? "run" : "call"}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="row" style={{ gap: 8 }}>
          <span className="mono mut">{dp.dp_id}</span>
          <span className="tier">{dp.dp_type}</span>
        </div>
        <Pill lamp={resolved ? "run" : "call"}>{resolved ? "Taken" : "Waiting on a person"}</Pill>
      </div>
      <div style={{ fontSize: 15 }}>{dp.question}</div>
      <div className="mut" style={{ fontSize: 12.5 }}>Owner: {dp.owner}</div>
      {!resolved ? (
        <>
          <div className="banner" data-lamp="blue" style={{ margin: 0 }}>
            <span className="bar" />
            <div style={{ fontSize: 12.5 }}>{dpRelease(dp)}</div>
          </div>
          <div>
            <button className="btn primary sm" disabled={!props.writable} onClick={() => props.onResolve(dp)}>
              Take this decision
            </button>
          </div>
        </>
      ) : (
        <div className="mono mut" style={{ fontSize: 12 }}>
          {dp.resolution!.value} · decided by {dp.resolution!.by}
          {dp.resolution!.evidence ? ` · evidence ${dp.resolution!.evidence}` : ""}
          {dp.resolution!.second_approver ? ` · countersigned ${dp.resolution!.second_approver}` : ""}
        </div>
      )}
    </div>
  );
}

/* ---------------- 4 · Landscape ---------------- */
export function LandscapeView(props: {
  landscape: Landscape | null;
  writable: boolean;
  onRegister: () => void;
}) {
  const l = props.landscape;
  if (!l) return <Skeleton rows={4} tall />;
  const byRole = l.systems.reduce<Record<string, typeof l.systems>>((acc, s) => {
    (acc[s.role] ??= []).push(s);
    return acc;
  }, {});
  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">Landscape</div>
          <h1>The systems in scope</h1>
        </div>
        <button className="btn" onClick={props.onRegister} disabled={!props.writable}>Register a system</button>
      </div>

      {l.systems.length === 0 ? (
        <Empty title="No systems registered"
               body="Register the systems this engagement touches. Legacy sources and digital twins are write-locked the moment they are declared — the platform makes writing to them impossible, not merely discouraged." />
      ) : (
        <div className="board">{Object.entries(byRole).map(([role, systems]) => {
          const locked = role === "SOURCE_LEGACY" || role === "TWIN";
          return (
            <Section key={role} title={role.replace(/_/g, " ")}
                     note={locked ? "Write-locked — writes are impossible here" : `${systems.length} system(s)`}
                     lamp={locked ? "stop" : "run"} status={locked ? "Read only" : "Writable"}>
              <div className="cols">
                {systems.map((s) => (
                  <div className="card" key={s.system_id}>
                    <div className="row" style={{ justifyContent: "space-between" }}>
                      <strong className="display" style={{ fontSize: 16 }}>{s.system_id}</strong>
                      <Pill lamp={locked ? "stop" : "run"}>{locked ? "Read only" : "Writable"}</Pill>
                    </div>
                    <div className="mut" style={{ fontSize: 12.5, marginTop: 6 }}>
                      {s.product} · {s.environment}
                    </div>
                    <div className="mono dim" style={{ fontSize: 11, marginTop: 6 }}>
                      {s.change_substrate || "no change substrate declared"}
                      {s.owner ? ` · ${s.owner}` : ""}
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          );
        })}</div>
      )}

      {l.promotion_paths.length > 0 && (
        <Section title="Promotion paths" note="How change travels to production">
          <div className="grid">
            {l.promotion_paths.map((p, i) => (
              <div className="row" key={i} style={{ gap: 10 }}>
                {p.map((step, j) => (
                  <span key={j} className="row" style={{ gap: 10 }}>
                    <span className="pill none mono">{step}</span>
                    {j < p.length - 1 && <span className="dim">──</span>}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </Section>
      )}
    </>
  );
}

/* ---------------- 5 · Intent (IR) ---------------- */
export function IntentView(props: {
  records: IRRecordView[] | null;
  gaps: Record<string, string[]>;
  schemaVersion: string;
  writable: boolean;
  onLoad: () => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  if (!props.records) return <Skeleton rows={5} />;
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

      {props.records.length === 0 ? (
        <Empty title="No signed intent yet"
               body="JIDOKA does not execute unsigned intent. Load a signed configuration record set — every record names the workbook it came from, who signed it and when — and the plan builds itself from there." />
      ) : (
        <div className="card scroll-x">
          <table className="tbl">
            <thead>
              <tr>
                <th>Object</th><th>Product</th><th>Tier</th><th>Binds to</th>
                <th>Source</th><th>Signed by</th><th></th>
              </tr>
            </thead>
            <tbody>
              {props.records.map((r) => (
                <Fragment key={r.key}>
                  <tr>
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
                    <td className="mono dim">
                      {String(r.source.signed_by ?? "—")}
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
                        <div className="verbatim calm">{JSON.stringify(r.intent, null, 2)}</div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

/* ---------------- 6 · Ledger ---------------- */
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

  if (!props.entries) return <Skeleton rows={6} />;
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

      <div className="card scroll-x">
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
                <td><span className="hash" title={`${e.hash}\nprev ${e.prev}`}>{e.hash}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <div className="mut" style={{ padding: 14 }}>Nothing matches that filter.</div>}
      </div>
    </>
  );
}

/* ---------------- 7 · Evidence ---------------- */
export function EvidenceView(props: {
  evidence: Evidence | null;
  onRefresh: () => void;
  onDownload: () => void;
}) {
  const b = props.evidence;
  if (!b) return <Skeleton rows={5} tall />;
  const v = b.chain.verification;
  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">Evidence · {b.bundle_version}</div>
          <h1>The auditor's copy</h1>
        </div>
        <div className="row">
          <button className="btn" onClick={props.onRefresh}>Rebuild</button>
          <button className="btn primary" onClick={props.onDownload}>Download bundle</button>
        </div>
      </div>

      <div className="banner" data-lamp={v.verified ? "run" : "stop"}>
        <span className="bar" />
        <div>
          <strong>
            {v.verified
              ? `The chain verifies. ${v.entries} entries, unbroken from genesis.`
              : `The chain breaks at entry ${v.broken_at}.`}
          </strong>
          <div className="mut" style={{ marginTop: 4 }}>
            {v.verified
              ? "This was recomputed from the entries themselves — the stored hashes were not trusted."
              : v.reason}
          </div>
        </div>
      </div>

      <div className="cols">
        <div className="card">
          <div className="eyebrow">Manifest</div>
          <div className="mono" style={{ fontSize: 11.5, marginTop: 8, wordBreak: "break-all" }}>
            {b.manifest_sha256}
          </div>
          <div className="mut" style={{ fontSize: 12.5, marginTop: 8 }}>
            A changed byte anywhere in this bundle changes this digest.
          </div>
        </div>
        <div className="card">
          <div className="eyebrow">Genesis</div>
          <div className="mono dim" style={{ fontSize: 11.5, marginTop: 8, wordBreak: "break-all" }}>
            {b.chain.genesis}
          </div>
          <div className="mut" style={{ fontSize: 12.5, marginTop: 8 }}>
            Every chain starts here, so the first entry cannot be forged onto an earlier history.
          </div>
        </div>
        <div className="card">
          <div className="eyebrow">Sources of intent</div>
          <div style={{ marginTop: 8 }}>
            {b.ir.sources.length
              ? b.ir.sources.map((s) => <div key={s} className="mono" style={{ fontSize: 11.5 }}>{s}</div>)
              : <span className="mut">No signed intent loaded.</span>}
          </div>
        </div>
      </div>

      <Section title="Separation of duties"
               note="Recomputed from history, not asserted from roles"
               lamp={b.separation_of_duties.every((s) => s.separation_held) ? "run" : "stop"}
               status={b.separation_of_duties.every((s) => s.separation_held) ? "Held on every task" : "Violated"}>
        {b.separation_of_duties.length === 0 ? (
          <span className="mut">Nothing has been approved yet.</span>
        ) : (
          <div className="scroll-x">
            <table className="tbl">
              <thead>
                <tr><th>Task</th><th>Executed by</th><th>Approved by</th><th>Separation</th><th>Snapshot</th></tr>
              </thead>
              <tbody>
                {b.separation_of_duties.map((s) => (
                  <tr key={s.task}>
                    <td className="mono">{s.task}</td>
                    <td>{s.executed_by.join(", ") || "—"}</td>
                    <td>{s.approved_by}</td>
                    <td><Pill lamp={s.separation_held ? "run" : "stop"}>{s.separation_held ? "Held" : "Violated"}</Pill></td>
                    <td><Pill lamp={s.snapshot_present ? "run" : "stop"}>{s.snapshot_present ? "Present" : "Missing"}</Pill></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="How to verify this yourself"
               note="Reimplementable in any language, without JIDOKA running">
        <div className="verbatim calm">{b.chain.verify_procedure}</div>
      </Section>
    </>
  );
}

/* ---------------- 8 · Milestones ---------------- */
export function MilestonesView(props: { milestones: Milestone[]; planBlock: string | null }) {
  if (props.planBlock) {
    return <Empty title="No milestones yet"
                  body="Milestones are earned from approved checkpoints, and there is no plan to earn them against."
                  verbatim={props.planBlock} />;
  }
  if (!props.milestones.length) return <Skeleton rows={4} tall />;
  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">Milestones</div>
          <h1>What has actually been earned</h1>
        </div>
        <span className="mut">A milestone is earned by approvals on the ledger, never declared.</span>
      </div>
      <div className="grid">
        {props.milestones.map((m) => (
          <div className="station" key={m.lane} data-lamp={m.earned ? "run" : "call"}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <div className="title">{m.name}</div>
                <div className="mut" style={{ fontSize: 12.5 }}>
                  {m.earned
                    ? "Every checkpoint in this phase, and every phase before it, is approved."
                    : `${m.approved} of ${m.total} approved.`}
                </div>
              </div>
              <Pill lamp={m.earned ? "run" : "call"}>{m.earned ? "Earned" : "Not yet"}</Pill>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

/* ---------------- 9 · Configure: the one screen that changes a customer's system ----------------
   Everything else in this console describes intent. This screen spends it. So it is deliberately
   the least eager screen in the product: dry run is the default action, arming is visible at all
   times, and every refusal is quoted in the platform's own words rather than softened. */

/* Mirrors executor.ABAP_PRODUCTS. The server is the authority — this only decides whether the
   console offers the button, never whether the hop is legal. */
const ABAP = new Set(["S4HANA", "S/4HANA", "ECC", "R3"].map((p) => p.toUpperCase()));
const isAbap = (product: string) => ABAP.has((product || "").toUpperCase().replace(/ /g, ""));

const STATUS_LAMP: Record<string, string> = {
  DRY_RUN: "call", HANDED_OFF: "call", IN_TRANSPORT: "call", PARTIAL: "stop",
  VERIFIED: "run", APPLIED: "run", ROLLED_BACK: "call", DRIFTED: "stop",
  FAILED: "stop", REFUSED: "stop",
};

const STATUS_WORDS: Record<string, string> = {
  DRY_RUN: "Rehearsed. Nothing was written.",
  HANDED_OFF: "A person does this one. The instruction sheet is ready.",
  IN_TRANSPORT: "Written and verified, but not yet in production.",
  VERIFIED: "Written, and the system agrees it took.",
  APPLIED: "Written. Verification has not run yet.",
  PARTIAL: "Some of it landed and some did not. Read this carefully.",
  DRIFTED: "Written, but the system does not look the way it should.",
  FAILED: "Nothing landed. The system refused or was unreachable.",
  ROLLED_BACK: "Put back the way it was.",
  REFUSED: "A gate stopped this before anything happened.",
};

export function ConfigureView(props: {
  plan: Plan | null;
  planBlock: string | null;
  armed: ArmedTarget[];
  connectors: Connector[];
  results: Record<string, ExecutionResult>;
  snapshots: Record<string, number>;
  transports: Record<string, StepTransport>;
  busy: string | null;
  canExecute: boolean;
  canArm: boolean;
  onSnapshot: (key: string) => void;
  onExecute: (key: string) => void;
  onRollback: (key: string) => void;
  onAdvanceTransport: (key: string) => void;
  onArm: (systemId: string) => void;
  onDisarm: (systemId: string) => void;
  onBind: (systemId: string) => void;
  canBind: boolean;
}) {
  if (props.planBlock) {
    return <Empty title="Nothing to configure yet"
                  body="Configuration runs off the plan, and there is no plan."
                  verbatim={props.planBlock} />;
  }
  if (!props.plan) return <Skeleton rows={5} tall />;

  const armedIds = new Set(props.armed.map((a) => a.system_id));
  const bound = new Map(props.connectors.map((c) => [c.system_id, c]));
  const systems = Array.from(new Set(props.plan.steps.map((s) => s.system)));
  const tierA = props.plan.steps.filter((s) => s.tier === "A");
  const live = tierA.filter((s) => armedIds.has(s.system)).length;

  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">Configure</div>
          <h1>Write the configuration</h1>
        </div>
        <Pill lamp={live ? "stop" : "run"}>
          {live ? `${live} step${live === 1 ? "" : "s"} armed for live` : "Dry run"}
        </Pill>
      </div>

      <Section title="Armed targets"
               note="A live write needs an approver to arm the target first — and the person who arms it may not be the one who runs it"
               lamp={armedIds.size ? "stop" : "run"}
               status={armedIds.size ? "LIVE" : "SAFE"}>
        <div className="grid">
          {systems.map((sid) => {
            const a = props.armed.find((x) => x.system_id === sid);
            const c = bound.get(sid);
            return (
              <div className="station" key={sid} data-lamp={a ? "stop" : "run"}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <div>
                    <div className="title">{sid}</div>
                    <div className="mut" style={{ fontSize: 12.5 }}>
                      {a
                        ? `Armed by ${a.armed_by}${a.reason ? ` — ${a.reason}` : ""}. Writes to this system are real.`
                        : "Not armed. Anything run against this system is a rehearsal."}
                    </div>
                    {/* Unbound is the more fundamental fact than unarmed: without a connector the
                        platform cannot even read the before-state, so no live write is reachable. */}
                    <div className="mut" style={{ fontSize: 12.5, marginTop: 4 }}>
                      {c
                        ? `Connected — ${c.kind} (${c.describe}).`
                        : "No connector bound. The platform can rehearse against this system but cannot read or write it."}
                    </div>
                  </div>
                  <div className="row">
                    {!c && props.canBind && (
                      <button className="btn" disabled={props.busy === sid}
                              onClick={() => props.onBind(sid)}>
                        Bind connector
                      </button>
                    )}
                    {props.canArm ? (
                      <button className={"btn" + (a ? "" : " danger")}
                              disabled={props.busy === sid}
                              onClick={() => (a ? props.onDisarm(sid) : props.onArm(sid))}>
                        {a ? "Disarm" : "Arm for live"}
                      </button>
                    ) : (
                      <Pill lamp={a ? "stop" : "run"}>{a ? "Armed" : "Safe"}</Pill>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      <Section title="Steps"
               note="Tier A is written by the platform. Tier B and C produce something for a person to carry out."
               lamp="run" status={`${props.plan.steps.length} STEPS`}>
        <div className="tblwrap">
          <table className="tbl">
            <thead>
              <tr>
                <th className="num">#</th><th>What</th><th>Tier</th><th>System</th>
                <th>Before</th><th>Outcome</th><th />
              </tr>
            </thead>
            <tbody>
              {props.plan.steps.map((s) => {
                const res = props.results[s.key];
                const snapped = props.snapshots[s.key];
                const isLive = s.tier === "A" && armedIds.has(s.system);
                const trans = props.transports[s.key] ?? res?.transport;
                return (
                  <tr key={s.key}>
                    <td className="num">{s.seq}</td>
                    <td>{stepWords(s)}</td>
                    <td><Pill lamp={s.tier === "A" ? "run" : "call"}>{s.tier}</Pill></td>
                    <td className="mono">{s.system}</td>
                    <td className="num">
                      {snapped === undefined
                        ? <span className="mut">not taken</span>
                        : `${snapped} row${snapped === 1 ? "" : "s"}`}
                    </td>
                    <td>
                      {res ? (
                        <>
                          <Pill lamp={STATUS_LAMP[res.status] ?? "call"}>{res.status}</Pill>
                          <div className="mut" style={{ fontSize: 12.5, marginTop: 4 }}>
                            {STATUS_WORDS[res.status] ?? res.detail}
                          </div>
                          {trans && (
                            <div className="mut mono" style={{ fontSize: 12, marginTop: 4 }}>
                              {trans.request_id} in {trans.currently_in}
                              {trans.in_production ? " — in production" : ` — next ${trans.next_hop}`}
                            </div>
                          )}
                        </>
                      ) : (
                        <span className="mut">not run</span>
                      )}
                    </td>
                    <td>
                      <div className="row">
                        {s.tier === "A" && (
                          <button className="btn ghost" disabled={!props.canExecute || props.busy === s.key}
                                  onClick={() => props.onSnapshot(s.key)}>
                            Snapshot
                          </button>
                        )}
                        <button className={"btn" + (isLive ? " danger" : "")}
                                disabled={!props.canExecute || props.busy === s.key}
                                onClick={() => props.onExecute(s.key)}>
                          {s.tier !== "A" ? "Produce sheet" : isLive ? "Write for real" : "Dry run"}
                        </button>
                        {/* Only ABAP steps carry a transport, and only the ones not yet in
                            production have a hop left to take (ADR-0006). */}
                        {s.tier === "A" && isAbap(s.product) && !trans?.in_production && (
                          <button className="btn ghost" disabled={!props.canExecute || props.busy === s.key}
                                  onClick={() => props.onAdvanceTransport(s.key)}>
                            {trans?.next_hop ? `Move to ${trans.next_hop}` : "Advance transport"}
                          </button>
                        )}
                        {/* Rollback is a write. The server re-runs every arming gate, so the
                            console offers it wherever a snapshot exists rather than guessing. */}
                        {s.tier === "A" && snapped !== undefined && (
                          <button className="btn ghost" disabled={!props.canExecute || props.busy === s.key}
                                  onClick={() => props.onRollback(s.key)}>
                            Roll back
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>
    </>
  );
}
