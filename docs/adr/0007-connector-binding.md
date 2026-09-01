# ADR-0007: A connector is a write credential, so binding one is a deliberate, ledgered act
Status: accepted. Touches invariants 3, 4, 6.

Context: a registered system had no way to reach the product it named. `_adapter_for` built every adapter
with no arguments, so no adapter had a reader. The symptom was a 409 on snapshot ("No fetcher configured")
with no endpoint through which a reader could ever be supplied — and since invariant 4 requires a
before-snapshot on the chain, no live write was reachable for any product. The platform could build payloads
and rehearse them, and nothing else.

Decision: a system gains a reader and a writer only through an explicit `POST /execution/connector`, in one
of two kinds — `mock` (in-process fake SAP) or `live` (a real tenant). A connector *is* a write credential,
and three things follow. (1) Invariant 3 is enforced at bind time as well as arm time: `build()` calls
`registry.assert_writable(system_id)` before constructing anything, because binding a connector to a
SOURCE_LEGACY or TWIN system would put a write path exactly where the registry says none may exist. Binding
is the earlier moment and the earlier refusal is the kinder one. (2) Credentials never travel in the request
body — a live binding carries a `base_url` and a `secret_env`, the *name* of an environment variable prefix,
and the process reads the secret from its own environment. A secret therefore cannot be logged by the HTTP
layer, echoed in a 4xx, or persisted beside the engagement; missing credentials are reported by variable name
only, and `Connector.__repr__` prints kind and description, never the client. (3) Connectors are not
persisted, like `_ARMED`: a restart unbinds every write path rather than reloading one nobody re-authorised.

Consequences: an unbound system is inert by default — the platform may rehearse against it but cannot read or
write it — and the Configure screen says so in place of a status badge, because unbound is more fundamental
than unarmed: with no reader there is no before-state, so there is no live write to be armed for. Binding
appends `CONNECTOR_BOUND`, so the chain records when a system became writable and who made it so. Invariant 6
is unchanged but now actually reachable: the adapter still defaults `dry_run=True`, the executor flips it only
for an armed target, and the mock's apply raises if handed a payload with `dry_run` still true, since a True
there means a gate was skipped upstream.

Evidence: `services/api/tests/test_execution_api.py` — `test_binding_a_connector_to_a_twin_is_refused`,
`test_binding_a_system_without_write_credentials_is_refused`,
`test_live_binding_refuses_when_the_credential_is_not_in_the_environment`,
`test_unknown_connector_kind_is_refused_rather_than_guessed`, `test_binding_is_ledgered`, and the end-to-end
`test_bound_system_can_snapshot_and_a_second_person_can_write_it_live`.
