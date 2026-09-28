"""Adapter contract: every SAP product implements exactly this surface.
The tier_map is the honest declaration of what the product's interfaces permit."""
from abc import ABC, abstractmethod


class AdapterError(Exception):
    """An adapter refusing to act, as distinct from an adapter breaking.

    Raised when the IR asks for something the product's interfaces cannot honestly deliver — a
    tier-A object with no declared entity set, a payload the substrate would reject. Every product's
    error type inherits this so the API can map refusals to 422 once, rather than growing an
    `except` clause per adapter and returning a 500 the first time somebody adds a new one.
    """


class Adapter(ABC):
    product: str = "?"

    @abstractmethod
    def tier_map(self) -> dict: ...

    def write_target(self, entity: str) -> str | None:
        """The named thing this adapter writes `entity` through — an entity set, a service — or
        None where the product publishes no write path. A Tier-A entity without one is a tier map
        that lies, and `audit_tier_map` says so before anybody tries to spend it."""
        return None

    def unverifiable(self) -> dict:
        """entity -> why this adapter cannot read it back, for the entities it cannot.

        ADR-0003 makes Tier B and C honest by pairing a human instruction sheet with an
        extract-diff: a person does the work and JIDOKA confirms it. That bargain needs a read
        path. Some objects have none — an SF Provisioning switch, an S/4 IMG table with no
        published service — and for those the platform must say so rather than wait forever for a
        confirmation it can never make (ADR-0022). Declaring the gap is the honest move; hiding it
        turns an unconfirmable change into one that merely looks outstanding.
        """
        return {}

    def verifiable(self, entity: str) -> bool:
        return entity not in self.unverifiable()

    #: Where this product keeps its own record of who changed what, if it keeps one, and what it
    #: is called. Declared rather than assumed: an adapter that cannot read one must say so, or a
    #: reconciliation finding nothing reads as "nothing happened outside the platform" when it
    #: means "I cannot see" (ADR-0044).
    change_log_entity: str | None = None

    def change_log(self, system, since: str = "") -> list[dict] | None:
        """The product's own change log, normalised to `{object, changed_by, ts, detail}`.

        None where the product publishes no readable log. Every product spells this differently —
        SuccessFactors has Change Audit, S/4 has change documents — so the translation belongs
        here, with the product, and never in the reconciliation.
        """
        return None

    def cannot_read_changes(self) -> str:
        """Why not, for an adapter that returns None. Printed where the answer would otherwise be
        an empty list that reads like a clean bill of health."""
        return (f"{self.product}: this adapter reads no change log, so it cannot tell a system "
                f"nobody touched from one it cannot see into.")
    @abstractmethod
    def extract(self, system, entity: str) -> list[dict]: ...
    @abstractmethod
    def build_apply(self, ir_record) -> dict:
        """Tier A -> API payload; Tier B -> file artefact; Tier C -> human instruction sheet."""
    @abstractmethod
    def verify(self, ir_record, live_state: list[dict]) -> dict: ...


def audit_tier_map(adapter: Adapter) -> dict:
    """What an adapter's own declaration admits about itself.

    Two findings, and they are not the same kind of thing:

    `lying` — Tier A with no write target. The adapter claims the product publishes a write path
    and cannot name it, so an armed step against it would fail at the substrate with a live
    target already armed. This is a defect in the map.

    `unconfirmable` — Tier B or C the adapter cannot read back. Not a defect: the product really
    does keep that object behind a UI with no read API. It is a limit, and it has to be visible,
    because the platform's promise for Tier B and C is that a person does the work and JIDOKA
    checks it (ADR-0003). Where it cannot check, somebody has to attest instead.
    """
    tiers = adapter.tier_map()
    unverifiable = adapter.unverifiable()
    return {
        "product": adapter.product,
        "lying": sorted(e for e, tier in tiers.items()
                        if tier == "A" and not adapter.write_target(e)),
        "unconfirmable": {e: unverifiable[e] for e in sorted(unverifiable) if e in tiers},
        "counts": {t: sum(1 for x in tiers.values() if x == t) for t in "ABC"},
    }


def audit_tenant(adapter: "Adapter", entity_sets: dict[str, dict]) -> dict:
    """What one tenant's own `$metadata` says about the adapter's tier map.

    `audit_tier_map` asks whether the map is honest against itself. This asks whether it is true
    *here*. The two differ because a product's write surface is a property of the tenant: SF creates
    an entity set per MDF object definition, so Tier-A coverage varies by customer, and a static map
    can only ever be a statement about the product's shipped defaults.

    Reports; never edits. Whether a published entity set is something the platform should write is
    the adapter's call and then a person's — `$metadata` says what a tenant publishes, and an
    entity set can be published and read-only.

      not_published        tier A, write target not on this tenant — the claim is false here
      not_writable         published, and the tenant says it is not upsertable
      writability_unknown  published, no write annotation — unconfirmed, and never assumed writable
      uncatalogued         published on the tenant and in no tier map; `candidates` are the ones the
                           tenant itself marks upsertable
    """
    tiers = adapter.tier_map()
    targets = {e: adapter.write_target(e) for e, t in tiers.items() if t == "A"}
    catalogued = {t for t in targets.values() if t}

    not_published = sorted(e for e, t in targets.items() if t and t not in entity_sets)
    not_writable, unknown = [], []
    for entity, target in sorted(targets.items()):
        row = entity_sets.get(target or "")
        if row is None:
            continue
        if row.get("upsertable") is False:
            not_writable.append(entity)
        elif row.get("upsertable") is None:
            unknown.append(entity)

    extra = {n: r for n, r in entity_sets.items() if n not in catalogued}
    candidates = sorted(n for n, r in extra.items() if r.get("upsertable") is True)
    confirmed = len(targets) - len(not_published) - len(not_writable) - len(unknown)
    return {
        "product": adapter.product,
        "tier_a_claimed": len(targets),
        "tier_a_confirmed_writable": confirmed,
        "not_published": not_published,
        "not_writable": not_writable,
        "writability_unknown": unknown,
        "uncatalogued": sorted(extra),
        "candidates": candidates,
        "says": _tenant_says(len(targets), confirmed, not_published, not_writable, unknown,
                             extra, candidates),
    }


def _tenant_says(claimed, confirmed, missing, readonly, unknown, extra, candidates) -> str:
    parts = [f"{confirmed} of {claimed} tier-A objects are confirmed writable on this tenant"]
    if missing:
        parts.append(f"{len(missing)} are not published by it at all: {', '.join(missing[:6])}"
                     + ("…" if len(missing) > 6 else "") + " — the tier-A claim is false here")
    if readonly:
        parts.append(f"{len(readonly)} are published and marked not upsertable")
    if unknown:
        parts.append(f"{len(unknown)} are published with no write annotation, so whether they can "
                     f"be written is unconfirmed rather than assumed")
    if extra:
        parts.append(f"{len(extra)} entity set(s) are on the tenant and in no tier map"
                     + (f", {len(candidates)} of which it marks upsertable" if candidates else ""))
    return ". ".join(parts) + "."
