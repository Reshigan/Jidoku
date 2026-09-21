# ADR-0038 — BTP is declarative, so the artefact is the plan

Status: Accepted
Date: 2026-09-21
Relates to ADR-0003 (the tier model), ADR-0006 (transport-aware completion), invariant 6.
Delivers E8's BTP adapter.

## Context

Every other product this platform touches has a configuration client: you log in, you change a
thing, the thing is changed. BTP does not. It is a control plane with REST APIs and a published
Terraform provider, and most of a subaccount's configuration is written as a declaration that
somebody applies.

The roadmap line said "BTP adapter via Terraform provider", and the obvious reading is that JIDOKA
runs `terraform apply` — a real write path, so Tier A.

## Decision

**Terraform-declared objects are Tier B, not Tier A.** JIDOKA emits the HCL; a person runs
`terraform plan`, reads the diff, and applies under their own credentials; JIDOKA verifies
afterwards by reading the BTP APIs. That is exactly the Tier-B bargain — an artefact a person
executes and the platform confirms — and it is the right one here for a specific reason:
**Terraform state**. If JIDOKA applied the plan, it would either own the customer's state file,
becoming the only thing that may ever touch that subaccount, or apply without state and destroy
whatever it did not know about. Neither is a thing to do to somebody's platform tenant.

**Tier B here is still verifiable, and that is what makes the hand-off honest.** The provider
reads through the same APIs this adapter reads through, so `unverifiable()` is derived from the
read map and Tier B is not in it. A Tier-B object elsewhere in this platform often cannot be read
back; here it can, and claiming otherwise would understate what the platform can prove.

**Tier A is small and real:** role collection membership and destinations, which publish a write
API that reads the result straight back. Nothing is Tier A because it ought to be.

**Tier C is cockpit-only and says so:** the commercial contract, IdP branding, analytics opt-in.
No API, no provider resource, a person and an attestation.

**A disagreement between the IR's tier and the adapter's is refused, not resolved.** Guessing
which is right would be the platform deciding what a product permits.

**An object with no declared provider resource is refused rather than guessed.** Emitting
plausible HCL would put a block in front of a reviewer who has no way to tell it was invented.

**The HCL is plain.** Named resources, explicit values, no modules, no variables. A consultant
reads it and a reviewer reviews it; a module is a thing a person writes, not a thing a config
compiler emits.

**`externalCode` is excluded from the verification diff.** It is the IR's own name for the record,
not a field of the BTP object, and comparing it against live state would report every object as
drifted for a difference that is not about the customer's tenant at all.

## Consequences

- There is no live BTP connector. `_live` refuses BTP by name, and a test asserts the refusal. A
  connector written against an API nobody has called would be a plausible-looking write path into
  a customer's control plane, which is the one thing worse than no connector.
- The plan sheet tells the operator, in its own words, that JIDOKA has not seen their state file
  and cannot know what else the plan will touch. That is the step the bargain exists for, and
  hiding it would make the artefact look safer than it is.
- `RESOURCES` covers seven provider resource types. The provider has more, and each one added is
  a line plus a fixture — an unlisted object is refused, loudly, rather than approximated.

## Alternatives rejected

*Run `terraform apply` from the executor.* Discussed above: state ownership or destruction. Also
it would need the Terraform binary in the kernel image and the customer's cloud credentials in
JIDOKA's process, both of which the deployment spec is at pains to avoid.

*Call the BTP REST APIs directly for everything and skip Terraform.* It would make more objects
Tier A and it would fight the customer's own tooling: a subaccount managed by Terraform and edited
by an API caller drifts on the next `apply`, and JIDOKA would be the thing that caused it.

*Declare the Terraform objects Tier C.* Dishonest in the other direction: a person really does run
a repeatable, reviewable artefact, and the platform really can read the result back.
