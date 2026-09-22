"""
Post-Quantum Cryptographic Spatial Identity & Certificate Module.
Cryptographically binds ML-KEM-1024 and ML-DSA-65 sovereign keys to the node's
exact 2D aperiodic coordinate, producing tamper-proof Spatial Certificates.
"""

import time
import hashlib
import binascii
from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional
from pqc_crypto.crypto_utils import (
    DEFAULT_KEM_ALG,
    DEFAULT_DSA_ALG,
    generate_kem_keypair,
    generate_dsa_keypair,
    sign_payload,
    verify_payload,
    encrypt_envelope,
    decrypt_envelope,
)
from geometry.spectre_hierarchy import HierarchicalAddress
from geometry.topological_proof import ProofOfGeometricFit


def compute_spatial_commitment(
    address_str: str,
    polygon_hash: str,
    kem_pk: bytes,
    dsa_pk: bytes,
    genesis_epoch: int,
) -> bytes:
    """
    Computes a SHA3-256 spatial commitment binding the cryptographic keys
    to the physical coordinate on the aperiodic lattice.
    """
    hasher = hashlib.sha3_256()
    hasher.update(address_str.encode("utf-8"))
    hasher.update(b"::")
    hasher.update(polygon_hash.encode("utf-8"))
    hasher.update(b"::")
    hasher.update(kem_pk)
    hasher.update(b"::")
    hasher.update(dsa_pk)
    hasher.update(b"::")
    hasher.update(str(genesis_epoch).encode("utf-8"))
    return hasher.digest()


@dataclass
class SpatialCertificate:
    """
    Cryptographic identity deed binding an autonomous agent to a Spectre monotile coordinate.
    Can be independently verified by any node on the network without a central authority.
    """
    address: str
    polygon_hash: str
    centroid: Tuple[float, float]
    kem_algorithm: str
    kem_public_key_hex: str
    dsa_algorithm: str
    dsa_public_key_hex: str
    genesis_epoch: int
    spatial_commitment_hex: str
    signature_hex: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "polygon_hash": self.polygon_hash,
            "centroid": [round(self.centroid[0], 4), round(self.centroid[1], 4)],
            "kem_algorithm": self.kem_algorithm,
            "kem_public_key_hex": self.kem_public_key_hex,
            "dsa_algorithm": self.dsa_algorithm,
            "dsa_public_key_hex": self.dsa_public_key_hex,
            "genesis_epoch": self.genesis_epoch,
            "spatial_commitment_hex": self.spatial_commitment_hex,
            "signature_hex": self.signature_hex,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpatialCertificate":
        return cls(
            address=data["address"],
            polygon_hash=data["polygon_hash"],
            centroid=(data["centroid"][0], data["centroid"][1]),
            kem_algorithm=data["kem_algorithm"],
            kem_public_key_hex=data["kem_public_key_hex"],
            dsa_algorithm=data["dsa_algorithm"],
            dsa_public_key_hex=data["dsa_public_key_hex"],
            genesis_epoch=data["genesis_epoch"],
            spatial_commitment_hex=data["spatial_commitment_hex"],
            signature_hex=data["signature_hex"],
        )

    def verify(self) -> bool:
        """
        Verifies that:
        1. The spatial commitment accurately reflects all header parameters.
        2. The node's ML-DSA public key signed the commitment.
        """
        kem_pk = binascii.unhexlify(self.kem_public_key_hex)
        dsa_pk = binascii.unhexlify(self.dsa_public_key_hex)
        sig = binascii.unhexlify(self.signature_hex)

        # 1. Re-calculate commitment
        expected_commitment = compute_spatial_commitment(
            address_str=self.address,
            polygon_hash=self.polygon_hash,
            kem_pk=kem_pk,
            dsa_pk=dsa_pk,
            genesis_epoch=self.genesis_epoch,
        )
        if expected_commitment.hex() != self.spatial_commitment_hex:
            return False

        # 2. Verify ML-DSA signature over commitment
        return verify_payload(
            public_key=dsa_pk,
            message=expected_commitment,
            signature=sig,
            alg=self.dsa_algorithm,
        )


class SpatialNodeIdentity:
    """
    Sovereign cryptographic identity of a Level-0 Spectre tile node.
    Possesses private keys and produces verified spatial certificates.
    """

    def __init__(
        self,
        address: HierarchicalAddress,
        proof_of_fit: ProofOfGeometricFit,
        kem_alg: str = DEFAULT_KEM_ALG,
        dsa_alg: str = DEFAULT_DSA_ALG,
        genesis_epoch: Optional[int] = None,
    ):
        self.address = address
        self.proof_of_fit = proof_of_fit
        self.kem_alg = kem_alg
        self.dsa_alg = dsa_alg
        self.genesis_epoch = genesis_epoch if genesis_epoch is not None else int(time.time())

        # Generate sovereign PQC keypairs
        self.kem_pk, self.kem_sk = generate_kem_keypair(kem_alg)
        self.dsa_pk, self.dsa_sk = generate_dsa_keypair(dsa_alg)

        # Compute commitment & sign spatial certificate
        self.commitment = compute_spatial_commitment(
            address_str=self.address.to_string(),
            polygon_hash=self.proof_of_fit.polygon_hash,
            kem_pk=self.kem_pk,
            dsa_pk=self.dsa_pk,
            genesis_epoch=self.genesis_epoch,
        )
        self.signature = sign_payload(
            private_key=self.dsa_sk,
            message=self.commitment,
            alg=self.dsa_alg,
        )

        self.certificate = SpatialCertificate(
            address=self.address.to_string(),
            polygon_hash=self.proof_of_fit.polygon_hash,
            centroid=self.proof_of_fit.centroid,
            kem_algorithm=self.kem_alg,
            kem_public_key_hex=self.kem_pk.hex(),
            dsa_algorithm=self.dsa_alg,
            dsa_public_key_hex=self.dsa_pk.hex(),
            genesis_epoch=self.genesis_epoch,
            spatial_commitment_hex=self.commitment.hex(),
            signature_hex=self.signature.hex(),
        )

    def sign_message(self, message: bytes) -> bytes:
        """Signs arbitrary cognitive data with this node's sovereign key."""
        return sign_payload(self.dsa_sk, message, self.dsa_alg)

    def encrypt_to_neighbor(self, neighbor_cert: SpatialCertificate, payload: bytes) -> Dict[str, Any]:
        """Encrypts payload to neighbor using neighbor's ML-KEM public key."""
        neighbor_kem_pk = binascii.unhexlify(neighbor_cert.kem_public_key_hex)
        return encrypt_envelope(payload, neighbor_kem_pk, self.kem_alg)

    def decrypt_from_neighbor(self, envelope: Dict[str, Any]) -> bytes:
        """Decrypts a message addressed to this node using its ML-KEM secret key."""
        return decrypt_envelope(envelope, self.kem_sk)
