"""
Dynamic Hierarchical Merkle-DAG Amalgamator.
Aggregates atomic micro-blocks into dynamic, shifting coalitions:
Super-Blocks (Level 1), Mega-Blocks (Level 2), Giga-Blocks (Level 3), etc.
Coalitions are ephemeral and shift dynamically around the prompt's active thinking loop.
Provides complete causal lineage proofs unrolling macro-consensus down to individual lemmas.
"""

import time
import hashlib
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional, Union
from ledger.micro_block import AtomicMicroBlock


def sha3_pair(left: str, right: str) -> str:
    """Computes SHA3-256 hash of two concatenated hexadecimal hashes."""
    combined = bytes.fromhex(left) + bytes.fromhex(right)
    return hashlib.sha3_256(combined).hexdigest()


def compute_merkle_root(leaf_hashes: List[str]) -> str:
    """
    Computes a binary SHA3-256 Merkle root over a dynamic, variable-length list of leaf hashes.
    If the number of leaves is odd, the last leaf is duplicated to complete the pair.
    """
    if not leaf_hashes:
        return hashlib.sha3_256(b"EMPTY_MERKLE_TREE").hexdigest()

    current_level = list(leaf_hashes)

    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else current_level[i]
            next_level.append(sha3_pair(left, right))
        current_level = next_level

    return current_level[0]


def build_merkle_tree(leaf_hashes: List[str]) -> List[List[str]]:
    """Builds and returns all levels of the Merkle tree from leaves to root."""
    if not leaf_hashes:
        return [[hashlib.sha3_256(b"EMPTY_MERKLE_TREE").hexdigest()]]

    tree = [list(leaf_hashes)]
    while len(tree[-1]) > 1:
        current_level = tree[-1]
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else current_level[i]
            next_level.append(sha3_pair(left, right))
        tree.append(next_level)
    return tree


def generate_merkle_proof(leaf_hashes: List[str], target_hash: str) -> List[Tuple[str, str]]:
    """
    Generates a cryptographic Merkle audit path for target_hash.
    Returns a list of tuples: (sibling_hash, direction) where direction is 'L' (left) or 'R' (right).
    """
    if target_hash not in leaf_hashes:
        raise ValueError(f"Target hash {target_hash} not found in leaves.")

    tree = build_merkle_tree(leaf_hashes)
    idx = leaf_hashes.index(target_hash)
    proof: List[Tuple[str, str]] = []

    for level in tree[:-1]:
        if idx % 2 == 0:
            # Sibling is to the right
            sibling_idx = idx + 1 if idx + 1 < len(level) else idx
            proof.append((level[sibling_idx], "R"))
        else:
            # Sibling is to the left
            proof.append((level[idx - 1], "L"))
        idx //= 2

    return proof


def verify_merkle_proof(leaf_hash: str, proof: List[Tuple[str, str]], expected_root: str) -> bool:
    """Verifies that a Merkle audit path resolves exactly to expected_root."""
    current = leaf_hash
    for sibling, direction in proof:
        if direction == "R":
            current = sha3_pair(current, sibling)
        else:
            current = sha3_pair(sibling, current)
    return current == expected_root


@dataclass
class DynamicCoalitionBlock:
    """
    A dynamic, shifting macro-block aggregating a variable-length coalition of participants.
    Can represent a Level-1 Super-Block (e.g. 5–9 tiles), Level-2 Mega-Block, or higher.
    """
    coalition_id: str                   # E.g. "coalition-niezsche-prompt-88"
    level: int                          # 1 = Super-Block, 2 = Mega-Block, 3 = Giga-Block...
    level_name: str                     # "SUPER_BLOCK" | "MEGA_BLOCK" | "GIGA_BLOCK"
    participant_addresses: List[str]    # Dynamic list of member coordinates
    member_hashes: List[str]            # Block hashes of participating units
    merkle_root: str                    # SHA3-256 Merkle root
    approved_count: int                 # Count of participants with "APPROVED" status
    quorum_threshold: float = 0.75      # Required approval ratio (e.g. 75%)
    timestamp: float = field(default_factory=time.time)

    @property
    def is_quorate(self) -> bool:
        if not self.participant_addresses:
            return False
        ratio = self.approved_count / float(len(self.participant_addresses))
        return ratio >= self.quorum_threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coalition_id": self.coalition_id,
            "level": self.level,
            "level_name": self.level_name,
            "participant_addresses": self.participant_addresses,
            "member_hashes": self.member_hashes,
            "merkle_root": self.merkle_root,
            "approved_count": self.approved_count,
            "quorum_threshold": self.quorum_threshold,
            "is_quorate": self.is_quorate,
            "timestamp": self.timestamp,
        }


@dataclass
class LineageProof:
    """Complete causal lineage receipt proving an atomic lemma was part of macro-consensus."""
    macro_root: str
    coalition_id: str
    level: int
    target_address: str
    target_block_hash: str
    merkle_proof: List[Tuple[str, str]]
    atomic_micro_block: Optional[AtomicMicroBlock] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "macro_root": self.macro_root,
            "coalition_id": self.coalition_id,
            "level": self.level,
            "target_address": self.target_address,
            "target_block_hash": self.target_block_hash,
            "merkle_proof": self.merkle_proof,
            "atomic_micro_block": self.atomic_micro_block.to_dict() if self.atomic_micro_block else None,
        }


class DAGAggregator:
    """Amalgamator engine organizing shifting dynamic coalitions into hierarchical Merkle-DAGs."""

    LEVEL_NAMES = {
        1: "SUPER_BLOCK",
        2: "MEGA_BLOCK",
        3: "GIGA_BLOCK",
        4: "TERA_BLOCK",
        5: "PETA_BLOCK",
    }

    @classmethod
    def assemble_super_block(
        cls,
        coalition_id: str,
        micro_blocks: List[AtomicMicroBlock],
        quorum_threshold: float = 0.75,
    ) -> DynamicCoalitionBlock:
        """
        Dynamically aggregates a variable-length list of micro-blocks (e.g. 5 to 9 tiles)
        into a Level-1 Super-Block.
        """
        addresses = [
            b.header.tile_address if hasattr(b, "header") else b.node_address
            for b in micro_blocks
        ]
        hashes = [b.block_hash for b in micro_blocks]
        approved = sum(
            1 for b in micro_blocks
            if (b.payload.proof_status if hasattr(b, "payload") else b.status) == "APPROVED"
        )

        root = compute_merkle_root(hashes)
        return DynamicCoalitionBlock(
            coalition_id=coalition_id,
            level=1,
            level_name=cls.LEVEL_NAMES.get(1, "SUPER_BLOCK"),
            participant_addresses=addresses,
            member_hashes=hashes,
            merkle_root=root,
            approved_count=approved,
            quorum_threshold=quorum_threshold,
        )

    @classmethod
    def assemble_macro_block(
        cls,
        coalition_id: str,
        level: int,
        child_blocks: List[Union[DynamicCoalitionBlock, AtomicMicroBlock]],
        quorum_threshold: float = 0.75,
    ) -> DynamicCoalitionBlock:
        """
        Dynamically aggregates child blocks into higher-order coalitions:
        Mega-Blocks (Level 2), Giga-Blocks (Level 3), etc.
        """
        addresses: List[str] = []
        hashes: List[str] = []
        approved = 0

        for child in child_blocks:
            if isinstance(child, DynamicCoalitionBlock):
                addresses.extend(child.participant_addresses)
                hashes.append(child.merkle_root)
                approved += child.approved_count
            else:
                addresses.append(child.header.tile_address)
                hashes.append(child.block_hash)
                if child.payload.proof_status == "APPROVED":
                    approved += 1

        root = compute_merkle_root(hashes)
        return DynamicCoalitionBlock(
            coalition_id=coalition_id,
            level=level,
            level_name=cls.LEVEL_NAMES.get(level, f"LEVEL_{level}_BLOCK"),
            participant_addresses=addresses,
            member_hashes=hashes,
            merkle_root=root,
            approved_count=approved,
            quorum_threshold=quorum_threshold,
        )

    @classmethod
    def generate_lineage_proof(
        cls,
        super_block: DynamicCoalitionBlock,
        target_micro_block: AtomicMicroBlock,
    ) -> LineageProof:
        """Generates a verifiable Merkle audit proof linking an atomic micro-block to a macro root."""
        proof_path = generate_merkle_proof(
            leaf_hashes=super_block.member_hashes,
            target_hash=target_micro_block.block_hash,
        )
        return LineageProof(
            macro_root=super_block.merkle_root,
            coalition_id=super_block.coalition_id,
            level=super_block.level,
            target_address=target_micro_block.header.tile_address,
            target_block_hash=target_micro_block.block_hash,
            merkle_proof=proof_path,
            atomic_micro_block=target_micro_block,
        )

    @classmethod
    def verify_lineage(cls, proof: LineageProof) -> bool:
        """
        Verifies complete causal lineage:
        1. Checks that the embedded micro-block internally verifies.
        2. Evaluates the Merkle audit path to ensure it resolves to macro_root.
        """
        if proof.atomic_micro_block is not None:
            if not proof.atomic_micro_block.verify():
                return False
            if proof.atomic_micro_block.block_hash != proof.target_block_hash:
                return False

        return verify_merkle_proof(
            leaf_hash=proof.target_block_hash,
            proof=proof.merkle_proof,
            expected_root=proof.macro_root,
        )
