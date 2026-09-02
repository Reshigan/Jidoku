/* Evidence + Milestones — the proof, and what it earned.
   Split out of views.tsx: nine screens in one file meant every rebuild collided. views.tsx is now
   the barrel App.tsx imports from. */
import type { ReactNode } from "react";
import type { Evidence } from "./api";
import { type Milestone } from "./derive";
import { Empty, Pill, Seal, Section, Skeleton } from "./ui";
import { Facts, Hash, Meter, Track } from "./viz";
import type { TrackStop } from "./viz";
import "./views_record.css";

/* ---------------- 7 · Evidence ----------------
   An auditor's screen has one job: let someone who does not trust us check. So every artefact is
   shown next to the claim it backs — a digest with nothing beside it is a number, not proof. The
   hashes go through `Hash`, which shows head and tail with the full value on the title: the v1
   screen rendered 64 literal zeroes at full width, which was the loudest and least informative
   thing on the page and told the reader nothing they could compare. */
export function EvidenceView(props: {
  evidence: Evidence | null;
  onRefresh: () => void;
  onDownload: () => void;
}) {
  const b = props.evidence;
  if (!b) return <Skeleton rows={5} tall />;
  const v = b.chain.verification;
  const sod = b.separation_of_duties;
  const sodHeld = sod.filter((s) => s.separation_held).length;
  const snapped = sod.filter((s) => s.snapshot_present).length;
  const unresolved = b.decision_points.unresolved.length;

  /* The proof pairs. Left: the artefact. Right: what it is evidence of. Kept as data so the
     pairing is enforced — an artefact cannot be added here without stating what it proves. */
  const proofs: { eyebrow: string; art: ReactNode; claim: string }[] = [
    {
      eyebrow: "Bundle digest",
      art: <Hash value={b.manifest_sha256} />,
      claim: "Proves this bundle is the one that was issued. A changed byte anywhere inside it changes this digest.",
    },
    {
      eyebrow: "Genesis",
      art: <Hash value={b.chain.genesis} />,
      claim: "Proves the chain has a fixed start, so no earlier history can be forged underneath the first entry.",
    },
    {
      eyebrow: "Head of chain",
      art: <Hash value={v.head ?? ""} />,
      claim: v.verified
        ? `Proves the ${v.entries ?? b.chain.entries.length} entries recomputed to the value that was stored.`
        : "Recomputation did not reach the stored head. Read the break above before trusting anything below it.",
    },
    {
      eyebrow: "Sources of intent",
      art: b.ir.sources.length ? (
        <>
          {b.ir.sources.map((s) => (
            <span className="mono" key={s} style={{ fontSize: 11.5 }} title={s}>{s}</span>
          ))}
        </>
      ) : (
        <span className="mut">None</span>
      ),
      claim: b.ir.sources.length
        ? "Proves every record executed here came from signed intent. Nothing unsigned can be loaded."
        : "No signed intent is loaded, so nothing here was executed from a design document.",
    },
  ];

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

      {/* The bundle's constants, dense. v1 spread these across three cards with a paragraph each
          and still left most of the row empty. */}
      <Facts items={[
        { k: "Client", v: b.engagement.client },
        { k: "Engagement", v: b.engagement.name },
        { k: "Phase", v: b.engagement.phase },
        { k: "Entries", v: String(b.chain.entries.length), mono: true },
        { k: "Signed records", v: String(b.ir.records), mono: true },
        { k: "Open decisions", v: unresolved ? `${unresolved} still open` : "None open", mono: true },
        { k: "Halts on record", v: String(b.line_state.halt_events.length), mono: true },
      ]} />

      <div className="board fill">
        <Section title="What this bundle proves"
                 note="Each artefact next to the claim it backs — full value on hover"
                 className="grow scrolls">
          <div className="ev-proofs">
            {proofs.map((p) => (
              <div className="ev-proof" key={p.eyebrow}>
                <div className="ev-proof-art">
                  <span className="eyebrow">{p.eyebrow}</span>
                  {p.art}
                </div>
                <div className="ev-proof-claim">{p.claim}</div>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Separation of duties"
                 note="Recomputed from history, not asserted from roles"
                 lamp={sod.length && sodHeld === sod.length ? "run" : sod.length ? "stop" : "idle"}
                 status={sod.length ? (sodHeld === sod.length ? "Held on every task" : "Violated") : "Nothing approved"}
                 /* One sentence cannot fill a row its neighbour sets the height of, and a panel
                    stretched over nothing reads as "no more to see". Before anything is approved
                    this panel sizes to its own content; once the table exists it takes the slack. */
                 className={sod.length ? "grow scrolls" : ""}>
          {sod.length === 0 ? (
            <span className="mut">Nothing has been approved yet, so there is no separation to check.</span>
          ) : (
            <>
              {/* Two ratios, stated flatly — bad ones included. Reading "9/12" is faster than
                  counting a column of pills, and it is the same number an auditor would compute. */}
              <div className="cols" style={{ marginBottom: 10 }}>
                <div>
                  <div className="eyebrow">Builder was not the approver</div>
                  <Meter value={sodHeld} of={sod.length} label="Separation held"
                         tone={sodHeld === sod.length ? "run" : "stop"} />
                </div>
                <div>
                  <div className="eyebrow">Approved on a prior snapshot</div>
                  <Meter value={snapped} of={sod.length} label="Snapshot present"
                         tone={snapped === sod.length ? "run" : "stop"} />
                </div>
              </div>
              <div className="scroll-x">
                <table className="tbl">
                  <thead>
                    <tr><th>Task</th><th>Executed by</th><th>Approved by</th><th>Separation</th><th>Snapshot</th></tr>
                  </thead>
                  <tbody>
                    {sod.map((s) => (
                      <tr key={s.task}>
                        <td className="mono">{s.task}</td>
                        <td>{s.executed_by.join(", ") || "—"}</td>
                        <td>{s.approved_by ? <Seal name={s.approved_by} kanji="承" /> : "—"}</td>
                        <td><Pill lamp={s.separation_held ? "run" : "stop"}>{s.separation_held ? "Held" : "Violated"}</Pill></td>
                        <td><Pill lamp={s.snapshot_present ? "run" : "stop"}>{s.snapshot_present ? "Present" : "Missing"}</Pill></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Section>

        <Section title="How to verify this yourself"
                 note="Reimplementable in any language, without JIDOKA running"
                 className="span2">
          <div className="verbatim calm">{b.chain.verify_procedure}</div>
        </Section>
      </div>
    </>
  );
}

/* ---------------- 8 · Milestones ----------------
   Rebuilt. v1 drew one card per milestone — a name at the far left, an "Earned / Not yet" pill at
   the far right, and a thousand pixels of nothing between them; measured at ~78% dead space. Two
   passes of layout CSS did not move it, because the fault was never layout: four one-line cards
   have nothing to fill a screen with.

   What a milestone actually is: a gate on an ordered run, opened only by approvals already on the
   ledger. So it is drawn as that run (`Track`), and each milestone shows the ratio that earned it
   or is still short of earning it (`Meter`). Per apps/web/CLAUDE.md, EARNED status only — the
   `earned` flag from derive.ts is the sole thing that may show green, and a phase that is fully
   approved but sits behind an unearned one is still not earned. */
export function MilestonesView(props: { milestones: Milestone[]; planBlock: string | null }) {
  if (props.planBlock) {
    return <Empty title="No milestones yet"
                  body="Milestones are earned from approved checkpoints, and there is no plan to earn them against."
                  verbatim={props.planBlock} />;
  }
  if (!props.milestones.length) return <Skeleton rows={4} tall />;

  const ms = props.milestones;
  const earned = ms.filter((m) => m.earned).length;
  const approved = ms.reduce((n, m) => n + m.approved, 0);
  const total = ms.reduce((n, m) => n + m.total, 0);
  /* The first unearned milestone is where the line actually is. Everything after it is waiting on
     that one, not on itself — which is the fact the old flat list hid. */
  const nextIdx = ms.findIndex((m) => !m.earned);
  const next = nextIdx === -1 ? null : ms[nextIdx];

  const stops: TrackStop[] = ms.map((m, i) => ({
    id: String(m.lane),
    label: m.name.replace(/ complete$/, ""),
    sub: m.earned ? "Earned" : i === nextIdx ? "In hand" : "Waiting on the phase before it",
    state: m.earned ? "done" : i === nextIdx ? "current" : "todo",
    badge: <Meter value={m.approved} of={m.total} label={m.name}
                  tone={m.earned ? "run" : i === nextIdx ? "call" : "blue"} />,
  }));

  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">Milestones</div>
          <h1>What has actually been earned</h1>
        </div>
        <span className="mut">A milestone is earned by approvals on the ledger, never declared.</span>
      </div>

      <Facts items={[
        { k: "Earned", v: `${earned} of ${ms.length}`, mono: true },
        { k: "Checkpoints approved", v: `${approved} of ${total}`, mono: true },
        {
          k: "Next milestone",
          v: next ? next.name.replace(/ complete$/, "") : "None — all earned",
        },
        {
          k: "What it is short of",
          v: next ? `${next.total - next.approved} approval${next.total - next.approved === 1 ? "" : "s"}` : "Nothing",
          mono: true,
        },
      ]} />

      <Section title="The run"
               note="Each gate opens only when every checkpoint before it is approved"
               lamp={earned === ms.length ? "run" : "call"}
               status={earned === ms.length ? "All earned" : `${earned} earned`}>
        <div className="ms-run">
          <Track stops={stops} note="Milestones, in order" />
        </div>
      </Section>

      {/* One milestone is a real engagement shape, but one row above 350px of nothing reads as a
          failure to render. The row keeps its height and the slack goes to the thing the operator
          would ask next — which checkpoints, by name, are still short of earning it. */}
      <Section title="Every milestone, and what earned it"
               note="Approvals counted off the ledger, not off the plan"
               className="grow scrolls">
        <div className="ms-list" data-sparse={ms.length === 1}>
          {ms.map((m, i) => {
            const short = m.total - m.approved;
            /* Three states, not two. A phase behind an unearned one is neither earned nor "nearly"
               — it is not its own turn yet, and saying so is more useful than an amber pill. */
            const kind = m.earned ? "true" : i === nextIdx ? "false" : "blocked";
            return (
              <div className="ms-row" key={m.lane} data-earned={kind}>
                <span className="ms-idx">{String(i + 1).padStart(2, "0")}</span>
                <span className="ms-name">{m.name}</span>
                <Meter value={m.approved} of={m.total} label={m.name}
                       tone={m.earned ? "run" : i === nextIdx ? "call" : "blue"} />
                <span className="ms-say">
                  {m.earned
                    ? "Every checkpoint here, and in every phase before it, is approved."
                    : m.total === 0
                      ? "This phase has no checkpoints, so there is nothing to earn it with."
                      : i === nextIdx
                        ? `${short} checkpoint${short === 1 ? "" : "s"} still waiting on a person to approve.`
                        : `${m.approved} of ${m.total} approved here, but an earlier phase has to finish first.`}
                </span>
                <Pill lamp={m.earned ? "run" : i === nextIdx ? "call" : undefined}>
                  {m.earned ? "Earned" : i === nextIdx ? "Not yet" : "Not its turn"}
                </Pill>
              </div>
            );
          })}
          {/* One milestone: the row keeps its height and the slack states the rule that decides it,
              counted out. Only the counts are on hand here — naming which checkpoints are short
              would mean inventing them, so this says how many and what opens the gate, no more. */}
          {ms.length === 1 && (
            <div className="ms-open">
              <div className="eyebrow">What opens this gate</div>
              <p className="ms-open-say">
                {ms[0].total === 0
                  ? "This phase has no checkpoints on the plan, so nothing can earn it. Load the intent that plans them."
                  : ms[0].earned
                    ? `All ${ms[0].total} checkpoint${ms[0].total === 1 ? "" : "s"} in this phase are approved on the ledger, so the milestone is earned. It was not declared — it was counted.`
                    : `${ms[0].total - ms[0].approved} of ${ms[0].total} checkpoint${ms[0].total === 1 ? "" : "s"} here are not yet approved. Each one needs a before-snapshot, a write, a validation, and an approver who did not build it. The Work board is where those run.`}
              </p>
              <Meter value={ms[0].approved} of={ms[0].total} label={ms[0].name}
                     tone={ms[0].earned ? "run" : "call"} />
            </div>
          )}
        </div>
      </Section>
    </>
  );
}
