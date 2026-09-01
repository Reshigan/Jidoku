/* Line + Work — the shop floor.
   Split out of views.tsx: nine screens in one file meant every rebuild collided. views.tsx is now
   the barrel App.tsx imports from. */
import type { DecisionPoint, EngagementDetail, LedgerEntry, Plan } from "./api";
import { STAGE_WORDS, type Lane, type Stage, type Station } from "./derive";
import { Empty, Pill, Section, Skeleton } from "./ui";
import { Chain, Facts, Meter, Track } from "./viz";
import type { ChainNode, TrackStop } from "./viz";
import { detailWords, fmt, humanAction, stepWords, taskWords } from "./viewkit";
import "./views_line.css";

/* The gates every station runs, in order. Both views draw from this one list: the Line's lane
   summary and the Work board's per-station track have to agree about what "third of five" means,
   and they only do that if there is one definition of the run. Rolledback is deliberately absent —
   it is not a gate you pass, it is the run being thrown away, so it is drawn as a stopped track. */
const GATES: { stage: Stage; label: string }[] = [
  { stage: "waiting", label: "Not started" },
  { stage: "snapshot", label: "Snapshot" },
  { stage: "executed", label: "Executed" },
  { stage: "validated", label: "Validated" },
  { stage: "approved", label: "Approved" },
];

const GATE_AT: Record<Stage, number> = {
  waiting: 0, snapshot: 1, executed: 2, validated: 3, approved: 4, rolledback: 0,
};

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

  const stations = props.lanes.flatMap((l) => l.stations);
  const approved = stations.filter((s) => s.stage === "approved").length;
  const total = stations.length;
  const waiting = props.dps.filter((x) => !x.resolution).length;
  const at = d.phases.indexOf(d.phase);

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

      {/* The engagement's constants, dense. Four counters spread across 1500px was the widest
          instance of the "label left, number right, void between" fault the audit found. */}
      <Facts items={[
        { k: "Client", v: d.client },
        { k: "Phase", v: d.phase },
        { k: "Signed intent", v: `${d.ir_records} records`, mono: true },
        { k: "Stations approved", v: `${approved}/${total}`, mono: true },
        { k: "Waiting on a person", v: waiting ? `${waiting} decision${waiting === 1 ? "" : "s"}` : "Nothing", mono: true },
        { k: "Ledger entries", v: String(d.ledger_entries), mono: true },
      ]} />

      {props.planBlock && (
        <div className="banner" data-lamp="call">
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

      {/* The phase run is a gated progression, so it is a Track, not five boxes in a row. The
          advance controls sit against the panel header — they act on the whole phase, and putting
          them there stops the panel body from ending in a stranded button row. */}
      <Section title="Phase"
               note="Forward only. A phase advance declares work complete, so it is an approval-grade act."
               actions={
                 d.next_phases.length === 0
                   ? <span className="mut">This is the final phase.</span>
                   : <>
                       {!props.canAdvance && <span className="mut">Waiting on someone who may approve.</span>}
                       {d.next_phases.map((n) => (
                         <button key={n} className="btn primary" disabled={!props.canAdvance}
                                 onClick={() => props.onAdvance(n)}>
                           Advance to {n}
                         </button>
                       ))}
                     </>
               }>
        <Track note="Build phases"
               stops={d.phases.map((p, i): TrackStop => ({
                 id: p,
                 label: p,
                 sub: i < at ? "complete" : i === at ? "current" : "not started",
                 state: i < at ? "done" : i === at ? "current" : "todo",
               }))} />
      </Section>

      <div className="board fill">
        {/* Lanes run in parallel, so they are listed as parallel runs with the earned ratio drawn.
            A lamp on its own says "amber"; a lamp beside 2/7 says how much amber. */}
        {/* One lane is the honest shape of a small engagement, not a rendering fault — but a row and
            700px of nothing reads as one. So a single lane opens: the row keeps its size and the
            slack below it carries that lane's stations, which is what the operator would click
            through to next anyway. With several lanes the rows fill the panel on their own.

            Not `grow` though: a lane list is a handful of rows however it is opened, and cannot
            fill a screen's height. Claiming the row's slack as well left 764px of void under it —
            both panels asked for the slack and only the activity feed beside it can use it. */}
        <Section title="Lanes" note={total ? `${approved} of ${total} stations approved` : "No plan built yet"}
                 className="scrolls">
          {!total ? (
            <span className="mut">Nothing to run until the plan builds.</span>
          ) : (
            <div className="lanes" data-sparse={props.lanes.length === 1}>
              {props.lanes.map((lane) => {
                const done = lane.stations.filter((s) => s.stage === "approved").length;
                const now = lane.stations.find((s) => !s.locked && s.stage !== "approved");
                return (
                  <div className="lane-row" key={lane.index} data-lamp={lane.lamp}>
                    <span className="lane-name">{lane.name}</span>
                    <Meter value={done} of={lane.stations.length} label={lane.name}
                           tone={lane.lamp === "stop" ? "stop" : lane.lamp === "run" ? "run" : "call"} />
                    <span className="lane-at mut">
                      {lane.lamp === "stop" ? "Rolled back — needs a fresh snapshot"
                        : done === lane.stations.length ? "Every station approved"
                        : now ? `Now: ${stepWords(now.step)}`
                        : "Not started"}
                    </span>
                    <Pill lamp={lane.lamp}>{laneWord(lane.lamp)}</Pill>
                  </div>
                );
              })}
              {props.lanes.length === 1 && (
                <div className="lane-open">
                  <div className="eyebrow">Every station in this phase</div>
                  <ol className="lane-stations">
                    {props.lanes[0].stations.map((s) => (
                      <li key={s.step.key} data-lamp={stationLamp(s)}>
                        <span className="lane-station-what">{stepWords(s.step)}</span>
                        <span className="lane-station-at mut">{STAGE_WORDS[s.stage]}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          )}
        </Section>

        <Section title="Recent activity" note="The last of the ledger, newest first." className="grow scrolls">
          {!props.entries ? <Skeleton /> : props.entries.length === 0 ? (
            <span className="mut">Nothing has happened on this engagement yet.</span>
          ) : (
            /* The chain is a narrative, so it speaks the way a person does — the raw task key and
               the raw detail belong to the Ledger table, which is the auditor's copy and stays raw.
               A detail that cannot be said faithfully is dropped rather than guessed at. */
            <Chain dense nodes={[...props.entries].reverse().slice(0, 24).map((e): ChainNode => {
              const said = detailWords(e.task, e.detail);
              return {
                id: e.hash,
                lamp: lampForAction(e.action),
                title: humanAction(e.action),
                meta: taskWords(e.task),
                body: `${e.actor}${said ? ` · ${said}` : ""} · ${fmt(e.ts)}`,
              };
            })} />
          )}
        </Section>
      </div>
    </>
  );
}

function lampForAction(a: string): ChainNode["lamp"] {
  if (a === "APPROVED" || a === "VALIDATED") return "run";
  if (a === "LINE_STOP" || a === "ROLLED_BACK") return "stop";
  if (a === "DP_RAISED") return "call";
  return "idle";
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

      {/* One panel per phase, side by side — a lane is a column on the floor, not a full-width band.
          With a single phase the board would otherwise stop at the height of its one panel and leave
          the rest of the glass empty, which reads as a screen that failed to finish drawing. data-fill
          makes the panel claim the height, and the order of the run underneath it takes the slack —
          the cards say what each station is, the order says which one the floor reaches next. */}
      <div className="board fill" data-fill={props.lanes.length === 1 ? "stretch" : undefined}>
      {props.lanes.map((lane, i) => (
        <Section key={i} title={`Phase ${i + 1}`}
                 className="grow scrolls"
                 note={`${lane.stations.filter((s) => s.stage === "approved").length} of ${lane.stations.length} approved`}
                 lamp={lane.lamp} status={laneWord(lane.lamp)}>
          <div className="grid">
            {lane.stations.map((s) => (
              <StationCard key={s.step.key} s={s} {...props} />
            ))}
          </div>
          {props.lanes.length === 1 && <LaneOrder lane={lane} />}
        </Section>
      ))}
      </div>
    </>
  );
}

/**
 * The order of the run, under the cards, when a phase is the only phase on the board.
 *
 * It states nothing the cards do not already carry — the same stations, the same stages — but it
 * states it as a sequence, which is the one thing the cards cannot show: a station opens when the
 * one before it is approved, so "which is next" is a fact about the order, not about any one card.
 * With several phases the board is full and the cards speak for themselves, so this stays off.
 */
function LaneOrder({ lane }: { lane: Lane }) {
  const next = lane.stations.find((s) => !s.locked && s.stage !== "approved");
  return (
    <div className="lane-order">
      <div className="eyebrow">The order of this run</div>
      <ol className="lane-order-list">
        {lane.stations.map((s, i) => (
          <li key={s.step.key} data-lamp={stationLamp(s)} data-next={s === next || undefined}>
            <span className="lane-order-idx">{String(i + 1).padStart(2, "0")}</span>
            <span className="lane-order-what">{stepWords(s.step)}</span>
            <span className="lane-order-at mut">
              {s === next ? `Open now · ${STAGE_WORDS[s.stage]}`
                : s.locked ? "Opens when the one before it is approved"
                : STAGE_WORDS[s.stage]}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function stationLamp(s: Station) {
  if (s.stage === "rolledback") return "stop";
  if (s.stage === "approved") return "run";
  if (s.stage === "validated") return "call";
  if (s.locked) return "idle";
  return s.stage === "waiting" ? "idle" : "blue";
}

function laneWord(l: string) {
  return l === "run" ? "Complete" : l === "stop" ? "Rolled back" : l === "call" ? "In progress" : "Not started";
}

/**
 * Where the station sits on its run, drawn. The stage word alone ("Validated — waiting on a
 * person to approve") makes the operator read a sentence to learn a position; the track makes it a
 * glance, and a locked station's track is entirely blocked so it looks shut rather than merely dim.
 */
function stationTrack(s: Station): TrackStop[] {
  const at = GATE_AT[s.stage];
  const rolled = s.stage === "rolledback";
  return GATES.map((g, i): TrackStop => ({
    id: g.stage,
    label: g.label,
    /* "blocked" draws red, and red is stop — something went wrong. A locked station is not wrong,
       it simply has not had its turn, so every gate is "todo" and the card's own dimming and its
       "locked until" line carry the state. Red is kept for the rollback, where a run really was
       thrown away. Teaching an operator that red can mean "not yet" is how an andon rail dies. */
    state: s.locked ? "todo"
      : rolled ? (i === 0 ? "blocked" : "todo")
      : i < at ? "done" : i === at ? "current" : "todo",
  }));
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
      <div className="station-head">
        <span className="title">{stepWords(s.step)}</span>
        <span className="tier" data-t={s.step.tier}>Tier {s.step.tier}</span>
        <Pill lamp={stationLamp(s)}>{STAGE_WORDS[s.stage]}</Pill>
      </div>
      {/* The key is the platform's identifier, not a person's words — BRAND is absolute about that.
          The system id stays: a consultant says "KOM-S4-DEV" out loud, and it is the one fact this
          line adds that the title above it does not already carry. */}
      <div className="key">{s.step.system}</div>

      <div className="station-track">
        <Track stops={stationTrack(s)} note={stepWords(s.step)} />
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
