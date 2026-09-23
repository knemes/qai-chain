"""
Unit tests for the Level-0 Sovereign Base Node Runtime (512 KB Footprint & Propose-and-Veto Pipeline).
"""

import json
import unittest
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier
from engine.node_runtime import SovereignTileNode, DEFAULT_INITIAL_FUEL, VERIFIED_FUEL_REWARD, VETO_FUEL_PENALTY
from engine.spectre_vm import Opcode


class TestNodeRuntime(unittest.TestCase):

    def setUp(self):
        self.addr1 = HierarchicalAddress.from_string("G0.M0.S0.T0")
        self.addr2 = HierarchicalAddress.from_string("G0.M0.S0.T1")

        poly1 = HierarchyEngine.get_polygon(self.addr1)
        poly2 = HierarchyEngine.get_polygon(self.addr2)

        fit1 = TopologicalVerifier.verify_tile(self.addr1, poly1, {})
        fit2 = TopologicalVerifier.verify_tile(self.addr2, poly2, {self.addr1.to_string(): poly1})

        self.node1 = SovereignTileNode(self.addr1, fit1, seed_domain="quantum_core")
        self.node2 = SovereignTileNode(self.addr2, fit2, seed_domain="threat_analyst")

        # Connect touching ports
        self.node1.connect_neighbor(port_idx=1, neighbor_cert=self.node2.identity.certificate)
        self.node2.connect_neighbor(port_idx=8, neighbor_cert=self.node1.identity.certificate)

    def test_memory_audit_under_512kb(self):
        audit = self.node1.audit_memory_footprint()
        self.assertTrue(audit["under_512kb_limit"])
        self.assertLessEqual(audit["total_kb"], 512.0)
        self.assertGreater(audit["margin_bytes_remaining"], 50_000)

    def test_legitimate_propose_and_veto_pass(self):
        # Node 1 sends vector to Node 2 via touching port
        payload_vector = [10, 20, 30, 40, 50]
        raw_bytes = json.dumps(payload_vector).encode("utf-8")
        packet = self.node1.send_to_port(port_idx=1, payload=raw_bytes, expected_invariant="non_negative")

        # Node 2 processes ingress
        receipt = self.node2.process_ingress(packet)

        self.assertEqual(receipt.status, "APPROVED")
        self.assertIsNone(receipt.rejection_reason)
        self.assertGreater(len(receipt.block_hash), 0)
        self.assertEqual(len(self.node2.committed_micro_blocks), 1)

        # Fuel should be credited: initial - gas + reward
        expected_fuel = DEFAULT_INITIAL_FUEL - receipt.gas_consumed + VERIFIED_FUEL_REWARD
        self.assertEqual(self.node2.fuel_gauge, expected_fuel)

    def test_invariant_violation_veto(self):
        # Force a policy proposal that fails the invariant:
        # e.g. We pass a packet expecting "strictly_positive", but we inject an impossible condition
        payload_vector = [0, 0, 0, 0]
        raw_bytes = json.dumps(payload_vector).encode("utf-8")
        packet = self.node1.send_to_port(port_idx=1, payload=raw_bytes, expected_invariant="strictly_positive")

        # Force candidate to propose a non-positive value (e.g. 0)
        self.node2.policy.propose_candidate = lambda vec, inv: type("Proposal", (), {
            "proposed_lemma": 0,
            "confidence_score": 10,
            "concept_domain": "forced_fail",
            "verification_bytecode": [
                (Opcode.PUSH, 0),
                (Opcode.PUSH, 0),
                Opcode.GT,
                Opcode.ASSERT, # 0 > 0 evaluates to False -> VETO!
                Opcode.HALT_PASS
            ],
            "proposal_hash": "deadbeef" * 8
        })()

        receipt = self.node2.process_ingress(packet)

        # Invariant failure must trigger VETO!
        self.assertEqual(receipt.status, "VETOED")
        self.assertIn("ERR_ASSERTION_FAILED", receipt.rejection_reason)
        self.assertEqual(len(self.node2.committed_micro_blocks), 0)

        # Fuel must be penalized with VETO_FUEL_PENALTY
        expected_fuel = DEFAULT_INITIAL_FUEL - receipt.gas_consumed - VETO_FUEL_PENALTY
        self.assertEqual(self.node2.fuel_gauge, expected_fuel)


if __name__ == "__main__":
    unittest.main()
