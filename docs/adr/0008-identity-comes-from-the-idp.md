# ADR-0008: Identity comes from the IdP, roles come from its groups, and the ledger is anchored on `sub`
Status: accepted. Touches invariants 4, 5, 7.

Context: separation of duties is the property this platform sells. Invariant 4 needs reviewer != builder,
invariant 5 needs two distinct named approvers for a ONE_WAY decision, invariant 7 says the agent is never an
approver. All three are assertions about *who* — and all three are worthless if the deployment mints its own
identities. A locally-signed dev token means anyone holding the signing secret can mint an approver, and the
default secret means anyone at all can.

Decision: when `JIDOKA_OIDC_*` is configured, OIDC is the only accepted path. `authenticate()` does not fall
back to the local HMAC verifier, because a fallback *is* a bypass: the weaker path is the one an attacker
picks. Configuring an issuer turns authentication on by itself — a real IdP is never a dev deployment — and
`auth_router` refuses to mint local tokens at all while it is on, so the dev endpoint cannot become a
credential path in a real tenant. Roles are never self-asserted in a token claim the user controls; they are
derived from IdP group membership through `JIDOKA_OIDC_GROUP_MAP`, so granting someone approver is an act
performed in the customer's directory, by whoever administers it, with that system's own audit trail. The
map is validated at load: an unknown role name is a startup failure, not a silently ignored line.

The ledger subject is the IdP's `sub` and nothing else. This is the correction to an earlier draft that
preferred `preferred_username` or `email` because they read better. Both are mutable — people marry, change
teams, get a new address — and the ledger is permanent: a builder's entries from last quarter must still
resolve to that same person after a rename, and two people must never collide because one inherited the
other's freed-up username. The readable name travels alongside as `Identity.display`, which consoles and
refusal messages use; it is never the anchor. Every `ledger.append` call site passes `identity.subject`.

Consequences: a customer's joiner/mover/leaver process becomes JIDOKA's, at no cost — revoking a group
revokes the permission at the next token. Ledger entries name an opaque identifier rather than a person, so
any human-facing rendering must resolve `sub` to a name through the IdP or a local directory; that is the
right trade, since the alternative is a record that quietly rewrites who did what.

Evidence: `services/api/tests/test_oidc.py` — `test_valid_token_is_accepted_and_anchors_the_subject_on_sub`,
`test_a_renamed_user_keeps_the_same_ledger_subject`, `test_display_falls_back_to_sub_when_the_idp_sends_no_name`,
plus the signature/issuer/audience/expiry rejection cases and the group-map validation tests. The
role-separation asserts in `auth.py` run at import, so a deployment that grants `approve` to builders cannot
start.
