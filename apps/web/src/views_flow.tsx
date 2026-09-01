/* Decisions + Landscape — what blocks, and where it lands.
   Split out of views.tsx: nine screens in one file meant every rebuild collided. views.tsx is now
   the barrel App.tsx imports from. */
import type { DecisionPoint, Landscape, SystemRecord } from "./api";
import { dpRelease } from "./derive";
import { kindWords, roleLabel } from "./viewkit";
import { Empty, Pill, Section, Skeleton } from "./ui";
import { Facts, Flow, Meter, Track } from "./viz";
import type { GraphNode, TrackStop } from "./viz";
import "./views_flow.css";

/* ---------------- 3 · Decisions ---------------- */

/**
 * The queue of things holding the line. Invariant 2 says an open decision point hard-blocks
 * planning, so the screen leads with that consequence rather than leaving it to be inferred from
 * a panel title: the count of open decisions is the count of reasons the plan will not build.
 */
export function DecisionsView(props: {
  dps: DecisionPoint[] | null;
  irGaps: Record<string, string[]>;
  writable: boolean;
  onResolve: (dp: DecisionPoint) => void;
  onRaise: () => void;
}) {
  const all = props.dps ?? [];
  const open = all.filter((d) => !d.resolution);
  const done = all.filter((d) => d.resolution);
  const gapKeys = Object.keys(props.irGaps);
  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">Decisions</div>
          <h1>{open.length ? "The line is waiting on a person" : "Nothing is waiting on a person"}</h1>
        </div>
        <button className="btn" onClick={props.onRaise} disabled={!props.writable}>Raise a decision</button>
      </div>

      {/* The screen's constants in one dense strip. Previously these were a title on the left and a
          pill on the right with the whole viewport between them. */}
      <div className="fl-strip">
        <Facts items={[
          { k: "Holding the line", v: open.length ? `${open.length} open` : "None" },
          { k: "Taken", v: <Meter value={done.length} of={all.length || 1} tone="run" label="Decided" /> },
          {
            k: "Planning",
            v: open.length ? "Blocked until these are taken" : "Nothing here blocks it",
          },
          { k: "Gaps in signed intent", v: gapKeys.length ? `${gapKeys.length} record(s)` : "None", mono: gapKeys.length > 0 },
        ]} />
      </div>

      {gapKeys.length > 0 && (
        <div className="banner" data-lamp="call">
          <span className="bar" />
          <div>
            <strong>{gapKeys.length} record(s) of signed intent have gaps.</strong>
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

      {!props.dps ? <Skeleton rows={4} tall /> : all.length === 0 ? (
        <Empty title="No decisions raised"
               body="Raise a decision when the workbook leaves a question open. JIDOKA never invents a statutory or client value — it stops the line and asks the named owner." />
      ) : (
        /* `fill` so the panels take the glass instead of stacking in the top third, and data-fill so
           they claim the height rather than stopping at whichever has the most content. A queue with
           one card in it is the normal shape of this screen, not a failure to load, and the panels
           are the screen — a board ending mid-glass is what reads as the failure. */
        <div className="board fill" data-fill="stretch">
          <Section title="Open" note={`${open.length} unresolved`} lamp={open.length ? "call" : "run"}
                   status={open.length ? "Waiting on a person" : "Nothing open"}
                   className="grow scrolls">
            {open.length === 0 ? (
              /* An empty queue is the good state, so it says so and then says what would fill it.
                 The gates are invariant 5's, the same ones needsOf draws on a card — stated here
                 because with nothing open there is no card to read them from. */
              <div className="fl-quiet">
                <span className="mut">Nothing is blocked on a human right now.</span>
                <div className="fl-quiet-rule">
                  <div className="eyebrow">What would stop the line here</div>
                  <ul className="fl-quiet-list">
                    <li>A workbook value nobody answered. JIDOKA raises the question rather than
                        inventing the number.</li>
                    <li>A one-way decision, which needs two different named people — the person who
                        decides cannot also countersign.</li>
                    <li>A statutory decision, which needs a signed client evidence reference before
                        it can be taken.</li>
                  </ul>
                  <div className="mut" style={{ fontSize: 12 }}>
                    While anything is open here the plan will not build.
                  </div>
                </div>
              </div>
            ) : (
              <div className="fl-dp">{open.map((d) => <DPCard key={d.dp_id} dp={d} {...props} />)}</div>
            )}
          </Section>
          {done.length > 0 && (
            <Section title="Taken" note={`${done.length} decided`} lamp="run" status="Decided"
                     className="grow scrolls">
              <div className="fl-dp">{done.map((d) => <DPCard key={d.dp_id} dp={d} {...props} />)}</div>
            </Section>
          )}
        </div>
      )}
    </>
  );
}

/** One requirement a decision must satisfy before the station it gates can move. */
type Need = { id: string; label: string; met: boolean };

/**
 * The gates, per kind. These mirror invariant 5 — ONE_WAY needs two distinct named approvers,
 * STATUTORY needs an evidence reference — so a person can see what is still missing rather than
 * discovering it when the server refuses. The server remains the authority; this only shows the
 * shape of the gate.
 */
function needsOf(dp: DecisionPoint): Need[] {
  const r = dp.resolution;
  const needs: Need[] = [
    { id: "owner", label: `${dp.owner || "The named owner"} states the value`, met: !!r?.value },
  ];
  if (dp.dp_type === "ONE_WAY") {
    needs.push({
      id: "second",
      label: "A second, different person countersigns it — the same person cannot count twice",
      met: !!r?.second_approver && r.second_approver !== r.by,
    });
  }
  if (dp.dp_type === "STATUTORY") {
    needs.push({
      id: "evidence",
      label: "A signed client evidence reference is attached",
      met: !!r?.evidence,
    });
  }
  return needs;
}

/**
 * A decision's own progression, drawn as a track. Three gates read at a glance; the same three
 * as a sentence read as a paragraph nobody finishes.
 */
function trackOf(needs: Need[]): TrackStop[] {
  const firstOpen = needs.findIndex((n) => !n.met);
  const stops: TrackStop[] = [
    // No sub: the reference is already in the card header, and repeating it there put the same id on
    // screen twice — a second field that says nothing new, and one that made the id ambiguous to
    // anything selecting on it. "Raised" needs no qualifier.
    { id: "raised", label: "Raised", state: "done" },
    ...needs.map((n, i) => ({
      id: n.id,
      label: n.id === "owner" ? "Decided" : n.id === "second" ? "Countersigned" : "Evidenced",
      sub: n.met ? "held" : "waiting",
      state: (n.met ? "done" : i === firstOpen ? "current" : "todo") as TrackStop["state"],
    })),
    {
      id: "released",
      label: "Line released",
      sub: firstOpen === -1 ? "the plan may build" : "blocked",
      state: firstOpen === -1 ? "done" : "blocked",
    },
  ];
  return stops;
}

function DPCard(props: { dp: DecisionPoint; writable: boolean; onResolve: (dp: DecisionPoint) => void }) {
  const { dp } = props;
  const resolved = !!dp.resolution;
  const needs = needsOf(dp);
  // `.station` is load-bearing: the e2e specs locate a decision by it. Keep the class.
  return (
    <div className="station" data-lamp={resolved ? "run" : "call"}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="row" style={{ gap: 8 }}>
          <span className="mono mut">{dp.dp_id}</span>
          <span className="tier">{kindWords(dp.dp_type)}</span>
        </div>
        <Pill lamp={resolved ? "run" : "call"}>{resolved ? "Taken" : "Waiting on a person"}</Pill>
      </div>

      <div className="fl-q">{dp.question}</div>

      {!resolved && (
        <div className="fl-blocks">
          <span className="fl-blocks-k">Blocks</span>
          <span>The plan will not build while this is open.</span>
        </div>
      )}

      <Track stops={trackOf(needs)} note={`What ${dp.dp_id} still needs`} />

      <div className="fl-needs">
        {needs.map((n) => (
          <div key={n.id} className={n.met ? "fl-need is-met" : "fl-need is-open"}>
            <span>{n.label}</span>
          </div>
        ))}
      </div>

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
        <Facts items={[
          { k: "Value", v: dp.resolution!.value },
          { k: "Decided by", v: dp.resolution!.by, mono: true },
          ...(dp.resolution!.second_approver
            ? [{ k: "Countersigned", v: dp.resolution!.second_approver, mono: true }] : []),
          ...(dp.resolution!.evidence
            ? [{ k: "Evidence", v: dp.resolution!.evidence, mono: true }] : []),
        ]} />
      )}
    </div>
  );
}


/* ---------------- 4 · Landscape ---------------- */

/** Invariant 3: a legacy source or a digital twin can never hold a write credential. */
const READ_ONLY_ROLES = new Set(["SOURCE_LEGACY", "TWIN"]);
const isLocked = (s: SystemRecord) => READ_ONLY_ROLES.has(s.role);

/**
 * The landscape is a graph, and v1 drew it as two pills and a dash. It is drawn as a graph here:
 * the systems ledger says which systems can actually be written to and which structurally cannot,
 * and the promotion routes are edges with the write-capability of each end carried in its lamp.
 */
export function LandscapeView(props: {
  landscape: Landscape | null;
  writable: boolean;
  onRegister: () => void;
}) {
  const l = props.landscape;
  if (!l) return <Skeleton rows={4} tall />;

  const locked = l.systems.filter(isLocked);
  /* Two different definitions of "writable" on one screen is how a console starts lying: the strip
     counted every system that was not read-only, while each row separately required a change
     substrate, so three systems with nothing to bind to were reported as 3/3 writable. A write needs
     both — a role that permits it (invariant 3) AND a declared substrate to land through. */
  const bindableOf = (s: SystemRecord) => !isLocked(s) && !!s.change_substrate;
  const open = l.systems.filter(bindableOf);
  const unbound = l.systems.filter((s) => !isLocked(s) && !s.change_substrate);
  const byId = new Map(l.systems.map((s) => [s.system_id, s]));

  /* An edge's tone is the write-capability of the system it lands in: change can only travel into
     something the platform is allowed to write to. A route ending in a write-locked system is a
     route that cannot complete, and it should look like one. */
  const node = (id: string): GraphNode => {
    const s = byId.get(id);
    if (!s) return { id, label: id, sub: "not registered", tone: "call" };
    return {
      id,
      label: s.system_id,
      sub: `${s.environment} · ${s.product}`,
      tone: isLocked(s) ? "stop" : "run",
    };
  };
  const routes = l.promotion_paths.map(([from, to]) => ({
    from: node(from),
    to: node(to),
    label: "promotes into",
  }));

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
        <>
          <div className="fl-strip">
            <Facts items={[
              { k: "Systems", v: String(l.systems.length) },
              { k: "Can be written to", v: <Meter value={open.length} of={l.systems.length} tone="run" label="Writable" /> },
              { k: "Not bound yet", v: unbound.length ? `${unbound.length} — no substrate` : "None" },
              { k: "Write-locked", v: locked.length ? `${locked.length} — reading only` : "None" },
              { k: "Promotion routes", v: routes.length ? String(routes.length) : "None declared" },
            ]} />
          </div>

          {/* Both panels are always drawn here, so the only fault is the board stopping at the taller
              one's content height — the routes panel is short by nature and left ~400px blank under
              the pair. Stretching makes the two panels the board, which is what they are. */}
          <div className="board fill" data-fill="stretch">
            <Section title="How change travels" className="grow"
                     note={routes.length ? `${routes.length} route(s) to production` : "No routes declared"}
                     lamp={routes.some((r) => r.to.tone === "stop") ? "stop" : routes.length ? "run" : undefined}
                     status={routes.some((r) => r.to.tone === "stop")
                       ? "A route lands somewhere unwritable"
                       : routes.length ? "Routes hold" : undefined}>
              {routes.length === 0 ? (
                <span className="mut">
                  No promotion route is declared. Change made in one system stays there until a route says
                  where it goes next.
                </span>
              ) : (
                <>
                  <div className="fl-routes"><Flow rows={routes} /></div>
                  <div className="mut" style={{ fontSize: 12, marginTop: 10 }}>
                    A route that ends in a write-locked system cannot complete: the platform holds no
                    credential for that end and will refuse the hop.
                  </div>
                </>
              )}
            </Section>

            <Section title="Where writes are possible" className="grow scrolls"
                     note={`${open.length} writable · ${unbound.length} not bound yet · ${locked.length} write-locked`}
                     lamp={open.length ? "run" : "call"}
                     status={open.length ? "Writable" : "Nowhere writable yet"}>
              <SystemTable systems={l.systems} />
            </Section>
          </div>
        </>
      )}
    </>
  );
}

/**
 * One row per system, with the write column stated flatly — BRAND.md's rule about earned numbers
 * applies to capabilities too. A target with no declared change substrate is shown as unbindable
 * rather than silently listed as writable: without a substrate there is nothing to bind to.
 */
function SystemTable({ systems }: { systems: SystemRecord[] }) {
  return (
    <div className="fl-sys">
      {systems.map((s) => {
        const lock = isLocked(s);
        const bindable = !!s.change_substrate;
        return (
          <div key={s.system_id}
               className={"fl-sys-row " + (lock ? "is-locked" : bindable ? "is-writable" : "")}>
            <span className="fl-sys-id" title={s.system_id}>{s.system_id}</span>
            <span className="fl-sys-v" title={`${s.product} · ${roleLabel(s.role)}`}>
              {s.product} · {roleLabel(s.role)}
            </span>
            <span className="fl-sys-v mono" title={s.change_substrate || "no change substrate declared"}>
              {s.environment} · {s.change_substrate || "no change substrate"}
            </span>
            <Pill lamp={lock ? "stop" : bindable ? "run" : "call"}>
              {lock ? "Read only" : bindable ? "Writable" : "Cannot be bound yet"}
            </Pill>
            <span className="fl-sys-why">
              {lock
                ? "Declared as a legacy source or a digital twin, so no write credential can ever be attached to it."
                : bindable
                  ? `Change lands here through ${s.change_substrate}${s.owner ? `, owned by ${s.owner}` : ""}.`
                  : "No change substrate is declared, so there is nothing to bind a write credential to."}
            </span>
          </div>
        );
      })}
    </div>
  );
}
