"""
Unit tests for the Airlock Severing & Apoptosis Protocol.
"""

import unittest
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier
from engine.node_runtime import SovereignTileNode, PortPacket
from consensus.fuel_ledger import FuelLedger
from consensus.apoptosis import ApoptosisEngine


class TestApoptosis(unittest.TestCase):

    def setUp(self):
        self.ledger = FuelLedger()
        self.apoptosis = ApoptosisEngine(self.ledger)

        self.addr1 = "G0.M0.S0.T0"
        self.addr2 = "G0.M0.S0.T1"

        h_addr1 = HierarchicalAddress.from_string(self.addr1)
        h_addr2 = HierarchicalAddress.from_string(self.addr2)

        poly1 = HierarchyEngine.get_polygon(h_addr1)
        poly2 = HierarchyEngine.get_polygon(h_addr2)

        fit1 = TopologicalVerifier.verify_tile(h_addr1, poly1, {})
        fit2 = TopologicalVerifier.verify_tile(h_addr2, poly2, {self.addr1: poly1})

        # Node 1 is healthy; Node 2 has critically low fuel (5 units)
        self.node1 = SovereignTileNode(h_addr1, fit1, initial_fuel=10_000)
        self.node2 = SovereignTileNode(h_addr2, fit2, initial_fuel=5)

        self.ledger.register_node(self.addr1, initial_fuel=10_000)
        self.ledger.register_node(self.addr2, initial_fuel=5)

        # Connect mutual ports
        self.node1.connect_neighbor(port_idx=1, neighbor_cert=self.node2.identity.certificate)
        self.node2.connect_neighbor(port_idx=8, neighbor_cert=self.node1.identity.certificate)

        self.cluster = {self.addr1: self.node1, self.addr2: self.node2}

    def test_inter_prompt_sweep_triggers_unilateral_severing(self):
        # Node 1 port 1 is currently connected to Node 2
        self.assertIsNotNone(self.node1.port_neighbors[1])

        # Run inter-prompt sweep: Node 2 burns 10 fuel from 5 -> insolvency
        events = self.apoptosis.run_inter_prompt_sweep(self.cluster)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].insolvent_address, self.addr2)
        self.assertTrue(self.node2.is_apoptotic)

        # UNILATERAL PORT SEVERING: Node 1 must have severed port connection to Node 2!
        self.assertIsNone(self.node1.port_neighbors[1], "Healthy neighbor must sever port connection to insolvent node")

        # Slot must be designated as a Tombstone Slot
        self.assertTrue(self.apoptosis.is_tombstone(self.addr2))

    def test_apoptotic_node_rejects_ingress(self):
        # Trigger apoptosis on Node 2
        self.node2.is_apoptotic = True

        dummy_packet = PortPacket(
            source_address=self.addr1,
            target_address=self.addr2,
            egress_port=1,
            ingress_port=8,
            envelope={},
        )
        receipt = self.node2.process_ingress(dummy_packet)
        self.assertEqual(receipt.status, "VETOED")
        self.assertIn("ERR_NODE_APOPTOTIC", receipt.rejection_reason)


if __name__ == "__main__":
    unittest.main()
