/* Vocabulary shared by more than one screen. Lives here so a rebuild of one view cannot silently
   change the words another view speaks. */

export const fmt = (ts: string) => (ts || "").replace("T", " ").replace("Z", "");

/** The plan speaks in substrate verbs. A person reads what actually happens. */
export function stepWords(step: { action: string; system: string; key: string }) {
  // key is product:object:code, and "?" is the platform's word for "no external code yet".
  const [, object = step.key, code = ""] = step.key.split(":");
  const what = code && code !== "?" ? `${object} ${code}` : `a new ${object}`;
  switch (step.action) {
    case "API_WRITE": return `Write ${what} into ${step.system}`;
    case "FILE_IMPORT_HUMAN": return `Import ${what} into ${step.system} — by hand`;
    case "UI_INSTRUCTION_HUMAN": return `Configure ${what} by hand in ${step.system}`;
    default: return `${step.action} ${what}`;
  }
}

/* Mirrors executor.ABAP_PRODUCTS. The server is the authority — this only decides whether the
   console offers the button, never whether the hop is legal. */
export const ABAP = new Set(["S4HANA", "S/4HANA", "ECC", "R3"].map((p) => p.toUpperCase()));
export const isAbap = (product: string) => ABAP.has((product || "").toUpperCase().replace(/ /g, ""));

export const STATUS_LAMP: Record<string, string> = {
  DRY_RUN: "call", HANDED_OFF: "call", IN_TRANSPORT: "call", PARTIAL: "stop",
  VERIFIED: "run", APPLIED: "run", ROLLED_BACK: "call", DRIFTED: "stop",
  FAILED: "stop", REFUSED: "stop",
};

export const STATUS_WORDS: Record<string, string> = {
  DRY_RUN: "Rehearsed. Nothing was written.",
  HANDED_OFF: "A person does this one. The instruction sheet is ready.",
  IN_TRANSPORT: "Written and verified, but not yet in production.",
  VERIFIED: "Written, and the system agrees it took.",
  APPLIED: "Written. Verification has not run yet.",
  PARTIAL: "Some of it landed and some did not. Read this carefully.",
  DRIFTED: "Written, but the system does not look the way it should.",
  FAILED: "Nothing landed. The system refused or was unreachable.",
  ROLLED_BACK: "Put back the way it was.",
  REFUSED: "A gate stopped this before anything happened.",
};

/* ---------------- memory badges (ADR-0010) ----------------
   A claim's status is a hash comparison, and the three outcomes are three different things a
   person can do something about. Note what is NOT here: stop/red. A stale claim is uncertainty,
   not failure — the evidence moved under a belief that is still held and still useful. Badging it
   red would put it in the same class as a broken chain and a refused write, and an operator who
   learns red means "probably fine" stops reading red at all, which is the andon system defeated.
   Amber is the honest lamp: this is waiting on a person to re-check it. */
export const CLAIM_LAMP: Record<string, string> = {
  TRUSTED: "run", STALE: "call", UNVERIFIED: "idle",
};

export const CLAIM_BADGE: Record<string, string> = {
  TRUSTED: "Verified",
  STALE: "Needs re-checking",
  UNVERIFIED: "Not yet checked",
};

/** Same contract as statusName: a status with no badge degrades to a sentence, never to the enum. */
export const claimBadge = (s: string) => CLAIM_BADGE[s] ?? sentence(s);

/** What the badge actually means, said as the consequence rather than the state. */
export const CLAIM_WORDS: Record<string, string> = {
  TRUSTED: "Re-checked against its source, and the source still says this.",
  STALE: "The evidence moved under this. It is still held, and it may not be used as fact until someone re-checks it.",
  UNVERIFIED: "Formed from a source but never re-checked since. Treat it as a lead, not a finding.",
};

/** A system's role, as a phrase inside a sentence: "KOM-S4-DEV — a system JIDOKA may write into". */
export const ROLE_PHRASE: Record<string, string> = {
  TARGET: "a system JIDOKA may write into",
  SOURCE_LEGACY: "a read-only legacy source",
  TWIN: "a twin, which never holds write credentials",
  SANDBOX: "a sandbox",
};

/** The same role as a standalone label. Enum-shaped caps are the platform's word, not a person's,
    and BRAND is absolute: never name internals in the UI. */
export const ROLE_LABEL: Record<string, string> = {
  TARGET: "Write target",
  SOURCE_LEGACY: "Legacy source",
  TWIN: "Digital twin",
  SANDBOX: "Sandbox",
};

export const roleLabel = (r: string) => ROLE_LABEL[r] ?? sentence(r);

export function humanAction(a: string) {
  const words: Record<string, string> = {
    CREATED: "Engagement opened", LOADED: "Signed intent loaded", BUILT: "Plan built",
    SNAPSHOT: "Before-snapshot taken", EXECUTED: "Change executed", VALIDATED: "Change validated",
    APPROVED: "Approved", ROLLED_BACK: "Rolled back", LINE_STOP: "Line stopped",
    LINE_RESUME: "Line released", PHASE_ADVANCED: "Phase advanced",
    SYSTEM_REGISTERED: "System registered", DP_RAISED: "Decision raised", DP_RESOLVED: "Decision taken",
    /* The executor and the execution router emit these too, and the fallback below turned them
       into lowercased tokens ("dry run", "drift detected") — still the internal word, just quieter. */
    DRY_RUN: "Rehearsed, nothing written", HANDED_OFF: "Handed to a person",
    VERIFIED: "Change verified", DRIFT_DETECTED: "The system does not match",
    PARTIAL: "Landed only in part", FAILED: "Nothing landed",
    IN_TRANSPORT: "Waiting on transport", TRANSPORT_ADVANCED: "Transport moved on",
    TRANSPORT_FAILED: "Transport refused", ARMED: "Armed for a live write",
    DISARMED: "Live writing turned off", CONNECTOR_BOUND: "Connected to the system",
  };
  return words[a] ?? a.replace(/_/g, " ").toLowerCase();
}

/* ---------------- ledger → narrative ----------------
   The ledger stores what the platform did, in the platform's own tokens. An auditor reads those
   verbatim (the Ledger table is deliberately raw). Every other surface is a narrative for a person,
   and BRAND is absolute about it: "waiting on a person", not "PENDING_APPROVAL". These two are the
   only translators; a second one would let two screens disagree about what a word means. */

/** The ledger's task column, said aloud. Product and system ids stay — a consultant uses those. */
export function taskWords(task: string): string {
  // These are the platform's buckets for entries that belong to no station, not real task keys.
  const bucket: Record<string, string> = {
    ENGAGEMENT: "This engagement",
    REGISTRY: "The landscape",
    EXECUTION: "Execution",
    IR: "Signed intent",
    PLAN: "The plan",
    LINE: "The line",
  };
  if (bucket[task]) return bucket[task];
  if (!task.includes(":")) return task; // a decision reference (DP-B11) is already a name people use.
  // Same shape stepWords reads: product:object:code, "?" meaning no external code yet.
  const [, object = task, code = ""] = task.split(":");
  return code && code !== "?" ? `${object} ${code}` : `a new ${object}`;
}

/* Details are free text written by whoever appended the entry, so this translates the shapes the
   platform itself emits and leaves anything else alone — except a bare key, which is an internal
   token wherever it appears. Never guess: an untranslatable detail is dropped, not paraphrased. */
const KEYISH = /\b[A-Za-z0-9_/]+:[A-Za-z0-9_]+:[A-Za-z0-9_?]+/g;

export function detailWords(task: string, detail: string): string {
  const d = (detail || "").trim();
  if (!d) return "";

  // "API_WRITE" alone — the change method, which the executor writes as the whole detail. The entry
  // already says the change was executed, so the only thing left to say is how it was made.
  const method = METHOD_WORDS[d];
  if (method) return method;

  // "2 records, 0 with open DPs" — the loader's count. "DP" is the platform's abbreviation for a
  // decision point; the counts are the fact a person wants, so only the abbreviation is replaced.
  const loaded = d.match(/^(\d+) records?, (\d+) with open DPs$/);
  if (loaded) {
    return `${loaded[1]} record${loaded[1] === "1" ? "" : "s"}, ${loaded[2]} still waiting on a decision`;
  }

  // "DISCOVER -> SCOPE" — a phase advance, which is the one detail that is purely two enum values.
  const phases = d.match(/^([A-Z_]+) -> ([A-Z_]+)$/);
  if (phases) return `Moved from ${sentence(phases[1])} to ${sentence(phases[2])}`;

  // "KOM-S4-DEV role=TARGET" — the id stays, the enum does not.
  const role = d.match(/^(\S+) role=([A-Z_]+)$/);
  if (role) return `${role[1]} — ${ROLE_PHRASE[role[2]] ?? sentence(role[2])}`;

  // "value='-5' evidence=KOM-POL-114" — a taken decision. The value is the client's, so it stays.
  const dp = d.match(/^value=(.+?) evidence=(.*)$/);
  // The value arrives as a Python repr, so it comes wrapped in the quotes that repr added. The
  // value itself is the client's word and stays; the quoting is the platform's and does not.
  if (dp) return `Decided ${dp[1].replace(/^'(.*)'$/, "$1")}${dp[2] ? `, on ${dp[2]}` : ""}`;

  // "STATUTORY: What is the ZA floor? -> Komatsu HR" — a raised decision.
  const raised = d.match(/^([A-Z_]+): (.+) -> (.+)$/);
  if (raised) return `${sentence(raised[1])} question for ${raised[3]}: ${raised[2]}`;

  // "Komatsu:Payroll go-live" — the engagement's own client and name, joined by a colon.
  if (task === "ENGAGEMENT" && /^[^:]+:[^:]+$/.test(d)) return d.replace(":", " · ");

  // "2 steps {'A': 2}" — a step count with the planner's tier tally rendered as a Python dict.
  // The count is a fact a person wants; the repr is not, and there is nothing faithful to say
  // about it here, so it is dropped rather than reformatted into a guess.
  const plan = d.match(/^(\d+ steps)\b/);
  if (plan) return sentence(plan[1]);

  // Anything else: strip the task key the detail repeats (the entry already names its task) and
  // any bare enum token left standing on its own.
  const stripped = d
    .replace(KEYISH, (k) => (k === task ? "" : taskWords(k)))
    .replace(/^[\s:—-]+/, "")
    .trim();
  return stripped ? sentence(stripped) : "";
}

/* The substrate verbs, said as a method rather than as the enum. Same three stepWords names, said
   from the ledger's side: stepWords writes an instruction ("Write a new X into Y"), this reports a
   finished act, so it names the route the change took and nothing else. */
const METHOD_WORDS: Record<string, string> = {
  API_WRITE: "Written through the system's own interface",
  FILE_IMPORT_HUMAN: "Imported by hand from a file",
  UI_INSTRUCTION_HUMAN: "Configured by hand in the system",
};

/** SCREAMING_SNAKE reads as an internal token. Sentence case reads as a word. */
function sentence(s: string) {
  if (!/^[A-Z][A-Z0-9_]*$/.test(s)) return s;
  const w = s.replace(/_/g, " ").toLowerCase();
  return w.charAt(0).toUpperCase() + w.slice(1);
}

/* The short name for a result, for the pill. STATUS_WORDS is the sentence beneath it; this is the
   two words that go in the badge. BRAND: never name internals in the UI — DRY_RUN is a value in a
   database column, not something a person on a shop floor says. The fallback title-cases rather
   than passing the raw enum through, so a status the server adds tomorrow degrades to "Rolled back"
   instead of shouting ROLLED_BACK at the operator. */
export const STATUS_NAME: Record<string, string> = {
  DRY_RUN: "Rehearsed",
  HANDED_OFF: "Handed to a person",
  IN_TRANSPORT: "Not yet in production",
  VERIFIED: "Verified",
  APPLIED: "Written",
  PARTIAL: "Partly landed",
  DRIFTED: "Drifted",
  FAILED: "Failed",
  ROLLED_BACK: "Rolled back",
  REFUSED: "Refused",
};

/* Falls back to `sentence`, which roleLabel already uses for the same purpose — one rule for what
   an untranslated enum looks like, so two screens cannot disagree about it. */
export const statusName = (s: string) => STATUS_NAME[s] ?? sentence(s);

/** A decision's kind, as a plain description of the gate rather than the enum. BRAND.md: never
    name an internal in the UI. Lives here, not in the Decisions view, because the raise-a-decision
    form offers the same five and a second copy is how two screens start disagreeing. */
export const DP_KINDS = ["DESIGN", "STATUTORY", "ONE_WAY", "SEQUENCE", "COMMERCIAL"] as const;
export const KIND_WORDS: Record<string, string> = {
  ONE_WAY: "One way — no undo",
  STATUTORY: "Statutory",
  SEQUENCE: "Order of work",
  COMMERCIAL: "Commercial",
  DESIGN: "Design",
};
export const kindWords = (t: string) => KIND_WORDS[t] ?? sentence(t);

/** The four roles a registered system may hold, in the order the registry lists them. */
export const SYSTEM_ROLES = ["TARGET", "SOURCE_LEGACY", "TWIN", "SANDBOX"] as const;
