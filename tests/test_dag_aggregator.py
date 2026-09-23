"""
Unit tests for the Dynamic Hierarchical Merkle-DAG Amalgamator.
"""

import unittest
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier
from pqc_crypto.spatial_identity import SpatialNodeIdentity
from ledger.micro_block import MicroBlockHeader, MicroBlockPayload, AtomicMicroBlock
from ledger.dag_aggregator import (
    DAGAggregator,
    compute_merkle_root,
    generate_merkle_proof,
    verify_merkle_proof,
)


class TestDAGAggregator(unittest.TestCase):

    def _create_dummy_block(self, addr_str: str, lemma: int, status: str = "APPROVED") -> AtomicMicroBlock:
        addr = HierarchicalAddress.from_string(addr_str)
        poly = HierarchyEngine.get_polygon(addr)
        proof = TopologicalVerifier.verify_tile(addr, poly, {})
        node = SpatialNodeIdentity(addr, proof)

        header = MicroBlockHeader(
            parent_block_hash="0" * 64,
            tile_address=addr_str,
            ingress_port=1,
            egress_port=8,
            epoch_index=0,
            gas_consumed=10,
            fuel_after=99_000,
        )
        payload = MicroBlockPayload(
            input_state_hash="a" * 64,
            proposed_lemma=lemma,
            confidence_score=90,
            verified_lemmas=[lemma],
            vm_bytecode_hash="b" * 64,
            proof_status=status,
        )
        return AtomicMicroBlock.create(header, payload, node.certificate)

    def test_dynamic_variable_length_super_block(self):
        # Assemble a dynamic coalition of 6 participating tiles (variable length, shifting coalition!)
        blocks = [
            self._create_dummy_block(f"G0.M0.S0.T{i}", lemma=i * 10)
            for i in range(6)
        ]

        super_block = DAGAggregator.assemble_super_block(
            coalition_id="coalition-physics-epoch-1",
            micro_blocks=blocks,
            quorum_threshold=0.75,
        )

        self.assertEqual(super_block.level, 1)
        self.assertEqual(len(super_block.participant_addresses), 6)
        self.assertEqual(len(super_block.member_hashes), 6)
        self.assertTrue(super_block.is_quorate)
        self.assertEqual(len(super_block.merkle_root), 64)

    def test_dynamic_mega_block_assembly(self):
        # Create two Super-Blocks with different shifting coalitions
        super_block_1 = DAGAggregator.assemble_super_block(
            coalition_id="coalition-ethics",
            micro_blocks=[self._create_dummy_block(f"G0.M0.S0.T{i}", lemma=i) for i in range(5)],
        )
        super_block_2 = DAGAggregator.assemble_super_block(
            coalition_id="coalition-epistemology",
            micro_blocks=[self._create_dummy_block(f"G0.M0.S1.T{i}", lemma=i + 50) for i in range(7)],
        )

        # Assemble into a Level-2 Mega-Block
        mega_block = DAGAggregator.assemble_macro_block(
            coalition_id="macro-philosophy-mega-0",
            level=2,
            child_blocks=[super_block_1, super_block_2],
        )

        self.assertEqual(mega_block.level, 2)
        self.assertEqual(mega_block.level_name, "MEGA_BLOCK")
        self.assertEqual(len(mega_block.member_hashes), 2)
        self.assertTrue(mega_block.is_quorate)
        self.assertEqual(len(mega_block.merkle_root), 64)

    def test_causal_lineage_proof_verification(self):
        # Create 7 dynamic blocks in an active thinking loop
        blocks = [
            self._create_dummy_block(f"G0.M0.S0.T{i}", lemma=100 + i)
            for i in range(7)
        ]
        super_block = DAGAggregator.assemble_super_block(
            coalition_id="coalition-quantum-loop",
            micro_blocks=blocks,
        )

        # Generate proof for Tile 3
        target_block = blocks[3]
        lineage_proof = DAGAggregator.generate_lineage_proof(super_block, target_block)

        # Verify lineage proof evaluates to True
        self.assertTrue(DAGAggregator.verify_lineage(lineage_proof))

        # Tampering with target block lemma must break lineage proof
        target_block.payload.proposed_lemma = 9999
        self.assertFalse(DAGAggregator.verify_lineage(lineage_proof), "Tampered block must fail lineage verification")

    def test_merkle_tree_odd_leaves(self):
        # Test Merkle root calculation with odd leaf count
        leaves = ["a" * 64, "b" * 64, "c" * 64]
        root = compute_merkle_root(leaves)
        self.assertEqual(len(root), 64)

        # Test proof generation and verification for 3 leaves
        proof = generate_merkle_proof(leaves, leaves[1])
        self.assertTrue(verify_merkle_proof(leaves[1], proof, root))


if __name__ == "__main__":
    unittest.main()
