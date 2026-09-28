"""Where an interruption actually goes — and what it must never carry with it."""
import json
import pathlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient
from jidoka_api.main import app
from jidoka_api.notify import URL_ENV, payload, send_interruptions
from jidoka_api.routers.engagements import STORE

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))


class Sink(BaseHTTPRequestHandler):
    got: list = []
    status = 200

    def do_POST(self):
        Sink.got.append(json.loads(self.rfile.read(int(self.headers["content-length"]))))
        self.send_response(Sink.status)
        self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture()
def sink(monkeypatch):
    Sink.got, Sink.status = [], 200
    srv = HTTPServer(("127.0.0.1", 0), Sink)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv(URL_ENV, f"http://127.0.0.1:{srv.server_port}/hook")
    yield Sink
    srv.shutdown()


def _eng():
    eid = c.post("/engagements", json={"name": "ZA payroll", "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=IR)
    return eid


def _break_the_chain(eid):
    """The one finding the night is willing to wake somebody for."""
    STORE.get(eid).ledger.entries[0]["detail"] = "tampered after the fact"


def test_what_the_budget_spent_is_sent_and_what_it_held_back_is_not(sink):
    """A sink that sent everything would quietly undo the budget, which is the product."""
    eid = _eng()
    _break_the_chain(eid)
    out = c.post(f"/engagements/{eid}/nightshift").json()

    assert out["notified"]["configured"] is True
    assert len(sink.got) == len(out["interrupted"]) == out["budget"]["spent"]
    said = " ".join(g["what"] for g in sink.got)
    assert "chain" in said
    for held in out["waited"] + out["deferred"]:
        assert held["what"] not in said


def test_the_payload_is_a_tap_on_the_shoulder_not_an_export():
    """It leaves the tenant, so it carries the least that is useful: no hashes, no configured
    values, no evidence."""
    body = payload("ZA payroll", "Komatsu", {
        "who": "T. Mabaso", "what": "the ledger chain does not verify", "cost": 100,
        "why": "the least senior person who may 'halt'", "detail": "LedgerTampered",
        "kind": "chain_broken", "needs": "halt"})
    assert set(body) == {"engagement", "client", "who", "what", "cost_of_silence", "why_you", "text"}
    assert "LedgerTampered" not in json.dumps(body), "the detail stays in the handover"


def test_every_attempt_is_on_the_chain_so_a_failing_sink_is_visible(sink):
    """A sink nobody can see failing is a sink everybody assumes is working."""
    sink.status = 500
    eid = _eng()
    _break_the_chain(eid)
    out = c.post(f"/engagements/{eid}/nightshift").json()

    assert out["notified"]["failed"] and not out["notified"]["sent"]
    entry = next(e for e in STORE.get(eid).ledger.entries if e["action"] == "NOTIFIED")
    assert entry["delivered"] is False and "could not tell" in entry["detail"]


def test_a_sink_that_is_down_never_costs_the_night_its_work(monkeypatch):
    monkeypatch.setenv(URL_ENV, "http://127.0.0.1:9/nothing-listens-here")
    eid = _eng()
    _break_the_chain(eid)
    out = c.post(f"/engagements/{eid}/nightshift").json()
    assert out["handover"] and out["interrupted"], "the night's work survived the sink"
    assert out["notified"]["failed"]


def test_with_no_sink_it_says_nobody_was_told_rather_than_implying_somebody_was(monkeypatch):
    monkeypatch.delenv(URL_ENV, raising=False)
    eid = _eng()
    _break_the_chain(eid)
    out = c.post(f"/engagements/{eid}/nightshift").json()
    assert out["notified"]["configured"] is False
    assert "nowhere to go" in out["notified"]["says"] and "nobody was told" in out["notified"]["says"]


def test_the_sink_url_never_appears_in_a_result_or_on_the_chain(monkeypatch):
    """A webhook URL is a credential in every practical sense."""
    secret = "http://127.0.0.1:9/hook-with-a-token-in-it"
    monkeypatch.setenv(URL_ENV, secret)
    eid = _eng()
    _break_the_chain(eid)
    out = c.post(f"/engagements/{eid}/nightshift").json()
    assert "hook-with-a-token" not in json.dumps(out)
    assert "hook-with-a-token" not in json.dumps(STORE.get(eid).ledger.entries)


def test_a_quiet_night_sends_nothing_at_all(sink):
    eid = _eng()
    out = c.post(f"/engagements/{eid}/nightshift").json()
    assert out["interrupted"] == [] and sink.got == []
    assert out["notified"]["says"] == "Nothing was worth an interruption."


def test_sending_is_not_something_the_crew_can_reach():
    """`send_interruptions` takes an engagement and a night, and the only caller is the night
    shift endpoint. An agent that could notify could page a customer at will."""
    root = pathlib.Path(__file__).parents[1] / "src/jidoka_api"
    callers = sorted(f.relative_to(root).as_posix() for f in root.rglob("*.py")
                     if "send_interruptions(" in f.read_text() and f.name != "notify.py")
    assert callers == ["routers/nightshift.py"], (
        f"{callers} can notify. An agent that could page a customer at will would be an agent "
        f"with a channel to them, and the crew's rings deliberately have none.")
