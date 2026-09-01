"""OIDC verification, offline. A locally generated RSA keypair stands in for the IdP's JWKS, so
these tests never touch the network.

Attacks covered: expiry, audience substitution, issuer substitution, alg:none, unknown signing key,
HMAC-signed token against an RSA JWKS (algorithm confusion), and a group map that would grant an
agent identity the approve permission.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jidoka_api import auth, oidc
from jidoka_api.auth import ROLE_PERMISSIONS, AuthError
from jidoka_api.main import app
from jidoka_api.oidc import OIDCConfig, OIDCConfigError, Verifier, load_config

ISSUER = "https://login.example.com/tenant/v2.0"
AUDIENCE = "api://jidoka"
KID = "test-key-1"

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeJWK:
    def __init__(self, key, kty="RSA"):
        self.key = key
        self._jwk_data = {"kty": kty, "kid": KID}


class _FakeJWKClient:
    """Stands in for PyJWKClient: publishes exactly one key, under KID."""

    def __init__(self, key=None, kty="RSA"):
        self._jwk = _FakeJWK(key if key is not None else _KEY.public_key(), kty)

    def get_signing_key(self, kid):
        if kid != KID:
            raise Exception("kid not found")  # PyJWKClient raises PyJWKClientError here
        return self._jwk


def _config(**over) -> OIDCConfig:
    base = dict(issuer=ISSUER, audience=AUDIENCE, jwks_url="https://login.example.com/jwks",
                group_map={"grp-build": ("builder",), "grp-appr": ("approver",),
                           "grp-audit": ("auditor", "reviewer")})
    base.update(over)
    return OIDCConfig(**base)


def _verifier(**over) -> Verifier:
    return Verifier(_config(**over), jwks_client=_FakeJWKClient())


def _token(key=_KEY, alg="RS256", kid=KID, **over) -> str:
    now = int(time.time())
    claims = {"sub": "u-1", "iss": ISSUER, "aud": AUDIENCE, "exp": now + 600, "iat": now,
              "nbf": now - 10, "email": "ada@example.com", "groups": ["grp-build"]}
    claims.update(over)
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": kid})


# --- happy path ---------------------------------------------------------------------------------
def test_valid_token_is_accepted_and_anchors_the_subject_on_sub():
    """The ledger is permanent, so identity is anchored on the one claim an IdP will not reassign."""
    ident = _verifier().verify(_token(preferred_username="ada"))
    assert ident.subject == "u-1"
    assert ident.display == "ada"               # the readable name travels alongside, never instead
    assert ident.roles == ("builder",)


def test_a_renamed_user_keeps_the_same_ledger_subject():
    """Someone changes their username or email at the IdP. Their prior ledger entries must still be
    theirs — which is exactly what anchoring on a mutable claim would break."""
    before = _verifier().verify(_token(preferred_username="ada", email="ada@example.com"))
    after = _verifier().verify(_token(preferred_username="ada.lovelace", email="ada.l@example.com"))
    assert before.subject == after.subject == "u-1"
    assert before.display != after.display


def test_display_falls_back_to_sub_when_the_idp_sends_no_name():
    ident = _verifier().verify(_token(email=None, groups=["grp-build"]))
    assert ident.subject == "u-1" and ident.display == "u-1"


# --- rejections ---------------------------------------------------------------------------------
def test_expired_token_is_rejected():
    now = int(time.time())
    with pytest.raises(AuthError, match="expired"):
        _verifier().verify(_token(exp=now - 60, iat=now - 600, nbf=now - 600))


def test_not_yet_valid_token_is_rejected():
    now = int(time.time())
    with pytest.raises(AuthError, match="not valid yet"):
        _verifier().verify(_token(nbf=now + 300, iat=now))


def test_wrong_audience_is_rejected():
    with pytest.raises(AuthError, match="audience"):
        _verifier().verify(_token(aud="api://someone-elses-api"))


def test_wrong_issuer_is_rejected():
    with pytest.raises(AuthError, match="issuer"):
        _verifier().verify(_token(iss="https://evil.example.com/"))


def test_alg_none_is_rejected():
    """The unsigned-token attack. jwt.encode(algorithm='none') produces a token with an empty
    signature; we must refuse on the header alone, before any key lookup."""
    now = int(time.time())
    claims = {"sub": "attacker", "iss": ISSUER, "aud": AUDIENCE, "exp": now + 600,
              "groups": ["grp-appr"]}
    token = jwt.encode(claims, key=None, algorithm="none", headers={"kid": KID})
    with pytest.raises(AuthError, match="algorithm"):
        _verifier().verify(token)


def test_token_signed_by_unknown_key_is_rejected():
    """Right kid, wrong private key — signature must fail against the published public key."""
    with pytest.raises(AuthError, match="[Ss]ignature|rejected"):
        _verifier().verify(_token(key=_OTHER_KEY))


def test_token_with_unknown_kid_is_rejected():
    with pytest.raises(AuthError, match="not published"):
        _verifier().verify(_token(kid="rotated-away"))


def test_hmac_token_against_rsa_jwks_is_rejected():
    """Algorithm confusion: the attacker HMACs the token using the RSA *public* key as the shared
    secret and claims alg HS256. Only asymmetric algs are allowed, so this dies on the header."""
    pub_pem = _KEY.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    now = int(time.time())
    # PyJWT refuses to *encode* HS256 with a PEM key, so forge it by hand — the attacker has no
    # such scruples, and the point is that OUR verifier refuses it.
    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    head = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": KID}).encode())
    body = b64(json.dumps({"sub": "attacker", "iss": ISSUER, "aud": AUDIENCE,
                           "exp": now + 600, "groups": ["grp-appr"]}).encode())
    sig = b64(hmac.new(pub_pem, f"{head}.{body}".encode(), hashlib.sha256).digest())
    forged = f"{head}.{body}.{sig}"
    assert jwt.get_unverified_header(forged)["alg"] == "HS256"   # the attack is well-formed
    with pytest.raises(AuthError, match="algorithm"):
        _verifier().verify(forged)


def test_key_type_must_match_the_algorithm():
    """An RS256 header satisfied by an EC key would be a downgrade; the kty check refuses it."""
    v = Verifier(_config(), jwks_client=_FakeJWKClient(kty="EC"))
    with pytest.raises(AuthError, match="does not match the key type"):
        v.verify(_token())


def test_garbage_is_not_a_jwt():
    with pytest.raises(AuthError, match="Malformed"):
        _verifier().verify("not-a-token")


def test_token_without_kid_is_rejected():
    now = int(time.time())
    t = jwt.encode({"sub": "u", "iss": ISSUER, "aud": AUDIENCE, "exp": now + 600},
                   _KEY, algorithm="RS256")
    with pytest.raises(AuthError, match="kid"):
        _verifier().verify(t)


# --- group mapping ------------------------------------------------------------------------------
def test_group_mapping_produces_roles():
    ident = _verifier().verify(_token(groups=["grp-audit", "grp-appr"]))
    assert set(ident.roles) == {"auditor", "reviewer", "approver"}
    assert ident.may("approve") and ident.may("export_evidence")


def test_unmapped_group_grants_nothing():
    ident = _verifier().verify(_token(groups=["grp-random"]))
    assert ident.roles == () and not ident.may("read")


def test_groups_claim_name_is_configurable():
    v = Verifier(_config(groups_claim="roles"), jwks_client=_FakeJWKClient())
    ident = v.verify(_token(groups=["grp-appr"], roles=["grp-build"]))
    assert ident.roles == ("builder",)   # read from "roles", not "groups"


# --- invariant 7 --------------------------------------------------------------------------------
def test_builder_never_holds_approve():
    assert "approve" not in ROLE_PERMISSIONS["builder"]


def test_group_map_granting_builder_and_approve_is_refused_at_load():
    env = {"JIDOKA_OIDC_ISSUER": ISSUER, "JIDOKA_OIDC_AUDIENCE": AUDIENCE,
           "JIDOKA_OIDC_GROUP_MAP": json.dumps({"grp-agent": ["builder", "approver"]})}
    with pytest.raises(OIDCConfigError, match="[Ii]nvariant 7"):
        load_config(env)


def test_group_map_with_unknown_role_is_refused_at_load():
    env = {"JIDOKA_OIDC_ISSUER": ISSUER, "JIDOKA_OIDC_AUDIENCE": AUDIENCE,
           "JIDOKA_OIDC_GROUP_MAP": json.dumps({"grp": ["superuser"]})}
    with pytest.raises(OIDCConfigError, match="unknown role"):
        load_config(env)


# --- config loading -----------------------------------------------------------------------------
def test_no_issuer_means_oidc_is_not_configured():
    assert load_config({}) is None


def test_issuer_without_audience_is_refused():
    with pytest.raises(OIDCConfigError, match="AUDIENCE"):
        load_config({"JIDOKA_OIDC_ISSUER": ISSUER})


def test_jwks_url_defaults_from_issuer_and_must_be_https():
    cfg = load_config({"JIDOKA_OIDC_ISSUER": ISSUER, "JIDOKA_OIDC_AUDIENCE": AUDIENCE})
    assert cfg.jwks_url == ISSUER + "/.well-known/jwks.json"
    with pytest.raises(OIDCConfigError, match="HTTPS"):
        load_config({"JIDOKA_OIDC_ISSUER": "http://insecure.example.com",
                     "JIDOKA_OIDC_AUDIENCE": AUDIENCE,
                     "JIDOKA_OIDC_JWKS_URL": "http://insecure.example.com/jwks"})


def test_malformed_group_map_json_is_refused():
    with pytest.raises(OIDCConfigError, match="valid JSON"):
        load_config({"JIDOKA_OIDC_ISSUER": ISSUER, "JIDOKA_OIDC_AUDIENCE": AUDIENCE,
                     "JIDOKA_OIDC_GROUP_MAP": "{not json"})


# --- wiring into auth.py ------------------------------------------------------------------------
@pytest.fixture
def oidc_active(monkeypatch):
    """Install a verifier backed by the local keypair, as if OIDC were configured."""
    v = _verifier()
    monkeypatch.setattr(oidc, "_verifier", v)
    monkeypatch.setattr(oidc, "_loaded", True)
    yield v
    oidc.reset()


def test_dev_hmac_token_is_impossible_once_oidc_is_configured(oidc_active):
    """The dev path is not a fallback — a valid HMAC dev token must be refused outright."""
    dev = auth.issue_token("mallory", ("approver",))
    with pytest.raises(AuthError):
        auth.authenticate(dev)


def test_oidc_token_populates_identity_through_authenticate(oidc_active):
    ident = auth.authenticate(_token(groups=["grp-appr"]))
    assert ident.roles == ("approver",) and ident.may("approve")


def test_configuring_oidc_enables_auth_and_disables_local_token_issue(oidc_active):
    assert auth.auth_enabled() is True
    r = TestClient(app).post("/auth/token", json={"subject": "mallory", "roles": ["approver"]})
    assert r.status_code == 403


def test_dev_token_still_works_when_oidc_is_not_configured(monkeypatch):
    monkeypatch.delenv("JIDOKA_AUTH", raising=False)
    oidc.reset()
    assert auth.auth_enabled() is False
    ident = auth.authenticate(auth.issue_token("ada", ("builder",)))
    assert ident.subject == "ada" and ident.roles == ("builder",)


def test_no_token_material_appears_in_error_messages():
    """Nothing we raise may echo the credential back into a log."""
    token = _token(aud="wrong")
    try:
        _verifier().verify(token)
    except AuthError as ex:
        msg = str(ex)
        assert token not in msg and token.split(".")[1] not in msg
    else:
        pytest.fail("expected rejection")
