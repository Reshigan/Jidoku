import unittest
from jidoka_core.registry import SystemRegistry, SystemRecord, RegistryError
from jidoka_core.transport import (TransportRequest, TransportRoute, TransportError,
                                   release, import_into, import_status,
                                   MODIFIABLE, RELEASED, IMPORTED)

def registry() -> SystemRegistry:
    r = SystemRegistry()
    for sid, role in (("S4-DEV", "DEV"), ("S4-QA", "TEST"), ("S4-PRD", "PROD"), ("S4-TWIN", "TWIN")):
        r.register(SystemRecord(system_id=sid, product="S/4HANA", role=role, environment=role,
                                connectivity={"write_credentials": role != "TWIN"}))
    return r

def req() -> TransportRequest:
    return TransportRequest(request_id="S4DK900123", owner="j.smith", description="Absence quota config",
                            source_system="S4-DEV", objects=["V_T556A", "V_T559L"])

ROUTE = ["S4-DEV", "S4-QA", "S4-PRD"]

class TestRoute(unittest.TestCase):
    def test_unregistered_hop_refused(self):
        with self.assertRaises(RegistryError):
            TransportRoute(["S4-DEV", "S4-GHOST", "S4-PRD"]).validate(registry())

    def test_write_forbidden_final_hop_refused(self):
        with self.assertRaises(TransportError) as cm:
            TransportRoute(["S4-DEV", "S4-TWIN"]).validate(registry())
        self.assertIn("TWIN", str(cm.exception))

    def test_single_system_is_not_a_route(self):
        with self.assertRaises(TransportError):
            TransportRoute(["S4-DEV"]).validate(registry())

class TestStateMachine(unittest.TestCase):
    def setUp(self):
        self.route = TransportRoute(ROUTE).validate(registry())
        self.tr = req()

    def test_modifiable_cannot_be_imported(self):
        with self.assertRaises(TransportError) as cm:
            import_into(self.tr, self.route, "S4-QA", "basis")
        self.assertIn("MODIFIABLE", str(cm.exception))

    def test_release_requires_owner(self):
        self.tr.owner = ""
        with self.assertRaises(TransportError):
            release(self.tr, "j.smith")

    def test_release_is_one_way(self):
        release(self.tr, "j.smith")
        self.assertEqual(self.tr.status, RELEASED)
        with self.assertRaises(TransportError):
            release(self.tr, "j.smith")

    def test_skipping_qa_to_reach_prod_refused(self):
        release(self.tr, "j.smith")
        with self.assertRaises(TransportError) as cm:
            import_into(self.tr, self.route, "S4-PRD", "basis")
        msg = str(cm.exception)
        self.assertIn("S4-PRD", msg)   # attempted target
        self.assertIn("S4-QA", msg)    # actual next hop
        self.assertEqual(self.tr.imported_into, [])

    def test_route_order_enforced_end_to_end(self):
        release(self.tr, "j.smith")
        e1 = import_into(self.tr, self.route, "S4-QA", "basis")
        self.assertEqual(e1["next_hop"], "S4-PRD")
        e2 = import_into(self.tr, self.route, "S4-PRD", "basis")
        self.assertIsNone(e2["next_hop"])
        self.assertEqual(self.tr.status, IMPORTED)
        self.assertTrue(import_status(self.tr, self.route)["in_production"])

    def test_reimport_refused(self):
        release(self.tr, "j.smith")
        import_into(self.tr, self.route, "S4-QA", "basis")
        with self.assertRaises(TransportError) as cm:
            import_into(self.tr, self.route, "S4-QA", "basis")
        self.assertIn("already IMPORTED", str(cm.exception))

    def test_import_past_end_of_route_refused(self):
        release(self.tr, "j.smith")
        import_into(self.tr, self.route, "S4-QA", "basis")
        import_into(self.tr, self.route, "S4-PRD", "basis")
        with self.assertRaises(TransportError):
            import_into(self.tr, self.route, "S4-PRD", "basis")

class TestStatusAndLedgerShape(unittest.TestCase):
    def setUp(self):
        self.route = TransportRoute(ROUTE).validate(registry())
        self.tr = req()

    def test_status_before_release(self):
        s = import_status(self.tr, self.route)
        self.assertEqual((s["status"], s["currently_in"], s["next_hop"]), (MODIFIABLE, "S4-DEV", "S4-QA"))
        self.assertFalse(s["in_production"])

    def test_entries_are_ledger_shaped(self):
        from jidoka_core.ledger import Ledger
        led = Ledger()
        e = release(self.tr, "j.smith")
        led.append("TR-S4DK900123", e.pop("action"), e.pop("actor"), **e)
        e = import_into(self.tr, self.route, "S4-QA", "basis")
        led.append("TR-S4DK900123", e.pop("action"), e.pop("actor"), **e)
        self.assertTrue(led.verify_chain())
        self.assertEqual([x["action"] for x in led.entries],
                         ["TRANSPORT_RELEASED", "TRANSPORT_IMPORTED"])

if __name__ == "__main__":
    unittest.main()
