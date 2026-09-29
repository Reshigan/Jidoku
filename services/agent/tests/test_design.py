"""The design pass: what the platform refuses to accept from its own model.

Driven by a scripted client, so the loop, the gates and the request shape are all tested without a
network and without spending anything. That is not a compromise — a loop that can only be exercised
by paying for it is a loop nobody exercises, and the gates here are the reason this pass is allowed
to author intent at all.
"""
import json
from types import SimpleNamespace

import pytest
from jidoka_adapters.successfactors import SFAdapter
from jidoka_core.schema import IR_SCHEMA
from jidoka_agent.design import (SYSTEM, DesignSession, ir_tool_schema, request, requirements_of,
                                 run, tools)

SCHEMA = {"type": "object", "properties": {"object": {"type": "string"}},
          "additionalProperties": True}

META = {"FOPayComponent": {"fields": {
    "externalCode": {"type": "String", "required": True, "picklist": None},
    "name": {"type": "String", "required": True, "picklist": None},
    "payComponentType": {"type": "String", "required": False, "picklist": "PayComponentType"},
}}}

PACK = {
    "specification": {
        "requirements": [{"req_id": "BRS-EC-001", "requirement": "Basic salary component",
                          "rationale": "the baseline", "fit": "CFG", "control": "C01"}],
        "controls": [{"control_id": "C01", "objective": "attributable", "owner": "GONXT",
                      "frequency": "per cycle", "evidence": "the change log"}]},
    "programme": {"gates": [{"gate_id": "G1"}]},
    "contracts": {"Pay components": {"owner": "EC Payroll", "consumers": ["Analytics"]}},
    "interlocks": [{"interlock": "I-01", "failure_mode": "stale master data"}],
    "scope": [{"scope_item": "G01", "scope": "Model company activation"}],
    "ordering": [{"by": "Week 1", "must_be_complete": "extracts profiled"}],
    "rules": [{"rule_id": "A1", "rule": "One picklist source"}],
    "notes": ["2 sheet(s) were not absorbed"],
    "documents": {"SDD.docx": {
        "headings": ["1.2 The accountability boundary", "The Eight Rules the Design Obeys"],
        "sections": {"1.2 The accountability boundary": "GONXT configures; Komatsu approves.",
                     "The Eight Rules the Design Obeys": "P1 Fit to standard."}}},
}

GOOD = {
    "object": "FOPayComponent", "product": "SuccessFactors", "system_binding": "KOM-SF-DEV",
    "tier": "A", "external_code": "BASIC",
    # A draft: it cites where its values came from and carries no signature. A person signs it.
    "source": {"workbook": "SDD.docx"},
    "intent": {"externalCode": "BASIC", "name": "Basic Salary"},
}


def session(metadata=META, picklists=None):
    return DesignSession(PACK, SFAdapter(), metadata=metadata,
                         documents=PACK["documents"], picklists=picklists)


class Scripted:
    """A client that replays a fixed sequence of assistant turns and records what it was asked.

    Mirrors the one shape of the SDK this module uses — a streaming context manager whose
    `get_final_message()` returns the turn — which is also the only shape a test of the loop needs.
    """

    def __init__(self, turns):
        self.turns, self.sent, self.i = turns, [], 0

    def _block(self, i, call):
        name, args = call
        return SimpleNamespace(type="tool_use", id=f"tu{i}", name=name, input=args)

    @property
    def beta(self):
        return SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **body):
        self.sent.append(body)
        stop, calls = self.turns[min(self.i, len(self.turns) - 1)]
        self.i += 1
        message = SimpleNamespace(stop_reason=stop,
                                  content=[self._block(j, c) for j, c in enumerate(calls)])
        return _Stream(message)


class _Stream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


# --- the request shape -----------------------------------------------------------------------

def test_the_request_caches_the_stable_prefix_and_paces_itself_on_a_budget():
    body = request(session(), [{"role": "user", "content": "go"}], SCHEMA)
    assert body["cache_control"] == {"type": "ephemeral"}
    # A budget the model can see, not a turn cap it cannot: a whole configuration is thousands of
    # decisions, and being cut off mid-object with no warning is the failure mode of a turn cap.
    assert body["output_config"]["task_budget"]["type"] == "tokens"
    assert "task-budgets-2026-03-13" in body["betas"]
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"]["effort"] == "xhigh"


def test_every_closed_shape_tool_is_strict_so_a_malformed_call_never_costs_a_turn():
    for tool in tools(SCHEMA):
        # `check_design` takes no arguments; every other tool names what it needs.
        assert tool["input_schema"]["required"] or not tool["input_schema"]["properties"], tool["name"]
        if tool["name"] == "propose_ir":
            # Deliberately not strict: `intent` is the product's free-form shape, and strict needs a
            # closed schema at every level. The four gates validate it properly.
            assert "strict" not in tool
            continue
        assert tool["strict"] is True, tool["name"]
        assert tool["input_schema"]["additionalProperties"] is False, tool["name"]


def test_the_record_schema_is_a_projection_of_the_published_one_not_a_second_copy():
    schema = ir_tool_schema()
    assert schema["required"] == IR_SCHEMA["required"]
    assert schema["properties"]["tier"]["enum"] == ["A", "B", "C"]
    # The meta keys mean nothing to a tool definition, and carrying them invites a drift nobody reads.
    assert not [k for k in schema if k.startswith("$")]


def test_the_tools_default_to_the_published_schema_so_a_caller_cannot_pass_a_stale_one():
    proposal = next(t for t in tools() if t["name"] == "propose_ir")
    assert proposal["input_schema"]["properties"]["record"]["required"] == IR_SCHEMA["required"]


def test_the_system_prompt_states_the_invariants_it_has_to_state():
    assert "Never invent a value" in SYSTEM
    assert "The product decides the tier" in SYSTEM
    assert "builder, never the approver" in SYSTEM
    assert "never write source.signed_by" in SYSTEM
    assert "call check_design" in SYSTEM and "not a number to drive to zero" in SYSTEM


# --- the reads -------------------------------------------------------------------------------

def test_the_pack_is_readable_register_by_register():
    s = session()
    assert s.read_pack("requirements")["requirements"][0]["req_id"] == "BRS-EC-001"
    assert s.read_pack("interlocks")["interlocks"][0]["failure_mode"] == "stale master data"
    assert "not a register" in s.read_pack("velocity")["error"]


def test_a_document_gives_its_outline_first_and_a_section_on_request():
    s = session()
    outline = s.read_document("SDD.docx", "")
    assert "1.2 The accountability boundary" in outline["outline"]
    got = s.read_document("SDD.docx", "accountability")
    assert got["text"] == "GONXT configures; Komatsu approves."
    assert "no section" in s.read_document("SDD.docx", "velocity")["error"]
    assert "not a document" in s.read_document("Nope.docx", "")["error"]


def test_metadata_the_tenant_does_not_publish_is_a_refusal_with_advice():
    got = session().read_metadata("TimeAccountType")
    assert "does not publish" in got["error"] and "Do not write a record against it" in got["error"]
    assert "FOPayComponent" in got["published"]


def test_the_tier_comes_from_the_adapter_and_an_unknown_object_says_so():
    s = session()
    assert s.read_tier("FOPayComponent")["tier"] == "A"
    assert s.read_tier("PicklistOption")["tier"] == "B"
    unknown = s.read_tier("cust_Whatever")
    assert unknown["tier"] is None and "may never be tier A" in unknown["note"]


# --- the gates -------------------------------------------------------------------------------

def test_a_sourced_valid_record_that_fits_the_tenant_is_accepted():
    s = session()
    got = s.propose_ir(GOOD, ["SDD §5.1"])
    assert got["accepted"] is True
    assert len(s.out.accepted) == 1 and s.out.refused == []


def test_a_record_with_no_source_is_refused_because_provenance_is_the_invariant():
    s = session()
    got = s.propose_ir(GOOD, ["  "])
    assert got["accepted"] is False
    assert any("No source given" in p for p in got["problems"])
    assert len(s.out.refused) == 1


def test_a_drafter_that_writes_a_signature_is_refused_because_it_is_asserting_an_approval():
    # The hole this closes: `validate_record` checks signed_by is *present*, so a model could pass the
    # gate by writing a person's name into it. Unsigned intent wearing a signature.
    s = session()
    forged = {**GOOD, "source": {"workbook": "SDD.docx", "signed_by": "N. Sango",
                                 "date": "2026-09-30"}}
    got = s.propose_ir(forged, ["SDD §5.1"])
    assert got["accepted"] is False
    assert any("asserting an approval nobody gave" in p for p in got["problems"])
    assert s.out.accepted == []


def test_an_accepted_record_is_stored_as_a_draft_with_no_signature_and_platform_stamped_provenance():
    s = session()
    typed = {**GOOD, "source": {"workbook": "something the model made up"}}
    s.propose_ir(typed, ["SDD §5.1", "DP-C04"])
    stored = s.out.accepted[0].record["source"]
    assert stored == {"workbook": "SDD §5.1; DP-C04", "signed_by": "", "date": ""}


def test_an_accepted_record_is_still_unloadable_until_a_person_signs_it():
    from jidoka_core.ir import IRValidationError, validate_record
    s = session()
    s.propose_ir(GOOD, ["SDD §5.1"])
    with pytest.raises(IRValidationError) as ex:
        validate_record(s.out.accepted[0].record)
    assert "does not execute unsigned intent" in str(ex.value)


def test_the_tool_schema_no_longer_asks_the_model_for_a_signature_it_may_not_give():
    source = ir_tool_schema()["properties"]["source"]
    assert source["required"] == ["workbook"]
    assert "signed_by" not in source["properties"] and "date" not in source["properties"]
    # …while the published schema still demands them of a *signed* record.
    assert "signed_by" in IR_SCHEMA["properties"]["source"]["required"]


def test_a_tier_the_model_invented_is_refused_naming_both_answers():
    s = session()
    got = s.propose_ir({**GOOD, "object": "PicklistOption", "tier": "A"}, ["SDD §5.1"])
    assert any("Tier mismatch on PicklistOption" in p and "'B'" in p for p in got["problems"])


def test_tier_a_for_an_object_no_adapter_knows_is_refused():
    s = session()
    got = s.propose_ir({**GOOD, "object": "cust_Invented", "tier": "A"}, ["SDD §5.1"])
    assert any("nothing can name its write path" in p for p in got["problems"])


def test_a_field_the_tenant_does_not_publish_is_refused_before_it_is_ever_written():
    s = session()
    bad = {**GOOD, "intent": {"externalCode": "BASIC", "name": "Basic", "madeUpField": "x"}}
    got = s.propose_ir(bad, ["SDD §5.1"])
    assert any("madeUpField" in p and "$metadata" in p for p in got["problems"])


def test_a_field_the_tenant_requires_and_the_record_omits_is_refused():
    s = session()
    got = s.propose_ir({**GOOD, "intent": {"externalCode": "BASIC"}}, ["SDD §5.1"])
    assert any("name" in p and "required by $metadata" in p for p in got["problems"])


def test_a_picklist_value_the_tenant_does_not_have_is_refused_as_an_orphan():
    s = session(picklists={"PayComponentType": {"RECURRING"}})
    bad = {**GOOD, "intent": {**GOOD["intent"], "payComponentType": "INVENTED"}}
    got = s.propose_ir(bad, ["SDD §5.1"])
    assert any("orphan reference" in p for p in got["problems"])


def test_a_decision_placeholder_left_in_a_record_is_refused_with_the_reason():
    s = session()
    bad = {**GOOD, "intent": {**GOOD["intent"], "payComponentType": {"decision_point": "DP-C04"}}}
    got = s.propose_ir(bad, ["SDD §5.1"])
    assert any("hard-blocks the plan" in p for p in got["problems"])


def test_a_refusal_names_every_gate_that_failed_not_just_the_first():
    s = session()
    bad = {**GOOD, "object": "PicklistOption", "tier": "A",
           "intent": {"externalCode": "BASIC", "madeUpField": "x"}}
    got = s.propose_ir(bad, [])
    assert len(got["problems"]) >= 3
    assert "Do not work around them" in got["note"]


def test_with_no_tenant_metadata_the_twin_gate_is_skipped_rather_than_faked():
    # A design pass before a tenant exists is legitimate — the other three gates still run — and a
    # twin with no metadata would otherwise reject every entity as absent.
    s = session(metadata={})
    assert s.propose_ir(GOOD, ["SDD §5.1"])["accepted"] is True


# --- traces and decisions --------------------------------------------------------------------

def test_a_trace_is_proposed_and_never_accepted_by_the_platform_itself():
    s = session()
    got = s.propose_trace("BRS-EC-001", ["FOPayComponent"], "agreed in design authority")
    assert got["traced"] == "BRS-EC-001"
    assert "A person signs it" in got["note"]
    assert s.out.traces[0]["objects"] == ["FOPayComponent"]


def test_a_trace_to_an_unknown_requirement_or_to_nothing_is_refused():
    s = session()
    assert "not a requirement" in s.propose_trace("BRS-XX-9", ["X"], "why")["error"]
    assert "already says" in s.propose_trace("BRS-EC-001", [" "], "why")["error"]


def test_a_raised_decision_says_it_blocks_planning_and_not_the_pass():
    s = session()
    got = s.raise_dp("DP-S01", "STATUTORY", "ZA minimum leave days?", "Komatsu HR",
                     "no document states it")
    assert got["dp_type"] == "STATUTORY"
    assert "does not block you from authoring the rest" in got["note"]
    assert s.out.decisions[0]["why_not_sourced"] == "no document states it"


def test_an_unknown_tool_and_a_malformed_call_both_come_back_as_errors():
    s = session()
    assert "not a tool" in s.dispatch("rm_rf", {})["error"]
    assert "error" in s.dispatch("read_tier", {"nope": 1})


# --- the loop --------------------------------------------------------------------------------

def test_the_loop_feeds_every_tool_result_back_in_one_user_message():
    # Split across several and the model learns not to make parallel calls, which on a per-object
    # design pass is most of the throughput.
    client = Scripted([("tool_use", [("read_tier", {"object": "FOPayComponent"}),
                                     ("read_metadata", {"entity": "FOPayComponent"})]),
                       ("end_turn", [])])
    out = run(session(), "design G01", SCHEMA, client=client)
    assert out.stopped == "the model stopped calling tools"
    results = client.sent[-1]["messages"][-1]
    assert results["role"] == "user"
    assert len(results["content"]) == 2
    assert all(b["type"] == "tool_result" for b in results["content"])


def test_a_tool_error_is_marked_as_one_so_the_model_can_correct_itself():
    client = Scripted([("tool_use", [("read_metadata", {"entity": "Nope"})]), ("end_turn", [])])
    run(session(), "design", SCHEMA, client=client)
    block = client.sent[-1]["messages"][-1]["content"][0]
    assert block.get("is_error") is True
    assert "does not publish" in json.loads(block["content"])["error"]


def test_a_full_pass_reports_what_it_authored_what_was_refused_and_what_it_asked():
    client = Scripted([
        ("tool_use", [("propose_ir", {"record": GOOD, "sources": ["SDD §5.1"]}),
                      ("propose_ir", {"record": {**GOOD, "tier": "C"}, "sources": ["SDD §5.1"]}),
                      ("propose_trace", {"req_id": "BRS-EC-001", "objects": ["FOPayComponent"],
                                         "why": "design authority"}),
                      ("raise_dp", {"dp_id": "DP-S01", "dp_type": "STATUTORY",
                                    "question": "leave days?", "owner": "HR",
                                    "why_not_sourced": "unstated"})]),
        ("end_turn", [])])
    out = run(session(), "design G01", SCHEMA, client=client)
    s = out.summary()
    assert (s["accepted"], s["refused"], s["traces"], s["decisions"]) == (1, 1, 1, 1)
    assert "refused by the platform's own gates" in s["says"]
    assert "raised rather than answered" in s["says"]


def test_a_pass_that_authored_nothing_and_asked_nothing_says_that_plainly():
    out = run(session(), "design", SCHEMA, client=Scripted([("end_turn", [])]))
    assert "did not read its inputs" in out.summary()["says"]


def test_the_runaway_guard_stops_a_pass_that_only_argues_with_itself():
    client = Scripted([("tool_use", [("read_metadata", {"entity": "Nope"})])])
    out = run(session(), "design", SCHEMA, client=client, max_turns=3)
    assert out.turns == 3
    assert "runaway guard" in out.stopped and "is not claimed as one" in out.stopped


def test_a_declined_request_stops_the_pass_and_says_so():
    out = run(session(), "design", SCHEMA, client=Scripted([("refusal", [])]))
    assert out.stopped == "the model declined the request"


def test_the_specification_comes_back_as_kernel_requirements_for_coverage():
    reqs = requirements_of(PACK)
    assert [r.req_id for r in reqs] == ["BRS-EC-001"] and reqs[0].objects == ()


def test_a_record_that_is_not_an_object_is_refused_rather_than_crashing_the_loop():
    # A model can send anything. `.get` on a string ends the pass with a traceback.
    got = session().propose_ir("a pay component called BASIC", ["SDD §5.1"])
    assert got["accepted"] is False
    assert "A record is an object, not a str" in got["problems"][0]


def test_the_summary_carries_the_transcript_because_it_is_the_only_record_of_the_pass():
    client = Scripted([("tool_use", [("read_tier", {"object": "FOPayComponent"})]),
                       ("end_turn", [])])
    out = run(session(), "design", SCHEMA, client=client)
    assert out.summary()["transcript"][0]["tools"] == ["read_tier"]
    assert out.summary()["transcript"][-1]["stop_reason"] == "end_turn"


def test_a_turn_is_streamed_so_a_long_pass_does_not_time_out_halfway_through():
    # Adaptive thinking at high effort over a design pack with a large output ceiling is the request
    # shape that hits an HTTP timeout, and a timeout mid-pass loses the turn and the money.
    client = Scripted([("end_turn", [])])
    run(session(), "design", SCHEMA, client=client)
    assert client.sent[0]["max_tokens"] == 64000
    assert not hasattr(client.beta.messages, "create")     # the loop never calls the buffered path


# --- integrity: would this design survive planning? -------------------------------------------------

def dep(code, *deps, obj="FOPayComponent"):
    return {**GOOD, "object": obj, "external_code": code,
            "intent": {"externalCode": code, "name": code}, "depends_on": list(deps)}


def test_a_dependency_on_something_nobody_authored_is_dangling_and_named():
    s = session()
    s.propose_ir(dep("A", "FOPayComponent:NOPE"), ["SDD"])
    got = s.check_design()
    assert got["dangling"] == [{"record": "SuccessFactors:FOPayComponent:A",
                                "references": "FOPayComponent:NOPE"}]
    assert "do not stop with these open" in got["says"]


def test_authoring_the_missing_record_later_in_the_pass_resolves_it():
    # Order of authoring is not order of dependency: a record may cite one the model writes next.
    s = session()
    s.propose_ir(dep("A", "FOPayComponent:B"), ["SDD"])
    assert s.check_design()["dangling"]
    s.propose_ir(dep("B"), ["SDD"])
    assert s.check_design() == {"dangling": [], "cycles": [],
                                "says": "Every dependency resolves and nothing is cyclic."}


def test_a_dependency_on_a_record_already_in_the_design_is_not_dangling():
    s = DesignSession(PACK, SFAdapter(), metadata=META, documents=PACK["documents"],
                      existing=[dep("OLD")])
    s.propose_ir(dep("NEW", "FOPayComponent:OLD"), ["SDD"])
    assert s.check_design()["dangling"] == []


def test_a_cycle_the_pass_authored_is_reported():
    s = session()
    s.propose_ir(dep("A", "FOPayComponent:B"), ["SDD"])
    s.propose_ir(dep("B", "FOPayComponent:A"), ["SDD"])
    assert s.check_design()["cycles"] == ["SuccessFactors:FOPayComponent:A",
                                          "SuccessFactors:FOPayComponent:B"]


def test_a_refused_proposal_does_not_count_towards_the_design():
    s = session()
    s.propose_ir({**dep("A"), "tier": "C"}, ["SDD"])          # refused: the adapter says A
    s.propose_ir(dep("B", "FOPayComponent:A"), ["SDD"])
    assert s.check_design()["dangling"][0]["references"] == "FOPayComponent:A"


def test_the_outcome_reports_integrity_whether_or_not_the_model_asked():
    client = Scripted([("tool_use", [("propose_ir", {"record": dep("A", "FOPayComponent:NOPE"),
                                                     "sources": ["SDD"]})]),
                       ("end_turn", [])])
    out = run(session(), "design", SCHEMA, client=client)
    assert out.summary()["integrity"]["dangling"]
    assert "not a finished design" in out.summary()["says"]


def test_a_clean_pass_says_nothing_about_dependencies():
    client = Scripted([("tool_use", [("propose_ir", {"record": dep("A"), "sources": ["SDD"]})]),
                       ("end_turn", [])])
    out = run(session(), "design", SCHEMA, client=client)
    assert "not a finished design" not in out.summary()["says"]


def test_the_runaway_guard_still_computes_integrity():
    client = Scripted([("tool_use", [("propose_ir", {"record": dep("A", "FOPayComponent:NOPE"),
                                                     "sources": ["SDD"]})])])
    out = run(session(), "design", SCHEMA, client=client, max_turns=2)
    assert "runaway guard" in out.stopped and out.integrity["dangling"]


# --- gaps: what the catalogue lists that the design does not describe ------------------------------

def test_the_gaps_list_catalogued_objects_nothing_describes_by_tier():
    s = session()
    before = s.read_gaps()
    assert "FOPayComponent" in before["not_described"]["A"]
    assert "PicklistOption" in before["not_described"]["B"]
    assert "BUSINESS_RULE" in before["not_described"]["C"]
    s.propose_ir(dep("A"), ["SDD"])
    after = s.read_gaps()
    assert "FOPayComponent" not in after["not_described"]["A"]
    assert after["described"] == ["FOPayComponent"]


def test_objects_already_in_the_design_are_not_gaps():
    s = DesignSession(PACK, SFAdapter(), metadata=META, documents=PACK["documents"],
                      existing=[dep("OLD")])
    assert "FOPayComponent" not in s.read_gaps()["not_described"]["A"]


def test_an_object_the_catalogue_does_not_know_is_reported_apart_not_hidden():
    s = DesignSession(PACK, SFAdapter(), metadata=META, documents=PACK["documents"],
                      existing=[{**dep("X"), "object": "cust_Grievance"}])
    assert s.read_gaps()["outside_the_catalogue"] == ["cust_Grievance"]


def test_the_gaps_are_not_a_coverage_percentage_because_the_model_would_try_to_close_it():
    got = session().read_gaps()
    assert not any("percent" in k or "coverage" in k or "score" in k for k in got)
    assert "Not every catalogued object belongs in every engagement" in got["note"]
