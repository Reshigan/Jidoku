/* The console's structured data, drawn as what it is.
 *
 * The audit of v1 found the same fault on nearly every screen: a hash chain, a state machine, a
 * dependency graph and a timeline were all rendered as flat rows of text. A chain whose linkage is
 * invisible cannot support the claim "16 links verified" — the operator is asked to take it on
 * faith, which is precisely what this platform exists not to do. These primitives are the smallest
 * set that lets each screen show its own evidence.
 *
 * Nothing here fetches, derives or decides. They render what they are handed.
 */
import type { ReactNode } from "react";

/* ---------------- the spine: a vertical chain of linked events ---------------- */

/** One node on a chain. `broken` marks the first link whose hash did not reconcile. */
export type ChainNode = {
  id: string;
  lamp?: "run" | "call" | "stop" | "idle";
  title: ReactNode;
  meta?: ReactNode;
  body?: ReactNode;
  broken?: boolean;
};

/**
 * A hash chain drawn as a chain. The connector between two nodes is the assertion that one hash
 * follows from the other, so it is a drawn line and it breaks visibly where verification fails —
 * a flat list can only tell you it broke somewhere.
 */
export function Chain({ nodes, dense = false }: { nodes: ChainNode[]; dense?: boolean }) {
  return (
    <ol className={dense ? "chain dense" : "chain"}>
      {nodes.map((n, i) => (
        <li key={n.id} className={n.broken ? "chain-node broken" : "chain-node"}>
          <span className={`chain-mark lamp-${n.lamp ?? "idle"}`} aria-hidden />
          {i < nodes.length - 1 && <span className="chain-link" aria-hidden />}
          <div className="chain-content">
            <div className="chain-title">
              {n.title}
              {n.meta && <span className="chain-meta">{n.meta}</span>}
            </div>
            {n.body && <div className="chain-body">{n.body}</div>}
          </div>
        </li>
      ))}
    </ol>
  );
}

/* ---------------- the track: a gated left-to-right progression ---------------- */

export type TrackStop = {
  id: string;
  label: string;
  sub?: string;
  state: "done" | "current" | "todo" | "blocked";
  /** Rendered inside the stop — a ratio, a count, a lamp. */
  badge?: ReactNode;
};

/**
 * Phases, transport routes and milestones are all the same shape: an ordered run of gates where
 * each one opens only when the one before it closed. Drawn as a track, "where are we" is a glance
 * rather than a read.
 */
export function Track({ stops, note }: { stops: TrackStop[]; note?: string }) {
  return (
    <div className="track" role="list" aria-label={note}>
      {stops.map((s, i) => (
        <div key={s.id} className={`track-stop is-${s.state}`} role="listitem">
          {i > 0 && <span className="track-rail" aria-hidden />}
          <span className="track-dot" aria-hidden />
          <span className="track-idx mono">{String(i + 1).padStart(2, "0")}</span>
          <span className="track-label">{s.label}</span>
          {s.sub && <span className="track-sub mut">{s.sub}</span>}
          {s.badge && <span className="track-badge">{s.badge}</span>}
        </div>
      ))}
    </div>
  );
}

/* ---------------- the meter: a ratio that has been earned ---------------- */

/** A proportion stated flatly, bad ones included — BRAND.md's rule, drawn. */
export function Meter({ value, of, tone = "run", label }: {
  value: number; of: number; tone?: "run" | "call" | "stop" | "blue"; label?: string;
}) {
  const pct = of > 0 ? Math.round((value / of) * 100) : 0;
  return (
    <div className="meter" title={label ? `${label}: ${value} of ${of}` : `${value} of ${of}`}>
      <div className="meter-track">
        <div className={`meter-fill tone-${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="meter-num mono">{value}<span className="dim">/{of}</span></span>
    </div>
  );
}

/* ---------------- the graph: nodes and the edges between them ---------------- */

export type GraphNode = { id: string; label: string; sub?: string; tone?: "run" | "call" | "stop" | "idle" };

/**
 * A promotion path, a binding, a blocked plan step: all edges. Drawn as columns joined by real
 * connectors rather than a dash between two pills, so a landscape with three routes still reads.
 * Deliberately not a force-directed canvas — these graphs are short, ordered chains, and a layout
 * engine would be a dependency and a debugging surface for something a grid already does.
 */
export function Flow({ rows }: { rows: { from: GraphNode; to: GraphNode; label?: string }[] }) {
  if (!rows.length) return null;
  return (
    <div className="flow">
      {rows.map((r, i) => (
        <div className="flow-row" key={`${r.from.id}-${r.to.id}-${i}`}>
          <FlowNode n={r.from} />
          <span className="flow-edge" aria-hidden>
            {r.label && <span className="flow-edge-label mono">{r.label}</span>}
          </span>
          <FlowNode n={r.to} />
        </div>
      ))}
    </div>
  );
}

function FlowNode({ n }: { n: GraphNode }) {
  return (
    <span className={`flow-node tone-${n.tone ?? "idle"}`}>
      <span className="flow-node-label mono">{n.label}</span>
      {n.sub && <span className="flow-node-sub dim">{n.sub}</span>}
    </span>
  );
}

/* ---------------- the hash: a value you are meant to be able to compare ---------------- */

/**
 * A hash is shown head-and-tail, never as a wrapped wall of characters. The full value is on the
 * element for copying — 64 literal zeroes rendered in full was the loudest and least informative
 * thing on the evidence screen.
 */
export function Hash({ value, prev }: { value: string; prev?: string }) {
  if (!value) return <span className="dim mono">—</span>;
  const short = value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;
  return (
    <span className="hash mono" title={prev ? `${value}\nfollows ${prev}` : value}>
      {short}
    </span>
  );
}

/* ---------------- the facts strip: dense key/value, no dead middle ---------------- */

/**
 * The single most repeated fault in v1: a label at the far left, a pill at the far right, and a
 * thousand pixels of nothing between them. A screen's constants belong in one dense strip.
 */
export function Facts({ items }: { items: { k: string; v: ReactNode; mono?: boolean }[] }) {
  return (
    <div className="facts">
      {items.map((f) => (
        <div className="fact" key={f.k}>
          <span className="fact-k">{f.k}</span>
          <span className={f.mono ? "fact-v mono" : "fact-v"}>{f.v}</span>
        </div>
      ))}
    </div>
  );
}
