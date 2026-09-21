import time
import json
import hashlib
import binascii
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple

from geometry.spectre import SpectreTransform, SpectrePolygon
from pqc_crypto.crypto_utils import (
    sign_payload,
    verify_payload,
    encrypt_dual_envelope,
    decrypt_dual_envelope,
    encrypt_envelope,
    decrypt_envelope,
)


class TileStatus(str, Enum):
    ACTIVE = "ACTIVE"
    QUARANTINED = "QUARANTINED"
    HIBERNATED = "HIBERNATED"
    MONUMENT = "MONUMENT"


class SpectreTile:
    """
    Represents an autonomous AI Agent born onto the aperiodic Spectre ledger.
    Acts as the agent's spatial block anchor, decentralized PKI, and network port.
    """

    def __init__(
        self,
        index: int,
        agent_alias: str,
        transform: SpectreTransform,
        ml_kem_public_key: bytes,
        ml_dsa_public_key: bytes,
        system_prompt_commitment: str,
        timestamp: Optional[float] = None,
        previous_block_hash: str = "0",
    ):
        self.index = index
        self.agent_alias = agent_alias
        self.transform = transform
        self.polygon = SpectrePolygon(self.transform)
        self.ml_kem_public_key = ml_kem_public_key
        self.ml_dsa_public_key = ml_dsa_public_key
        self.system_prompt_commitment = system_prompt_commitment
        self.timestamp = timestamp or time.time()
        self.previous_block_hash = previous_block_hash
        self.neighborhood_index = index // 8
        self.neighborhood_slot = index % 8

        # Map of edge_idx (0..13) -> {"neighbor_tile_id": str, "neighbor_edge_idx": int}
        self.edge_connections: Dict[int, Dict[str, Any]] = {}
        self.status = TileStatus.ACTIVE
        self.proposer_signature: Optional[bytes] = None

        self.tile_id = self.calculate_tile_id()

    def _header_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "agent_alias": self.agent_alias,
            "neighborhood_index": self.neighborhood_index,
            "neighborhood_slot": self.neighborhood_slot,
            "neighborhood_name": f"Neighborhood-{self.neighborhood_index}",
            "transform": self.transform.to_dict(),
            "ml_kem_pk": binascii.hexlify(self.ml_kem_public_key).decode("ascii"),
            "ml_dsa_pk": binascii.hexlify(self.ml_dsa_public_key).decode("ascii"),
            "prompt_commitment": self.system_prompt_commitment,
            "timestamp": self.timestamp,
            "previous_block_hash": self.previous_block_hash,
        }

    def calculate_tile_id(self) -> str:
        header_bytes = json.dumps(self._header_dict(), sort_keys=True).encode("utf-8")
        return hashlib.sha256(header_bytes).hexdigest()

    def sign_tile(self, proposer_dsa_sk: bytes) -> None:
        msg = bytes.fromhex(self.tile_id)
        self.proposer_signature = sign_payload(proposer_dsa_sk, msg)

    def verify_tile_signature(self) -> bool:
        if not self.proposer_signature:
            return False
        msg = bytes.fromhex(self.tile_id)
        return verify_payload(self.ml_dsa_public_key, msg, self.proposer_signature)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tile_id": self.tile_id,
            "header": self._header_dict(),
            "geometry": self.polygon.to_dict(),
            "edge_connections": {str(k): v for k, v in self.edge_connections.items()},
            "status": self.status.value,
            "proposer_signature": binascii.hexlify(self.proposer_signature).decode("ascii")
            if self.proposer_signature else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpectreTile":
        hdr = data["header"]
        tile = cls(
            index=hdr["index"],
            agent_alias=hdr["agent_alias"],
            transform=SpectreTransform.from_dict(hdr["transform"]),
            ml_kem_public_key=binascii.unhexlify(hdr["ml_kem_pk"]),
            ml_dsa_public_key=binascii.unhexlify(hdr["ml_dsa_pk"]),
            system_prompt_commitment=hdr["prompt_commitment"],
            timestamp=hdr["timestamp"],
            previous_block_hash=hdr["previous_block_hash"],
        )
        tile.edge_connections = {int(k): v for k, v in data.get("edge_connections", {}).items()}
        tile.status = TileStatus(data.get("status", TileStatus.ACTIVE.value))
        if data.get("proposer_signature"):
            tile.proposer_signature = binascii.unhexlify(data["proposer_signature"])
        tile.tile_id = data["tile_id"]
        return tile

    def __repr__(self) -> str:
        return (
            f"SpectreTile(#{self.index} [{self.agent_alias}], ID: {self.tile_id[:8]}..., "
            f"Pos: ({self.transform.x:.2f}, {self.transform.y:.2f}, {self.transform.rotation_index*30}°), "
            f"Status: {self.status.value}, Edges: {len(self.edge_connections)}/14)"
        )


class CognitiveEpoch:
    """
    Append-only discrete thought update for an agent's living memory stream.
    Dual-encrypted with ML-KEM-1024 (Agent Key + Colony Auditor Key) and signed with ML-DSA.
    """

    def __init__(
        self,
        agent_tile_id: str,
        epoch_index: int,
        prev_epoch_hash: str,
        dual_envelope: Dict[str, Any],
        timestamp: Optional[float] = None,
    ):
        self.agent_tile_id = agent_tile_id
        self.epoch_index = epoch_index
        self.prev_epoch_hash = prev_epoch_hash
        self.dual_envelope = dual_envelope
        self.timestamp = timestamp or time.time()
        self.signature: Optional[bytes] = None
        self.epoch_hash = self.calculate_hash()

    def _header_dict(self) -> Dict[str, Any]:
        return {
            "agent_tile_id": self.agent_tile_id,
            "epoch_index": self.epoch_index,
            "prev_epoch_hash": self.prev_epoch_hash,
            "envelope_ct_hash": hashlib.sha256(
                self.dual_envelope["ciphertext"].encode()
            ).hexdigest(),
            "timestamp": self.timestamp,
        }

    def calculate_hash(self) -> str:
        b = json.dumps(self._header_dict(), sort_keys=True).encode("utf-8")
        return hashlib.sha256(b).hexdigest()

    def sign(self, agent_dsa_sk: bytes) -> None:
        msg = bytes.fromhex(self.epoch_hash)
        self.signature = sign_payload(agent_dsa_sk, msg)

    def verify(self, agent_dsa_pk: bytes) -> bool:
        if not self.signature:
            return False
        msg = bytes.fromhex(self.epoch_hash)
        return verify_payload(agent_dsa_pk, msg, self.signature)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epoch_hash": self.epoch_hash,
            "header": self._header_dict(),
            "dual_envelope": self.dual_envelope,
            "signature": binascii.hexlify(self.signature).decode("ascii") if self.signature else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CognitiveEpoch":
        hdr = data["header"]
        epoch = cls(
            agent_tile_id=hdr["agent_tile_id"],
            epoch_index=hdr["epoch_index"],
            prev_epoch_hash=hdr["prev_epoch_hash"],
            dual_envelope=data["dual_envelope"],
            timestamp=hdr["timestamp"],
        )
        if data.get("signature"):
            epoch.signature = binascii.unhexlify(data["signature"])
        epoch.epoch_hash = data["epoch_hash"]
        return epoch


class RelayPacket:
    """
    Quantum-safe multi-hop transport packet traversing touching edges across the Spatial Firewall.
    The inner payload is sealed exclusively for the destination agent via ML-KEM-1024.
    """

    def __init__(
        self,
        source_tile_id: str,
        destination_tile_id: str,
        hop_path: List[str],
        encrypted_payload_envelope: Dict[str, str],
        packet_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ):
        self.source_tile_id = source_tile_id
        self.destination_tile_id = destination_tile_id
        self.hop_path = hop_path  # e.g. [A_id, B_id, C_id]
        self.current_hop_index = 0
        self.encrypted_payload_envelope = encrypted_payload_envelope
        self.timestamp = timestamp or time.time()
        self.packet_id = packet_id or hashlib.sha256(
            f"{source_tile_id}:{destination_tile_id}:{self.timestamp}:{json.dumps(encrypted_payload_envelope)}".encode()
        ).hexdigest()
        self.hop_signatures: List[str] = []  # ML-DSA hex signatures for each completed hop

    def sign_hop(self, current_agent_dsa_sk: bytes) -> None:
        msg = f"{self.packet_id}:{self.current_hop_index}".encode()
        sig = sign_payload(current_agent_dsa_sk, msg)
        self.hop_signatures.append(binascii.hexlify(sig).decode("ascii"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "source_tile_id": self.source_tile_id,
            "destination_tile_id": self.destination_tile_id,
            "hop_path": self.hop_path,
            "current_hop_index": self.current_hop_index,
            "encrypted_payload_envelope": self.encrypted_payload_envelope,
            "timestamp": self.timestamp,
            "hop_signatures": self.hop_signatures,
        }


class TileAuditRecord:
    """
    Forensic audit report logged when neighbors observe protocol or behavioral violations.
    Contains neighbor quorum attestations that trigger geometric airlock/quarantine.
    """

    def __init__(
        self,
        target_tile_id: str,
        accuser_tile_id: str,
        incident_type: str,
        details: str,
        timestamp: Optional[float] = None,
    ):
        self.target_tile_id = target_tile_id
        self.accuser_tile_id = accuser_tile_id
        self.incident_type = incident_type  # e.g. "INVALID_SIGNATURE", "GEOMETRIC_FORGERY"
        self.details = details
        self.timestamp = timestamp or time.time()
        self.supporting_neighbor_signatures: Dict[str, str] = {}  # neighbor_tile_id -> dsa_sig_hex
        self.audit_id = hashlib.sha256(
            f"{target_tile_id}:{accuser_tile_id}:{incident_type}:{self.timestamp}".encode()
        ).hexdigest()

    def add_attestation(self, neighbor_tile_id: str, neighbor_dsa_sk: bytes) -> None:
        msg = f"AUDIT_ATTESTATION:{self.audit_id}:{self.target_tile_id}:{self.incident_type}".encode()
        sig = sign_payload(neighbor_dsa_sk, msg)
        self.supporting_neighbor_signatures[neighbor_tile_id] = binascii.hexlify(sig).decode("ascii")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "target_tile_id": self.target_tile_id,
            "accuser_tile_id": self.accuser_tile_id,
            "incident_type": self.incident_type,
            "details": self.details,
            "timestamp": self.timestamp,
            "supporting_neighbor_signatures": self.supporting_neighbor_signatures,
        }
