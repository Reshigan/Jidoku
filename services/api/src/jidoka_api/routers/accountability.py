"""The platform's account of itself: where it was wrong, and where its gates were friction.

Every other surface reports on the engagement. This one reports on JIDOKA, from the same chain,
and it is deliberately not flattering — a governance tool that publishes only its successes is
asking to be trusted on its own account, which is the thing it exists to stop anyone else doing.

Nothing here is computed for this endpoint. Refusals, clearings, drift after a verification, the
twin's settled predictions: all of it is on the ledger because the platform put it there while
doing the work, and this reads it back.
"""
from fastapi import APIRouter, Depends
from jidoka_core.accountability import account
from jidoka_core.twin import fidelity

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/accountability", tags=["accountability"])


@router.get("")
def accountability(eid: str, identity: Identity = Depends(require("read"))):
    """Read access, not audit access. Somebody deciding whether to trust this platform should not
    need a privileged role to see how often it has been wrong."""
    e = get_or_404(eid)
    return account(e.ledger.entries, fidelity(e.ledger.entries))
