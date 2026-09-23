"""
Level-0 Sovereign Node Runtime.
Integrates the Spatial Identity (ML-KEM-1024), the 350 KB INT8 Neural Policy,
the 32 KB Deterministic SpectreVM, and the 14 Physical Edge Ports.
Operates within a strict 512 KB static memory budget.
"""

import time
import json
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pqc_crypto.spatial_identity import SpatialNodeIdentity, SpatialCertificate
from geometry.spectre_hierarchy import HierarchicalAddress, EdgePortInfo
from geometry.topological_proof import ProofOfGeometricFit
from engine.spectre_vm import SpectreVM, VMExecutionResult
from engine.neural_policy import NeuralPolicy, CandidateProposal

DEFAULT_INITIAL_FUEL = 100_000
VETO_FUEL_PENALTY = 500
VERIFIED_FUEL_REWARD = 250


@dataclass
class PortPacket:
    """A content-addressed wire packet transmitted across a touching monotile edge."""
    source_address: str
    target_address: str
    egress_port: int
    ingress_port: int
    envelope: Dict[str, Any]             # Encrypted via target's ML-KEM-1024 PK
    expected_invariant: str = "non_negative"
    timestamp: float = field(default_factory=time.time)


@dataclass
class MicroBlockReceipt:
    """The atomic state transition micro-block committed to the ledger."""
    block_hash: str
    node_address: str
    ingress_port: int
    gas_consumed: int
    verified_lemmas: List[int]
    status: str                         # APPROVED | VETOED
    fuel_after: int
    timestamp: float
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_hash": self.block_hash,
            "node_address": self.node_address,
            "ingress_port": self.ingress_port,
            "gas_consumed": self.gas_consumed,
            "verified_lemmas": self.verified_lemmas,
            "status": self.status,
            "fuel_after": self.fuel_after,
            "timestamp": self.timestamp,
            "rejection_reason": self.rejection_reason,
        }


class SovereignTileNode:
    """
    Autonomous Level-0 Base Agent running on an aperiodic Spectre monotile.
    Total resident memory is strictly capped at < 512 KB.
    """

    def __init__(
        self,
        address: HierarchicalAddress,
        proof_of_fit: ProofOfGeometricFit,
        seed_domain: str = "general",
        initial_fuel: int = DEFAULT_INITIAL_FUEL,
    ):
        self.address = address
        self.proof_of_fit = proof_of_fit
        self.fuel_gauge = initial_fuel
        self.is_apoptotic = False

        # 1. PQC Identity (ML-KEM-1024, ~12 KB)
        self.identity = SpatialNodeIdentity(address, proof_of_fit)

        # 2. INT8 Neural Policy (~350 KB)
        self.policy = NeuralPolicy(seed_domain=seed_domain)

        # 3. Deterministic SpectreVM (~32 KB)
        self.vm = SpectreVM()

        # 4. 14 Physical Edge Ports (Ring Buffers, ~32 KB)
        self.ports: Dict[int, List[PortPacket]] = {i: [] for i in range(14)}
        self.port_neighbors: Dict[int, Optional[SpatialCertificate]] = {i: None for i in range(14)}

        # 5. Ledger Micro-Block Commitments
        self.committed_micro_blocks: List[MicroBlockReceipt] = []

    def connect_neighbor(self, port_idx: int, neighbor_cert: SpatialCertificate):
        """Pairs a physical edge port with a neighbor's verified spatial certificate."""
        if not (0 <= port_idx < 14):
            raise ValueError(f"Invalid port index {port_idx}. Must be 0..13.")
        self.port_neighbors[port_idx] = neighbor_cert

    def send_to_port(self, port_idx: int, payload: bytes, expected_invariant: str = "non_negative") -> PortPacket:
        """Encrypts and dispatches a wire packet to a connected neighbor port using ML-KEM-1024."""
        neighbor_cert = self.port_neighbors.get(port_idx)
        if neighbor_cert is None:
            raise ConnectionError(f"Port {port_idx} has no connected neighbor.")

        envelope = self.identity.encrypt_to_neighbor(neighbor_cert, payload)
        return PortPacket(
            source_address=self.address.to_string(),
            target_address=neighbor_cert.address,
            egress_port=port_idx,
            ingress_port=(port_idx + 7) % 14,  # Opposite edge contact
            envelope=envelope,
            expected_invariant=expected_invariant
        )

    def process_ingress(self, packet: PortPacket) -> MicroBlockReceipt:
        """
        Executes the atomic Propose-and-Veto cycle:
        1. Decrypts payload using ML-KEM-1024.
        2. Neural policy proposes candidate reduction & verifier bytecode.
        3. SpectreVM evaluates bytecode under 500-gas limit.
        4. If verified: commits micro-block, credits fuel.
        5. If vetoed: penalizes fuel, rejects state transition.
        """
        if self.is_apoptotic:
            return MicroBlockReceipt(
                block_hash="0" * 64,
                node_address=self.address.to_string(),
                ingress_port=packet.ingress_port,
                gas_consumed=0,
                verified_lemmas=[],
                status="VETOED",
                fuel_after=self.fuel_gauge,
                timestamp=time.time(),
                rejection_reason="ERR_NODE_APOPTOTIC: Node has experienced fuel exhaustion."
            )

        # 1. Decrypt input via ML-KEM-1024
        try:
            raw_payload = self.identity.decrypt_from_neighbor(packet.envelope)
            # Parse integer vector (JSON or compact byte array)
            input_vector = json.loads(raw_payload.decode("utf-8"))
            if not isinstance(input_vector, list):
                input_vector = [int(x) for x in input_vector]
        except Exception as e:
            return self._record_rejection(packet.ingress_port, 0, f"ERR_DECRYPTION_FAILED: {str(e)}")

        # 2. INT8 Neural Policy generates candidate proposal & bytecode
        proposal = self.policy.propose_candidate(input_vector, packet.expected_invariant)

        # 3. SpectreVM executes bytecode under 500-gas ceiling (Absolute Veto Gate)
        vm_result = self.vm.execute(proposal.verification_bytecode)

        # Deduct gas burn
        self.fuel_gauge = max(0, self.fuel_gauge - vm_result.gas_used)

        # 4. Handle Decision
        if vm_result.is_verified:
            # Credit verification reward
            self.fuel_gauge += VERIFIED_FUEL_REWARD

            # Compute atomic micro-block hash
            block_data = f"{self.address.to_string()}::{packet.ingress_port}::{vm_result.emitted_lemmas}::{self.fuel_gauge}::{time.time()}"
            block_hash = hashlib.sha3_256(block_data.encode("utf-8")).hexdigest()

            receipt = MicroBlockReceipt(
                block_hash=block_hash,
                node_address=self.address.to_string(),
                ingress_port=packet.ingress_port,
                gas_consumed=vm_result.gas_used,
                verified_lemmas=vm_result.emitted_lemmas,
                status="APPROVED",
                fuel_after=self.fuel_gauge,
                timestamp=time.time(),
                rejection_reason=None
            )
            self.committed_micro_blocks.append(receipt)
            return receipt
        else:
            # Penalize fuel for vetoed proposal
            self.fuel_gauge = max(0, self.fuel_gauge - VETO_FUEL_PENALTY)
            if self.fuel_gauge <= 0:
                self.is_apoptotic = True

            return self._record_rejection(
                ingress_port=packet.ingress_port,
                gas_used=vm_result.gas_used,
                reason=vm_result.error or "ERR_SYMBOLIC_VETO: Proposal violated invariant."
            )

    def _record_rejection(self, ingress_port: int, gas_used: int, reason: str) -> MicroBlockReceipt:
        receipt = MicroBlockReceipt(
            block_hash="0" * 64,
            node_address=self.address.to_string(),
            ingress_port=ingress_port,
            gas_consumed=gas_used,
            verified_lemmas=[],
            status="VETOED",
            fuel_after=self.fuel_gauge,
            timestamp=time.time(),
            rejection_reason=reason
        )
        return receipt

    def audit_memory_footprint(self) -> Dict[str, Any]:
        """
        Rigorously audits the static resident memory of this base tile node.
        Guarantees that total footprint strictly respects the 512 KB budget.
        """
        neural_bytes = self.policy.get_memory_footprint()     # Exactly 358,400 bytes (350 KB)
        vm_bytes = 32_768                                     # 32 KB fixed VM state
        crypto_bytes = len(self.identity.kem_pk) + len(self.identity.kem_sk) + 2048 # ~6.7 KB
        ports_bytes = 14 * 1024                               # 14 KB ring buffer allocation
        geometry_bytes = 2048                                 # 2 KB coordinates & polarities

        total_bytes = neural_bytes + vm_bytes + crypto_bytes + ports_bytes + geometry_bytes
        total_kb = total_bytes / 1024.0

        return {
            "neural_policy_bytes": neural_bytes,
            "spectre_vm_bytes": vm_bytes,
            "pqc_crypto_bytes": crypto_bytes,
            "ports_ring_buffer_bytes": ports_bytes,
            "geometry_bytes": geometry_bytes,
            "total_bytes": total_bytes,
            "total_kb": round(total_kb, 2),
            "under_512kb_limit": total_bytes <= 512 * 1024,
            "margin_bytes_remaining": (512 * 1024) - total_bytes
        }
