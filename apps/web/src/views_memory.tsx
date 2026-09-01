/* Memory — what this engagement believes, and the gated path into shared knowledge (ADR-0010).
 *
 * The screen's whole argument is that a belief is not a sentence. Every claim on it carries what
 * it was grounded in and whether that ground has moved, because a claim without its receipt is
 * exactly the thing this platform exists not to produce.
 *
 * Two tiers, drawn as two tiers: project memory is this client's, system memory is JIDOKA's
 * knowledge of SAP. The asymmetry between them is the design, so it is stated on the screen
 * rather than left to be inferred from a panel title.
 */
import { useState } from "react";
import type { Claim, MemoryView } from "./api";
import { CLAIM_LAMP, CLAIM_WORDS, fmt, claimBadge } from "./viewkit";
import { Empty, Pill, Section, Skeleton } from "./ui";
import { Chain, Facts, Meter } from "./viz";
import type { ChainNode } from "./viz";
import "./views_memory.css";

export type ClaimAction = "recheck" | "correct" | "promote";

export function MemoryView(props: {
  memory: MemoryView | null;
  /** Claims as they stood at a chosen moment — null until someone asks for a moment. */
  asOf: { as_of: string; claims: Claim[] } | null;
  writable: boolean;
  /** Promotion needs approve authority as well as a named approver who is not the builder. */
  canPromote: boolean;
  busy: string | null;
  onAct: (claim: Claim, action: ClaimAction) => void;
  onForm: () => void;
  /** Read a registered system's own metadata and form claims from it. */
  onHarvest: () => void;
  onAsOf: (when: string) => void;
  onClearAsOf: () => void;
}) {
  const m = props.memory;
  if (!m) return <Skeleton rows={4} tall />;

  const counts = m.counts ?? { TRUSTED: 0, STALE: 0, UNVERIFIED: 0 };
  const total = m.project.length;
  const stale = counts.STALE ?? 0;
  const verified = counts.TRUSTED ?? 0;

  return (
    <>
      <div className="head">
        <div>
          <div className="eyebrow">Memory</div>
          {/* The headline is the state of the belief, not the name of the screen. Stale claims are
              the thing worth leading with: durable uncertainty is the product. */}
          <h1>
            {total === 0
              ? "Nothing is remembered yet"
              : stale
                ? `${stale} belief${stale === 1 ? " needs" : "s need"} re-checking`
                : "Every belief here is verified"}
          </h1>
        </div>
        <div className="row">
          {/* A system's own metadata is a primary source, so learning from one sits beside
              recording a belief rather than under a settings menu (ADR-0012). */}
          <button className="btn" onClick={props.onHarvest} disabled={!props.writable}>
            Learn from a system…
          </button>
          <button className="btn" onClick={props.onForm} disabled={!props.writable}>
            Record a belief
          </button>
        </div>
      </div>

      {/* The screen's constants in one dense strip, so the counts are read at a glance rather
          than counted off the list below. */}
      <div className="mem-strip">
        <Facts items={[
          { k: "Beliefs held", v: total ? String(total) : "None" },
          { k: "Still standing up", v: <Meter value={verified} of={total || 1} tone="run" label="Verified" /> },
          {
            k: "Needs re-checking",
            v: stale ? `${stale} — evidence moved` : "None",
          },
          { k: "Not yet checked", v: counts.UNVERIFIED ? String(counts.UNVERIFIED) : "None" },
          { k: "Shared knowledge", v: m.system.length ? `${m.system.length} promoted` : "None promoted" },
        ]} />
      </div>

      {stale > 0 && (
        /* Amber, never red. The evidence moved under a belief that is still held — that is a
           person's job to close, which is precisely what the call lamp means. */
        <div className="banner" data-lamp="call">
          <span className="bar" />
          <div>
            <strong>{stale} belief{stale === 1 ? " has" : "s have"} lost {stale === 1 ? "its" : "their"} ground.</strong>
            <div className="mut" style={{ marginTop: 4 }}>
              The evidence these were formed from has changed since. They are kept, not deleted, and
              they keep the badge until something re-checks them against the source. Nothing here may
              be presented as fact in the meantime.
            </div>
          </div>
        </div>
      )}

      <AsOf asOf={props.asOf} onAsOf={props.onAsOf} onClear={props.onClearAsOf} />

      {total === 0 && m.system.length === 0 ? (
        <Empty
          title="Nothing is remembered yet"
          body="JIDOKA stores claims, not notes. A claim carries the thing it was read from and the hash of that thing at the time, which is what lets it go stale by itself rather than quietly drifting. Record a belief and it arrives unchecked, with its source attached — never as a bare sentence. Or point it at a registered system: its own metadata says what its configuration may be, and that is a source an auditor can follow." />
      ) : (
        /* data-fill scoped through .page > in the sheet: app.css pins .board.fill to the top,
           which leaves this board ending mid-glass. The two panels are the screen. */
        <div className="board fill" data-fill="stretch">
          <Section title="What we believe about this client" className="grow scrolls"
                   note={total ? `${total} held · ${stale} needing a re-check` : "Nothing held"}
                   lamp={total === 0 ? undefined : stale ? "call" : "run"}
                   status={total === 0 ? undefined : stale ? "Some ground has moved" : "All verified"}>
            {total === 0 ? (
              <div className="mem-quiet">
                <span className="mut">This engagement holds no beliefs yet.</span>
                <div className="mem-quiet-rule">
                  <div className="eyebrow">What a belief has to carry</div>
                  <ul className="mem-quiet-list">
                    <li>The thing it was read from. A claim with no source is refused — it cannot
                        be storable, because nothing could ever check it.</li>
                    <li>That source as it read at the time, so going stale is a comparison rather
                        than a judgement nobody can audit.</li>
                    <li>Who formed it, and from when. Correcting one closes its interval instead of
                        overwriting it, so what was believed in March survives being wrong.</li>
                  </ul>
                </div>
              </div>
            ) : (
              /* Ordered stale-first: the claims that need a person are the ones worth the top of
                 the panel, and a supersession is a chain, so it is drawn as one. */
              <Chain nodes={m.project.slice().sort(byUrgency).map((c) => claimNode(c, props))} />
            )}
          </Section>

          <Section title="What JIDOKA knows about SAP" className="grow scrolls"
                   note={m.system.length ? `${m.system.length} shape(s), no client values` : "Nothing has crossed"}
                   lamp={m.system.length ? "blue" : undefined}
                   status={m.system.length ? "Shared across engagements" : undefined}>
            {m.system.length === 0 ? (
              <div className="mem-quiet">
                <span className="mut">No shape has crossed into shared knowledge yet.</span>
                <div className="mem-quiet-rule">
                  <div className="eyebrow">How anything gets here</div>
                  <ul className="mem-quiet-list">
                    <li>Only through a promotion, approved by a named person who is not the one who
                        formed the claim. There is no automatic path and no background sweep.</li>
                    <li>Shapes may cross; client values never. “Cost centre codes here were
                        four-digit numeric” is a shape. <span className="mono">1000</span> is a
                        value, and the gate refuses it rather than stripping it out.</li>
                    <li>A promoted shape is grounded in the ceremony that promoted it, never in a
                        pointer back into this client's data.</li>
                  </ul>
                  <div className="mut" style={{ fontSize: 12 }}>
                    A client value leaked into shared knowledge is unrecallable — every later
                    engagement reads it, and nothing revokes it. That is why this is slow.
                  </div>
                </div>
              </div>
            ) : (
              <div className="mem-sys-wrap">
                <div className="mem-sys">
                  {m.system.map((c) => (
                    <div className="mem-sys-row" key={c.id}>
                      <span className="mem-sys-sub mono">{c.subject}</span>
                      <span className="mem-sys-text">{c.text}</span>
                      <span className="mem-sys-by mut">Promoted by {c.actor}</span>
                    </div>
                  ))}
                </div>
                {/* Pinned to the foot of the panel: the rule these shapes live under is the last
                    thing read, and it closes the slack the list leaves rather than floating in it. */}
                <div className="mut mem-sys-note">
                  These are shapes, not values. They read across every engagement, which is why a
                  named person had to approve each one crossing.
                </div>
              </div>
            )}
          </Section>
        </div>
      )}
    </>
  );
}

/** Stale first, then never-checked, then verified: the panel is ordered by what needs a person. */
const RANK: Record<string, number> = { STALE: 0, UNVERIFIED: 1, TRUSTED: 2 };
const byUrgency = (a: Claim, b: Claim) => (RANK[a.status] ?? 3) - (RANK[b.status] ?? 3);

/**
 * One claim as a chain node — a claim IS a link in a supersession chain, so the primitive fits and
 * a second card component would only be the same thing drawn differently.
 */
function claimNode(c: Claim, props: {
  writable: boolean; canPromote: boolean; busy: string | null;
  onAct: (claim: Claim, action: ClaimAction) => void;
}): ChainNode {
  const lamp = CLAIM_LAMP[c.status] as ChainNode["lamp"];
  const busy = props.busy === c.id;
  return {
    id: c.id,
    lamp,
    title: (
      <>
        <span className="mem-subject mono">{c.subject}</span>
        <Pill lamp={lamp === "idle" ? undefined : lamp}>{claimBadge(c.status)}</Pill>
      </>
    ),
    meta: <span className="mono dim">{fmt(c.valid_from)}</span>,
    body: (
      <div className="mem-claim">
        <div className="mem-text">{c.text}</div>
        <div className="mem-why">{CLAIM_WORDS[c.status]}</div>

        <Facts items={[
          { k: "Grounded in", v: c.source_ref, mono: true },
          { k: "Formed by", v: c.actor, mono: true },
          ...(c.supersedes
            ? [{ k: "Replaces", v: <span title={c.supersedes}>an earlier belief</span>, mono: true }]
            : []),
        ]} />

        <div className="mem-acts">
          <button className="btn sm" disabled={busy} onClick={() => props.onAct(c, "recheck")}>
            Re-check it
          </button>
          <button className="btn sm" disabled={!props.writable || busy}
                  onClick={() => props.onAct(c, "correct")}>
            Correct it
          </button>
          {/* Promotion is not a sibling of the other two. It is the only action on this screen
              that leaves the engagement, so it is set apart and named as the ceremony it is. */}
          <span className="mem-acts-gap" />
          <button className="btn sm mem-promote" disabled={!props.canPromote || busy}
                  onClick={() => props.onAct(c, "promote")}
                  title={props.canPromote
                    ? "Crosses into shared knowledge. Needs a named approver who is not the person who formed it."
                    : "Promotion needs approval authority."}>
            Promote to shared knowledge…
          </button>
        </div>
      </div>
    ),
  };
}

/**
 * What was believed at a moment. Validity intervals give this for free, so it is a read rather
 * than a reconstruction — and a native date input rather than a picker dependency.
 */
function AsOf(props: {
  asOf: { as_of: string; claims: Claim[] } | null;
  onAsOf: (when: string) => void;
  onClear: () => void;
}) {
  const [when, setWhen] = useState("");
  return (
    <div className="mem-asof">
      <div className="mem-asof-ask">
        <span className="eyebrow">What did we believe on</span>
        <input type="date" value={when} aria-label="As of date"
               onChange={(e) => setWhen(e.target.value)} />
        <button className="btn sm" disabled={!when}
                onClick={() => props.onAsOf(`${when}T23:59:59.999999Z`)}>
          Read it back
        </button>
        {props.asOf && (
          <button className="btn ghost sm" onClick={props.onClear}>Back to now</button>
        )}
        <span className="mut mem-asof-note">
          Corrections close a belief's interval rather than erasing it, so an earlier day is still
          readable.
        </span>
      </div>
      {props.asOf && (
        <div className="mem-asof-out">
          <div className="eyebrow">
            Held on {props.asOf.as_of.slice(0, 10)} — {props.asOf.claims.length} belief(s)
          </div>
          {props.asOf.claims.length === 0 ? (
            <span className="mut">Nothing was believed yet on that day.</span>
          ) : (
            <div className="mem-asof-list">
              {props.asOf.claims.map((c) => (
                <div className="mem-asof-row" key={c.id}>
                  <span className="mono dim">{c.subject}</span>
                  <span>{c.text}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
