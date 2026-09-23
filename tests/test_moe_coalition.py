"""
Unit tests for the Ad-Hoc MoE Coalition Coordinator.
"""

import unittest
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier
from engine.node_runtime import SovereignTileNode
from routing.moe_coalition import MoECoalitionCoordinator


class TestMoECoalition(unittest.TestCase):

    def setUp(self):
        # Instantiate 6 sovereign tiles
        self.nodes = []
        for i in range(6):
            addr = HierarchicalAddress.from_string(f"G0.M0.S0.T{i}")
            poly = HierarchyEngine.get_polygon(addr)
            proof = TopologicalVerifier.verify_tile(addr, poly, {})
            node = SovereignTileNode(addr, proof, seed_domain=f"domain_{i}")
            self.nodes.append(node)

    def test_form_coalition(self):
        coalition = MoECoalitionCoordinator.form_coalition(
            topic="quantum_cryptanalysis",
            available_nodes=self.nodes,
            max_members=5,
        )
        self.assertEqual(len(coalition), 5)

    def test_execute_wavefront_lifecycle(self):
        # Execute the 4-phase wavefront across all 6 tiles
        result = MoECoalitionCoordinator.execute_wavefront(
            coalition_id="wavefront-quantum-epoch-1",
            topic="prime_factorization_bounds",
            coalition_nodes=self.nodes,
            input_vector=[10, 20, 30, 40, 50, 60],
            expected_invariant="non_negative",
            quorum_threshold=0.75,
        )

        # All 6 nodes should reach APPROVED status
        self.assertEqual(result.participant_count, 6)
        self.assertEqual(result.approved_count, 6)
        self.assertTrue(result.is_consensus_reached)
        self.assertTrue(len(result.composite_lemmas) >= 6)
        self.assertEqual(len(result.macro_block.merkle_root), 64)
        self.assertGreater(result.execution_time_ms, 0.0)


if __name__ == "__main__":
    unittest.main()
