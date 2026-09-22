"""
Unit tests for the Topological Sybil Resistance & Proof of Geometric Fit Engine.
"""

import unittest
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.spectre import SpectreTransform, SpectrePolygon
from geometry.topological_proof import (
    TopologicalVerifier,
    compute_polygon_hash,
)


class TestTopologicalProof(unittest.TestCase):

    def setUp(self):
        # Generate an existing valid 8-tile supertile
        self.supertile = HierarchyEngine.get_supertile_polygons(giga_idx=0, mega_idx=0, super_idx=0)
        self.existing_map = {addr.to_string(): poly for addr, poly in self.supertile}

    def test_valid_tiles_satisfy_invariants(self):
        for addr, poly in self.supertile:
            proof = TopologicalVerifier.verify_tile(addr, poly, self.existing_map)
            self.assertTrue(proof.is_edge_length_valid, f"Edge length failed for {addr}: {proof.rejection_reason}")
            self.assertTrue(proof.is_angle_valid, f"Angle failed for {addr}: {proof.rejection_reason}")
            self.assertTrue(proof.is_non_overlapping, f"Overlap failed for {addr}: {proof.rejection_reason}")
            self.assertTrue(proof.is_polarity_valid, f"Polarity failed for {addr}: {proof.rejection_reason}")
            self.assertTrue(proof.is_fully_valid, f"Full proof failed for {addr}: {proof.rejection_reason}")
            self.assertTrue(len(proof.polygon_hash) == 64)

    def test_touching_contacts_exist(self):
        # In an 8-tile supertile, all tiles should have at least 1 touching neighbor
        total_contacts = 0
        for addr, poly in self.supertile:
            proof = TopologicalVerifier.verify_tile(addr, poly, self.existing_map)
            total_contacts += len(proof.neighbor_contacts)
            self.assertGreater(len(proof.neighbor_contacts), 0, f"Tile {addr} has zero touching neighbors")
            for contact in proof.neighbor_contacts:
                self.assertTrue(contact.is_polarity_valid)
                self.assertEqual(contact.local_polarity + contact.neighbor_polarity, 0)
        self.assertGreaterEqual(total_contacts, 16)

    def test_reject_penetrating_overlapping_tile(self):
        # Try to place a rogue tile with address G0.M0.S1.T0 right on top of slot 0
        rogue_addr = HierarchicalAddress.from_string("G0.M0.S1.T0")
        rogue_poly = HierarchyEngine.get_polygon(HierarchicalAddress.from_string("G0.M0.S0.T0"))
        proof = TopologicalVerifier.verify_tile(rogue_addr, rogue_poly, self.existing_map)
        self.assertFalse(proof.is_fully_valid)
        self.assertFalse(proof.is_non_overlapping)
        self.assertIn("penetration", proof.rejection_reason.lower())

    def test_reject_distorted_edge_length(self):
        # Create a polygon with distorted coordinates
        addr = HierarchicalAddress.from_string("G0.M0.S0.T0")
        poly = HierarchyEngine.get_polygon(addr)
        # Hack internal vertex
        poly.vertices[0] = (poly.vertices[0][0] + 0.5, poly.vertices[0][1])
        poly._edges = None  # Force recompute
        proof = TopologicalVerifier.verify_tile(addr, poly, {})
        self.assertFalse(proof.is_edge_length_valid)
        self.assertFalse(proof.is_fully_valid)


if __name__ == "__main__":
    unittest.main()
