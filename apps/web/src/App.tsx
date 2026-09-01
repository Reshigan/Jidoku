/* The console shell. Loads everything the platform exposes, refuses nothing locally:
   a refusal shown here is always the server's own words, quoted verbatim. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError, platform, setSession, getSession,
  type Claim, type DecisionPoint, type EngagementDetail, type EngagementSummary, type Evidence,
  type ArmedTarget, type Connector, type ExecutionResult, type MemoryView as Memory,
  type StepTransport, type IRRecordView, type Landscape, type LedgerEntry, type Plan,
} from "./api";
import { LINE_STOP, LINE_RESUME, buildLanes, lineStop, milestones, type Lane, type Station } from "./derive";
import { AndonRail, Empty, Field, Modal, Skeleton, VIEWS, type ViewName } from "./ui";
import {
  ConfigureView, DecisionsView, EvidenceView, IntentView, LandscapeView, LedgerView, LineView,
  MemoryView, MilestonesView, WorkView,
} from "./views";
import { DP_KINDS, SYSTEM_ROLES, kindWords, roleLabel } from "./viewkit";
import "./app.css";

/** Everything the console holds about one engagement. Loaded together, refreshed together. */
type Data = {
  detail: EngagementDetail | null;
  plan: Plan | null;
  planBlock: string | null;
  entries: LedgerEntry[] | null;
  chainBroken: string | null;
  dps: DecisionPoint[] | null;
  irGaps: Record<string, string[]>;
  records: IRRecordView[] | null;
  schemaVersion: string;
  landscape: Landscape | null;
  evidence: Evidence | null;
  memory: Memory | null;
};

const EMPTY: Data = {
  detail: null, plan: null, planBlock: null, entries: null, chainBroken: null, dps: null,
  irGaps: {}, records: null, schemaVersion: "", landscape: null, evidence: null, memory: null,
};

export default function App() {
  const [who, setWho] = useState(() => getSession()?.subject ?? "");
  const [roles, setRoles] = useState<string[]>(() => getSession()?.roles ?? []);
  const [engagements, setEngagements] = useState<EngagementSummary[] | null>(null);
  const [eid, setEid] = useState<string | null>(null);
  const [d, setD] = useState<Data>(EMPTY);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [view, setView] = useState<ViewName>("Line");
  const [refusal, setRefusal] = useState<{ title: string; text: string } | null>(null);
  const [dialog, setDialog] = useState<null | { kind: string; station?: Station; dp?: DecisionPoint; claim?: Claim }>(null);
  // Execution state is per-session, not per-engagement history: the ledger is the record of what
  // happened, this is only what this operator has run since opening the screen.
  const [armed, setArmed] = useState<ArmedTarget[]>([]);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [results, setResults] = useState<Record<string, ExecutionResult>>({});
  const [transports, setTransports] = useState<Record<string, StepTransport>>({});
  const [snapshots, setSnapshots] = useState<Record<string, number>>({});
  // A time query is this operator's question, not engagement state — it is cleared with the view.
  const [asOf, setAsOf] = useState<{ as_of: string; claims: Claim[] } | null>(null);

  const signedIn = !!who && roles.length > 0;
  const can = (c: string) =>
    signedIn && (
      c === "read" ? true :
      c === "approve" ? roles.includes("approver") :
      roles.includes("builder") || roles.includes("approver"));
  const writable = can("write") && !offline;

  /* Every write goes through here, so the double-click guard goes here too rather than onto each of
     the twenty buttons that would each forget it. Approve fired ten times is ten ledger entries. */
  const inFlight = useRef(false);

  /* One place turns an ApiError into a visible refusal, so no view ever invents a message. */
  const guard = useCallback(async <T,>(title: string, fn: () => Promise<T>): Promise<T | null> => {
    if (inFlight.current) return null;
    inFlight.current = true;
    try {
      const out = await fn();
      setOffline(false);
      return out;
    } catch (err) {
      const e = err as ApiError;
      if (e.status === 0) { setOffline(true); return null; }
      /* A token that expired while the screen was open is not a refusal to explain — it is a session
         that ended. Showing "Not authenticated" in a dialog leaves the operator clicking a dead
         console; returning them to sign-in is the only honest thing the screen can do. */
      if (e.status === 401) {
        setSession(null); setRoles([]); setWho("");
        return null;
      }
      setRefusal({ title, text: e.detail || e.message });
      return null;
    } finally {
      inFlight.current = false;
    }
  }, []);

  const loadList = useCallback(async () => {
    const list = await guard("Could not list engagements", () => platform.engagements());
    if (list) {
      setEngagements(list);
      setEid((cur) => cur ?? list[0]?.engagement_id ?? null);
    }
  }, [guard]);

  const load = useCallback(async (id: string) => {
    const soft = async <T,>(fn: () => Promise<T>): Promise<T | null> => {
      try { return await fn(); } catch (e) {
        if ((e as ApiError).status === 0) setOffline(true);
        return null;
      }
    };
    const [detail, ledger, dps, ir, landscape, schema, memory] = await Promise.all([
      soft(() => platform.detail(id)),
      soft(() => platform.ledger(id)),
      soft(() => platform.decisions(id)),
      soft(() => platform.ir(id)),
      soft(() => platform.landscape(id)),
      soft(() => platform.schema()),
      soft(() => platform.memory(id)),
    ]);

    // The plan is allowed to be blocked; that is information, not an error.
    let plan: Plan | null = null;
    let planBlock: string | null = null;
    try { plan = await platform.currentPlan(id); }
    catch (e) {
      const err = e as ApiError;
      if (err.status === 409) planBlock = err.detail || err.message;
      else if (err.status === 0) setOffline(true);
      else planBlock = err.detail || err.message;
    }

    let chainBroken: string | null = null;
    let entries: LedgerEntry[] | null = null;
    if (ledger) {
      entries = ledger.entries;
      if (!ledger.verified) chainBroken = "The recomputed chain does not match the stored hashes.";
    } else {
      try { await platform.ledger(id); } catch (e) {
        const err = e as ApiError;
        if (err.status === 409) chainBroken = err.detail || err.message;
      }
    }

    setD({
      detail, plan, planBlock, entries, chainBroken,
      dps: dps?.decision_points ?? null,
      irGaps: dps?.ir_gaps ?? ir?.open_decision_points ?? {},
      records: ir?.records ?? null,
      schemaVersion: ir?.schema ?? schema?.version ?? "",
      landscape, evidence: null, memory,
    });
  }, []);

  useEffect(() => { if (signedIn) loadList(); }, [signedIn, loadList]);

  // The offline state is measured, not guessed: a health check every 20s decides it.
  useEffect(() => {
    let alive = true;
    const beat = async () => {
      try { await platform.health(); if (alive) setOffline(false); }
      catch { if (alive) setOffline(true); }
    };
    beat();
    const t = setInterval(beat, 20_000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  useEffect(() => { if (signedIn && eid) load(eid); }, [signedIn, eid, load]);

  // Number keys select a view, as the brand asks. There are ten views and only nine digits that
  // read as ordinals, so 0 is the tenth — the same place it sits on the row.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (!/^[0-9]$/.test(e.key)) return;
      const n = e.key === "0" ? 10 : Number(e.key);
      if (n <= VIEWS.length) setView(VIEWS[n - 1]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const lanes: Lane[] = useMemo(
    () => (d.plan && d.entries ? buildLanes(d.plan, d.entries) : []), [d.plan, d.entries]);
  const stopped = useMemo(() => !!(d.entries && lineStop(d.entries)), [d.entries]);
  const halt = useMemo(() => (d.entries ? lineStop(d.entries) : null), [d.entries]);

  const after = async () => { if (eid) await load(eid); };

  /* Armings live on the server, never in this component: a stale local "safe" badge over a live
     target is exactly the mistake this screen exists to prevent. */
  const refreshArmed = useCallback(async () => {
    if (!eid) return;
    try {
      setArmed((await platform.armed(eid)).armed);
    } catch {
      setArmed([]);   // unknown is shown as unarmed; the server refuses anyway if it is not
    }
    try {
      setConnectors((await platform.connectors(eid)).connectors);
    } catch {
      setConnectors([]);
    }
    /* Where each ABAP change sits on its route is server truth too: the hop may have been taken
       by someone else in another tab. */
    try {
      const t = (await platform.transports(eid)).transports;
      setTransports(Object.fromEntries(t.map((x) => [x.key, x])));
    } catch {
      setTransports({});
    }
  }, [eid]);

  useEffect(() => {
    setResults({});
    setSnapshots({});
    setTransports({});
    setAsOf(null);
  }, [eid]);

  /* Someone else's arming is the case that matters: this operator never sees it happen, so the
     badge is re-read from the server every time the screen is opened, not only when they arm. */
  useEffect(() => {
    if (view === "Configure") void refreshArmed();
  }, [view, refreshArmed]);

  const stage = async (s: Station, action: string, detail = "") => {
    if (!eid) return;
    setBusy(s.step.key);
    await guard("The platform refused that step",
      () => platform.appendLedger(eid, { task: s.step.key, action, detail }));
    setBusy(null);
    await after();
  };

  const approve = async (s: Station) => {
    if (!eid) return;
    setBusy(s.step.key);
    await guard("Approval refused", () => platform.approve(eid, { task: s.step.key }));
    setBusy(null);
    await after();
  };

  /* Re-checking names the belief and nothing else. The server re-reads the source the claim was
     formed from and compares hashes; the console holds no evidence and must not supply any, or
     it would be answering the question it asked. A belief whose ground has moved comes back
     stale, which is the gate reporting, not a failure. */
  const recheck = async (claim: Claim) => {
    if (!eid) return;
    setBusy(claim.id);
    await guard("That belief could not be re-checked",
      () => platform.recheckClaim(eid, claim.id));
    setBusy(null);
    await after();
  };

  return (
    <div className="shell" data-stopped={stopped}>
      <AndonRail view={view} onView={setView} lanes={lanes} stopped={stopped}
                 onCord={() => setDialog({ kind: stopped ? "resume" : "stop" })} />

      <div className="main">
        <header className="topbar">
          <div className="wordmark">
            <span>go</span><span className="nxt">NXT</span>
            <span className="jid">JIDOKA</span><span className="kanji">自働化</span>
          </div>
          <div className="row">
            {offline && <span className="pill" data-lamp="call">Offline — showing last verified state</span>}
            {signedIn ? (
              <>
                <select value={eid ?? ""} onChange={(e) => setEid(e.target.value || null)}
                        aria-label="Engagement">
                  {(engagements ?? []).map((e) => (
                    <option key={e.engagement_id} value={e.engagement_id}>
                      {e.client} — {e.name}
                    </option>
                  ))}
                </select>
                <button className="btn ghost sm" onClick={() => setDialog({ kind: "newEngagement" })}>
                  New engagement
                </button>
                <span className="mut">{who} · {roles.join(", ")}</span>
                <button className="btn ghost sm" onClick={() => { setSession(null); setRoles([]); setWho(""); }}>
                  Sign out
                </button>
              </>
            ) : null}
          </div>
        </header>

        <main className="page">
          {!signedIn ? (
            <SignIn who={who} setWho={setWho} guard={guard}
                    onSignIn={(s, r, tok) => { setSession({ subject: s, roles: r }, tok); setWho(s); setRoles(r); }} />
          ) : !eid ? (
            engagements === null ? <Skeleton rows={4} tall /> : (
              <Empty title="No engagements yet"
                     body="An engagement is the unit JIDOKA governs: one client, one landscape, one hash-chained ledger from first intent to hypercare. Open one to begin." />
            )
          ) : (
            <>
              {stopped && halt && (
                <div className="banner" data-lamp="stop">
                  <span className="bar" />
                  <div>
                    <strong>The line is stopped.</strong>
                    <div className="mut" style={{ marginTop: 4 }}>
                      Pulled by {halt.actor}. Nothing executes until it is released.
                    </div>
                    <div className="verbatim" style={{ marginTop: 8 }}>{halt.detail}</div>
                  </div>
                </div>
              )}
              {d.chainBroken && view !== "Ledger" && (
                <div className="banner" data-lamp="stop">
                  <span className="bar" />
                  <div><strong>The ledger does not verify. Approvals are suspended.</strong></div>
                </div>
              )}

              {view === "Line" && (
                <LineView detail={d.detail} lanes={lanes} plan={d.plan} planBlock={d.planBlock}
                          entries={d.entries} dps={d.dps ?? []} chainBroken={d.chainBroken}
                          canAdvance={can("approve") && !offline && !stopped}
                          onAdvance={async (to) => {
                            await guard("The phase cannot advance", () => platform.advancePhase(eid, to));
                            await after();
                          }} />
              )}
              {view === "Work" && (
                <WorkView lanes={lanes} planBlock={d.planBlock} busy={busy}
                          writable={writable && !stopped && !d.chainBroken}
                          onStage={stage} onApprove={approve}
                          onRollback={(s) => stage(s, "ROLLED_BACK", "rolled back from the console")} />
              )}
              {view === "Configure" && (
                <ConfigureView plan={d.plan} planBlock={d.planBlock} armed={armed}
                               connectors={connectors}
                               results={results} snapshots={snapshots}
                               transports={transports} busy={busy}
                               canExecute={can("write") && !offline && !stopped && !d.chainBroken}
                               canArm={can("approve") && !offline && !stopped && !d.chainBroken}
                               canBind={can("write") && !offline && !stopped}
                               onBind={async (sid) => {
                                 setBusy(sid);
                                 const ok = await guard(`${sid} cannot be connected`,
                                   () => platform.bindConnector(eid!, sid, "mock"));
                                 setBusy(null);
                                 if (ok) await refreshArmed();
                               }}
                               onArm={async (sid) => {
                                 setBusy(sid);
                                 const ok = await guard(`${sid} cannot be armed`,
                                   () => platform.arm(eid!, sid, "armed from the console"));
                                 setBusy(null);
                                 if (ok) await refreshArmed();
                               }}
                               onDisarm={async (sid) => {
                                 setBusy(sid);
                                 await guard(`${sid} cannot be disarmed`, () => platform.disarm(eid!, sid));
                                 setBusy(null);
                                 await refreshArmed();
                               }}
                               onSnapshot={async (key) => {
                                 setBusy(key);
                                 const out = await guard("The snapshot could not be taken",
                                   () => platform.snapshot(eid!, key));
                                 setBusy(null);
                                 if (out) setSnapshots((x) => ({ ...x, [key]: out.rows }));
                                 await after();
                               }}
                               onExecute={async (key) => {
                                 setBusy(key);
                                 const out = await guard("This step did not run",
                                   () => platform.execute(eid!, key));
                                 setBusy(null);
                                 if (out) setResults((x) => ({ ...x, [key]: out }));
                                 await refreshArmed();
                                 await after();
                               }}
                               onRollback={async (key) => {
                                 setBusy(key);
                                 const out = await guard("This step was not rolled back",
                                   () => platform.rollback(eid!, key, "rolled back from the console"));
                                 setBusy(null);
                                 if (out) setResults((x) => ({ ...x, [key]: { ...x[key], ...out } as ExecutionResult }));
                                 await after();
                               }}
                               onAdvanceTransport={async (key) => {
                                 setBusy(key);
                                 await guard("The transport did not advance",
                                   () => platform.advanceTransport(eid!, key));
                                 setBusy(null);
                                 await refreshArmed();
                                 await after();
                               }} />
              )}
              {view === "Decisions" && (
                <DecisionsView dps={d.dps} irGaps={d.irGaps} writable={writable}
                               onRaise={() => setDialog({ kind: "raiseDp" })}
                               onResolve={(dp) => setDialog({ kind: "resolveDp", dp })} />
              )}
              {view === "Intent" && (
                <IntentView records={d.records} gaps={d.irGaps} schemaVersion={d.schemaVersion}
                            writable={writable} onLoad={() => setDialog({ kind: "loadIr" })} />
              )}
              {view === "Landscape" && (
                <LandscapeView landscape={d.landscape} writable={writable}
                               onRegister={() => setDialog({ kind: "registerSystem" })} />
              )}
              {view === "Memory" && (
                <MemoryView memory={d.memory} asOf={asOf} busy={busy}
                            writable={writable}
                            canPromote={can("approve") && !offline && !stopped}
                            onForm={() => setDialog({ kind: "formClaim" })}
                            onClearAsOf={() => setAsOf(null)}
                            onAsOf={async (when) => {
                              const out = await guard("That moment could not be read back",
                                () => platform.memoryAsOf(eid, when));
                              if (out) setAsOf(out);
                            }}
                            onAct={(claim, action) => {
                              // Re-check is deterministic and needs nothing from a person, so it
                              // runs. Correction and promotion both need typed input, and
                              // promotion needs a named approver, so both open a dialog.
                              if (action === "recheck") void recheck(claim);
                              else setDialog({ kind: action === "correct" ? "correctClaim" : "promoteClaim", claim });
                            }} />
              )}
              {view === "Ledger" && <LedgerView entries={d.entries} chainBroken={d.chainBroken} />}
              {view === "Evidence" && (
                <EvidenceLoader eid={eid} evidence={d.evidence} guard={guard}
                                onLoaded={(ev) => setD((x) => ({ ...x, evidence: ev }))} />
              )}
              {view === "Milestones" && (
                <MilestonesView milestones={milestones(lanes)} planBlock={d.planBlock} />
              )}
            </>
          )}
        </main>

        <footer>
          goNXT · What Comes Next is Built Here
        </footer>
      </div>

      {refusal && (
        <Modal title={refusal.title} refusal onClose={() => setRefusal(null)}>
          <p className="mut">The platform refused. Its own words:</p>
          <div className="verbatim">{refusal.text}</div>
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn" onClick={() => setRefusal(null)}>Understood</button>
          </div>
        </Modal>
      )}

      {dialog && (
        <Dialogs kind={dialog.kind} eid={eid ?? ""} dp={dialog.dp} claim={dialog.claim} halt={halt} who={who}
                 onClose={() => setDialog(null)} guard={guard}
                 onDone={async (created) => {
                   setDialog(null);
                   await loadList();
                   if (created) setEid(created); else await after();
                 }} />
      )}
    </div>
  );
}

/* ---------------- sign in ---------------- */
function SignIn(props: {
  who: string; setWho: (s: string) => void;
  guard: <T,>(t: string, fn: () => Promise<T>) => Promise<T | null>;
  onSignIn: (s: string, r: string[], token: string) => void;
}) {
  const [picked, setPicked] = useState<string[]>(["builder"]);
  const [roles, setRoles] = useState<string[]>([]);
  // The role list is the server's, so the console cannot offer authority the API does not know.
  useEffect(() => { platform.roles().then((r) => setRoles(r.roles)).catch(() => setRoles([])); }, []);
  return (
    <div className="signin">
      <div className="card" style={{ maxWidth: 520 }}>
        <div className="eyebrow">Identify yourself</div>
        <h1 style={{ marginTop: 6 }}>Who is at the line?</h1>
        <p className="mut">
          JIDOKA records who did what. Separation of duties is decided by what the ledger already
          holds, never by the badge you carry — the person who executed a change cannot approve it,
          whatever roles they hold.
        </p>
        <Field label="Name" value={props.who} onChange={props.setWho} required
               placeholder="e.g. a.builder" />
        <div style={{ marginTop: 12 }}>
          <span className="eyebrow">Roles</span>
          <div className="row" style={{ marginTop: 8 }}>
            {roles.map((r) => (
              <button key={r} className={"btn sm" + (picked.includes(r) ? " primary" : " ghost")}
                      onClick={() => setPicked((p) => p.includes(r) ? p.filter((x) => x !== r) : [...p, r])}>
                {r}
              </button>
            ))}
          </div>
        </div>
        <div className="row" style={{ marginTop: 16 }}>
          <button className="btn primary" disabled={!props.who.trim() || !picked.length}
                  onClick={async () => {
                    const t = await props.guard("Sign-in refused",
                      () => platform.signIn(props.who.trim(), picked));
                    if (t) props.onSignIn(t.subject, t.roles, t.token);
                  }}>
            Enter the console
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------------- evidence, loaded on demand ---------------- */
function EvidenceLoader(props: {
  eid: string; evidence: Evidence | null;
  guard: <T,>(t: string, fn: () => Promise<T>) => Promise<T | null>;
  onLoaded: (e: Evidence) => void;
}) {
  const fetchIt = useCallback(async () => {
    const ev = await props.guard("Evidence export refused", () => platform.evidence(props.eid));
    if (ev) props.onLoaded(ev);
  }, [props]);
  useEffect(() => { if (!props.evidence) fetchIt(); }, [props.evidence, fetchIt]);

  const download = () => {
    if (!props.evidence) return;
    const blob = new Blob([JSON.stringify(props.evidence, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `jidoka-evidence-${props.eid}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  return <EvidenceView evidence={props.evidence} onRefresh={fetchIt} onDownload={download} />;
}

/* ---------------- every write the platform accepts ---------------- */
function Dialogs(props: {
  kind: string; eid: string; who: string; dp?: DecisionPoint; claim?: Claim; halt?: LedgerEntry | null;
  onClose: () => void; onDone: (created?: string) => void;
  guard: <T,>(t: string, fn: () => Promise<T>) => Promise<T | null>;
}) {
  const [a, setA] = useState(""); const [b, setB] = useState(""); const [c, setC] = useState("");
  const [dd, setDd] = useState(""); const [e, setE] = useState("");
  const [creds, setCreds] = useState(false);
  const [promotes, setPromotes] = useState("");
  const [check, setCheck] = useState<string | null>(null);
  const { eid, guard, onDone } = props;

  const run = (title: string, fn: () => Promise<unknown>) => async () => {
    const ok = await guard(title, fn);
    if (ok === null) return;
    // Opening an engagement selects it: nobody opens one meaning to keep looking at another.
    const created = (ok as { engagement_id?: string })?.engagement_id;
    onDone(created);
  };

  switch (props.kind) {
    case "stop":
      return (
        <Modal title="Halt the line" onClose={props.onClose}>
          <p className="mut">
            Anyone may stop the line. Nothing executes until it is released, and the reason is written
            to the ledger under your name.
          </p>
          <Field label="Reason" value={a} onChange={setA} required textarea
                 placeholder="What did you see that should stop work?" />
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn danger" disabled={!a.trim()}
                    onClick={run("The line could not be stopped",
                      () => platform.appendLedger(eid, { task: "LINE", action: LINE_STOP, detail: a }))}>
              Pull the cord
            </button>
            <button className="btn ghost" onClick={props.onClose}>Cancel</button>
          </div>
        </Modal>
      );

    case "resume":
      return (
        <Modal title="Release the line" onClose={props.onClose}>
          <p className="mut">The line was stopped for this reason:</p>
          <div className="verbatim">{props.halt?.detail}</div>
          <Field label="What was done about it" value={a} onChange={setA} required textarea />
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn primary" disabled={!a.trim()}
                    onClick={run("The line could not be released",
                      () => platform.appendLedger(eid, { task: "LINE", action: LINE_RESUME, detail: a }))}>
              Release the line
            </button>
            <button className="btn ghost" onClick={props.onClose}>Cancel</button>
          </div>
        </Modal>
      );

    case "newEngagement":
      return (
        <Modal title="Open an engagement" onClose={props.onClose}>
          <Field label="Client" value={a} onChange={setA} required placeholder="Komatsu" />
          <Field label="Name" value={b} onChange={setB} required placeholder="SuccessFactors Greenfield" />
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn primary" disabled={!a.trim() || !b.trim()}
                    onClick={run("The engagement could not be opened",
                      () => platform.createEngagement({ name: b, client: a }))}>
              Open it
            </button>
            <button className="btn ghost" onClick={props.onClose}>Cancel</button>
          </div>
        </Modal>
      );

    case "registerSystem": {
      const locked = c === "SOURCE_LEGACY" || c === "TWIN";
      return (
        <Modal title="Register a system" onClose={props.onClose}>
          <p className="mut">
            Declaring a system as a legacy source or a digital twin write-locks it. That lock is
            structural: the platform will refuse write credentials, not merely warn about them.
          </p>
          <Field label="System id" value={a} onChange={setA} required placeholder="KOM-SF-DEV" />
          <Field label="Product" value={b} onChange={setB} required placeholder="SuccessFactors" />
          <div className="cols2">
            <label className="field">
              <span className="eyebrow">Role</span>
              <select value={c} onChange={(x) => setC(x.target.value)}>
                <option value="">Choose…</option>
                {SYSTEM_ROLES.map((r) => <option key={r} value={r}>{roleLabel(r)}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="eyebrow">Environment</span>
              <select value={dd} onChange={(x) => setDd(x.target.value)}>
                <option value="">Choose…</option>
                {["DEV", "TEST", "PROD"].map((r) => <option key={r}>{r}</option>)}
              </select>
            </label>
          </div>
          <Field label="Change substrate" value={e} onChange={setE}
                 placeholder="OData provisioning API" hint="How change reaches this system natively." />
          {/* On the ABAP stack a write is not finished until its transport lands in production, and
              the route it takes is declared, never guessed (ADR-0006). */}
          <Field label="Promotes into" value={promotes} onChange={setPromotes}
                 placeholder="KOM-S4-QA"
                 hint="The next system on the transport route. Leave blank if this one is the end of it." />
          {/* Without this, a system can be registered but never bound to a connector — and the
              refusal arrives much later, at bind time, reading like a bug rather than a choice. */}
          <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <input type="checkbox" checked={creds && !locked} disabled={locked}
                   onChange={(x) => setCreds(x.target.checked)} />
            <span>
              This system holds write credentials
              <span className="mut" style={{ display: "block", fontSize: 12 }}>
                {locked
                  ? `A ${c.replace(/_/g, " ").toLowerCase()} may never hold them — invariant 3 refuses the registration.`
                  : "Required before a connector can be bound. Nothing is written until a second person arms it."}
              </span>
            </span>
          </label>
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn primary" disabled={!a.trim() || !b.trim() || !c || !dd}
                    onClick={run("The system could not be registered",
                      () => platform.registerSystem(eid, {
                        system_id: a, product: b, role: c, environment: dd, change_substrate: e,
                        connectivity: creds && !locked ? { write_credentials: true } : {},
                        promotes_to: promotes.trim(),
                      }))}>
              Register
            </button>
            <button className="btn ghost" onClick={props.onClose}>Cancel</button>
          </div>
        </Modal>
      );
    }

    case "loadIr":
      return (
        <Modal title="Load signed intent" onClose={props.onClose} labelledBy="ir-title">
          <p className="mut">
            Paste the signed record set. Check it first and every problem is reported at once — the
            loader itself stops at the first, which is no use to whoever has to fix the workbook.
          </p>
          <Field label="Records (JSON array)" value={a} onChange={setA} textarea required
                 placeholder='[{"object": "...", "product": "...", ...}]' />
          {check && <div className="verbatim calm" style={{ marginTop: 10 }}>{check}</div>}
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn" disabled={!a.trim()} onClick={async () => {
              let parsed: unknown;
              try { parsed = JSON.parse(a); } catch (err) { setCheck(String(err)); return; }
              const r = await guard("The check could not run",
                () => platform.validateIR(eid, parsed as Record<string, unknown>[]));
              if (r) setCheck(r.loadable
                ? `${r.records} record(s) check clean against schema ${r.schema}.`
                : JSON.stringify(r.errors, null, 2));
            }}>Check it</button>
            <button className="btn primary" disabled={!a.trim()} onClick={async () => {
              let parsed: unknown;
              try { parsed = JSON.parse(a); } catch (err) { setCheck(String(err)); return; }
              const ok = await guard("The intent was refused",
                () => platform.uploadIR(eid, parsed as Record<string, unknown>[]));
              if (ok) onDone();
            }}>Load it</button>
            <button className="btn ghost" onClick={props.onClose}>Cancel</button>
          </div>
        </Modal>
      );

    case "raiseDp":
      return (
        <Modal title="Raise a decision" onClose={props.onClose}>
          <Field label="Reference" value={a} onChange={setA} required placeholder="DP-B11" />
          <label className="field">
            <span className="eyebrow">Kind</span>
            <select value={b} onChange={(x) => setB(x.target.value)}>
              <option value="">Choose…</option>
              {DP_KINDS.map((r) => <option key={r} value={r}>{kindWords(r)}</option>)}
            </select>
          </label>
          <Field label="Question" value={c} onChange={setC} required textarea
                 placeholder="What must a person decide?" />
          <Field label="Owner" value={dd} onChange={setDd} required placeholder="Komatsu HR" />
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn primary" disabled={!a.trim() || !b || !c.trim() || !dd.trim()}
                    onClick={run("The decision could not be raised",
                      () => platform.raiseDP(eid, { dp_id: a, dp_type: b, question: c, owner: dd }))}>
              Raise it
            </button>
            <button className="btn ghost" onClick={props.onClose}>Cancel</button>
          </div>
        </Modal>
      );

    case "resolveDp": {
      const dp = props.dp!;
      const statutory = dp.dp_type === "STATUTORY";
      const oneWay = dp.dp_type === "ONE_WAY";
      return (
        <Modal title={`Take decision ${dp.dp_id}`} onClose={props.onClose}>
          <p style={{ fontSize: 15 }}>{dp.question}</p>
          <Field label="Decision" value={a} onChange={setA} required
                 hint={dp.options.length ? `Offered: ${dp.options.join(", ")}` : undefined} />
          {statutory && (
            <Field label="Client evidence reference" value={b} onChange={setB} required
                   placeholder="KOM-POL-114"
                   hint="A statutory value needs a signed client source. JIDOKA will not supply one." />
          )}
          {oneWay && (
            <Field label="Second approver" value={c} onChange={setC} required
                   hint="A one-way door needs two different named people." />
          )}
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn primary"
                    disabled={!a.trim() || (statutory && !b.trim()) || (oneWay && !c.trim())}
                    onClick={run("The decision was refused",
                      () => platform.resolveDP(eid, dp.dp_id, {
                        decided_by: props.who, value: a,
                        evidence_ref: b || undefined, second_approver: c || undefined,
                      }))}>
              Record the decision
            </button>
            <button className="btn ghost" onClick={props.onClose}>Cancel</button>
          </div>
        </Modal>
      );
    }
    /* ---- memory (ADR-0010) ---- */

    case "formClaim":
      return (
        <Modal title="Record a belief" onClose={props.onClose}>
          <p className="mut">
            A belief arrives unchecked and stays that way until something re-checks it against its
            source. It is stored with what it was read from, so it can go stale on its own rather
            than quietly drifting.
          </p>
          <Field label="Subject" value={a} onChange={setA} required placeholder="payroll.cycle"
                 hint="What this belief is about." />
          <Field label="What we believe" value={b} onChange={setB} required textarea
                 placeholder="Payroll runs monthly on the 25th." />
          <Field label="Read from" value={c} onChange={setC} required placeholder="KOM-HR-WB-04"
                 hint="The document or system this came out of. A belief with no source is refused." />
          <Field label="The source as it read" value={dd} onChange={setDd} required textarea
                 placeholder="Paste the passage this was formed from."
                 hint="Kept as a hash, never as content. Staleness is a comparison against this." />
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn primary"
                    disabled={!a.trim() || !b.trim() || !c.trim() || !dd.trim()}
                    onClick={run("The belief was refused",
                      () => platform.formClaim(eid, {
                        subject: a, text: b, source_ref: c, evidence: dd,
                      }))}>
              Record it
            </button>
            <button className="btn ghost" onClick={props.onClose}>Cancel</button>
          </div>
        </Modal>
      );

    case "correctClaim": {
      const cl = props.claim!;
      return (
        <Modal title="Correct a belief" onClose={props.onClose}>
          <p className="mut">
            The old belief is not erased. Its interval closes here and the new one takes over, so
            reading back an earlier day still shows what was believed then.
          </p>
          <div className="verbatim calm">{cl.text}</div>
          <Field label="What we believe now" value={a} onChange={setA} required textarea />
          <Field label="Read from" value={b} onChange={setB} required placeholder={cl.source_ref}
                 hint="The source for the corrected belief." />
          <Field label="The source as it reads" value={c} onChange={setC} required textarea
                 hint="What the new belief was formed from." />
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn primary" disabled={!a.trim() || !b.trim() || !c.trim()}
                    onClick={run("The correction was refused",
                      () => platform.correctClaim(eid, cl.id, { text: a, source_ref: b, evidence: c }))}>
              Replace it
            </button>
            <button className="btn ghost" onClick={props.onClose}>Cancel</button>
          </div>
        </Modal>
      );
    }

    case "promoteClaim": {
      const cl = props.claim!;
      // The approver is typed rather than assumed. The server refuses a self-approval anyway, but a
      // console that quietly filled in the signed-in name would be inviting one.
      const self = a.trim() && a.trim() === cl.actor;
      return (
        <Modal title="Promote into shared knowledge" onClose={props.onClose}>
          <p className="mut">
            This belief leaves the engagement. Once it is shared knowledge every later engagement
            reads it and nothing recalls it, which is why it needs a named person who is not the one
            who formed it.
          </p>
          <div className="verbatim calm">{cl.text}</div>
          <ul className="mem-quiet-list" style={{ marginTop: 12 }}>
            <li>Formed by <span className="mono">{cl.actor}</span> — that name may not approve this.</li>
            <li>Shapes may cross; client values never. The gate refuses a claim carrying one rather
                than stripping it out, and it says which value stopped it.</li>
          </ul>
          <Field label="Approved by" value={a} onChange={setA} required
                 placeholder="A named person, not the builder"
                 hint={self ? "That is the person who formed it. The gate will refuse this." : undefined} />
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn primary" disabled={!a.trim() || !!self}
                    onClick={run("The promotion was refused",
                      () => platform.promoteClaim(eid, cl.id, a.trim()))}>
              Approve the crossing
            </button>
            <button className="btn ghost" onClick={props.onClose}>Cancel</button>
          </div>
        </Modal>
      );
    }

    default:
      return null;
  }
}
