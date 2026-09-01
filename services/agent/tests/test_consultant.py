"""The loop must terminate, dispatch, and — invariant #7 — never offer an approve tool."""
import inspect, json, pytest

from jidoka_agent import client as client_mod, consultant
from jidoka_agent.client import JidokaClient

APPROVAL_WORDS = ("approve", "approval", "apjidokal", "sign off", "sign-off", "reviewer", "resolve")


def _client(calls):
    def transport(method, url, body):
        calls.append((method, url, body))
        return {"ok": True, "url": url}
    return JidokaClient("http://api.test", transport=transport)


def _scripted(*replies):
    it = iter(replies)
    seen = []

    def ask(messages, system=None):
        seen.append((messages, system))
        return next(it)
    ask.seen = seen
    return ask


def test_loop_dispatches_tools_and_terminates():
    calls = []
    ask = _scripted(
        {"stop_reason": "tool_use", "content": [
            {"type": "tool_use", "id": "t1", "name": "build_plan", "input": {"eid": "E1"}},
            {"type": "tool_use", "id": "t2", "name": "get_ledger", "input": {"eid": "E1"}}]},
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "plan built"}]})
    msgs = consultant.run("sequence the build", _client(calls), ask_fn=ask)
    assert [m["method"] for m in ({"method": c[0]} for c in calls)] == ["POST", "GET"]
    assert msgs[-1]["content"][0]["text"] == "plan built"
    # both results ride in ONE user message, keyed by tool_use_id
    results = msgs[2]["content"]
    assert msgs[2]["role"] == "user" and [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert all(r["is_error"] is False for r in results)


def test_loop_guards_against_runaway():
    forever = {"stop_reason": "tool_use",
               "content": [{"type": "tool_use", "id": "t", "name": "build_plan", "input": {"eid": "E1"}}]}
    ask = _scripted(*[forever] * 5)
    with pytest.raises(RuntimeError, match="did not terminate"):
        consultant.run("go", _client([]), ask_fn=ask, max_iterations=3)


def test_failed_tool_is_reported_not_dropped():
    ask = _scripted(
        {"stop_reason": "tool_use", "content": [
            {"type": "tool_use", "id": "t1", "name": "ledger_append",
             "input": {"eid": "E1", "task": "M1", "action": "APPROVED"}}]},
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "refused"}]})
    msgs = consultant.run("approve it", _client([]), ask_fn=ask)
    err = msgs[2]["content"][0]
    assert err["is_error"] is True and "ValueError" in err["content"]


def test_no_approval_tool_exists_anywhere_in_the_tool_set():
    """Invariant #7: builder never approver — structural, not prompt-level."""
    blob = json.dumps(consultant.TOOLS).lower()
    for word in APPROVAL_WORDS:
        assert word not in blob, f"approval-shaped tool surface: {word!r}"
    assert "approve" not in json.dumps(list(consultant.TOOLS)).lower()


def test_client_has_no_method_that_can_post_to_approve_or_resolve():
    names = [n for n in dir(JidokaClient) if not n.startswith("__")]
    assert not [n for n in names if any(w in n.lower() for w in APPROVAL_WORDS)]
    # no executable line may name an approval/resolve endpoint (the module docstring says why not)
    code = [ln.lower() for ln in inspect.getsource(client_mod).splitlines()
            if ln.strip() and not ln.strip().startswith("#")]
    code = code[code.index([l for l in code if l.startswith("import ")][0]):]
    assert not [ln for ln in code if "/approve" in ln or "/resolve" in ln]
    # and the dispatch table cannot reach one
    with pytest.raises(KeyError):
        consultant.dispatch(_client([]), "approve", {"eid": "E1"})


def test_ledger_append_is_restricted_to_builder_actions():
    c = _client(calls := [])
    c.ledger_append("E1", "M1", "SNAPSHOT", "pre-load")
    assert calls[0][2]["actor"] == "jidoka-agent"
    for bad in ("APPROVED", "SIGNED_OFF", "approve"):
        with pytest.raises(ValueError):
            c.ledger_append("E1", "M1", bad)
