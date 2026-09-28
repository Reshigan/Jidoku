"""$batch loader tests. The dry_run and replay tests are gate tests: they prove a live write
cannot happen by accident (invariant 6) and that a retry cannot double-apply."""
import unittest

from jidoka_adapters.successfactors.loader import (
    BatchLoader, BatchError, build_batch, parse_batch_response, op_key, op_label, BOUNDARY)

OPS = [{"entity": "FOCostCenter", "payload": {"externalCode": "CC1", "name": "Finance"}},
       {"entity": "FOCostCenter", "payload": {"externalCode": "CC2", "name": "Ops"}}]


def multipart(*statuses):
    parts = []
    for i, (st, body) in enumerate(statuses, 1):
        parts += [f"--{BOUNDARY}", "Content-Type: application/http", "",
                  f"HTTP/1.1 {st} X", "Content-Type: application/json", "", body, ""]
    parts += [f"--{BOUNDARY}--", ""]
    return "\r\n".join(parts).encode()


class FakeClient:
    base_url = "https://api.example.com"

    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, method, url, headers=None, body=None):
        self.calls.append((method, url, headers, body))
        return self.response


class TestBuild(unittest.TestCase):
    def test_body_shape(self):
        body = build_batch(OPS, "https://api.example.com")
        self.assertTrue(body.startswith(f"--{BOUNDARY}"))
        self.assertIn("multipart/mixed; boundary=changeset_jidoka", body)
        self.assertEqual(body.count("Content-ID:"), 2)
        self.assertIn('"externalCode": "CC1"', body)
        self.assertTrue(body.rstrip().endswith(f"--{BOUNDARY}--"))

    def test_refuses_empty(self):
        with self.assertRaises(BatchError):
            build_batch([])
        with self.assertRaises(BatchError):
            build_batch([{"entity": "FOCostCenter", "payload": {}}])

    def test_op_key_is_payload_sensitive(self):
        a = op_key(OPS[0])
        b = op_key({"entity": "FOCostCenter", "payload": {"externalCode": "CC1", "name": "Changed"}})
        self.assertEqual(a[0], b[0])
        self.assertNotEqual(a[1], b[1])


class TestParse(unittest.TestCase):
    def test_per_part_results(self):
        res = parse_batch_response(multipart((200, '{"d":{"externalCode":"CC1"}}'),
                                             (400, '{"error":{"message":"bad picklist"}}')))
        self.assertEqual([r["status"] for r in res], [200, 400])
        self.assertEqual(res[1]["body"]["error"]["message"], "bad picklist")

    def test_empty_reply_raises(self):
        with self.assertRaises(BatchError):
            parse_batch_response(b"not a multipart body")


class TestApply(unittest.TestCase):
    def test_dry_run_performs_no_transport_call(self):
        c = FakeClient((200, {}, multipart((200, "{}"), (200, "{}"))))
        out = BatchLoader(c).apply(OPS)  # default is dry_run
        self.assertEqual(out["status"], "DRY_RUN")
        self.assertEqual(c.calls, [])
        self.assertIn("Content-ID: 1", out["batch"])

    def test_dry_run_without_client_still_builds(self):
        out = BatchLoader().apply(OPS)
        self.assertEqual(out["status"], "DRY_RUN")

    def test_live_apply_without_client_refuses(self):
        with self.assertRaises(BatchError):
            BatchLoader().apply(OPS, dry_run=False)

    def test_error_journal_on_partial_failure(self):
        c = FakeClient((200, {}, multipart((200, "{}"), (400, '{"error":"picklist orphan"}'))))
        ld = BatchLoader(c)
        out = ld.apply(OPS, dry_run=False)
        self.assertEqual(out["status"], "PARTIAL")
        self.assertEqual(out["applied"], ["CC1"])
        self.assertEqual(out["errors"][0]["externalCode"], "CC2")
        self.assertEqual(out["errors"][0]["status"], 400)
        self.assertEqual(ld.errors, out["errors"])
        self.assertNotIn("CC2", ld.journal)

    def test_truncated_reply_leaves_tail_unconfirmed(self):
        c = FakeClient((200, {}, multipart((200, "{}"))))
        ld = BatchLoader(c)
        out = ld.apply(OPS, dry_run=False)
        self.assertEqual(out["errors"][0]["externalCode"], "CC2")
        self.assertEqual(ld.pending(OPS), [OPS[1]])

    def test_replay_skips_applied_and_retries_the_rest(self):
        ld = BatchLoader(FakeClient((200, {}, multipart((200, "{}"), (400, '{"error":"x"}')))))
        ld.apply(OPS, dry_run=False)
        ld._client = FakeClient((200, {}, multipart((200, "{}"))))
        out = ld.apply(OPS, dry_run=False)
        self.assertEqual(out["skipped"], 1)
        self.assertEqual(out["applied"], ["CC2"])
        self.assertIn("CC2", out["batch"])
        self.assertNotIn("CC1", out["batch"])

    def test_full_replay_is_a_noop(self):
        ld = BatchLoader(FakeClient((200, {}, multipart((200, "{}"), (200, "{}")))))
        ld.apply(OPS, dry_run=False)
        c = FakeClient((200, {}, multipart((200, "{}"))))
        ld._client = c
        out = ld.apply(OPS, dry_run=False)
        self.assertEqual(out["status"], "NOOP")
        self.assertEqual(c.calls, [])

    def test_changed_payload_replays_despite_same_code(self):
        ld = BatchLoader(FakeClient((200, {}, multipart((200, "{}"), (200, "{}")))))
        ld.apply(OPS, dry_run=False)
        edited = [{"entity": "FOCostCenter", "payload": {"externalCode": "CC1", "name": "Finance EMEA"}}]
        self.assertEqual(ld.pending(edited), edited)

    def test_transport_error_raises(self):
        with self.assertRaises(BatchError):
            BatchLoader(FakeClient((500, {}, b""))).apply(OPS, dry_run=False)

    def test_journal_survives_construction(self):
        code, h = op_key(OPS[0])
        self.assertEqual(BatchLoader(journal={code: h}).pending(OPS), [OPS[1]])


if __name__ == "__main__":
    unittest.main()


class TestRecordIdentity(unittest.TestCase):
    """The journal answers "was exactly this operation confirmed?", and it can only answer that if
    two different records never share a slot. `op_key` read `externalCode` and nothing else, so every
    entity keyed by userId or personIdExternal — the whole employee-data family — landed in the same
    slot (''), a clean two-employee apply left one still pending, and every failure was reported as
    `externalCode: ""`, which nothing downstream can reconcile against."""

    EMP = [{"entity": "EmpJob", "payload": {"userId": "u1", "startDate": "2026-01-01", "jobCode": "A"}},
           {"entity": "EmpJob", "payload": {"userId": "u2", "startDate": "2026-01-01", "jobCode": "B"}}]

    def test_two_employees_never_share_a_journal_slot(self):
        self.assertNotEqual(op_key(self.EMP[0])[0], op_key(self.EMP[1])[0])

    def test_a_clean_apply_leaves_nothing_pending(self):
        ld = BatchLoader(FakeClient((200, {}, multipart((200, "{}"), (200, "{}")))))
        ld.apply(self.EMP, dry_run=False)
        self.assertEqual(ld.pending(self.EMP), [])

    def test_the_same_employee_on_a_different_effective_date_is_a_different_record(self):
        # A new startDate is a new slice in SF, so it must be a new slot here — and the earlier
        # slice's confirmation must not be overwritten by it.
        later = {"entity": "EmpJob", "payload": {**self.EMP[0]["payload"], "startDate": "2026-07-01"}}
        self.assertNotEqual(op_key(self.EMP[0])[0], op_key(later)[0])

    def test_the_same_employee_and_date_with_a_corrected_value_is_the_same_record_revised(self):
        fixed = {"entity": "EmpJob", "payload": {**self.EMP[0]["payload"], "jobCode": "A2"}}
        self.assertEqual(op_key(self.EMP[0])[0], op_key(fixed)[0])
        self.assertNotEqual(op_key(self.EMP[0])[1], op_key(fixed)[1])

    def test_two_pay_components_for_one_employee_on_one_date_are_two_records(self):
        a = {"entity": "EmpPayCompRecurring",
             "payload": {"userId": "u1", "startDate": "2026-01-01", "payComponent": "BASIC", "paycompvalue": 1}}
        b = {"entity": "EmpPayCompRecurring",
             "payload": {"userId": "u1", "startDate": "2026-01-01", "payComponent": "HOUSING", "paycompvalue": 2}}
        self.assertNotEqual(op_key(a)[0], op_key(b)[0])

    def test_an_operation_with_no_identifiable_key_is_refused_not_filed_under_nothing(self):
        with self.assertRaises(BatchError) as ex:
            op_key({"entity": "EmpJob", "payload": {"jobCode": "A"}})
        self.assertIn("EmpJob", str(ex.exception))
        self.assertIn("userId", str(ex.exception))

    def test_a_failure_names_the_record_that_failed(self):
        ld = BatchLoader(FakeClient((200, {}, multipart((200, "{}"), (400, '{"error":"x"}')))))
        out = ld.apply(self.EMP, dry_run=False)
        self.assertEqual(out["errors"][0]["externalCode"], "u2|startDate=2026-01-01")
        self.assertNotEqual(out["errors"][0]["externalCode"], "")

    def test_an_externalcode_entity_reports_its_plain_business_key(self):
        self.assertEqual(op_label(OPS[0]), "CC1")

    def test_two_entities_sharing_a_code_are_two_records(self):
        # FOCostCenter CC1 and FODepartment CC1 shared a slot too: the slot never named the entity.
        dept = {"entity": "FODepartment", "payload": {"externalCode": "CC1", "name": "Finance"}}
        self.assertNotEqual(op_key(OPS[0])[0], op_key(dept)[0])
