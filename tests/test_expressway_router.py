"""
Unit tests for the Hierarchical Super-Tile Expressway (HSTE) Router.
"""

import unittest
from routing.expressway_router import HierarchicalExpresswayRouter


class TestExpresswayRouter(unittest.TestCase):

    def test_intra_supertile_direct_hop(self):
        # Siblings in same Super-Tile: G0.M0.S0.T0 -> G0.M0.S0.T4
        src = "G0.M0.S0.T0"
        dst = "G0.M0.S0.T4"

        trace = HierarchicalExpresswayRouter.route(src, dst)
        self.assertTrue(trace.success)
        self.assertEqual(trace.divergence_level, 0)
        self.assertEqual(trace.total_hops, 1)
        self.assertEqual(trace.hops[0].action, "DIRECT_CONTACT")
        self.assertEqual(trace.hops[0].layer_name, "ATOMIC_EDGE")

    def test_inter_supertile_macro_expressway(self):
        # Cousins in same Mega-Tile, different Super-Tile: G0.M0.S0.T1 -> G0.M0.S3.T5
        src = "G0.M0.S0.T1"
        dst = "G0.M0.S3.T5"

        trace = HierarchicalExpresswayRouter.route(src, dst)
        self.assertTrue(trace.success)
        self.assertEqual(trace.divergence_level, 1)
        self.assertEqual(trace.total_hops, 3)

        # Step 1: Ascend, Step 2: Cross Macro-Boundary, Step 3: Descend
        self.assertEqual(trace.hops[0].action, "ASCEND_TO_MACRO")
        self.assertEqual(trace.hops[1].action, "CROSS_MACRO_BOUNDARY")
        self.assertEqual(trace.hops[2].action, "DESCEND_TO_TARGET")

    def test_inter_megatile_macro_expressway(self):
        # Different Mega-Tiles: G0.M1.S0.T2 -> G0.M5.S2.T7
        src = "G0.M1.S0.T2"
        dst = "G0.M5.S2.T7"

        trace = HierarchicalExpresswayRouter.route(src, dst)
        self.assertTrue(trace.success)
        self.assertEqual(trace.divergence_level, 2)
        self.assertEqual(trace.total_hops, 5)

    def test_scale_free_logarithmic_efficiency(self):
        # In a 512-tile Giga-Tile lattice, planar naive hops could be up to 45 hops.
        # With HSTE, hops are capped at 1 + 2*D = 7 hops max!
        src = "G0.M0.S0.T0"
        dst = "G1.M7.S7.T7"

        trace = HierarchicalExpresswayRouter.route(src, dst)
        self.assertTrue(trace.success)
        self.assertEqual(trace.total_hops, 7)
        self.assertLessEqual(trace.total_hops, 10, "Routing must scale logarithmically, not linearly or square-root")


if __name__ == "__main__":
    unittest.main()
