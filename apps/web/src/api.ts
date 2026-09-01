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

export type ArmedTarget = { system_id: string; armed_by: string; reason: string };
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
};

/** One client surface. Typed by construction, so a missing endpoint is a compile error. */
export const platform = { ...api, ...api2 };
