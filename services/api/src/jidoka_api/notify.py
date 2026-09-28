"""Where an interruption actually goes.

The night shift ranks every finding by what it costs to stay unsaid, spends a hard interruption
budget, picks the cheapest sufficient authority, checks their working hours in their own named
timezone, respects the capacity their organisation declared and reports how fast they answer — and
then put the result in a dictionary. `people.py` says so in its own docstring: *nothing here sends
anything, and nothing here knows what a notification is.* Every piece upstream of a sink was built
and tested, and without the sink "I woke somebody three times" was not a true sentence.

This is the sink, and it is deliberately one thing: an HTTP POST to a URL somebody configured.
Slack, Teams, Opsgenie, PagerDuty and a script on a box all accept one, so a webhook is the whole
integration surface rather than three SDKs and their transitive dependencies.

Three rules it does not bend:

  **Only what the budget spent.** `interrupted` is sent; `deferred` and `waited` are not. The
  budget is the product — a colleague who talks less than they could is trusted more — and a sink
  that sent everything would quietly undo it.

  **The payload leaves the tenant, so it carries the least that is useful.** Who is being asked,
  what for, what it costs to stay quiet, and where to look. No ledger hashes, no configured
  values, no evidence. A notification is a tap on the shoulder, not an export.

  **Failing to send never fails the night.** The handover is on the ledger either way, and a
  webhook that is down is a reason to lose a notification, not a reason to lose the night's work.
  Every attempt is recorded, so a sink that has been silently failing is visible rather than
  assumed to be working.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

#: Where to post. Absent, nothing is sent and the night says so rather than pretending.
URL_ENV = "JIDOKA_NOTIFY_URL"

#: The ledger action. Recorded whether the send worked or not: a sink nobody can see failing is a
#: sink everybody assumes is working.
NOTIFIED = "NOTIFIED"

TIMEOUT = 10


def configured() -> bool:
    return bool(os.environ.get(URL_ENV, "").strip())


def payload(engagement: str, client: str, finding: dict) -> dict:
    """The least that is useful. See the module docstring on why it is not more."""
    return {"engagement": engagement, "client": client,
            "who": finding.get("who", ""), "what": finding.get("what", ""),
            "cost_of_silence": finding.get("cost", 0),
            "why_you": finding.get("why", ""),
            "text": (f"{finding.get('who') or 'Somebody'} — {client}, {engagement}: "
                     f"{finding.get('what', '')}")}


def post(body: dict) -> tuple[bool, str]:
    """One POST. Returns (sent, reason). The URL is read here and nowhere else, and never
    returned, logged or raised — a webhook URL is a credential in every practical sense."""
    url = os.environ.get(URL_ENV, "").strip()
    if not url:
        return False, "no sink configured"
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            ok = 200 <= resp.status < 300
            return ok, f"HTTP {resp.status}"
    except urllib.error.HTTPError as ex:
        return False, f"HTTP {ex.code}"
    except Exception as ex:                  # noqa: BLE001 — the class, never the message: a URL
        return False, type(ex).__name__      # in an exception string is the credential leaking


def send_interruptions(e, night: dict, actor: str) -> dict:
    """Send what the budget actually spent, and put every attempt on the chain.

    Nothing here raises. A night that lost its work because a webhook was down would be a night
    that traded the thing it is for the thing that announces it.
    """
    sent, failed = [], []
    for finding in night.get("interrupted", []):
        ok, why = post(payload(e.name, e.client, finding))
        (sent if ok else failed).append(finding.get("who") or finding.get("what", ""))
        e.ledger.append("NIGHTSHIFT", NOTIFIED, actor,
                        f"{'told' if ok else 'could not tell'} "
                        f"{finding.get('who') or 'nobody in particular'}: {why}",
                        person=finding.get("who", ""), delivered=ok)
    return {"configured": configured(), "sent": sent, "failed": failed,
            "says": ("Nothing was worth an interruption." if not night.get("interrupted") else
                     f"Told {len(sent)} of {len(sent) + len(failed)}."
                     if configured() else
                     f"{len(failed)} interruption(s) had nowhere to go: no sink is configured, so "
                     f"they are in the handover and nobody was told. Set {URL_ENV}.")}
