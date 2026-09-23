"""
The Atomic Micro-Block Schema.
Fuses state execution and blockchain storage into a single atomic event:
Computing a verified transition and committing an on-chain micro-block are identical.
Sealed with pure ML-KEM-1024 spatial commitments and SHA3-256 state hashes.
"""

import time
import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pqc_crypto.spatial_identity import SpatialCertificate, STRICT_KEM_ALG


@dataclass
class MicroBlockHeader:
    """Header of the atomic micro-block."""
    parent_block_hash: str          # SHA3-256 of the tile's previous micro-block
    tile_address: str               # Hierarchical coordinate (e.g. "G0.M0.S0.T1")
    ingress_port: int               # Port (0..13) where input was received
    egress_port: int                # Port (0..13) where output was dispatched
    epoch_index: int                # Monotonically increasing local epoch
    gas_consumed: int               # Gas consumed by SpectreVM (<= 500)
    fuel_after: int                 # Remaining fuel gauge balance
    timestamp: float = field(default_factory=time.time)

    def canonical_bytes(self) -> bytes:
        data = {
            "parent_block_hash": self.parent_block_hash,
            "tile_address": self.tile_address,
            "ingress_port": self.ingress_port,
            "egress_port": self.egress_port,
            "epoch_index": self.epoch_index,
            "gas_consumed": self.gas_consumed,
            "fuel_after": self.fuel_after,
            "timestamp": round(self.timestamp, 4),
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def hash(self) -> str:
        return hashlib.sha3_256(self.canonical_bytes()).hexdigest()


@dataclass
class MicroBlockPayload:
    """Cognitive and symbolic verification payload of the transition."""
    input_state_hash: str           # SHA3-256 of decrypted input vector
    proposed_lemma: int             # Lemma proposed by INT8 neural policy
    confidence_score: int           # Heuristic confidence (0..100)
    verified_lemmas: List[int]      # Emitted by SpectreVM
    vm_bytecode_hash: str           # SHA3-256 of executed bytecode
    proof_status: str               # "APPROVED" | "VETOED"
    rejection_reason: Optional[str] = None

    def canonical_bytes(self) -> bytes:
        data = {
            "input_state_hash": self.input_state_hash,
            "proposed_lemma": self.proposed_lemma,
            "confidence_score": self.confidence_score,
            "verified_lemmas": self.verified_lemmas,
            "vm_bytecode_hash": self.vm_bytecode_hash,
            "proof_status": self.proof_status,
            "rejection_reason": self.rejection_reason,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def hash(self) -> str:
        return hashlib.sha3_256(self.canonical_bytes()).hexdigest()


@dataclass
class MicroBlockSeal:
    """Cryptographic seal binding the block to the tile's pure ML-KEM-1024 spatial certificate."""
    spatial_commitment: str         # From SpatialCertificate (SHA3-256)
    kem_public_key_hex: str         # ML-KEM-1024 PK (1568 bytes hex)
    block_hash: str                 # SHA3-256(header_hash || payload_hash || spatial_commitment)

    def verify(self, header_hash: str, payload_hash: str) -> bool:
        expected = hashlib.sha3_256(
            f"{header_hash}::{payload_hash}::{self.spatial_commitment}".encode("utf-8")
        ).hexdigest()
        return expected == self.block_hash


@dataclass
class AtomicMicroBlock:
    """Complete sovereign on-chain micro-block."""
    header: MicroBlockHeader
    payload: MicroBlockPayload
    seal: MicroBlockSeal

    @classmethod
    def create(
        cls,
        header: MicroBlockHeader,
        payload: MicroBlockPayload,
        certificate: SpatialCertificate,
    ) -> "AtomicMicroBlock":
        if certificate.kem_algorithm != STRICT_KEM_ALG:
            raise ValueError(f"Block seal requires pure ML-KEM-1024, received {certificate.kem_algorithm}")

        h_hash = header.hash()
        p_hash = payload.hash()
        block_hash = hashlib.sha3_256(
            f"{h_hash}::{p_hash}::{certificate.spatial_commitment_hex}".encode("utf-8")
        ).hexdigest()

        seal = MicroBlockSeal(
            spatial_commitment=certificate.spatial_commitment_hex,
            kem_public_key_hex=certificate.kem_public_key_hex,
            block_hash=block_hash,
        )
        return cls(header=header, payload=payload, seal=seal)

    @property
    def block_hash(self) -> str:
        return self.seal.block_hash

    def verify(self) -> bool:
        """Verifies the micro-block's structural and cryptographic integrity."""
        h_hash = self.header.hash()
        p_hash = self.payload.hash()
        return self.seal.verify(h_hash, p_hash)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "header": asdict(self.header),
            "payload": asdict(self.payload),
            "seal": asdict(self.seal),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AtomicMicroBlock":
        header = MicroBlockHeader(**data["header"])
        payload = MicroBlockPayload(**data["payload"])
        seal = MicroBlockSeal(**data["seal"])
        return cls(header=header, payload=payload, seal=seal)
