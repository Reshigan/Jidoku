# ADR-0045 — The adapter decides the tier, and a workbook may not overrule it

Status: Accepted
Date: 2026-09-28
Relates to ADR-0003 (the tier model), ADR-0038 (BTP refuses a tier mismatch), invariant 6.
Found by compiling a real client design pack.

## Context

ADR-0003 makes the tier map the honest declaration of what a product's interfaces permit: A where
the product publishes a write API, B where a person runs a file, C where only a UI exists. The
adapters carry that map and `audit_tier_map` reports where one lies.

Nothing checked the *other* direction. An IR record carries a `tier`, and it came from whoever
compiled the workbook. The executor refused a Tier-A object with no write target at execution time,
which is late, and the planner never questioned the claim at all.

Compiling a real design pack produced the failure. The compiler profile wrote `tier: A` for
picklist options; the SuccessFactors adapter declares `PicklistOption` as **Tier B**, a file a
person imports; nothing compared them; and the planner emitted **198 steps, every one
`API_WRITE`**, against objects SAP publishes no write API for. The plan was internally consistent,
signed, and wrong about the product.

Two of this repository's own fixtures carried the same lie — `LegalEntity` and
`cust_NotADeclaredObject`, both claimed Tier A against an adapter that knows neither.

## Decision

**The load checks the workbook's tier against the adapter's, and refuses a mismatch,** naming both
answers and which one is authoritative: *"the workbook says tier A and the SuccessFactors adapter
declares 'PicklistOption' as tier B. The product decides what it publishes a write path for."*

**Both directions are refused.** Overstating is obvious — a plan that rehearses an API call against
something only a person can change. Understating is not, and it is also wrong: a Tier-C instruction
sheet for an object with a real write API hands a person work the platform could have rehearsed,
and leaves evidence saying a human did it.

**An object no adapter knows may be Tier B or C, never Tier A.** A person doing it by hand needs no
entry in a map; a claimed write path that nothing can name is a claim with nothing behind it. This
is what keeps the gate from blocking a design whose adapter support comes later.

**At load, because the earlier refusal is the kinder one.** The same argument the connector binding
makes: this was previously caught after the design had been loaded, planned, and put in front of an
operator with an armed target.

**The executor's gate stays.** The load gate must not become the reason the write path's own check
is never exercised, so a test puts a bad record into the store directly and asserts the executor
still refuses it with the tier map named.

## Consequences

- A programme whose workbook and adapter disagree cannot load until somebody decides which is
  right, and the answer is almost always the adapter. That is a real friction on day one of an
  engagement and it is the friction the platform is for.
- A new adapter with a thin tier map now blocks Tier-A claims for everything it has not
  catalogued. That is correct — and it means adding a product means cataloguing it, rather than
  discovering the gaps one refused execution at a time.
- The compiler is now the place where tiers get asserted wrongly, and it has no access to the
  adapters (`jidoka-compiler` does not depend on `jidoka-adapters`, deliberately). The check
  therefore lives at the API boundary, which is the first place both are in scope.

## Alternatives rejected

*Have the compiler look up the tier.* It would make the compiler depend on the adapter package and
turn a design document's statement into a derived value. The workbook should be allowed to say what
it thinks; the platform should be allowed to disagree out loud.

*Silently take the adapter's tier and ignore the workbook's.* The design document would then
disagree with the plan built from it, and nobody would be told. A refusal that names both answers
is the whole point.

*Warn instead of refusing.* A warning about a claim that would rehearse an API call against a
UI-only object is a warning read after the rehearsal.
