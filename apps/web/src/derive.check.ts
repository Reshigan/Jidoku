// ponytail: one runnable check for the only non-trivial logic in the app.
// Run: npx tsx src/derive.check.ts  (or import from a scratch script)
import { buildLanes, lineStop, milestones } from "./derive";
import type { LedgerEntry, Plan } from "./api";

const e = (task: string, action: string, actor: string): LedgerEntry => ({
  ts: "2026-09-01T00:00:00Z", task, action, actor, detail: "", hash: "x", prev: "y",
});

const plan: Plan = {
  steps: [
    { seq: 1, key: "A", tier: "A", system: "S", product: "SuccessFactors", action: "API_WRITE" },
    { seq: 2, key: "B", tier: "A", system: "S", product: "SuccessFactors", action: "API_WRITE" },
    { seq: 3, key: "C", tier: "C", system: "S", product: "SuccessFactors", action: "UI_INSTRUCTION_HUMAN" },
  ],
  lanes: [["A", "B"], ["C"]],
  tier_summary: { A: 2, B: 0, C: 1 },
};

function assert(cond: boolean, msg: string) {
  if (!cond) throw new Error("FAIL: " + msg);
  console.log("ok -", msg);
}

// Fresh plan, empty ledger: nothing started, no milestone earned.
let lanes = buildLanes(plan, []);
assert(lanes[0].stations[0].stage === "waiting", "empty ledger leaves station waiting");
assert(lanes[0].stations[1].locked, "later station in a lane is locked until the earlier is approved");
assert(lanes[0].lamp === "idle", "untouched lane shows an idle lamp");
assert(milestones(lanes).every((m) => !m.earned), "no milestone earned without approvals");

// Snapshot -> Execute -> Approve moves the station and unlocks the next.
lanes = buildLanes(plan, [e("A", "SNAPSHOT", "rg"), e("A", "EXECUTED", "rg"), e("A", "APPROVED", "kt")]);
assert(lanes[0].stations[0].stage === "approved", "approval lands the station on approved");
assert(lanes[0].stations[0].builder === "rg" && lanes[0].stations[0].approver === "kt", "builder and approver read back");
assert(!lanes[0].stations[1].locked, "approving the earlier station unlocks the next");
assert(lanes[0].lamp === "call", "a part-done lane calls for a person");

// A rollback resets the run and stops the lane's lamp.
lanes = buildLanes(plan, [e("A", "SNAPSHOT", "rg"), e("A", "EXECUTED", "rg"), e("A", "ROLLED_BACK", "kt")]);
assert(lanes[0].stations[0].stage === "rolledback", "rollback wins over earlier progress");
assert(!lanes[0].stations[0].hasSnapshot, "rollback clears the snapshot: execution must be refused again");
assert(lanes[0].lamp === "stop", "a rolled-back lane shows a stop lamp");

// Milestones are earned only from full approval, and only in order.
const full = [
  e("A", "SNAPSHOT", "rg"), e("A", "EXECUTED", "rg"), e("A", "APPROVED", "kt"),
  e("B", "SNAPSHOT", "rg"), e("B", "EXECUTED", "rg"), e("B", "APPROVED", "kt"),
];
const ms = milestones(buildLanes(plan, full));
assert(ms[0].earned && !ms[1].earned, "a milestone is earned only when its lane is fully approved");

// The stop cord latches until it is released.
assert(lineStop([e("*", "LINE_STOP", "rg")]) !== null, "a stop cord pull halts the line");
assert(lineStop([e("*", "LINE_STOP", "rg"), e("*", "LINE_RESUME", "kt")]) === null, "a release restarts the line");

console.log("\nall derive checks passed");
