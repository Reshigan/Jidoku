import { useEffect, useRef, type KeyboardEvent as ReactKeyEvent, type ReactNode } from "react";
import type { Lamp, Lane } from "./derive";

/** Accessible modal: focus moves in, Escape closes, background is inert to the reader. */
export function Modal(props: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  refusal?: boolean;
  labelledBy?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        props.onClose();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      prev?.focus();
    };
  }, [props]);
  const id = props.labelledBy ?? "modal-title";
  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && props.onClose()}>
      <div
        className={"modal" + (props.refusal ? " refusal" : "")}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={id}
        tabIndex={-1}
        ref={ref}
      >
        <h2 id={id}>{props.title}</h2>
        {props.children}
      </div>
    </div>
  );
}

/** Shape of the thing being loaded — never a fake number in its place. */
export function Skeleton({ rows = 3, tall = false }: { rows?: number; tall?: boolean }) {
  return (
    <div aria-busy="true" aria-live="polite" style={{ display: "grid", gap: 8 }}>
      <span className="mono mut">Reading the ledger…</span>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={"skeleton" + (tall ? " tall" : "")} style={{ width: `${100 - i * 7}%` }} />
      ))}
    </div>
  );
}

/** The mark: three lamps on a royal-blue spine. */
function Mark() {
  return (
    <svg className="rail-mark" viewBox="0 0 40 52" aria-hidden="true">
      <rect x="18" y="2" width="4" height="48" fill="#2B50E2" />
      <circle cx="20" cy="10" r="7" fill="#E5484D" />
      <circle cx="20" cy="26" r="7" fill="#E3A008" />
      <circle cx="20" cy="42" r="7" fill="#3FB950" />
    </svg>
  );
}

export const VIEWS = ["Line", "Work", "Configure", "Decisions", "Intent", "Landscape", "Memory", "Ledger", "Evidence", "Milestones"] as const;
export type ViewName = (typeof VIEWS)[number];

/**
 * The andon rail. One lamp per build phase, always visible, plus the stop cord
 * any user may pull. On narrow screens this becomes the bottom bar.
 */
export function AndonRail(props: {
  view: ViewName;
  onView: (v: ViewName) => void;
  lanes: Lane[];
  stopped: boolean;
  onCord: () => void;
}) {
  /* The tabs keyboard contract, which the roving tabIndex above is half of: arrows walk the rail and
     wrap, Home and End jump to its ends. Moving selects, because each lamp is a whole screen and
     there is nothing to preview — the same thing a click does. */
  const onRailKey = (e: ReactKeyEvent) => {
    const at = VIEWS.indexOf(props.view);
    const to =
      e.key === "ArrowDown" || e.key === "ArrowRight" ? (at + 1) % VIEWS.length
      : e.key === "ArrowUp" || e.key === "ArrowLeft" ? (at - 1 + VIEWS.length) % VIEWS.length
      : e.key === "Home" ? 0
      : e.key === "End" ? VIEWS.length - 1
      : -1;
    if (to < 0) return;
    e.preventDefault();
    props.onView(VIEWS[to]);
    // The old tab is now tabIndex -1, so focus would fall to the body if it were not moved.
    (e.currentTarget.children[to] as HTMLElement | undefined)?.focus();
  };

  return (
    <nav className="rail" aria-label="Andon rail — build phases and the stop cord">
      <Mark />
      <div className="rail-lamps" role="tablist" aria-label="Views" onKeyDown={onRailKey}>
        {VIEWS.map((v, i) => (
          <button
            key={v}
            className="lamp"
            role="tab"
            /* A tablist is one tab stop, not ten: Tab reaches the rail, arrows move along it. Ten
               stops between the rail and the page is how a keyboard user learns to skip the rail. */
            tabIndex={props.view === v ? 0 : -1}
            aria-current={props.view === v}
            aria-selected={props.view === v}
            data-lamp={laneLampFor(props, v)}
            onClick={() => props.onView(v)}
            /* At the mobile breakpoint the label is clipped away, so the name has to be on the
               button itself — title is a tooltip, and a tooltip is not a name. */
            aria-label={`${v} — press ${(i + 1) % 10}`}
            title={`${v} — press ${(i + 1) % 10}`}
          >
            <span className="glass" />
            <span className="lamp-label">{v}</span>
          </button>
        ))}
      </div>
      <div className="rail-spacer" />
      <button
        className="cord"
        data-stopped={props.stopped}
        onClick={props.onCord}
        title={props.stopped ? "The line is stopped. Open the halt to release it." : "Halt the line. A reason is required and is written to the ledger."}
      >
        {props.stopped ? "Line stopped" : "Stop cord"}
      </button>
    </nav>
  );
}

/** The Line lamp reflects the worst lane; the others are navigation only. */
function laneLampFor(props: { lanes: Lane[]; stopped: boolean }, v: ViewName): Lamp | undefined {
  if (v !== "Line") return undefined;
  if (props.stopped) return "stop";
  if (!props.lanes.length) return "idle";
  if (props.lanes.some((l) => l.lamp === "stop")) return "stop";
  if (props.lanes.every((l) => l.lamp === "run")) return "run";
  if (props.lanes.some((l) => l.lamp === "call")) return "call";
  return "idle";
}


/* ---- small shared pieces. Kept here so every view speaks the same visual language. ---- */

export function Pill({ lamp, children }: { lamp?: string; children: ReactNode }) {
  return <span className={"pill" + (lamp ? "" : " none")} data-lamp={lamp}>{children}</span>;
}

export function Section(props: {
  title: string; note?: string; lamp?: string; status?: string; children: ReactNode;
  /** Extra panel classes — `grow` to take the screen's slack, `scrolls` to keep the header fixed
      while the body scrolls. A long ledger must not push its own title off the top of the glass. */
  className?: string;
  /** Controls that belong to the panel, set against its header rather than floating above it. */
  actions?: ReactNode;
}) {
  return (
    <section className={props.className ? `sec ${props.className}` : "sec"}>
      <div className="sec-head">
        <h2>{props.title}</h2>
        {props.note && <span className="mut">{props.note}</span>}
        {props.lamp && props.status && <Pill lamp={props.lamp}>{props.status}</Pill>}
        {props.actions && <span className="sec-actions">{props.actions}</span>}
      </div>
      <div className="body">{props.children}</div>
    </section>
  );
}

/** An empty state is an invitation, not an apology. */
export function Empty(props: { title: string; body: string; verbatim?: string | null }) {
  return (
    <div className="empty">
      <h2>{props.title}</h2>
      <p>{props.body}</p>
      {props.verbatim && <div className="verbatim calm">{props.verbatim}</div>}
    </div>
  );
}

export function Field(props: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; hint?: string; textarea?: boolean; required?: boolean;
}) {
  const id = "f-" + props.label.toLowerCase().replace(/[^a-z]+/g, "-");
  return (
    <label className="field" htmlFor={id}>
      <span className="eyebrow">{props.label}{props.required && <span className="req"> required</span>}</span>
      {props.textarea ? (
        <textarea id={id} value={props.value} placeholder={props.placeholder} rows={8}
                  onChange={(e) => props.onChange(e.target.value)} />
      ) : (
        <input id={id} value={props.value} placeholder={props.placeholder}
               onChange={(e) => props.onChange(e.target.value)} />
      )}
      {props.hint && <span className="mut" style={{ fontSize: 12 }}>{props.hint}</span>}
    </label>
  );
}
