import unittest
import math
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from geometry.spectre import (
    SPECTRE_BASE_VERTICES,
    SPECTRE_EDGE_POLARITIES,
    SpectreTransform,
    SpectrePolygon,
    edges_touch_and_align,
    check_polygons_overlap,
    verify_geometric_fit,
    find_valid_open_sites,
)


class TestSpectreGeometry(unittest.TestCase):
    def test_base_polygon_properties(self):
        self.assertEqual(len(SPECTRE_BASE_VERTICES), 14)
        self.assertEqual(len(SPECTRE_EDGE_POLARITIES), 14)

        # Verify each of the 14 edges has unit length 1.0
        poly = SpectrePolygon(SpectreTransform(0, 0, 0))
        for i, edge in enumerate(poly.edges):
            p1, p2 = edge
            length = math.dist(p1, p2)
            self.assertAlmostEqual(length, 1.0, places=3, msg=f"Edge {i} length not 1.0")

    def test_rotational_transform(self):
        poly_0 = SpectrePolygon(SpectreTransform(0, 0, 0))
        poly_12 = SpectrePolygon(SpectreTransform(0, 0, 12))  # 12 * 30° = 360° = 0°
        for v0, v12 in zip(poly_0.vertices, poly_12.vertices):
            self.assertAlmostEqual(v0[0], v12[0], places=4)
            self.assertAlmostEqual(v0[1], v12[1], places=4)

    def test_genesis_fit(self):
        genesis = SpectrePolygon(SpectreTransform(0, 0, 0))
        is_valid, reason, contacts = verify_geometric_fit(genesis, [])
        self.assertTrue(is_valid)
        self.assertEqual(len(contacts), 0)

    def test_identical_overlap_rejection(self):
        tile1 = SpectrePolygon(SpectreTransform(0, 0, 0))
        tile2 = SpectrePolygon(SpectreTransform(0, 0, 0))
        is_valid, reason, _ = verify_geometric_fit(tile2, [tile1])
        self.assertFalse(is_valid)
        self.assertIn("Geometric collision", reason)

    def test_open_site_discovery_and_fit(self):
        genesis = SpectrePolygon(SpectreTransform(0, 0, 0))
        mosaic = [genesis]

        open_sites = find_valid_open_sites(mosaic, max_sites=5)
        self.assertGreater(len(open_sites), 0, "Should discover valid open perimeter sites")

        # Pick the first discovered site and verify it fits perfectly
        neighbor_candidate = open_sites[0]
        is_valid, reason, contacts = verify_geometric_fit(neighbor_candidate, mosaic)
        self.assertTrue(is_valid, f"Candidate failed: {reason}")
        self.assertGreater(len(contacts), 0, "Candidate must touch at least 1 edge")

        # Now add neighbor to mosaic and find next generation of open sites
        mosaic.append(neighbor_candidate)
        next_sites = find_valid_open_sites(mosaic, max_sites=5)
        self.assertGreater(len(next_sites), 0)

        third_tile = next_sites[0]
        is_valid3, reason3, contacts3 = verify_geometric_fit(third_tile, mosaic)
        self.assertTrue(is_valid3, f"Third tile failed: {reason3}")

    def test_gapless_neighborhood_eight_tiles(self):
        """Verifies that an entire 8-tile Neighborhood packs with zero gaps and zero overlaps."""
        mosaic = []
        for i in range(8):
            sites = find_valid_open_sites(mosaic, max_sites=3)
            self.assertGreater(len(sites), 0, f"Slot {i} must find a valid site")
            site = sites[0]
            ok, msg, contacts = verify_geometric_fit(site, mosaic)
            self.assertTrue(ok, f"Slot {i} failed fit: {msg}")
            mosaic.append(site)

        self.assertEqual(len(mosaic), 8)

        # Verify no pair of polygons overlap
        for i in range(len(mosaic)):
            for j in range(i + 1, len(mosaic)):
                self.assertFalse(
                    check_polygons_overlap(mosaic[i], mosaic[j]),
                    f"Tiles {i} and {j} overlap!"
                )


if __name__ == "__main__":
    unittest.main()
