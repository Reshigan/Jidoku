"""AuthN/Z: OIDC-compatible bearer identity + roles, with SoD enforced SERVER-side (E2).

Two things matter here and they are separate:
  authentication — who is calling. A bearer token, verified. In dev, a signed local token; in
                   production, an OIDC ID token whose claims are mapped onto the same Identity.
  authorization  — what that role may do. The role table below is the ceiling; a request may need
                   less authority than the role holds, never more.

SoD is NOT expressed here as "the approver role may approve". It is enforced against the LEDGER at
the moment of approval (jidoka_core.ledger.approve: reviewer != builder), because separation of
duties is a property of the history, not of the caller's badge. This module only ensures an approval
attempt carries a named, authenticated human — the ledger decides whether that human is allowed.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass, field

from fastapi import Depends, Header, HTTPException

ROLES = ("builder", "reviewer", "approver", "auditor")

# What each role may attempt. The agent runs as `builder` — note that no path grants it approve,
# mirroring invariant 7 at the transport layer as well as in the OS capability table.
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "builder": {"read", "write_ir", "plan", "ledger_append", "raise_dp", "register_system", "halt",
                "snapshot", "execute", "transport"},
    "reviewer": {"read", "ledger_append", "raise_dp", "halt"},
    "approver": {"read", "approve", "resolve_dp", "halt", "arm"},
    "auditor": {"read", "export_evidence", "halt"},
}

assert "approve" not in ROLE_PERMISSIONS["builder"], "invariant 7: builders never approve"
# Invariant 6: the role that executes a write is never the role that arms it for live.
assert "arm" not in ROLE_PERMISSIONS["builder"], "invariant 6: builders never arm their own write"
assert "execute" not in ROLE_PERMISSIONS["approver"], "invariant 7: approvers never execute"


class AuthError(Exception): ...


@dataclass
class Identity:
    subject: str                       # stable IdP `sub` — appears in the ledger verbatim, forever
    roles: tuple[str, ...] = ()
    email: str = ""
    display: str = ""                  # readable name for consoles; mutable, so never the anchor
    claims: dict = field(default_factory=dict)

    def permissions(self) -> set[str]:
        out: set[str] = set()
        for r in self.roles:
            out |= ROLE_PERMISSIONS.get(r, set())
        return out

    def may(self, permission: str) -> bool:
        return permission in self.permissions()


def _secret() -> bytes:
    """Dev-token signing key. Absent in production, where OIDC verification replaces local tokens."""
    return os.environ.get("JIDOKA_AUTH_SECRET", "jidoka-dev-secret").encode()


def _b64e(raw: bytes) -> str:
    return urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(txt: str) -> bytes:
    return urlsafe_b64decode(txt + "=" * (-len(txt) % 4))


def issue_token(subject: str, roles: tuple[str, ...] | list[str], ttl_seconds: int = 3600,
                email: str = "") -> str:
    """Mint a local dev token. Same claim shape as the OIDC ID token we accept in production, so the
    downstream code path is identical in both modes."""
    for r in roles:
        if r not in ROLES:
            raise AuthError(f"Unknown role {r!r} — roles are {list(ROLES)}.")
    payload = {"sub": subject, "roles": list(roles), "email": email,
               "exp": int(time.time()) + ttl_seconds, "iat": int(time.time())}
    body = _b64e(json.dumps(payload, sort_keys=True).encode())
    sig = _b64e(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str) -> Identity:
    try:
        body, sig = token.split(".")
    except ValueError:
        raise AuthError("Malformed token — expected <payload>.<signature>.")
    expected = _b64e(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise AuthError("Token signature does not verify.")
    claims = json.loads(_b64d(body))
    if claims.get("exp", 0) < time.time():
        raise AuthError("Token expired — sign in again.")
    roles = tuple(r for r in claims.get("roles", []) if r in ROLES)
    # Dev tokens carry the operator's own name as `sub`, so it is both anchor and display.
    return Identity(subject=claims["sub"], roles=roles, email=claims.get("email", ""),
                    display=claims["sub"], claims=claims)


def _oidc_verifier():
    """Late import: oidc imports this module, and OIDC is optional at runtime."""
    from .oidc import get_verifier

    return get_verifier()


def auth_enabled() -> bool:
    """Auth is opt-in for local development and mandatory anywhere a real tenant is bound.
    Configuring OIDC turns it on by itself — a real IdP is never a dev deployment.
    ponytail: one env flag rather than a config system — flip JIDOKA_AUTH=required in deployment."""
    if os.environ.get("JIDOKA_AUTH", "optional").lower() == "required":
        return True
    return _oidc_verifier() is not None


def authenticate(token: str) -> Identity:
    """Verify a bearer token. When OIDC is configured it is the ONLY accepted path — the local HMAC
    token is not a fallback, because a fallback is a bypass: anyone holding the dev secret (or the
    default one) could otherwise mint an approver."""
    verifier = _oidc_verifier()
    if verifier is not None:
        return verifier.verify(token)
    return verify_token(token)


ANONYMOUS = Identity(subject="anonymous", roles=("builder", "reviewer", "approver", "auditor"))


def current_identity(authorization: str | None = Header(default=None)) -> Identity:
    """FastAPI dependency. With auth optional (dev), an unauthenticated call runs as ANONYMOUS so the
    console and tests work out of the box; with auth required, a missing or bad token is a 401."""
    if not authorization:
        if auth_enabled():
            raise HTTPException(401, "Authentication required — present a bearer token.")
        return ANONYMOUS
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Expected 'Authorization: Bearer <token>'.")
    try:
        return authenticate(token)
    except AuthError as ex:
        raise HTTPException(401, str(ex))


def require(permission: str):
    """Dependency factory: gate a route on one permission, refusing with the rule and the way forward."""

    def _dep(identity: Identity = Depends(current_identity)) -> Identity:
        if not identity.may(permission):
            raise HTTPException(
                403,
                # A refusal is read by a person, so name them the way they know themselves.
                f"{identity.display or identity.subject} holds roles {list(identity.roles) or ['none']} and may not "
                f"'{permission}'. Ask someone holding a role that grants it.",
            )
        return identity

    return _dep
