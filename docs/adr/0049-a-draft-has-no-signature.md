# ADR-0049 — A draft has no signature

Status: Accepted
Date: 2026-09-28
Amends ADR-0048. Touches invariants 1 and 7.
Found by re-reading ADR-0048's own design pass for how it could be defeated.

## Context

ADR-0048 gave the agent tools to author intent, behind four gates. One of those gates was
`validate_record`, and the design pass's tool schema was a projection of the published IR schema —
which requires `source.signed_by` and `source.date`.

So the agent was *asked* to write a signature, and the gate checked that one was *present*. Invariant
1 says unsigned intent is unloadable; what the code enforced was that a field was non-empty. Those are
different properties, and the difference is exactly the size of a model typing a person's name into
the field. A record carrying a signature nobody gave is unsigned intent wearing a signature, and it
passed every gate this repository had.

Invariant 7 — the agent is always builder, never approver — was procedural. Nothing structural
prevented the builder from writing the approval into the record it authored.

## Decision

**A draft has no signature, and there is nowhere in one for a signature to go.**
`jidoka_core.proposals.check` refuses a draft that arrives carrying `source.signed_by` or
`source.date`, naming the reason: *a model that writes a name here is asserting an approval nobody
gave.* The design pass's tool schema no longer asks for either field — it asks for `source.workbook`,
the document section or decision point the values came from.

**Provenance is stamped from what was cited, not from what was typed.** `draft()` replaces whatever
`source` the drafter supplied with the platform's own from the `sources` argument. A proposal that
passes cannot carry anything the model wrote in a field a person will later rely on.

**A person's signature is stamped from an authenticated identity.** `POST .../proposals/{key}/sign`
takes no body. `signed_by` is `identity.subject` and `date` is the server's, so there is no request
field in which to supply a name — the property is structural, not a rule about what to put there.

**Signing is `approve`, and the signer cannot be the drafter.** A builder has no `approve`, so the
agent cannot sign; and a person holding both roles is refused on their own draft with a 409 naming the
rule. Drafter and signer are two people (invariant 4).

**The signed record goes through the one load path.** `routers/ir.py` now exposes `load_records`,
shared by the workbook upload and by signing, so a signed draft meets exactly the gates a workbook
does — signed source, numbering, tier honesty, supersession, orphans, the delta pool. A second path
that "merged one record" would be a second set of gates, and the weaker one is the one that gets used.
Signing *merges* into the design; `POST /ir` replaces it, which is right for a workbook and would have
deleted every other record on the first signature.

**Proposals are a projection over the chain.** `IR_PROPOSED` carries the record; `IR_SIGNED` and
`IR_PROPOSAL_REJECTED` close it. Nothing is stored beside the ledger, so a restart loses nothing and
the state cannot disagree with the record of what happened. A re-proposal after a rejection is pending
again and the rejection stays.

**A batch is checked whole.** A pass half of whose drafts were refused leaves a reviewer reading
proposals from a pass the platform declined.

## Consequences

- An accepted draft is unloadable until signed — asserted in a test, because that is invariant 1
  holding rather than merely being claimed.
- The design pass's output is now drafts, not records. `tools/jidoka-design.py` emits them and the
  proposals endpoint takes them; a person reads and signs on the Proposals screen.
- `validate_record` is unchanged and still trusts `source.signed_by` on anything it is given. That is
  correct for a workbook a person signed and is the reason drafts must never reach it unsigned. The
  guarantee is now: **nothing an agent wrote reaches `validate_record` except through `sign`.**
- Signing is one record at a time. A hundred drafts is a hundred signatures, which is the honest cost
  of a person reading what they sign; bulk signing is a decision for later and would need its own
  answer to "what did the signer actually read".
- What this does not prevent: a signer who signs without reading. That is a human failure and the
  platform's answer to it is the ledger, which records who signed what and when.

## Alternatives rejected

*Strip a signature the drafter wrote and accept the rest.* Silently repairing a fabricated approval
teaches the drafter nothing and hides the attempt. It is refused, loudly, and the attempt is on the
record.

*Let the agent's own identity sign, since it is "authenticated".* An authenticated agent signing its
own work is invariant 7 defeated by a technicality.

*Trust `validate_record` and add a prompt instruction not to sign.* A prompt is a request. The gate
is what makes it true.

*Store proposals in a table.* A second source of truth that has to agree with the ledger, and will
not.
