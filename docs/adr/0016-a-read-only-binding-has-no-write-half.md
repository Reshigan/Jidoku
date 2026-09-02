# ADR-0016 — A read-only binding has no write half

Status: Accepted
Date: 2026-09-02
Relates to ADR-0003 (honest tier maps), ADR-0012 (metadata is the primary source), invariants 3 and 6.

## Context

Invariant 3 says SOURCE_LEGACY and TWIN systems cannot hold write credentials. Harvesting a legacy
system's structure (ADR-0012) still needs to *read* one, so `connectors.build_reader` exists to bind
a reader to a system `connectors.build` would refuse.

It was implemented by building the ordinary write-capable connector and then overwriting one
attribute:

```python
c = _mock(system_id)          # or _live(...)
c.apply = refuse
c.kind = f"{c.kind}-read"
return c
```

That is a refusal on one door of a building with several. The connector object carries more than
`apply`: `_mock` hangs the `MockSAP` instance on `c.mock`, and a live binding's client is reachable
through every closure the object retains. Anything holding the "read-only" connector could reach the
substrate around the refusal. A test asserting `not hasattr(c, "mock")` failed on the first run —
this was not hypothetical.

Nothing in the current code walked that path. That is exactly the argument invariant 3 exists to
reject: a credential that is only unreachable by convention is a credential the next caller reaches.

## Decision

A reader is a **different, smaller object**, not a write-capable one with a method replaced:

```python
return Connector(f"{c.kind}-read", c.fetch, refuse, c.describe, metadata_xml=c.metadata_xml)
```

Only the halves that read cross over — `fetch`, `describe`, `metadata_xml`. The write path is not
refused; it is absent. `apply` remains present and raising so a caller that tries gets a legible
error rather than an `AttributeError`, but there is no object graph behind it to reach.

## Consequences

- Invariant 3 holds by the shape of the object rather than by a caller remembering not to look.
- Adding an attribute to `Connector` does not silently widen a reader: it crosses over only if it is
  named in the constructor call above, which is a deliberate edit.
- `registry.get()` still runs first: an unregistered system has no binding of any kind.
- Regression test: `services/api/tests/test_connectors.py::test_a_read_only_binding_has_no_reachable_write_path`
  enumerates the write-bearing attribute names and asserts none survive.
