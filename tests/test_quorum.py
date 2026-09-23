"""
Unit tests for the Quorum & Convergence Oracle with Speculative Straggler Bypass.
"""

import unittest
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier
from engine.node_runtime import SovereignTileNode
from ledger.dag_aggregator import DynamicCoalitionBlock
from routing.quorum import QuorumOracle, DEFAULT_QUORUM_THRESHOLD


class TestQuorumOracle(unittest.TestCase):

    def test_evaluate_quorum_success(self):
        # 6 of 7 approve (85.7% >= 75%)
        is_quorate, ratio = QuorumOracle.evaluate_quorum(6, 7, DEFAULT_QUORUM_THRESHOLD)
        self.assertTrue(is_quorate)
        self.assertAlmostEqual(ratio, 6 / 7.0, places=3)

    def test_evaluate_quorum_failure(self):
        # 3 of 7 approve (42.8% < 75%)
        is_quorate, ratio = QuorumOracle.evaluate_quorum(3, 7, DEFAULT_QUORUM_THRESHOLD)
        self.assertFalse(is_quorate)
        self.assertAlmostEqual(ratio, 3 / 7.0, places=3)

    def test_certify_macro_block(self):
        macro_block = DynamicCoalitionBlock(
            coalition_id="coalition-test-1",
            level=1,
            level_name="SUPER_BLOCK",
            participant_addresses=["G0.T0", "G0.T1", "G0.T2", "G0.T3"],
            member_hashes=["a" * 64] * 4,
            merkle_root="b" * 64,
            approved_count=3, # 3 of 4 = 75%
            quorum_threshold=0.75,
        )

        cert = QuorumOracle.certify_macro_block(macro_block, bypassed_nodes=["G0.T3"])
        self.assertTrue(cert.is_quorate)
        self.assertEqual(cert.approval_ratio, 0.75)
        self.assertEqual(cert.bypassed_stragglers, ["G0.T3"])

    def test_speculative_straggler_bypass(self):
        addr1 = HierarchicalAddress.from_string("G0.M0.S0.T0")
        addr2 = HierarchicalAddress.from_string("G0.M0.S0.T1")

        poly1 = HierarchyEngine.get_polygon(addr1)
        poly2 = HierarchyEngine.get_polygon(addr2)

        fit1 = TopologicalVerifier.verify_tile(addr1, poly1, {})
        fit2 = TopologicalVerifier.verify_tile(addr2, poly2, {})

        stalled_node = SovereignTileNode(addr1, fit1, initial_fuel=0)
        stalled_node.is_apoptotic = True

        healthy_node = SovereignTileNode(addr2, fit2, initial_fuel=10_000)

        # Bypass stalled node
        replacement = QuorumOracle.speculative_bypass(
            stalled_node=stalled_node,
            candidate_replacements=[stalled_node, healthy_node],
        )

        self.assertIsNotNone(replacement)
        self.assertEqual(replacement.address.to_string(), addr2.to_string())


if __name__ == "__main__":
    unittest.main()
