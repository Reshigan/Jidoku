"""Metadata harvest: learn a system from its own schema, not from documentation about it.

Everything JIDOKA needs to know about what a configuration *may* be is inside the system as
queryable data. A domain's fixed values are the permitted values. A check table is the permitted
set. A number range object's intervals are the numbers that may be issued. None of this is SAP's
prose about the product; it is the product's own metadata, read through the adapter's existing
read path, and it is a fact about a tenant the client licenses.

That distinction is the whole reason this module exists (DP-K01). Documentation may not be
ingested until that decision is taken. Metadata needs no such gate: a claim formed here cites a
table in a named system, which is a reference an auditor can follow, unlike a page in a manual.

Two kinds of thing come back, and they are not interchangeable:

  STRUCTURE  — this table has this field, of this type, checked against that table. True of the
               product, identical across every tenant on the same release. A candidate for
               system memory, because it carries no client value.
  SETTING    — what this tenant actually put in that field. True of one engagement only, and
               never promotable. Stays in project memory.

The harvester never promotes. It marks candidates; a named human runs the scrubber gate, because
"this is general SAP truth" is exactly the judgement the party proposing it should not be
ratifying (ADR-0010).
"""
from .claim import Claim, evidence_hash

# The metadata entity sets a harvest reads, and what each one is evidence *of*. Keyed by the name
# the adapter's extract() is asked for; the adapter maps that onto the product's real interface,
# which is why this table names no OData path and no ABAP table directly.
STRUCTURE_SOURCES = ("tables", "fields", "domains", "value_help", "check_tables", "tiers")
SETTING_SOURCES = ("img_nodes", "number_ranges", "org_units", "customising")


class HarvestRefused(Exception):
    """The harvester declining to read. Not a failure — a gate holding."""


def _claim(subject, text, system, entity, row, actor):
    """One grounded claim. source_ref names the system and entity so the read is repeatable."""
    return Claim(
        subject=subject,
        text=text,
        # An auditor must be able to go back to the exact read. Naming the system and the entity
        # is what makes staleness a re-read rather than an opinion.
        source_ref=f"harvest:{system.system_id}:{entity}",
        source_hash=evidence_hash(row),
        actor=actor,
        # Metadata is not an inference. The system said this; confidence is not the question.
        # A harvested claim is still UNVERIFIED until re-read, which is the honest status.
        confidence=1.0,
    )


def harvest(adapter, system, store, actor: str, sources=None) -> list[Claim]:
    """Read a system's metadata and form claims into `store`.

    Read-only by construction: the only adapter method called is extract(). A SOURCE_LEGACY or
    TWIN system can therefore be harvested without ever holding a write credential, which is
    invariant 3 holding rather than being checked.
    """
    if getattr(system, "credentials", None) and getattr(system, "role", "") in ("SOURCE_LEGACY", "TWIN"):
        # Invariant 3 is enforced at registration; if one of these ever arrives here holding a
        # credential, the registry has been bypassed and the right move is to stop, not to read.
        raise HarvestRefused(
            f"{system.system_id} is {system.role} and holds credentials — invariant 3 is violated upstream"
        )

    wanted = tuple(sources) if sources else STRUCTURE_SOURCES + SETTING_SOURCES
    formed: list[Claim] = []
    for entity in wanted:
        try:
            rows = adapter.extract(system, entity)
        except Exception:
            # A product without an interface for this entity is the ordinary case, not an error:
            # SuccessFactors has no DDIC and S/4 has no picklists. Skip and keep harvesting.
            # ponytail: bare except is deliberate — every adapter raises its own error type and
            # the only correct response to all of them here is identical.
            continue
        for row in rows or []:
            text = describe(entity, row)
            if not text:
                continue
            formed.append(store.add(_claim(
                subject=f"{system.product}:{entity}", text=text,
                system=system, entity=entity, row=row, actor=actor,
            )))
    return formed


def describe(entity: str, row: dict) -> str:
    """Say what one metadata row means, as a sentence a consultant would recognise.

    Deliberately not a template dump of the row: a claim whose text is a serialised dict is
    unreadable in the console and unfalsifiable in review. If a row does not match a shape this
    knows, it forms no claim — a silent skip is better than a sentence nobody wrote.
    """
    g = row.get
    if entity == "tables" and g("table"):
        return f"{g('table')} holds {g('description') or 'configuration'}" + (
            f", keyed on {g('key')}" if g("key") else "")
    if entity == "fields" and g("table") and g("field"):
        checked = f", checked against {g('check_table')}" if g("check_table") else ""
        length = f" of length {g('length')}" if g("length") else ""
        return f"{g('table')}.{g('field')} is {g('datatype') or 'a field'}{length}{checked}"
    if entity == "domains" and g("domain"):
        vals = g("fixed_values") or []
        if vals:
            return (f"Domain {g('domain')} permits exactly "
                    + ", ".join(str(v) for v in vals[:12])
                    + (f" and {len(vals) - 12} more" if len(vals) > 12 else ""))
        return f"Domain {g('domain')} is {g('datatype') or 'unconstrained'}"
    if entity == "check_tables" and g("field") and g("check_table"):
        return f"{g('field')} may only hold a value present in {g('check_table')}"
    if entity == "value_help" and g("field"):
        return f"{g('field')} offers {g('count') or 'a fixed list of'} permitted values"
    if entity == "img_nodes" and g("node"):
        return (f"IMG node {g('node')}"
                + (f" — {g('title')}" if g("title") else "")
                + (f" configures {g('object')}" if g("object") else ""))
    if entity == "number_ranges" and g("object"):
        return (f"Number range object {g('object')} issues "
                + (f"{g('from')} to {g('to')}" if g("from") else "numbers")
                + (" (buffered)" if g("buffered") else ""))
    if entity == "org_units" and g("unit"):
        return f"{g('type') or 'Org unit'} {g('unit')}" + (f" — {g('name')}" if g("name") else "")
    if entity == "customising" and g("table"):
        return f"{g('table')} is configured with {g('rows')} entries in this system"
    return ""


def resolver(registry: dict):
    """A `harvest:` scheme resolver for staleness.resolve.

    `registry` maps system_id -> (adapter, system). Re-reading through the same adapter is what
    makes a re-harvest a comparison rather than a fresh opinion: the claim named the system and
    the entity, so the exact read that formed it can be run again.

    Note this resolves an *entity*, not a row: the claim's hash is over one row, so a re-read of
    the whole entity would never match. Callers pair this with `row_of` below.
    """
    def read(source_ref: str):
        _, system_id, entity = source_ref.split(":", 2)
        pair = registry.get(system_id)
        if pair is None:
            # Unresolvable, not stale: nobody can see the ground is not the ground moving.
            from .staleness import Unresolvable
            raise Unresolvable(f"no adapter registered for system {system_id}")
        adapter, system = pair
        return adapter.extract(system, entity)
    return read


def row_of(claim, rows) -> dict | None:
    """Find the row a claim was formed from, by hash. None when it is gone from the source.

    Matching on the hash rather than on a key is what lets this work for every entity without
    the harvester knowing any product's key fields. A row that changed at all hashes differently
    and so reads as gone — which is correct: the evidence this claim was formed from no longer
    exists, and sweep() will mark it STALE.
    """
    from .claim import evidence_hash
    return next((r for r in rows or [] if evidence_hash(r) == claim.source_hash), None)


def promotable(claims) -> list:
    """The harvested claims that are candidates for system memory.

    Structure only — a setting is one tenant's choice and can never be general SAP truth. And
    only those whose text the scrubber would actually accept, so the reviewer's queue is claims
    a human could approve rather than claims the gate will refuse anyway.

    This proposes; it does not promote. scrubber.promote still needs a named approver who is not
    the builder, because "this is true of SAP generally" is a judgement, not a read (ADR-0010).
    """
    from .scrubber import screen
    return [c for c in claims
            if c.source_ref.rsplit(":", 1)[-1] in STRUCTURE_SOURCES and not screen(c.text)]


def from_tier_map(adapter, system, store, actor: str) -> list:
    """Learn a product's *shape of change* from the adapter's own honest tier declaration.

    A tier_map is not documentation and not a guess: it is the adapter's binding statement about
    which objects have a write API, which need a human-run file load, and which are transported
    customising nobody may write at all (ADR-0003). That is exactly the fact a consultant needs
    before planning, and it is the fact a manual gets wrong the moment a release ships.

    These are STRUCTURE — true of the product, carrying no client value — so they are the part of
    a harvest most likely to be worth promoting to system memory.
    """
    formed = []
    for obj, tier in sorted((adapter.tier_map() or {}).items()):
        text = TIER_WORDS.get(tier, "").format(obj=obj)
        if not text:
            continue
        formed.append(store.add(_claim(
            subject=f"{system.product}:tiers", text=text, system=system, entity="tiers",
            row={"object": obj, "tier": tier}, actor=actor,
        )))
    return formed


# Said as what the interface permits, not as the tier letter: a claim reading "T001 is tier C" is
# an internal name, and a reviewer approving it into system memory would be approving a token.
TIER_WORDS = {
    "A": "{obj} has a published write API and can be configured by machine",
    "B": "{obj} has no write API and is loaded from a file by a person",
    "C": "{obj} is transported customising with no write path — a person changes it in the system",
}
