"""Project documents from an engagement's signed state.

Read-only by construction, and gated on `read` rather than a new permission: a document is not a new
kind of access, it is the state the caller could already list, arranged for a human. Anyone who could
not read the engagement cannot read a document about it either.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from jidoka_compiler.project import DOCUMENTS, ProjectionError, render

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/documents", tags=["documents"])


@router.get("")
def catalogue(eid: str, identity: Identity = Depends(require("read"))):
    get_or_404(eid)
    return {"documents": [{"id": k, "title": v} for k, v in sorted(DOCUMENTS.items())]}


@router.get("/{document}")
def project(eid: str, document: str, identity: Identity = Depends(require("read"))):
    """Markdown, not JSON. The document is the artefact; wrapping it in an envelope would only make
    every consumer unwrap it before showing a human."""
    e = get_or_404(eid)
    try:
        return Response(render(e, document), media_type="text/markdown; charset=utf-8")
    except ProjectionError as ex:
        raise HTTPException(404, str(ex))
