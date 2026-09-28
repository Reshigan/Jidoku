# ADR-0048 — The agent authors the design, and the platform refuses what it authors

Status: Accepted
Date: 2026-09-28
Relates to ADR-0045 (the adapter decides the tier), ADR-0046 (absorb the pack), ADR-0047 (the
specification), ADR-0018/0020 (the crew), invariants 1, 2 and 7.
Found by asking what "configure the entire solution" actually requires.

## Context

The K5 consultant (`consultant.py`) had six tools: `load_ir`, `build_plan`, `ledger_append`,
`raise_dp`, `get_plan`, `get_ledger`. Every one of them operates on a design **somebody else
authored**. The service was configured to use a frontier model and given a clipboard.

That made the platform's central claim false in the place it mattered. On the Komatsu pack, **86 of
87 catalogued SuccessFactors object types had no signed intent at all**, and the 62 requirements
describing them are prose in a Word document that ADR-0047's absorber deliberately does not
interpret. The gap was never SAP's write surface — 47 of 87 objects have an OData path already
implemented. The gap was that nothing turned the client's documents into intent.

A previous position in this repository's history held that rule engines, data models, workflows and
time valuations were "permanently human" because SAP publishes no write API for them. That conflated
*substrate* with *capability*. The substrate for a business rule is a UI; the authoring of one from a
stated requirement is a translation problem. Sixteen objects were excluded on the strength of that
confusion.

## Decision

**The agent gets tools to author intent**, in `jidoka_agent.design`: `read_pack` (the absorbed
registers), `read_document` (the prose — an SDD's 31 sections, carried verbatim by ADR-0046's
absorber and interpreted by nothing in it), `read_metadata` (what *this tenant* publishes),
`read_tier` (what the *product* permits), `propose_ir`, `propose_trace`, `raise_dp`.

**Four gates run on every proposal, and a refusal is returned to the model to fix.**

1. **IR validation** — `jidoka_core.ir.validate_record`, the same function the API uses. Unsigned
   intent is unloadable (invariant 1), checked here rather than three steps later.
2. **The adapter's tier, not the model's** (ADR-0045). A model writing `tier: A` for a file-import
   object produces a plan of API calls against something with no write path, and the plan looks
   right.
3. **The tenant's own `$metadata`**, through `SchemaTwin`: required fields present, no unknown
   fields, no orphan picklist references. This is the difference between a plausible record and a
   loadable one, and it checks the model against the substrate rather than against its own memory of
   SuccessFactors.
4. **Provenance is required.** Every value traces to a document section the model read or to a
   resolved decision point. A record with no source is refused, because invariant 2 means the
   platform does not make guesses — it raises decision points.

**A refused proposal is reported, never dropped.** A pass that authored forty records and refused
nine is a more useful report than one that authored thirty-one. Refusals name every gate that failed,
not the first.

**Traceability is proposed, never accepted.** The agent may propose which objects satisfy a
requirement — that is 62 judgements a person would otherwise make by hand — and a person signs it.
ADR-0047's rule is unchanged; what changed is who drafts.

**A token budget the model can see, not a turn cap it cannot.** `consultant.py` uses
`MAX_ITERATIONS = 12`, which is honest for one question and meaningless for a configuration.
`design.py` uses a task budget, plus a separate runaway guard that exists only so a tool erroring on
every call cannot spend the budget arguing with itself — and which says, when it fires, that what it
produced is not a complete design and is not claimed as one.

**`propose_ir` is deliberately not a `strict` tool.** Every other tool is. An IR record carries
`intent`, whose shape is the product's, and `strict` requires a closed schema at every level; a
strict `propose_ir` would reject every real record. The four gates validate it properly.

**The benchmark takes something away.** `jidoka_agent.bench` withholds a register from the pack —
the compiled workbooks, typically — and compares what the pass authors against **configuration real
consultants really built from the same documents**. On the Komatsu pack that is 159 picklist options
derived from an SDD and a BRS: a real exam, marked against work that shipped.

This is allowed to be machine-marked where the K5 exam is not, and the distinction is not a
convenience: the K5 exam asks whether the agent behaved well, and a model marking that is not
governance. The benchmark asks whether the agent reached an answer people already wrote down. There
is a right answer and it is not ours to adjudicate.

**`extra` is never scored as wrong.** A record the pass authored that nobody built is sometimes
invention and sometimes the thing the project forgot. A benchmark punishing it would train the pass
to author less, which is the opposite of what is wanted. Those go to a person, named.

**No single score.** Matched, missed, extra and field-level agreement are reported separately.
A percentage over a benchmark whose `extra` column needs human reading would be quoted as accuracy,
and the first thing anybody would do is optimise it.

## Consequences

- **The sixteen-object exclusion list is withdrawn.** Rule engines, event reason derivations, time
  valuations and data model XML are authoring problems, and this is the authoring surface. What
  survives as permanently human is access we do not have (partner Provisioning), authority the
  platform must not hold (invariant 7), and decisions that are the client's to make (invariant 2).
  Three limits, not sixteen, and none of them is a capability limit.
- **The design pass has never been run against the live API from this repository.** It is tested with
  a scripted client — the loop, all four gates, the request shape and the marking scheme — which is
  why it is testable at all, and which is not the same as proven. `CLAIMS.md` says so.
- The SDK is an optional `live` extra, not a dependency. Running a pass needs it; testing one does
  not, and CI stays hermetic.
- A design pass costs real money — frontier effort over a design pack, hundreds of turns. The cache
  breakpoint sits after the tools and the system prompt, which are identical on every turn of a run;
  getting that wrong is the difference between viable and absurd at a thousand objects.
- `read_metadata` refuses an entity the tenant does not publish and says *do not write a record
  against it*. Before a tenant exists the `$metadata` gate is skipped, and both the pass and the CLI
  say so — a record authored against nobody's tenant is a guess about a product.

## Alternatives rejected

*Let the model post records directly to `/ir`.* The gates are the product. A model with write access
to signed intent is a model that can make unsigned intent loadable by asserting a signature.

*Use the SDK's beta tool runner.* Its documented `pause_turn` behaviour ends the loop silently and
returns a truncated answer as the final message. On a pass authoring hundreds of objects, a silent
truncation is the worst available failure, and the manual loop is twenty lines.

*Score the benchmark as a single accuracy number.* It would be quoted, then optimised, and the way
to optimise it is to author only the objects you are sure of — which is exactly the behaviour that
makes a config platform useless.

*Have the agent approve what it authored.* Invariant 7. Not because it could not, but because the
moment it can, the product is worth less: a J-SOX client will let an agent do all the work precisely
because it cannot sign off on it.

*Summarise the prose into intent with a separate pass.* A summary of a design document is a new
document nobody signed. The pass reads sections whole and cites them as provenance.
