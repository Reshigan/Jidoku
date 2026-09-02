// The ledger is the only record of what happened. Everything the board shows is read back out of it.
// Nothing here invents state: a station is where its ledger entries put it, and nowhere else.
import type { DecisionPoint, LedgerEntry, Plan, PlanStep } from "./api";

/** Where a station sits on the Snapshot -> Execute -> Validate -> Approve run. */
export type Stage =
  "waiting" | "snapshot" | "rehearsed" | "executed" | "validated" | "approved" | "rolledback";

/** Plain, human words for each stage. Never the internal token. */
export const STAGE_WORDS: Record<Stage, string> = {
  waiting: "Not started",
  snapshot: "Snapshot taken",
  rehearsed: "Rehearsed — nothing was written yet",
  executed: "Executed — waiting on a validator",
  validated: "Validated — waiting on a person to approve",
  approved: "Approved",
  rolledback: "Rolled back",
};

export type Station = {
  step: PlanStep;
  stage: Stage;
  entries: LedgerEntry[];
  builder: string | null;
  approver: string | null;
  hasSnapshot: boolean;
  /** Locked because an earlier station in the same lane is not approved. */
  locked: boolean;
};

export type Lane = {
  index: number;
  /** BRAND calls these build phases; the planner calls them lanes. One lamp each. */
  name: string;
  stations: Station[];
  lamp: Lamp;
};

export type Lamp = "run" | "call" | "stop" | "idle";

const ORDER: Record<Stage, number> = {
  waiting: 0,
  snapshot: 1,
  rehearsed: 2,
  executed: 3,
  validated: 4,
  approved: 5,
  rolledback: 6,
};

const ACTION_STAGE: Record<string, Stage> = {
  SNAPSHOT: "snapshot",
  // A dry run is work that happened and wrote nothing. Without a stage of its own the station
  // sat on "Snapshot taken" with an Execute button that appeared to do nothing at all — the
  // operator's only reading of that is a broken screen, when the truth is invariant 6 holding.
  DRY_RUN: "rehearsed",
  EXECUTED: "executed",
  VALIDATED: "validated",
  APPROVED: "approved",
  ROLLED_BACK: "rolledback",
};

export const LINE_STOP = "LINE_STOP";
export const LINE_RESUME = "LINE_RESUME";

/** The most recent stop cord pull that has not been released, or null if the line runs. */
export function lineStop(entries: LedgerEntry[]): LedgerEntry | null {
  for (let i = entries.length - 1; i >= 0; i--) {
    if (entries[i].action === LINE_STOP) return entries[i];
    if (entries[i].action === LINE_RESUME) return null;
  }
  return null;
}

function stationFrom(step: PlanStep, entries: LedgerEntry[]): Omit<Station, "locked"> {
  const mine = entries.filter((e) => e.task === step.key);
  let stage: Stage = "waiting";
  let builder: string | null = null;
  let approver: string | null = null;
  let hasSnapshot = false;
  for (const e of mine) {
    if (e.action === "SNAPSHOT") hasSnapshot = true;
    if (e.action === "EXECUTED") builder = e.actor;
    if (e.action === "APPROVED") approver = e.actor;
    const s = ACTION_STAGE[e.action];
    // A rollback resets the run; anything else only ever moves forward.
    if (s === "rolledback") {
      stage = "rolledback";
      builder = null;
      approver = null;
      hasSnapshot = false;
    } else if (s && (stage === "rolledback" || ORDER[s] > ORDER[stage])) {
      stage = s;
    }
  }
  return { step, stage, entries: mine, builder, approver, hasSnapshot };
}

export function buildLanes(plan: Plan, entries: LedgerEntry[]): Lane[] {
  const bySeq = new Map(plan.steps.map((s) => [s.key, s]));
  return plan.lanes.map((keys, index) => {
    let blocked = false;
    const stations: Station[] = [];
    for (const key of keys) {
      const step = bySeq.get(key);
      if (!step) continue;
      const base = stationFrom(step, entries);
      stations.push({ ...base, locked: blocked });
      if (base.stage !== "approved") blocked = true;
    }
    return { index, name: `Phase ${String(index + 1).padStart(2, "0")}`, stations, lamp: laneLamp(stations) };
  });
}

function laneLamp(stations: Station[]): Lamp {
  if (!stations.length) return "idle";
  if (stations.some((s) => s.stage === "rolledback")) return "stop";
  if (stations.every((s) => s.stage === "approved")) return "run";
  if (stations.some((s) => s.stage !== "waiting")) return "call";
  return "idle";
}

/** A milestone is earned when every station in every lane up to and including it is approved. */
export type Milestone = { lane: number; name: string; earned: boolean; approved: number; total: number };

export function milestones(lanes: Lane[]): Milestone[] {
  let allPriorEarned = true;
  return lanes.map((l) => {
    const approved = l.stations.filter((s) => s.stage === "approved").length;
    const earned = allPriorEarned && l.stations.length > 0 && approved === l.stations.length;
    if (!earned) allPriorEarned = false;
    return { lane: l.index, name: `${l.name} complete`, earned, approved, total: l.stations.length };
  });
}

/** What a blocked decision needs before the station it gates can move. */
export function dpRelease(dp: DecisionPoint): string {
  switch (dp.dp_type) {
    case "STATUTORY":
      return "Needs a signed client evidence reference. JIDOKA will not supply a statutory value.";
    case "ONE_WAY":
      return "Needs two different named approvers. The same person cannot count twice.";
    case "SEQUENCE":
      return "Needs the owner to confirm the order of work before the line moves on.";
    case "COMMERCIAL":
      return "Needs a commercial decision from the client before the line moves on.";
    default:
      return "Needs the named owner to decide.";
  }
}
