"""
Post-Quantum Cryptographic Spatial Identity & Certificate Module.
Cryptographically binds ML-KEM-1024 sovereign keys to the node's
exact 2D aperiodic coordinate, producing tamper-proof Spatial Certificates.
Exclusively uses ML-KEM-1024 for all post-quantum security.
"""

import time
import hmac
import hashlib
import binascii
from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional
from pqc_crypto.crypto_utils import (
    DEFAULT_KEM_ALG,
    generate_kem_keypair,
    encrypt_envelope,
    decrypt_envelope,
)
from geometry.spectre_hierarchy import HierarchicalAddress
from geometry.topological_proof import ProofOfGeometricFit

# Enforce ML-KEM-1024 exclusively
STRICT_KEM_ALG = "ML-KEM-1024"


def compute_spatial_commitment(
    address_str: str,
    polygon_hash: str,
    kem_pk: bytes,
    genesis_epoch: int,
) -> bytes:
    """
    Computes a SHA3-256 spatial commitment binding the ML-KEM-1024 key
    to the physical coordinate on the aperiodic lattice.
    """
    hasher = hashlib.sha3_256()
    hasher.update(address_str.encode("utf-8"))
    hasher.update(b"::")
    hasher.update(polygon_hash.encode("utf-8"))
    hasher.update(b"::")
    hasher.update(kem_pk)
    hasher.update(b"::")
    hasher.update(str(genesis_epoch).encode("utf-8"))
    return hasher.digest()


@dataclass
class SpatialCertificate:
    """
    Cryptographic identity deed binding an autonomous agent to a Spectre monotile coordinate.
    Can be independently verified by any node on the network without a central authority.
    Uses pure ML-KEM-1024.
    """
    address: str
    polygon_hash: str
    centroid: Tuple[float, float]
    kem_algorithm: str
    kem_public_key_hex: str
    genesis_epoch: int
    spatial_commitment_hex: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "polygon_hash": self.polygon_hash,
            "centroid": [round(self.centroid[0], 4), round(self.centroid[1], 4)],
            "kem_algorithm": self.kem_algorithm,
            "kem_public_key_hex": self.kem_public_key_hex,
            "genesis_epoch": self.genesis_epoch,
            "spatial_commitment_hex": self.spatial_commitment_hex,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpatialCertificate":
        return cls(
            address=data["address"],
            polygon_hash=data["polygon_hash"],
            centroid=(data["centroid"][0], data["centroid"][1]),
            kem_algorithm=data.get("kem_algorithm", STRICT_KEM_ALG),
            kem_public_key_hex=data["kem_public_key_hex"],
            genesis_epoch=data["genesis_epoch"],
            spatial_commitment_hex=data["spatial_commitment_hex"],
        )

    def verify(self) -> bool:
        """
        Verifies that:
        1. The algorithm is strictly ML-KEM-1024.
        2. The public key has the exact ML-KEM-1024 length (1568 bytes).
        3. The spatial commitment accurately binds address, geometry, and key.
        """
        if self.kem_algorithm != STRICT_KEM_ALG:
            return False

        try:
            kem_pk = binascii.unhexlify(self.kem_public_key_hex)
        except Exception:
            return False

        # ML-KEM-1024 public keys are strictly 1568 bytes
        if len(kem_pk) != 1568:
            return False

        # Re-calculate commitment
        expected_commitment = compute_spatial_commitment(
            address_str=self.address,
            polygon_hash=self.polygon_hash,
            kem_pk=kem_pk,
            genesis_epoch=self.genesis_epoch,
        )
        return expected_commitment.hex() == self.spatial_commitment_hex


class SpatialNodeIdentity:
    """
    Sovereign cryptographic identity of a Level-0 Spectre tile node.
    Exclusively uses ML-KEM-1024 for envelope encryption, key encapsulation,
    and KEM-derived message authentication across touching edge ports.
    """

    def __init__(
        self,
        address: HierarchicalAddress,
        proof_of_fit: ProofOfGeometricFit,
        genesis_epoch: Optional[int] = None,
    ):
        self.address = address
        self.proof_of_fit = proof_of_fit
        self.kem_alg = STRICT_KEM_ALG
        self.genesis_epoch = genesis_epoch if genesis_epoch is not None else int(time.time())

        # Generate sovereign ML-KEM-1024 keypair (PK: 1568 bytes, SK: 3168 bytes)
        self.kem_pk, self.kem_sk = generate_kem_keypair(self.kem_alg)

        # Compute spatial commitment
        self.commitment = compute_spatial_commitment(
            address_str=self.address.to_string(),
            polygon_hash=self.proof_of_fit.polygon_hash,
            kem_pk=self.kem_pk,
            genesis_epoch=self.genesis_epoch,
        )

        self.certificate = SpatialCertificate(
            address=self.address.to_string(),
            polygon_hash=self.proof_of_fit.polygon_hash,
            centroid=self.proof_of_fit.centroid,
            kem_algorithm=self.kem_alg,
            kem_public_key_hex=self.kem_pk.hex(),
            genesis_epoch=self.genesis_epoch,
            spatial_commitment_hex=self.commitment.hex(),
        )

    def encrypt_to_neighbor(self, neighbor_cert: SpatialCertificate, payload: bytes) -> Dict[str, Any]:
        """Encrypts payload to neighbor using neighbor's ML-KEM-1024 public key."""
        if neighbor_cert.kem_algorithm != STRICT_KEM_ALG:
            raise ValueError(f"Neighbor certificate uses invalid algorithm: {neighbor_cert.kem_algorithm}. Must be ML-KEM-1024.")
        neighbor_kem_pk = binascii.unhexlify(neighbor_cert.kem_public_key_hex)
        return encrypt_envelope(payload, neighbor_kem_pk, self.kem_alg)

    def decrypt_from_neighbor(self, envelope: Dict[str, Any]) -> bytes:
        """Decrypts a message addressed to this node using its ML-KEM-1024 secret key."""
        return decrypt_envelope(envelope, self.kem_sk)

    def create_message_mac(self, shared_secret: bytes, message: bytes) -> bytes:
        """Computes a SHA3-256 HMAC authentication tag over a message using a KEM shared secret."""
        return hmac.new(shared_secret, message, hashlib.sha3_256).digest()

    def verify_message_mac(self, shared_secret: bytes, message: bytes, tag: bytes) -> bool:
        """Verifies a message authentication tag."""
        expected_tag = self.create_message_mac(shared_secret, message)
        return hmac.compare_digest(expected_tag, tag)
