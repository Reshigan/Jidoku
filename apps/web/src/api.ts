// Every value the interface shows comes from here. No local truth, no placeholder data.

export type Engagement = {
  engagement_id: string;
  name: string;
  client: string;
  phase: string;
  ir_records: number;
  ledger_entries: number;
};
export type EngagementSummary = Engagement;

/** A record recovered from a live system. Unsigned by construction: `source.signed_by` is empty,
    which is exactly what makes it unloadable as intent until a person signs it. */
export type Draft = {
  key: string;
  object: string;
  product: string;
  system_binding: string;
  external_code: string;
  tier: string;
  intent: Record<string, unknown>;
  source: { workbook: string; cell_range: string; signed_by: string; date: string };
  provenance_status: string;
  rationale: string | null;
  signed: boolean;
};

export type Debt = {
  score: number;
  grade: string;
  top_driver: string | null;
  items: Record<string, number>;
  counts: Record<string, number>;
  /** The published weights, sent rather than derived: a weight inferred from a contribution
      divided by a zero count prints as 0, which is exactly what "published" must not mean. */
  weights: Record<string, number>;
  /** counter -> what it was derived from. A counter absent here contributed nothing. */
  measured: Record<string, string>;
  /** Weights with no measurement behind them. Published so the score cannot imply more than it knows. */
  unmeasured: string[];
};

export type Backlog = {
  drafts: Draft[];
  unexplained: string[];
  systems: string[];
  debt: Debt;
};

export type TimeTravel = {
  at: string;
  approved: string[];
  rolled_back: string[];
  open_dps: string[];
  halted: boolean;
  entries: number;
};

/** What one agent was allowed to do, and what it did with that. Both, always. */
export type CrewCard = {
  name: string;
  ring: "AGENT" | "SERVICE" | "UNTRUSTED";
  objective: string;
  capabilities: string[];
  syscalls: number;
  tokens: number;
  state: string;
  exit_reason: string;
  did: string[];
};

export type CrewRun = {
  crew: CrewCard[];
  plan: Plan | null;
  /** The planner's refusal, verbatim. An open decision stopping the plan is the platform working. */
  plan_blocked: string | null;
  steps: {
    key: string; tier: string; system: string; status: string; detail: string;
    /** Where an ABAP change sits on its route. Absent on products that do not transport. */
    transport?: TransportState;
  }[];
  artefacts: { key: string; tier: string; kind: string; human_step: string; steps: string[] }[];
  decisions_raised: string[];
  objections: { from: string; kind: string; body: Record<string, string> }[];
  economics: {
    steps: Record<string, number>; manual_steps: number; rehearsed: number; refused: number;
    open_questions: number; not_priced: string[];
  } | null;
  verification: VerificationRun | null;
  /** The handover. A run ends here rather than in a fait accompli — arming and approval are human. */
  waiting_on_a_person: { what: string; who: string; why: string }[];
  halted: boolean;
  halt_reason: string;
};

/** A night's work and the handover it left. `interrupted` earned a wake-up; everything else
    waited for the morning, which is the whole point of the budget (M3). */
export type NightShift = {
  did: string[];
  interrupted: NightFinding[];
  waited: NightFinding[];
  deferred: NightFinding[];
  budget: { of: number; spent: number; held_back: number; threshold: number } | null;
  handover: string;
  cost_of_silence: Record<string, number>;
};

export type NightFinding = {
  kind: string; what: string; who: string; detail: string; cost: number;
};

/** Somebody the platform may ask for something. Authority is written in the platform's own
    permission names, and cost is declared by the organisation — never inferred (M4). */
export type TeamMember = {
  name: string;
  authority: string[];
  cost: number;
  hours: [number, number];
  utc_offset: number;
  days: number[];
  capacity_per_week: number;
};

export type Blast = {
  population: number;
  affected: number;
  affected_ids: (string | number)[];
  unaffected: number;
  statement: string;
};

export type PlanStep = {
  seq: number;
  key: string;
  tier: "A" | "B" | "C";
  system: string;
  product: string;
  action: string;
};

export type Plan = {
  steps: PlanStep[];
  lanes: string[][];
  tier_summary: Record<string, number>;
};

export type LedgerEntry = {
  ts: string;
  task: string;
  action: string;
  actor: string;
  detail: string;
  hash: string;
  prev: string;
  [k: string]: unknown;
};

export type SystemRecord = {
  system_id: string;
  product: string;
  role: string;
  environment: string;
  connectivity: Record<string, unknown>;
  owner: string;
  change_substrate: string;
  /** The next hop on this system's transport route. Write-only: the landscape returns the
      declared paths separately. */
  promotes_to?: string;
};

export type Landscape = {
  systems: SystemRecord[];
  promotion_paths: [string, string][];
};

export type DecisionPoint = {
  dp_id: string;
  dp_type: string;
  question: string;
  owner: string;
  options: string[];
  resolution: { by: string; value: string; evidence: string; second_approver: string | null } | null;
};


export type StepStatus =
  | "DRY_RUN" | "APPLIED" | "VERIFIED" | "DRIFTED" | "PARTIAL"
  | "IN_TRANSPORT" | "FAILED" | "ROLLED_BACK" | "REFUSED" | "HANDED_OFF";

export type ExecutionResult = {
  key: string;
  tier: "A" | "B" | "C";
  system: string;
  status: StepStatus;
  detail: string;
  payload: Record<string, unknown>;
  verification: Record<string, unknown>;
  transport?: TransportState;
};

/** Where an ABAP change currently sits on its route. On the ABAP stack this, not the write,
    decides whether the step is done — ADR-0006. */
export type TransportState = {
  request_id: string;
  status: string;
  currently_in: string;
  imported_into: string[];
  next_hop: string | null;
  in_production: boolean;
  route: string[];
};

export type StepTransport = TransportState & { key: string };

/** An arming is a window, not a standing authority (ADR-0021): it names the moment it lapses,
    and a lapsed one is never listed here — the console must not offer a write about to be
    refused. `expires_at` is empty only for an arming made without one, which the API never does. */
export type ArmedTarget = {
  system_id: string; armed_by: string; reason: string; expires_at: string; minutes?: number;
};
export type Connector = { system_id: string; kind: string; describe: string };

/** A call the server refused, or could not answer. Carries the server's own words. */
export class ApiError extends Error {
  /** The server's own refusal text, quoted into the UI without rewording. */
  readonly detail: string;
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.detail = message;
  }
  /** True when the endpoint simply is not built yet — degrade, don't crash. */
  get notAvailable() {
    return this.status === 404 || this.status === 405 || this.status === 501;
  }
}

/* A fetch with no timeout does not fail, it hangs — and a console that hangs looks to an operator
   exactly like one that is thinking. Thirty seconds is longer than any call here legitimately takes.
   ponytail: one constant, per-call overrides when a call proves it needs one. */
const TIMEOUT_MS = 30_000;

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: {
        ...(init?.body ? { "content-type": "application/json" } : {}),
        ...authHeader(),
      },
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "TimeoutError") {
      throw new ApiError(0, "The platform did not answer within 30 seconds. Showing the last verified state.");
    }
    throw new ApiError(0, "The platform is unreachable. Showing the last verified state.");
  }
  const text = await res.text();
  let body: unknown = text;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    /* server sent plain text; keep it verbatim */
  }
  if (!res.ok) {
    // FastAPI puts the refusal in .detail — surface it verbatim, never reworded.
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : String(body || res.statusText);
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

export const api = {
  health: () => call<{ status: string }>("/health"),
  engagements: () => call<Engagement[]>("/engagements"),
  createEngagement: (body: { name: string; client: string }) =>
    call<{ engagement_id: string }>("/engagements", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  uploadIR: (eid: string, records: unknown[]) =>
    call<{ records: number; open_decision_points: Record<string, string[]> }>(
      `/engagements/${eid}/ir`,
      { method: "POST", body: JSON.stringify(records) },
    ),
  plan: (eid: string) => call<Plan>(`/engagements/${eid}/plan`, { method: "POST" }),
  ledger: (eid: string) =>
    call<{ verified: boolean; entries: LedgerEntry[] }>(`/engagements/${eid}/ledger`),
  // The actor is the authenticated identity, not a field the caller may choose.
  appendLedger: (eid: string, body: { task: string; action: string; detail?: string }) =>
    call<LedgerEntry>(`/engagements/${eid}/ledger`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  approve: (eid: string, body: { task: string; reviewer?: string }) =>
    call<LedgerEntry>(`/engagements/${eid}/ledger/approve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  raiseDP: (eid: string, dp: { dp_id: string; dp_type: string; question: string; owner: string; options?: string[] }) =>
    call<{ raised: string }>(`/engagements/${eid}/decisions`, {
      method: "POST",
      body: JSON.stringify(dp),
    }),
  resolveDP: (
    eid: string,
    dpId: string,
    body: { decided_by: string; value: string; evidence_ref?: string; second_approver?: string | null },
  ) =>
    call<{ resolved: string; resolution: DecisionPoint["resolution"] }>(
      `/engagements/${eid}/decisions/${dpId}/resolve`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  landscape: (eid: string) => call<Landscape>(`/engagements/${eid}/systems/landscape`),
  registerSystem: (eid: string, sys: Partial<SystemRecord>) =>
    call<{ registered: string }>(`/engagements/${eid}/systems`, {
      method: "POST",
      body: JSON.stringify(sys),
    }),
};

// --- full endpoint coverage (E2): identity, lifecycle, decisions, schema, evidence ---------------

export type EngagementDetail = Engagement & {
  phase: string;
  next_phases: string[];
  phases: string[];
  open_decision_points: Record<string, string[]>;
};

export type IRRecordView = {
  key: string;
  object: string;
  product: string;
  tier: "A" | "B" | "C";
  system_binding: string;
  external_code: string | null;
  depends_on: string[];
  intent: Record<string, unknown>;
  source: Record<string, string>;
};

export type Evidence = {
  bundle_version: string;
  engagement: { engagement_id: string; name: string; client: string; phase: string };
  chain: {
    genesis: string;
    entries: LedgerEntry[];
    verification: { verified: boolean; entries?: number; head?: string; broken_at?: number; reason?: string };
    verify_procedure: string;
  };
  separation_of_duties: {
    task: string; approved_by: string; executed_by: string[];
    separation_held: boolean; snapshot_present: boolean;
  }[];
  decision_points: { all: DecisionPoint[]; unresolved: string[] };
  landscape: Landscape;
  ir: { records: number; open_decision_points: Record<string, string[]>; sources: string[] };
  line_state: { halt_events: LedgerEntry[] };
  plan: Plan | null;
  manifest_sha256: string;
};

/** A belief with its receipt attached — ADR-0010. Never a bare sentence: `source_ref` is what it
    was grounded in, and `status` is a hash comparison against that source, not an opinion. */
export type Claim = {
  id: string;
  subject: string;
  text: string;
  status: "TRUSTED" | "STALE" | "UNVERIFIED";
  source_ref: string;
  confidence: number;
  actor: string;
  valid_from: string;
  valid_to: string | null;
  supersedes: string | null;
};

export type MemoryView = {
  project: Claim[];
  system: Claim[];
  counts: Record<Claim["status"], number>;
  stale: Claim[];
};

/** The signed-in operator. Empty roles means the API is running with auth optional. */

export type DriftFindingView = {
  key: string; status: "DRIFT" | "MISSING"; system: string;
  fields: Record<string, { intent: unknown; live: unknown }>;
  decision_point: string;
};
export type VerificationRun = {
  verified: string[];
  drift: DriftFindingView[];
  skipped: { key: string; reason: string }[];
  /** Signed intent describes it and nobody has built it yet. Not drift — nothing changed under
      anyone, because nothing was ever there. It is unbuilt work, and the plan is what closes it. */
  not_applied: { key: string; system: string; reason: string }[];
  /** Handed to a person and not in the system yet. Also not drift: the platform did its half of
      a Tier B/C step and the work is outstanding, which is a thing to chase with a date on it. */
  awaiting_a_person: { key: string; system: string; tier: string; handed_over: string; reason: string }[];
  /** The product publishes no way to read this object back, so no re-read will ever confirm it.
      Waiting would be waiting forever; what is owed is a named person's attestation (ADR-0022). */
  unconfirmable: { key: string; system: string; tier: string; reason: string }[];
  /** A person said they did it, on the chain, against one version of the record's intent. Weaker
      than verified and never shown as if it were — the platform has not seen the system. */
  attested: { key: string; system: string; tier: string; reason: string;
              attested_by: string; at: string; note: string }[];
  planning_blocked: boolean;
};
/** What this engagement can prove, counted from its own chain (ADR-0023). `fraction` is null when
    nothing claims to be done — an empty set has no score, and 0 would read as a failure. */
export type AssuranceView = {
  records: number;
  basis: Record<string, string[]>;
  counts: Record<string, number>;
  claimed: number;
  proven: number;
  fraction: number | null;
  /** Published with the number, so nobody has to take the number on trust. */
  formula: string;
  not_counted: string[];
};

/** A control written as a predicate over the whole ledger (C6). Violations are enumerated in
    full, never counted: a control that cannot show its violations is prose again. */
export type ControlResult = {
  control_id: string;
  statement: string;
  population: string;
  tested: number;
  passed: boolean;
  /** NOT_EXERCISED is not a pass — there was nothing on the chain to test. */
  status: "PASS" | "FAIL" | "NOT_EXERCISED";
  violations: { task: string; actor: string; ts: string; why: string }[];
};

export type ControlsView = {
  controls: ControlResult[];
  failing: string[];
  not_exercised: string[];
  population_complete: boolean;
  method: string;
};

/** What the twin predicts, and how much that is worth. `fidelity` is null until the twin has
    scored enough predictions to have earned a rate — a percentage from four comparisons is the
    kind of number that gets quoted (ADR-0026). */
export type TwinView = {
  predictions: { key: string; verdict: "ACCEPT" | "REJECT"; reasons: string[]; at?: string }[];
  rules_evaluatable: number;
  refused_rules: { rule_id: string; why: string }[];
  skipped?: { key: string; reason: string }[];
  fidelity: {
    scored: number; agreed: number; disagreed: number; unsettled: number;
    fidelity: number | null; status: "CALIBRATED" | "UNCALIBRATED"; min_scored: number;
    misses: { task: string; predicted: string; outcome: string }[];
    method: string;
  };
};

export type NumberRangeView = {
  range_id: string; object_type: string; prefix: string;
  start: number; end: number; width: number; next_free: string | null;
};
export type NumberingSnapshot = { ranges: NumberRangeView[]; allocated: Record<string, string> };

export type Session = { subject: string; roles: string[] };

const STORE_KEY = "jidoka.session";

/** sessionStorage, never localStorage: a governance console whose token outlives the browser is
    worse than a re-login. Every access is guarded — private browsing throws on the property
    itself, so the try must wrap the lookup and not only the call. */
function store(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

/** A token the console cannot read the expiry of is a token it must not keep. The claim shape is
    the API's own (auth.issue_token), so `exp` is always there on a token we minted. */
function expired(bearer: string): boolean {
  try {
    const body = bearer.split(".")[0];
    const json = atob(body.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (body.length % 4)) % 4));
    const exp = Number(JSON.parse(json).exp);
    return !Number.isFinite(exp) || exp * 1000 <= Date.now();
  } catch {
    return true;   // unreadable is treated as expired: sign out cleanly rather than 401 later
  }
}

function restore(): { session: Session; token: string } | null {
  const raw = (() => {
    try {
      return store()?.getItem(STORE_KEY) ?? null;
    } catch {
      return null;
    }
  })();
  if (!raw) return null;
  try {
    const held = JSON.parse(raw) as { session: Session; token: string };
    if (!held?.token || !held.session?.subject || expired(held.token)) {
      // An expired token is dropped here rather than sent — the reload signs the operator out,
      // it does not hand them a console that 401s on its first call.
      try { store()?.removeItem(STORE_KEY); } catch { /* nothing to clear */ }
      return null;
    }
    return held;
  } catch {
    return null;
  }
}

const held = restore();
let session: Session | null = held?.session ?? null;
let token: string | null = held?.token ?? null;

export function setSession(next: Session | null, bearer: string | null = null) {
  session = next;
  token = bearer;
  try {
    if (next && bearer) store()?.setItem(STORE_KEY, JSON.stringify({ session: next, token: bearer }));
    else store()?.removeItem(STORE_KEY);
  } catch {
    /* storage refused (private browsing, quota). The session still works for this tab. */
  }
}
export function getSession() {
  // Re-checked on every read, not only at load: a tab left open past the token's expiry must
  // sign out rather than keep calling with a token the API will reject.
  if (token && expired(token)) setSession(null);
  return session;
}
export function authHeader(): Record<string, string> {
  return token ? { authorization: `Bearer ${token}` } : {};
}

const api2 = {
  roles: () => call<{ roles: string[] }>("/auth/roles"),
  /** Dev sign-in. Returns the same claim shape production's identity provider issues. */
  signIn: (subject: string, roles: string[]) =>
    call<{ token: string; subject: string; roles: string[] }>("/auth/token", {
      method: "POST",
      body: JSON.stringify({ subject, roles }),
    }),
  detail: (eid: string) => call<EngagementDetail>(`/engagements/${eid}`),
  advancePhase: (eid: string, to: string, actor = "") =>
    call<{ phase: string; from: string }>(`/engagements/${eid}/phase`, {
      method: "POST",
      body: JSON.stringify({ to, actor }),
    }),
  currentPlan: (eid: string) => call<Plan>(`/engagements/${eid}/plan`),
  ir: (eid: string) =>
    call<{ schema: string; open_decision_points: Record<string, string[]>; records: IRRecordView[] }>(
      `/engagements/${eid}/ir`,
    ),
  validateIR: (eid: string, records: unknown[]) =>
    call<{ schema: string; records: number; errors: Record<string, string[]>; loadable: boolean }>(
      `/engagements/${eid}/ir/validate`,
      { method: "POST", body: JSON.stringify(records) },
    ),
  decisions: (eid: string) =>
    call<{ decision_points: DecisionPoint[]; unresolved: string[]; ir_gaps: Record<string, string[]> }>(
      `/engagements/${eid}/decisions`,
    ),
  evidence: (eid: string) => call<Evidence>(`/engagements/${eid}/ledger/evidence`),
  documents: (eid: string) =>
    call<{ documents: { id: string; title: string }[] }>(`/engagements/${eid}/documents`),
  /* Markdown, not JSON. `call` keeps a non-JSON body verbatim, so the document arrives as written
     rather than round-tripped through an envelope that would only be unwrapped again here. */
  document: (eid: string, id: string) => call<string>(`/engagements/${eid}/documents/${id}`),
  armed: (eid: string) => call<{ armed: ArmedTarget[] }>(`/engagements/${eid}/execution/arm`),
  connectors: (eid: string) =>
    call<{ connectors: Connector[] }>(`/engagements/${eid}/execution/connector`),
  /** A connector is a write credential, so binding one is refused wherever invariant 3 forbids it.
      `secret_env` is the NAME of an environment variable prefix — never a secret itself. */
  bindConnector: (eid: string, system_id: string, kind: string, base_url = "", secret_env = "") =>
    call<{ system_id: string; kind: string; product: string }>(
      `/engagements/${eid}/execution/connector`,
      { method: "POST", body: JSON.stringify({ system_id, kind, base_url, secret_env }) },
    ),
  /** Approver-only. The builder who executes can never be the one who arms — see ADR-0005. */
  arm: (eid: string, system_id: string, reason = "") =>
    call<{ armed: string; armed_by: string; reason: string }>(`/engagements/${eid}/execution/arm`, {
      method: "POST",
      body: JSON.stringify({ system_id, reason }),
    }),
  disarm: (eid: string, system_id: string) =>
    call<{ armed: null }>(`/engagements/${eid}/execution/arm/${system_id}`, { method: "DELETE" }),
  snapshot: (eid: string, key: string) =>
    call<{ key: string; rows: number; before: Record<string, unknown>[] }>(
      `/engagements/${eid}/execution/snapshot`,
      { method: "POST", body: JSON.stringify({ key }) },
    ),
  execute: (eid: string, key: string) =>
    call<ExecutionResult>(`/engagements/${eid}/execution/execute`, {
      method: "POST",
      body: JSON.stringify({ key }),
    }),
  /** A person's word about work this platform has no way to read back. Refused with a 409 where
      the object IS readable — there, the live system answers and nobody's word substitutes. */
  attest: (eid: string, key: string, note = "") =>
    call<{ key: string; attested_by: string; at: string; note: string }>(
      `/engagements/${eid}/execution/attest`,
      { method: "POST", body: JSON.stringify({ key, note }) },
    ),
  /** A restore is a write: it wears the same armed target, snapshot and builder-is-not-approver
      gates an execute does. The server refuses; the console only offers. */
  rollback: (eid: string, key: string, reason = "") =>
    call<{ key: string; tier: string; system: string; status: StepStatus; detail: string; rows: number }>(
      `/engagements/${eid}/execution/rollback`,
      { method: "POST", body: JSON.stringify({ key, reason }) },
    ),
  /** One call, one hop along the declared route. ABAP only — ADR-0006. */
  advanceTransport: (eid: string, key: string) =>
    call<StepTransport>(`/engagements/${eid}/execution/transport`, {
      method: "POST",
      body: JSON.stringify({ key }),
    }),
  transports: (eid: string) =>
    call<{ transports: StepTransport[] }>(`/engagements/${eid}/execution/transport`),
  schema: () => call<{ version: string; schema: Record<string, unknown> }>(`/schema/ir`),

  /* ---- memory (ADR-0010) — every route is scoped by engagement, deliberately. There is no
     call here that reads across engagements because the API publishes none. ---- */
  memory: (eid: string) => call<MemoryView>(`/engagements/${eid}/memory`),
  /** What was believed at a moment. Validity intervals make this a read, not a reconstruction. */
  memoryAsOf: (eid: string, when: string) =>
    call<{ as_of: string; claims: Claim[] }>(
      `/engagements/${eid}/memory/as-of?when=${encodeURIComponent(when)}`,
    ),
  /** Bind a reader with no write half. The systems most worth reading — legacy, twin — are the
      ones invariant 3 forbids a write credential on, so reading them needs a binding that has
      none rather than a relaxed check. */
  bindReader: (eid: string, system_id: string, kind = "mock", base_url = "", secret_env = "") =>
    call<{ system_id: string; kind: string; product: string }>(
      `/engagements/${eid}/execution/connector/reader`,
      { method: "POST", body: JSON.stringify({ system_id, kind, base_url, secret_env }) },
    ),
  /** Learn a system from its own metadata (ADR-0012). Read-only: the adapter's extract() is the
      only method this path can reach. Nothing is promoted — `offered` is a queue for a person. */
  harvest: (eid: string, system_id: string) =>
    call<{ system_id: string; formed: number; offered: Claim[]; claims: Claim[] }>(
      `/engagements/${eid}/memory/harvest`,
      { method: "POST", body: JSON.stringify({ system_id }) },
    ),
  /** A claim without a source is refused by the domain, so the console always sends one. */
  formClaim: (eid: string, body: { subject: string; text: string; source_ref: string; evidence: unknown }) =>
    call<Claim>(`/engagements/${eid}/memory`, { method: "POST", body: JSON.stringify(body) }),
  /** Deterministic: the server re-reads the claim's source and compares hashes, no model call.
      The console sends no evidence on purpose — it does not hold the source, and a caller that
      supplied the evidence would be answering the question it asked. */
  recheckClaim: (eid: string, claimId: string) =>
    call<{ status: Claim["status"]; claim: Claim }>(
      `/engagements/${eid}/memory/${claimId}/recheck`, { method: "POST" },
    ),
  /** Supersede, never overwrite: the prior belief keeps its place with a closed interval. */
  correctClaim: (eid: string, claimId: string,
                 body: { text: string; source_ref: string; evidence: unknown }) =>
    call<{ superseded: string; claim: Claim }>(
      `/engagements/${eid}/memory/${claimId}/correct`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  /** The scrubber gate — the only flow that crosses a tenant boundary. The server refuses a
      self-approval or a client value with a 422; the console quotes that refusal, never invents it. */
  promoteClaim: (eid: string, claimId: string, approver: string) =>
    call<{ promoted: Claim }>(`/engagements/${eid}/memory/${claimId}/promote`, {
      method: "POST",
      body: JSON.stringify({ approver }),
    }),
  /* ---- verification & number ranges (ADR-0013, ADR-0014) ---- */
  /** Read the live systems and compare them to signed intent. Reading only — a drift raises a
      blocking decision point on the server; the console never reconciles anything. */
  verify: (eid: string) =>
    call<VerificationRun>(`/engagements/${eid}/verification`, { method: "POST" }),
  /** A read of the chain: it costs nothing and cannot disagree with the ledger it is drawn from. */
  assurance: (eid: string) => call<AssuranceView>(`/engagements/${eid}/verification/assurance`),
  /** Every control, over every row. Read-only, and an auditor asks it more than anybody. */
  controls: (eid: string) => call<ControlsView>(`/engagements/${eid}/controls`),
  twin: (eid: string) => call<TwinView>(`/engagements/${eid}/twin`),
  /** Predicts and ledgers the prediction. It never blocks — see the view's own note. */
  runTwin: (eid: string) => call<TwinView>(`/engagements/${eid}/twin`, { method: "POST" }),
  /** Rules outside the evaluatable subset come back named, and are shown rather than swallowed. */
  loadTwinRules: (eid: string, rules: unknown[], source = "") =>
    call<{ evaluatable: number; refused: { rule_id: string; why: string }[] }>(
      `/engagements/${eid}/twin/rules`,
      { method: "POST", body: JSON.stringify({ rules, source }) },
    ),
  numbering: (eid: string) => call<NumberingSnapshot>(`/engagements/${eid}/numbering`),
  registerRange: (eid: string, body: {
    range_id: string; object_type: string; prefix: string; start: number; end: number; width?: number;
  }) =>
    call<{ registered: string; governs: string; codes: string }>(
      `/engagements/${eid}/numbering/ranges`, { method: "POST", body: JSON.stringify(body) },
    ),
  /** A collision comes back 409 with the holder's name in it. The console quotes it verbatim. */
  allocateCode: (eid: string, object_type: string, code?: string) =>
    call<{ allocated: string; object_type: string }>(
      `/engagements/${eid}/numbering/allocate`,
      { method: "POST", body: JSON.stringify({ object_type, code: code || null }) },
    ),
};

const api3 = {
  /* ---- insight: the brownfield door. Archaeology reads a live tenant into drafts that are
     unsigned by construction; signing one turns it into ordinary IR that the planner, the
     documents and verification already handle. Nothing here reconciles or writes to a tenant. ---- */
  /** Reverse a bound system into draft records. Reads only. */
  dig: (eid: string, system_id: string, entities: string[]) =>
    call<Backlog>(`/engagements/${eid}/insight/archaeology`, {
      method: "POST",
      body: JSON.stringify({ system_id, entities }),
    }),
  backlog: (eid: string) => call<Backlog>(`/engagements/${eid}/insight/archaeology`),
  /** The signature is the server's view of who is calling (ADR-0015) — there is no signer field
      to send, and the console does not offer one. */
  signDrafts: (eid: string, keys: string[], workbook: string, rationale = "") =>
    call<{ signed: string[]; open_dps: Record<string, string[]>; ir_records: number; backlog: Backlog }>(
      `/engagements/${eid}/insight/archaeology/sign`,
      { method: "POST", body: JSON.stringify({ keys, workbook, rationale }) },
    ),
  debt: (eid: string) => call<Debt>(`/engagements/${eid}/insight/debt`),
  timetravel: (eid: string, at: string) =>
    call<TimeTravel>(`/engagements/${eid}/insight/timetravel?at=${encodeURIComponent(at)}`),
  /** Counted in people, from the live system. A blast radius from a design document counts the
      people somebody meant to have. */
  blast: (eid: string, body: { system_id: string; entity: string; id_field: string;
                               selector: Record<string, string>; delta: string }) =>
    call<Blast>(`/engagements/${eid}/insight/blast`, { method: "POST", body: JSON.stringify(body) }),

  /* ---- the crew run (ADR-0018). The team takes the engagement as far as it can go alone and
     stops at every human gate: it cannot arm a live write and no ring it can occupy can approve. ---- */
  runCrew: (eid: string) => call<CrewRun>(`/engagements/${eid}/run`, { method: "POST" }),
  /** Work the night and compose the morning's handover. Writes the ledger, like any check does. */
  runNight: (eid: string) => call<NightShift>(`/engagements/${eid}/nightshift`, { method: "POST" }),
  lastNight: (eid: string) => call<NightShift>(`/engagements/${eid}/nightshift`),
  team: (eid: string) =>
    call<{ people: TeamMember[]; can_be_asked_for: string[] }>(`/engagements/${eid}/people`),
  /** Replaces the team: it is a statement about now, not an append log. */
  registerTeam: (eid: string, people: unknown[]) =>
    call<{ people: TeamMember[] }>(`/engagements/${eid}/people`,
      { method: "POST", body: JSON.stringify(people) }),
  lastRun: (eid: string) => call<CrewRun>(`/engagements/${eid}/run`),
};

/** One client surface. Typed by construction, so a missing endpoint is a compile error. */
export const platform = { ...api, ...api2, ...api3 };
