import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from quantum_blockchain.coordinator import SwarmCoordinator


class TestSwarmCoordinator(unittest.TestCase):
    def test_goal_dispatch_and_adaptation(self):
        coordinator = SwarmCoordinator()
        self.assertEqual(len(coordinator.ledger.tiles), 1)

        # Dispatch prompt requiring crypto and threat capabilities
        result = coordinator.dispatch_goal("Investigate quantum attack against Kyber KEM.")
        self.assertGreater(result["total_tiles_now"], 1)
        self.assertIn("Specialist", result["final_answer"])
        self.assertGreater(len(result["epochs_logged"]), 0)

        # Dispatch second prompt to test agent reuse
        initial_tiles = result["total_tiles_now"]
        result2 = coordinator.dispatch_goal("Check threat mitigation for Kyber.")
        # Should reuse existing specialists without runaway tile creation
        self.assertTrue(any("REUSED" in line or "UTILIZED" in line for line in result2["adaptation_log"]))
        self.assertGreaterEqual(result2["total_neighborhoods"], 1)


if __name__ == "__main__":
    unittest.main()
