"""
Unit tests for the Atomic Micro-Block Schema.
"""

import unittest
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier
from pqc_crypto.spatial_identity import SpatialNodeIdentity
from ledger.micro_block import (
    MicroBlockHeader,
    MicroBlockPayload,
    AtomicMicroBlock,
)


class TestMicroBlock(unittest.TestCase):

    def setUp(self):
        self.addr = HierarchicalAddress.from_string("G0.M0.S0.T0")
        poly = HierarchyEngine.get_polygon(self.addr)
        proof_of_fit = TopologicalVerifier.verify_tile(self.addr, poly, {})
        self.node = SpatialNodeIdentity(self.addr, proof_of_fit)

    def test_create_and_verify_atomic_micro_block(self):
        header = MicroBlockHeader(
            parent_block_hash="0" * 64,
            tile_address=self.addr.to_string(),
            ingress_port=1,
            egress_port=8,
            epoch_index=0,
            gas_consumed=15,
            fuel_after=99_750,
        )
        payload = MicroBlockPayload(
            input_state_hash="a" * 64,
            proposed_lemma=42,
            confidence_score=95,
            verified_lemmas=[42],
            vm_bytecode_hash="b" * 64,
            proof_status="APPROVED",
        )

        block = AtomicMicroBlock.create(header, payload, self.node.certificate)
        self.assertTrue(block.verify())
        self.assertEqual(len(block.block_hash), 64)

    def test_tamper_detection(self):
        header = MicroBlockHeader(
            parent_block_hash="0" * 64,
            tile_address=self.addr.to_string(),
            ingress_port=1,
            egress_port=8,
            epoch_index=0,
            gas_consumed=15,
            fuel_after=99_750,
        )
        payload = MicroBlockPayload(
            input_state_hash="a" * 64,
            proposed_lemma=42,
            confidence_score=95,
            verified_lemmas=[42],
            vm_bytecode_hash="b" * 64,
            proof_status="APPROVED",
        )
        block = AtomicMicroBlock.create(header, payload, self.node.certificate)

        # Tampering with payload lemma breaks verification
        block.payload.proposed_lemma = 999
        self.assertFalse(block.verify(), "Tampered lemma must invalidate micro-block seal")

        # Tampering with gas consumed breaks verification
        block.payload.proposed_lemma = 42
        block.header.gas_consumed = 500
        self.assertFalse(block.verify(), "Tampered gas must invalidate micro-block seal")

    def test_serialization_roundtrip(self):
        header = MicroBlockHeader(
            parent_block_hash="1" * 64,
            tile_address=self.addr.to_string(),
            ingress_port=2,
            egress_port=9,
            epoch_index=1,
            gas_consumed=20,
            fuel_after=99_500,
        )
        payload = MicroBlockPayload(
            input_state_hash="c" * 64,
            proposed_lemma=108,
            confidence_score=99,
            verified_lemmas=[108],
            vm_bytecode_hash="d" * 64,
            proof_status="APPROVED",
        )
        block = AtomicMicroBlock.create(header, payload, self.node.certificate)

        data = block.to_dict()
        restored = AtomicMicroBlock.from_dict(data)

        self.assertEqual(block.block_hash, restored.block_hash)
        self.assertTrue(restored.verify())


if __name__ == "__main__":
    unittest.main()
