/**
 * Edge front door for JIDOKA.
 *
 * Two jobs, deliberately no more. It serves the built console from static assets, and it forwards
 * the API surface to the Python kernel. It does NOT re-implement any gate: every invariant lives
 * once, in jidoka-core, and a second copy at the edge is a second copy that can drift out of
 * agreement with the first. Per docs/JIDOKA_DEPLOYMENT_AND_KNOWLEDGE_SPEC.md Part B the
 * Workers-native kernel port is phase 2; phase 1 runs the container image unchanged.
 *
 * The console calls same-origin relative paths, so fronting both from one hostname means the
 * frontend needs no build-time knowledge of where the API lives.
 */

export async function workTheNight(env: Env): Promise<{ worked: number; failed: number }> {
  if (!env.KERNEL_URL || !env.NIGHT_TOKEN) {
    // Refuse loudly rather than call a customer's kernel unauthenticated. A silent no-op here is
    // a night shift nobody knows stopped happening.
    console.error("nightshift: KERNEL_URL or NIGHT_TOKEN is not configured — no night was worked.");
    return { worked: 0, failed: 0 };
  }
  const auth = { authorization: `Bearer ${env.NIGHT_TOKEN}` };
  const list = await fetch(new URL("/engagements", env.KERNEL_URL), { headers: auth });
  if (!list.ok) {
    console.error(`nightshift: could not list engagements (HTTP ${list.status}).`);
    return { worked: 0, failed: 0 };
  }
  let worked = 0;
  let failed = 0;
  for (const path of nightTargets(await list.json())) {
    const res = await fetch(new URL(path, env.KERNEL_URL), { method: "POST", headers: auth });
    if (res.ok) worked += 1;
    else {
      failed += 1;
      console.error(`nightshift: ${path} returned HTTP ${res.status}.`);
    }
  }
  console.log(`nightshift: ${worked} engagement(s) worked, ${failed} failed.`);
  return { worked, failed };
}

// Kept in step with vite.config.ts. Anything not on this list is console routing and falls
// through to the SPA, so a typo'd API path renders the app rather than silently 404-ing as JSON.
const API_PREFIXES = ["/engagements", "/health", "/auth", "/schema", "/openapi.json"];

/** Kernel or console. Exported so src/routing.check.mjs can assert it without a test framework:
 *  a prefix match that forgets the "/" separator sends /healthz and /authors to the kernel. */
export const isApi = (pathname: string) =>
  API_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + "/"));

export interface Env {
  ASSETS: Fetcher;
  /** Origin of the FastAPI kernel (Cloudflare Container, or any reachable host). */
  KERNEL_URL: string;
  /** Bearer for the night shift's own calls, set with `wrangler secret put NIGHT_TOKEN`. It is a
   *  builder token and nothing more: the night reads, verifies and chases, and every gate it
   *  meets is the gate a person's token meets. Absent, the scheduled run refuses rather than
   *  calling the kernel unauthenticated. */
  NIGHT_TOKEN?: string;
}

/** Engagements the night has to work, as the kernel lists them. Exported for routing.check.mjs. */
export const nightTargets = (engagements: { engagement_id: string }[]) =>
  engagements.map((e) => `/engagements/${e.engagement_id}/nightshift`);

export default {
  /**
   * The night shift's clock. It calls the kernel rather than reimplementing anything: the shift,
   * its budget and its handover live in one place, tested, and the edge only decides when.
   *
   * One engagement failing does not stop the others — a night that abandoned twelve engagements
   * because the thirteenth had no connector bound would be worse than useless.
   */
  async scheduled(event: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(workTheNight(env));
  },

  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (!API_PREFIXES.some((p) => url.pathname === p || url.pathname.startsWith(p + "/"))) {
      return env.ASSETS.fetch(request);
    }

    if (!env.KERNEL_URL) {
      // Say which half is missing. A console that renders but cannot reach the kernel is the
      // confusing failure, so name it rather than returning an opaque 502.
      return Response.json(
        { detail: "KERNEL_URL is not configured for this deployment — the console is served but the governance kernel is unreachable." },
        { status: 503 },
      );
    }

    const target = new URL(url.pathname + url.search, env.KERNEL_URL);
    // Headers pass through verbatim: the Authorization bearer is what carries identity, and the
    // kernel — not the edge — decides what it permits. Stripping or rewriting it here would move
    // an authorisation decision to a layer that has no role table.
    const upstream = new Request(target, request);
    upstream.headers.set("host", target.host);

    try {
      return await fetch(upstream);
    } catch {
      return Response.json(
        { detail: "The platform is unreachable. Showing the last verified state." },
        { status: 502 },
      );
    }
  },
};
