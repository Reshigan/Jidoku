/** Types for chain.mjs, which is plain JavaScript so that the file CI checks is the file that
 *  ships. Declared here rather than by transpiling: a transpiled copy would be a third artefact
 *  to keep in agreement with the other two. */
export declare const GENESIS: string;
export declare class SoDViolation extends Error {}
export declare class LedgerTampered extends Error {}
export declare function canonical(value: unknown): string;
export declare function hashEntry(entry: Record<string, unknown>, prev: string): Promise<string>;

export type Entry = Record<string, unknown> & {
  ts: string; task: string; action: string; actor: string; detail: string;
  hash?: string; prev?: string;
};

export declare class Chain {
  entries: Entry[];
  constructor(entries?: Entry[]);
  append(task: string, action: string, actor: string, detail?: string,
         extra?: Record<string, unknown>, ts?: string): Promise<Entry>;
  approve(task: string, reviewer: string, ts?: string): Promise<Entry>;
  verify(): Promise<true>;
}
