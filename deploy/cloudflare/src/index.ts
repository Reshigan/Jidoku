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
}

export default {
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
