/**
 * EngagementLedger: the chain as a Durable Object, one per engagement.
 *
 * The chain itself is `chain.mjs` and is held to the kernel's conformance fixture. This file is
 * only what makes it durable and addressable — deliberately thin, because every line here is a
 * line that could hold a rule the kernel does not have.
 *
 * One DO per engagement is what makes appends serialisable without a lock: a Durable Object
 * handles its requests one at a time, so two appends cannot race for the same `prev` hash. That
 * is the property the in-process kernel gets for free from the GIL and a single store, and it is
 * the property a plain Worker over D1 would not have.
 */
import { Chain, type Entry, LedgerTampered, SoDViolation } from "./chain.mjs";

export { Chain, GENESIS, LedgerTampered, SoDViolation, canonical, hashEntry } from "./chain.mjs";

export class EngagementLedger {
  private chain: Chain | null = null;

  constructor(private state: DurableObjectState) {}

  private async load(): Promise<Chain> {
    if (!this.chain) {
      this.chain = new Chain((await this.state.storage.get<Entry[]>("entries")) ?? []);
    }
    return this.chain;
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const chain = await this.load();
    // Cloudflare Access puts the verified identity here. Never the request body: a client that
    // can name its own actor can name somebody else's, and the ledger's whole value is that the
    // name on an entry is the name of whoever did it (ADR-0008, invariant 4).
    const actor = request.headers.get("cf-access-authenticated-user-email") ?? "";

    try {
      if (url.pathname === "/entries") return Response.json(chain.entries);

      if (url.pathname === "/verify") {
        await chain.verify();
        return Response.json({ ok: true, entries: chain.entries.length });
      }

      if (!actor) {
        return Response.json(
          { detail: "No authenticated identity on this request. The ledger records who did a " +
                    "thing, and an entry attributed to nobody is not a record." },
          { status: 401 });
      }

      if (url.pathname === "/append" && request.method === "POST") {
        const b = await request.json() as {
          task: string; action: string; detail?: string; extra?: Record<string, unknown> };
        const entry = await chain.append(b.task, b.action, actor, b.detail ?? "", b.extra ?? {});
        await this.state.storage.put("entries", chain.entries);
        return Response.json(entry);
      }

      if (url.pathname === "/approve" && request.method === "POST") {
        const b = await request.json() as { task: string };
        const entry = await chain.approve(b.task, actor);
        await this.state.storage.put("entries", chain.entries);
        return Response.json(entry);
      }
    } catch (err) {
      // The kernel's own status mapping: a gate violation is a 403, a broken chain a 409.
      if (err instanceof SoDViolation) return Response.json({ detail: err.message }, { status: 403 });
      if (err instanceof LedgerTampered) return Response.json({ detail: err.message }, { status: 409 });
      throw err;
    }
    return Response.json({ detail: "No such ledger operation." }, { status: 404 });
  }
}
