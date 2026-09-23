"""
Unit tests for the Evolutionary Tombstone Re-Minting Protocol.
"""

import unittest
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier
from engine.node_runtime import SovereignTileNode
from engine.neural_policy import INT8_PARAM_COUNT
from consensus.fuel_ledger import FuelLedger
from consensus.apoptosis import ApoptosisEngine
from consensus.re_minting import ReMintingEngine, blend_and_mutate_weights, RE_MINT_SEED_FUEL


class TestReMinting(unittest.TestCase):

    def setUp(self):
        self.ledger = FuelLedger()
        self.apoptosis = ApoptosisEngine(self.ledger)
        self.re_minter = ReMintingEngine(self.ledger, self.apoptosis)

        self.addr1 = "G0.M0.S0.T0"
        self.addr2 = "G0.M0.S0.T1"

        h_addr1 = HierarchicalAddress.from_string(self.addr1)
        h_addr2 = HierarchicalAddress.from_string(self.addr2)

        poly1 = HierarchyEngine.get_polygon(h_addr1)
        poly2 = HierarchyEngine.get_polygon(h_addr2)

        fit1 = TopologicalVerifier.verify_tile(h_addr1, poly1, {})
        fit2 = TopologicalVerifier.verify_tile(h_addr2, poly2, {self.addr1: poly1})

        self.node1 = SovereignTileNode(h_addr1, fit1, seed_domain="parent_domain")
        self.node2 = SovereignTileNode(h_addr2, fit2, seed_domain="dying_domain")

        self.ledger.register_node(self.addr1, initial_fuel=10_000)
        self.ledger.register_node(self.addr2, initial_fuel=0)

        self.cluster = {self.addr1: self.node1, self.addr2: self.node2}

        # Kill node 2 and designate as tombstone
        self.apoptosis.run_inter_prompt_sweep(self.cluster)
        self.assertTrue(self.apoptosis.is_tombstone(self.addr2))

    def test_weight_blending_and_mutation(self):
        parent1 = b"\x10" * INT8_PARAM_COUNT
        parent2 = b"\x20" * INT8_PARAM_COUNT

        child = blend_and_mutate_weights([parent1, parent2], mutation_rate=0.01)
        self.assertEqual(len(child), INT8_PARAM_COUNT)

        # Most weights should be average of 0x10 (16) and 0x20 (32) = 24 (0x18)
        avg_sample = child[100]
        self.assertTrue(abs(avg_sample - 24) < 10)

    def test_remint_tombstone_reclaims_slot(self):
        old_kem_pk = self.node2.identity.certificate.kem_public_key_hex

        # Re-mint the tombstone slot inheriting from Node 1
        new_node = self.re_minter.remint_tombstone(
            tombstone_address_str=self.addr2,
            node_cluster=self.cluster,
            neighbor_addresses=[self.addr1],
            seed_domain="evolved_agent_slot1",
        )

        # 1. Slot is no longer a tombstone
        self.assertFalse(self.apoptosis.is_tombstone(self.addr2))

        # 2. Fresh ML-KEM-1024 identity (new key != old dead key)
        self.assertNotEqual(new_node.identity.certificate.kem_public_key_hex, old_kem_pk)

        # 3. Fresh seed fuel credited
        self.assertEqual(new_node.fuel_gauge, RE_MINT_SEED_FUEL)
        self.assertFalse(new_node.is_apoptotic)

        # 4. Port airlock re-established
        self.assertIsNotNone(self.node1.port_neighbors[1])
        self.assertEqual(self.node1.port_neighbors[1].address, self.addr2)

        # 5. Evolved node processes ingress successfully
        packet = self.node1.send_to_port(1, b"[1, 2, 3]", expected_invariant="non_negative")
        receipt = new_node.process_ingress(packet)
        self.assertEqual(receipt.status, "APPROVED")


if __name__ == "__main__":
    unittest.main()
