/* Configure — the execution console.
   Split out of views.tsx: nine screens in one file meant every rebuild collided. views.tsx is now
   the barrel App.tsx imports from.

   This is deliberately the least eager screen in the product, and the rebuild does not soften that
   by a pixel. Dry run stays the default action. Arming stays visible at all times rather than
   tucked behind a menu, because a target that can take a real write must never be a surprise.
   Every refusal the server issues is quoted verbatim by App.tsx's modal and is not reworded here.

   What the rebuild changes is only legibility of state: invariant 6 says a live write needs an
   explicit armed target AND a prior ledger snapshot, and v1 never showed whether either held —
   the operator had a system id at one edge and an Arm button at the other. Now each precondition
   is named next to the target it belongs to, and the run of gates a live write has to clear is
   drawn as the run it is. Showing that arming is hard is not making it easier. */
import type { ArmedTarget, Connector, ExecutionResult, Plan, StepTransport } from "./api";
import { Empty, Pill, Section, Skeleton } from "./ui";
import { Facts, Track } from "./viz";
import type { TrackStop } from "./viz";
import { STATUS_LAMP, STATUS_WORDS, isAbap, statusName, stepWords } from "./viewkit";
import "./views_config.css";

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
  const snappedKeys = tierA.filter((s) => props.snapshots[s.key] !== undefined).length;
  /* Invariant 6, read off the state rather than assumed: a real write needs a connector, an armed
     target and a before-snapshot on that step. Any one missing and the platform rehearses. */
  const liveReachable = tierA.some(
    (s) => bound.has(s.system) && armedIds.has(s.system) && props.snapshots[s.key] !== undefined,
  );

  /* The gates a live write has to clear, in the order the platform enforces them. Drawn so the
     operator can see how far the screen is from being able to write for real — which on a normal
     day is "not close", and that is the point. */
  const gates: TrackStop[] = [
    {
      id: "connector",
      label: "Connector bound",
      sub: `${bound.size} of ${systems.length} systems`,
      state: bound.size === systems.length ? "done" : bound.size ? "current" : "todo",
    },
    {
      id: "snapshot",
      label: "Before-snapshot taken",
      sub: `${snappedKeys} of ${tierA.length} platform-written steps`,
      state: tierA.length && snappedKeys === tierA.length ? "done" : snappedKeys ? "current" : "todo",
    },
    {
      id: "armed",
      label: "Target armed by an approver",
      sub: armedIds.size ? `${armedIds.size} armed` : "None armed",
      /* A gate that is satisfied is done, not in progress. This sat on "current" forever once
         anything was armed, so the rail read as amber-mid-flight on a screen that had in fact
         finished the step — and amber on this screen is the colour of "a person still has to act". */
      state: armedIds.size ? "done" : "todo",
    },
    {
      id: "write",
      label: "Live write possible",
      sub: liveReachable ? "Yes — on the armed, snapshotted steps" : "No — the platform will rehearse",
      /* Not "blocked". Red is stop and stop means failure; a reachable live write is this run of
         gates succeeding, and painting success red spends the one colour the operator must be able
         to trust as an alarm. Rehearsal-only is the ordinary resting state of this screen, so it is
         todo — the gate simply has not opened — and an open gate is done. The weight of "a real
         write is now possible" is carried by the panel's own lamp and by the armed pills, which is
         where a consequence belongs; the rail's job is only to say how far along the run we are. */
      state: liveReachable ? "done" : "todo",
    },
  ];

  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">Configure</div>
          <h1>Write the configuration</h1>
        </div>
        {/* Not run/green for the safe case. Rehearsal is the resting state of this screen, and a
            green lamp on "nothing is armed" spends the run colour on the absence of an event. */}
        <Pill lamp={live ? "stop" : undefined}>
          {live ? `${live} step${live === 1 ? "" : "s"} armed for live` : "Dry run"}
        </Pill>
      </div>

      {/* The screen's constants, stated flatly. A person arriving here should be able to answer
          "can anything real happen right now" without clicking. */}
      <Facts items={[
        { k: "Steps in the plan", v: String(props.plan.steps.length), mono: true },
        { k: "Written by the platform", v: `${tierA.length} of ${props.plan.steps.length}`, mono: true },
        { k: "Systems", v: `${bound.size} of ${systems.length} connected`, mono: true },
        { k: "Armed targets", v: armedIds.size ? `${armedIds.size} armed` : "None armed", mono: true },
        { k: "Before-snapshots", v: `${snappedKeys} of ${tierA.length}`, mono: true },
        { k: "A real write is", v: liveReachable ? "possible on some steps" : "not possible yet" },
      ]} />

      <Section title="What a live write has to clear"
               note="Every gate below has to hold before anything is written for real"
               lamp={liveReachable ? "stop" : undefined}
               status={liveReachable ? "A real write is possible" : "Rehearsal only"}>
        <Track stops={gates} note="Gates on a live write" />
      </Section>

      <Section title="Armed targets"
               note="A live write needs an approver to arm the target first — and the person who arms it may not be the one who runs it"
               lamp={armedIds.size ? "stop" : undefined}
               status={armedIds.size ? "Writes are real" : "Rehearsal only"}>
        <div className="cfg-targets">
          {systems.map((sid) => {
            const a = props.armed.find((x) => x.system_id === sid);
            const c = bound.get(sid);
            return (
              <div className="cfg-target" key={sid} data-armed={a ? "true" : "false"}>
                <div>
                  <div className="cfg-sys">{sid}</div>
                  <div className="cfg-say">
                    {a
                      ? `Armed by ${a.armed_by}${a.reason ? ` — ${a.reason}` : ""}.`
                      : "Not armed."}
                  </div>
                </div>
                {/* Unbound is the more fundamental fact than unarmed: without a connector the
                    platform cannot even read the before-state, so no live write is reachable. */}
                <div className="cfg-gate">
                  <span className="eyebrow">Connector</span>
                  <span className="cfg-say">
                    {c
                      ? `Connected — ${c.kind} (${c.describe}).`
                      : "None bound. The platform can rehearse against this system but cannot read or write it."}
                  </span>
                </div>
                <div className="cfg-gate">
                  <span className="eyebrow">What happens if a step runs</span>
                  <span className="cfg-say">
                    {a && c
                      ? "Writes to this system are real."
                      : a
                        ? "Armed, but with no connector nothing can reach the system."
                        : "Anything run against this system is a rehearsal."}
                  </span>
                </div>
                <div className="cfg-actions">
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
                    <Pill lamp={a ? "stop" : undefined}>{a ? "Armed for live" : "Rehearsal only"}</Pill>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      <Section title="Steps"
               note="Tier A is written by the platform. Tier B and C produce something for a person to carry out."
               status={`${props.plan.steps.length} step${props.plan.steps.length === 1 ? "" : "s"}`}
               className="grow scrolls">
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
                          <Pill lamp={STATUS_LAMP[res.status] ?? "call"}>{statusName(res.status)}</Pill>
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
