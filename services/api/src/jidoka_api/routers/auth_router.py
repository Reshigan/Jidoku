"""Local sign-in for the console.

Production mints tokens at the OIDC provider, not here; this route exists so a development
console can obtain the same claim shape without standing one up. It refuses to run once auth
is mandatory, so it cannot become a credential bypass in a real tenant.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..auth import ROLES, AuthError, auth_enabled, issue_token

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenIn(BaseModel):
    subject: str
    roles: list[str]
    email: str = ""


@router.post("/token")
def token(body: TokenIn):
    if auth_enabled():
        raise HTTPException(
            403,
            "Local token issue is disabled because authentication is mandatory here. "
            "Sign in through the identity provider.",
        )
    if not body.subject.strip():
        raise HTTPException(422, "A token must name a person — the ledger records the subject verbatim.")
    try:
        return {"token": issue_token(body.subject.strip(), body.roles, email=body.email),
                "subject": body.subject.strip(), "roles": body.roles}
    except AuthError as ex:
        raise HTTPException(422, str(ex))


@router.get("/roles")
def roles():
    return {"roles": list(ROLES)}
