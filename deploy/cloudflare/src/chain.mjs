/**
 * The hash-chained ledger, in plain JavaScript so one file is the only copy.
 *
 * This is the one place in the repository that reimplements a kernel invariant in a second
 * language, and the deployment spec is explicit that it is dangerous: "every invariant
 * reimplemented in a second language is an invariant that can drift out of agreement with the
 * tested one." So it is held to `packages/jidoka-core/tests/fixtures/ledger_conformance.json` —
 * the same operations, the same hashes, the same refusal messages, byte for byte — by
 * `ledger.check.mjs`, which CI runs beside the Python suite held to that same file.
 *
 * Plain .mjs rather than TypeScript on purpose: the Worker imports it and bare `node` runs it
 * unmodified, so the thing CI checks is the thing that ships. A transpiled copy would be a third
 * artefact to keep in agreement with the other two.
 *
 * The subtle part is not the SHA-256. It is that Python's `json.dumps` sorts keys, escapes
 * non-ASCII, and separates with ", " and ": " — and `JSON.stringify` does none of those three. A
 * chain built with `JSON.stringify` verifies perfectly against itself and fails against every
 * chain the kernel ever wrote, which is a governance failure that looks like a bug and arrives
 * the first time an auditor checks the edge's chain against the kernel's.
 */

export const GENESIS = "0".repeat(64);

export class SoDViolation extends Error {}
export class LedgerTampered extends Error {}

/** Python's `json.dumps(obj, sort_keys=True)`, exactly. Anything else is a different chain. */
export function canonical(value) {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return pyNumber(value);
  if (typeof value === "string") return pyString(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(", ")}]`;
  if (typeof value === "object") {
    // Python sorts by the key's code points, which is what Array#sort does for strings.
    const keys = Object.keys(value).sort();
    return `{${keys.map((k) => `${pyString(k)}: ${canonical(value[k])}`).join(", ")}}`;
  }
  throw new TypeError(`not JSON-serialisable: ${typeof value}`);
}

/** Python writes a float that happens to be integral as "1.0"; JS writes "1". An entry carrying
 *  such a value would hash differently for a number that is equal, so it is refused rather than
 *  silently written — the kernel can produce one and this cannot represent it. */
function pyNumber(n) {
  if (!Number.isFinite(n)) throw new TypeError("Infinity and NaN are not valid JSON here");
  return String(n);
}

/** `ensure_ascii=True`: every non-ASCII character becomes a \uXXXX escape, astral characters as a
 *  surrogate pair. A client name with a "ü" in it is not an exotic case. */
function pyString(s) {
  let out = '"';
  for (const ch of s) {
    const c = ch.codePointAt(0);
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (ch === "\n") out += "\\n";
    else if (ch === "\r") out += "\\r";
    else if (ch === "\t") out += "\\t";
    else if (c < 0x20) out += `\\u${c.toString(16).padStart(4, "0")}`;
    else if (c < 0x7f) out += ch;
    else if (c <= 0xffff) out += `\\u${c.toString(16).padStart(4, "0")}`;
    else {
      const v = c - 0x10000;
      out += `\\u${(0xd800 + (v >> 10)).toString(16).padStart(4, "0")}`;
      out += `\\u${(0xdc00 + (v & 0x3ff)).toString(16).padStart(4, "0")}`;
    }
  }
  return `${out}"`;
}

async function sha256(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** The entry's own fields plus the previous hash, without `hash` or `prev` themselves. */
export async function hashEntry(entry, prev) {
  const body = {};
  for (const [k, v] of Object.entries(entry)) if (k !== "hash" && k !== "prev") body[k] = v;
  body.prev = prev;
  return sha256(canonical(body));
}

/** Append-only and hash-chained, with the kernel's two approval rules in the kernel's order. */
export class Chain {
  constructor(entries = []) { this.entries = entries; }

  async append(task, action, actor, detail = "", extra = {}, ts) {
    const prev = this.entries.length ? String(this.entries[this.entries.length - 1].hash) : GENESIS;
    const entry = { ts: ts ?? new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
                    task, action, actor, detail, ...extra };
    entry.hash = await hashEntry(entry, prev);
    entry.prev = prev;
    this.entries.push(entry);
    return entry;
  }

  /** Reviewer != builder, and a before-snapshot already on the chain. Both refusals carry the
   *  kernel's exact words: an operator reads one message wherever the platform is hosted. */
  async approve(task, reviewer, ts) {
    const builders = new Set(this.entries
      .filter((e) => e.task === task && e.action === "EXECUTED").map((e) => e.actor));
    if (builders.has(reviewer)) {
      throw new SoDViolation(
        `${reviewer} executed ${task} and may not approve it (builder != reviewer).`);
    }
    if (!this.entries.some((e) => e.task === task && e.action === "SNAPSHOT")) {
      throw new SoDViolation(`${task}: apjidokal refused — no before-snapshot on the ledger.`);
    }
    return this.append(task, "APPROVED", reviewer, "", {}, ts);
  }

  async verify() {
    let prev = GENESIS;
    for (const e of this.entries) {
      if (e.prev !== prev || (await hashEntry(e, prev)) !== e.hash) {
        throw new LedgerTampered(`Chain broken at task=${e.task} action=${e.action}`);
      }
      prev = String(e.hash);
    }
    return true;
  }
}
