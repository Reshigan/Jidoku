"""Sessions: memory reaches the prompt, engagements stay isolated, the process is supervised."""
import threading

from jidoka_agent.client import JidokaClient
from jidoka_agent.session import Session, SessionRegistry
from jidoka_knowledge import recheck
from jidoka_os.capabilities import Cap


def _client():
    return JidokaClient("http://api.test", transport=lambda m, u, b: {"ok": True})


def _ask(record):
    def ask(messages, system=None):
        record.append(system)
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "done"}]}
    return ask


def test_session_runs_as_a_supervised_builder_process():
    s = Session("E1", _client())
    assert s.process.manifest.ring.name == "AGENT"
    # Invariant 7 enforced by the ring, not just by the tool list.
    assert Cap.APPROVE not in s.process.capabilities.caps
    assert Cap.RESOLVE_DP not in s.process.capabilities.caps


def test_memory_reaches_the_prompt_with_its_badge():
    seen = []
    s = Session("E1", _client())
    c = s.remember("cost-centres", "four-digit numeric", "ir:CC-01", {"r": 1}, "agent")
    recheck(c, {"r": 2})                       # evidence moved: now STALE
    s.ask("what do we know?", ask_fn=_ask(seen))
    system = seen[0]
    assert "four-digit numeric" in system
    assert "STALE" in system                   # uncertainty is shown, never hidden
    assert "may not be presented as fact" in system


def test_engagements_do_not_share_memory():
    a, b = Session("E-A", _client()), Session("E-B", _client())
    a.remember("shape", "A only", "ir:1", {"x": 1}, "agent")
    assert b.memory.current() == []
    seen = []
    b.ask("anything?", ask_fn=_ask(seen))
    assert "A only" not in seen[0]


def test_budget_kills_rather_than_degrading():
    s = Session("E1", _client())
    s.process.manifest.syscall_budget = 1
    s.ask("one", ask_fn=_ask([]))
    try:
        s.ask("two", ask_fn=_ask([]))
        assert False, "budget should have killed the process"
    except Exception as ex:
        assert "budget exceeded" in str(ex)
    assert s.process.state.name == "KILLED"


def test_registry_runs_projects_concurrently_without_crossing():
    reg = SessionRegistry()
    errors = []

    def work(eid):
        try:
            s = reg.get(eid, lambda e: _client())
            s.remember("shape", f"{eid} only", "ir:1", {"e": eid}, "agent")
            s.ask("go", ask_fn=_ask([]))
            texts = [c.text for c in s.memory.current()]
            assert texts == [f"{eid} only"], texts
        except Exception as ex:  # a thread's failure must not pass silently
            errors.append(ex)

    threads = [threading.Thread(target=work, args=(f"E{i}",)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    assert reg.active() == [f"E{i}" for i in range(8)]
