"""
Unit tests for P2P Point-to-Point Mesh Transport and Spatial Firewall Enforcement.
"""

import unittest
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier
from engine.node_runtime import SovereignTileNode
from network.p2p_mesh import P2PMeshTransport, P2PMeshLink


class TestP2PMesh(unittest.TestCase):

    def setUp(self):
        # Generate valid 8-tile supertile
        self.supertile = HierarchyEngine.get_supertile_polygons(giga_idx=0, mega_idx=0, super_idx=0)
        self.existing_map = {addr.to_string(): poly for addr, poly in self.supertile}

        # Find two touching tiles from topological verification
        addr_0, poly_0 = self.supertile[0]
        proof_0 = TopologicalVerifier.verify_tile(addr_0, poly_0, self.existing_map)
        self.assertGreater(len(proof_0.neighbor_contacts), 0)

        contact = proof_0.neighbor_contacts[0]
        self.port_a = contact.local_edge_idx
        self.port_b = contact.neighbor_edge_idx
        addr_1 = HierarchicalAddress.from_string(contact.neighbor_address)
        poly_1 = self.existing_map[contact.neighbor_address]
        proof_1 = TopologicalVerifier.verify_tile(addr_1, poly_1, self.existing_map)

        self.node_a = SovereignTileNode(addr_0, proof_0, seed_domain="node_a")
        self.node_b = SovereignTileNode(addr_1, proof_1, seed_domain="node_b")

    def test_successful_geometric_handshake(self):
        # Touching ports should pass spatial firewall
        res = P2PMeshTransport.attempt_geometric_handshake(
            self.node_a, self.port_a,
            self.node_b, self.port_b,
        )
        self.assertTrue(res.is_connected)
        self.assertIsNone(res.rejection_reason)
        self.assertEqual(res.local_port, self.port_a)
        self.assertEqual(res.remote_port, self.port_b)

        # Both nodes should have locked mutual neighbor certificates
        self.assertIsNotNone(self.node_a.port_neighbors[self.port_a])
        self.assertIsNotNone(self.node_b.port_neighbors[self.port_b])

    def test_rejection_spatial_firewall_wrong_port(self):
        # Try connecting with wrong, non-touching ports (e.g. port_a + 1)
        wrong_port_a = (self.port_a + 1) % 14
        res = P2PMeshTransport.attempt_geometric_handshake(
            self.node_a, wrong_port_a,
            self.node_b, self.port_b,
        )
        self.assertFalse(res.is_connected)
        self.assertIsNotNone(res.rejection_reason)
        self.assertIn("ERR_SPATIAL_FIREWALL", res.rejection_reason)

    def test_rejection_spatial_firewall_disjoint_tiles(self):
        # Create a distant node in another supertile
        distant_addr = HierarchicalAddress.from_string("G0.M1.S2.T3")
        distant_poly = HierarchyEngine.get_polygon(distant_addr)
        distant_proof = TopologicalVerifier.verify_tile(distant_addr, distant_poly, {})
        distant_node = SovereignTileNode(distant_addr, distant_proof, seed_domain="distant")

        res = P2PMeshTransport.attempt_geometric_handshake(
            self.node_a, self.port_a,
            distant_node, 0,
        )
        self.assertFalse(res.is_connected)
        self.assertIn("ERR_SPATIAL_FIREWALL", res.rejection_reason)

    def test_p2p_mesh_link_send_and_close(self):
        link = P2PMeshLink(
            local_port=self.port_a,
            remote_port=self.port_b,
            remote_cert=self.node_b.identity.certificate,
        )
        payload = b"binary_wire_frame_content"
        link.send_frame(payload)
        self.assertEqual(link.bytes_transmitted, len(payload))

        link.close()
        self.assertFalse(link.is_active)
        with self.assertRaises(ConnectionError):
            link.send_frame(payload)


if __name__ == "__main__":
    unittest.main()
