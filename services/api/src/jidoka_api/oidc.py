"""Real OIDC identity: verify an IdP-issued JWT against the provider's JWKS, map its group claims
onto JIDOKA roles.

Three things this module refuses to do, deliberately:
  * accept a token it has not signature-verified (no `alg: none`, no unsigned decode path);
  * accept a symmetric algorithm — an HS256 token presented against an RSA JWKS is the classic
    algorithm-confusion attack, where the attacker signs with the *public* key as the HMAC secret.
    Only RS256/ES256 from the JWKS are allowed, and the key type must match the alg family;
  * grant `approve` to a role set containing `builder`. Invariant 7 says the agent is always
    builder, never approver — so a group map that would hand a builder identity the approve
    permission is refused at CONFIG LOAD, not at request time. A misconfiguration must fail on
    startup, where an operator sees it, not silently on the one request that matters.

Nothing here logs a token, a claim set, or a header. Exceptions carry the reason, never the secret.

Config (env):
  JIDOKA_OIDC_ISSUER     https://login.microsoftonline.com/<tenant>/v2.0
  JIDOKA_OIDC_AUDIENCE   the client/application ID this API is registered as
  JIDOKA_OIDC_JWKS_URL   optional; defaults to <issuer>/.well-known/jwks.json when discovery is off
  JIDOKA_OIDC_GROUP_MAP  JSON object: {"<idp group id or name>": ["builder", ...], ...}
  JIDOKA_OIDC_GROUPS_CLAIM  optional claim name holding the groups (default "groups")
"""
from __future__ import annotations

import json
import os
import threading
import urllib.request
from dataclasses import dataclass, field
from typing import Any

import jwt
from jwt import PyJWKClient

from .auth import ROLE_PERMISSIONS, ROLES, AuthError, Identity

# Asymmetric only. Adding an HS* here would reopen algorithm confusion — don't.
ALLOWED_ALGS = ("RS256", "ES256")
_KTY_FOR_ALG = {"RS256": "RSA", "ES256": "EC"}


class OIDCConfigError(Exception):
    """Raised at config load — a bad mapping must break startup, not a request."""


@dataclass
class OIDCConfig:
    issuer: str
    audience: str
    jwks_url: str
    group_map: dict[str, tuple[str, ...]] = field(default_factory=dict)
    groups_claim: str = "groups"


def _validate_group_map(group_map: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Reject unknown roles, and any grant that would let a builder identity approve (invariant 7)."""
    out: dict[str, tuple[str, ...]] = {}
    for group, roles in group_map.items():
        if isinstance(roles, str):
            roles = [roles]
        if not isinstance(roles, list) or not roles:
            raise OIDCConfigError(
                f"Group {group!r} must map to a non-empty list of roles from {list(ROLES)}."
            )
        for r in roles:
            if r not in ROLES:
                raise OIDCConfigError(f"Group {group!r} maps to unknown role {r!r} — roles are {list(ROLES)}.")
        granted: set[str] = set()
        for r in roles:
            granted |= ROLE_PERMISSIONS[r]
        if "builder" in roles and "approve" in granted:
            raise OIDCConfigError(
                f"Group {group!r} maps to {sorted(roles)}, which grants both builder and approve. "
                "Invariant 7: the builder is never the approver. Split the group."
            )
        out[group] = tuple(roles)
    return out


def load_config(env: dict[str, str] | None = None) -> OIDCConfig | None:
    """Read OIDC config from the environment. Returns None when OIDC is not configured, so the dev
    token path stays available locally. Raises OIDCConfigError on a configured-but-broken setup —
    never falls back to dev tokens because of a typo."""
    env = os.environ if env is None else env
    issuer = (env.get("JIDOKA_OIDC_ISSUER") or "").strip()
    if not issuer:
        return None
    audience = (env.get("JIDOKA_OIDC_AUDIENCE") or "").strip()
    if not audience:
        raise OIDCConfigError("JIDOKA_OIDC_ISSUER is set but JIDOKA_OIDC_AUDIENCE is not — "
                              "a token without an audience check is a token for someone else's API.")
    jwks_url = (env.get("JIDOKA_OIDC_JWKS_URL") or "").strip() or \
        issuer.rstrip("/") + "/.well-known/jwks.json"
    if not jwks_url.startswith("https://"):
        raise OIDCConfigError(f"JWKS must be fetched over HTTPS — refusing {jwks_url!r}.")
    raw = (env.get("JIDOKA_OIDC_GROUP_MAP") or "").strip()
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError as ex:
        raise OIDCConfigError(f"JIDOKA_OIDC_GROUP_MAP is not valid JSON: {ex}.") from None
    if not isinstance(parsed, dict):
        raise OIDCConfigError('JIDOKA_OIDC_GROUP_MAP must be a JSON object: {"<group>": ["builder"]}.')
    return OIDCConfig(
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        group_map=_validate_group_map(parsed),
        groups_claim=(env.get("JIDOKA_OIDC_GROUPS_CLAIM") or "groups").strip(),
    )


class Verifier:
    """Verifies tokens against one provider. PyJWKClient caches keys by `kid` and refetches on an
    unknown kid, which is exactly the rotation behaviour we need — no cache of our own."""

    def __init__(self, config: OIDCConfig, jwks_client: Any | None = None):
        self.config = config
        self._jwks = jwks_client or PyJWKClient(
            config.jwks_url, cache_keys=True, lifespan=3600,
            # ponytail: urllib default opener; PyJWKClient already validates TLS. Swap for a
            # requests session with a proxy/timeout policy if the deployment needs one.
        )
        self._lock = threading.Lock()

    def verify(self, token: str) -> Identity:
        header = self._header(token)
        alg = header.get("alg")
        if alg not in ALLOWED_ALGS:
            # Covers alg:none and every HS* — refused before a key is even looked up.
            raise AuthError(f"Token algorithm {alg!r} is not accepted; expected one of {list(ALLOWED_ALGS)}.")
        kid = header.get("kid")
        if not kid:
            raise AuthError("Token header carries no 'kid' — cannot select a signing key.")
        try:
            with self._lock:
                key = self._jwks.get_signing_key(kid)
        except Exception:
            raise AuthError("Signing key for this token is not published by the identity provider.")
        # Belt and braces against algorithm confusion: an RSA public key must never be handed to an
        # HMAC verifier, and an RS256 header must not be satisfied by an EC key.
        jwk_data = getattr(key, "_jwk_data", None)
        kty = jwk_data.get("kty") if isinstance(jwk_data, dict) else None
        if kty and kty != _KTY_FOR_ALG[alg]:
            raise AuthError(f"Token algorithm {alg} does not match the key type published for this kid.")
        try:
            claims = jwt.decode(
                token,
                key.key,
                algorithms=list(ALLOWED_ALGS),
                audience=self.config.audience,
                issuer=self.config.issuer,
                options={"require": ["exp", "iss", "aud", "sub"],
                         "verify_signature": True, "verify_exp": True, "verify_nbf": True,
                         "verify_iat": True, "verify_aud": True, "verify_iss": True},
            )
        except jwt.ExpiredSignatureError:
            raise AuthError("Token expired — sign in again.")
        except jwt.ImmatureSignatureError:
            raise AuthError("Token is not valid yet (nbf).")
        except jwt.InvalidAudienceError:
            raise AuthError("Token audience does not match this API.")
        except jwt.InvalidIssuerError:
            raise AuthError("Token issuer is not the configured identity provider.")
        except jwt.InvalidTokenError as ex:
            # str(ex) is a PyJWT reason string ("Signature verification failed"), never token content.
            raise AuthError(f"Token rejected: {ex}.")
        return self.to_identity(claims)

    def to_identity(self, claims: dict) -> Identity:
        roles: list[str] = []
        for g in claims.get(self.config.groups_claim) or []:
            for r in self.config.group_map.get(str(g), ()):
                if r not in roles:
                    roles.append(r)
        # `sub` and nothing else. An IdP reassigns preferred_username and email — people marry,
        # change teams, get a new address — and the ledger is permanent: a builder's entries from
        # last quarter must still resolve to that same person after a rename. The readable name
        # travels alongside as `display`, for consoles, never as the identity itself.
        return Identity(
            subject=str(claims["sub"]),
            roles=tuple(roles),
            email=str(claims.get("email") or ""),
            display=str(claims.get("preferred_username") or claims.get("email") or claims["sub"]),
            claims=claims,
        )

    @staticmethod
    def _header(token: str) -> dict:
        try:
            return jwt.get_unverified_header(token)
        except jwt.InvalidTokenError:
            raise AuthError("Malformed token — not a JWT.")


_verifier: Verifier | None = None
_loaded = False
_init_lock = threading.Lock()


def get_verifier() -> Verifier | None:
    """Process-wide verifier, built once. None when OIDC is not configured."""
    global _verifier, _loaded
    with _init_lock:
        if not _loaded:
            config = load_config()
            _verifier = Verifier(config) if config else None
            _loaded = True
        return _verifier


def reset() -> None:
    """Drop the cached verifier — used by tests and after a config change."""
    global _verifier, _loaded
    with _init_lock:
        _verifier, _loaded = None, False


def oidc_configured() -> bool:
    return get_verifier() is not None
