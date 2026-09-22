"""
Unit tests for the Hierarchical Substitution Grammar Engine.
"""

import unittest
from geometry.spectre_hierarchy import (
    HierarchicalAddress,
    HierarchyEngine,
    compose_transforms,
)
from geometry.spectre import SpectreTransform


class TestHierarchicalGrammar(unittest.TestCase):

    def test_address_roundtrip(self):
        addr_str = "G0.M2.S5.T7"
        addr = HierarchicalAddress.from_string(addr_str)
        self.assertEqual(addr.giga_idx, 0)
        self.assertEqual(addr.mega_idx, 2)
        self.assertEqual(addr.super_idx, 5)
        self.assertEqual(addr.tile_idx, 7)
        self.assertEqual(addr.to_string(), addr_str)

    def test_address_hierarchical_relationships(self):
        t1 = HierarchicalAddress.from_string("G0.M1.S2.T0")
        t2 = HierarchicalAddress.from_string("G0.M1.S2.T4")
        t3 = HierarchicalAddress.from_string("G0.M1.S3.T0")
        t4 = HierarchicalAddress.from_string("G1.M1.S2.T0")

        self.assertTrue(t1.is_sibling(t2))
        self.assertFalse(t1.is_sibling(t3))
        self.assertTrue(t1.is_cousin(t3))
        self.assertFalse(t1.is_cousin(t4))

        self.assertEqual(t1.super_tile_address, "G0.M1.S2")
        self.assertEqual(t1.mega_tile_address, "G0.M1")
        self.assertEqual(t1.giga_tile_address, "G0")

    def test_linear_index_uniqueness(self):
        indices = set()
        for g in range(1):
            for m in range(2):
                for s in range(4):
                    for t in range(8):
                        addr = HierarchicalAddress(g, m, s, t)
                        idx = addr.linear_index()
                        self.assertNotIn(idx, indices)
                        indices.add(idx)

    def test_transform_composition(self):
        t1 = SpectreTransform(x=1.0, y=2.0, rotation_index=2)  # 60 degrees
        t2 = SpectreTransform(x=2.0, y=0.0, rotation_index=4)  # 120 degrees
        t_comp = compose_transforms(t1, t2)
        # Total rotation should be (2 + 4) % 12 = 6 (180 degrees)
        self.assertEqual(t_comp.rotation_index, 6)

    def test_supertile_generation(self):
        supertile_tiles = HierarchyEngine.get_supertile_polygons(giga_idx=0, mega_idx=0, super_idx=0)
        self.assertEqual(len(supertile_tiles), 8)
        for addr, poly in supertile_tiles:
            self.assertEqual(len(poly.vertices), 14)
            self.assertEqual(len(poly.edges), 14)
            # Centroid should be finite and valid
            cx, cy = poly.get_centroid()
            self.assertTrue(abs(cx) < 50.0)
            self.assertTrue(abs(cy) < 50.0)

    def test_megatile_generation(self):
        megatile_tiles = HierarchyEngine.get_megatile_polygons(giga_idx=0, mega_idx=0)
        self.assertEqual(len(megatile_tiles), 64)
        # Verify all addresses are unique
        addrs = set(addr.to_string() for addr, _ in megatile_tiles)
        self.assertEqual(len(addrs), 64)


if __name__ == "__main__":
    unittest.main()
