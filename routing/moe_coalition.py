"""
Ad-Hoc Mixture-of-Experts (MoE) Coalition Coordinator.
Dynamically orchestrates ephemeral clusters of specialized tiles around a prompt topic.
Executes the 4-phase wavefront lifecycle: Ingress Fan-Out, Parallel Atomic Reasoning,
Lattice Reduction, and Macro Synthesis.
"""

import time
import json
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from engine.node_runtime import SovereignTileNode, PortPacket
from ledger.micro_block import AtomicMicroBlock
from ledger.dag_aggregator import DAGAggregator, DynamicCoalitionBlock
from pqc_crypto.spatial_identity import STRICT_KEM_ALG


@dataclass
class WavefrontExecutionResult:
    """Receipt summarizing an end-to-end multi-agent thinking loop."""
    coalition_id: str
    topic: str
    participant_count: int
    approved_count: int
    macro_block: DynamicCoalitionBlock
    composite_lemmas: List[int]
    is_consensus_reached: bool
    execution_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coalition_id": self.coalition_id,
            "topic": self.topic,
            "participant_count": self.participant_count,
            "approved_count": self.approved_count,
            "macro_block": self.macro_block.to_dict(),
            "composite_lemmas": self.composite_lemmas,
            "is_consensus_reached": self.is_consensus_reached,
            "execution_time_ms": self.execution_time_ms,
        }


class MoECoalitionCoordinator:
    """
    Coordinates dynamic coalitions of 5 to 9 tiles.
    Executes parallel atomic reasoning without introducing central bottleneck servers.
    """

    @classmethod
    def form_coalition(
        cls,
        topic: str,
        available_nodes: List[SovereignTileNode],
        max_members: int = 8,
    ) -> List[SovereignTileNode]:
        """
        Dynamically forms an ephemeral coalition of active solvent nodes.
        Filters out apoptotic/insolvent nodes.
        """
        solvent_nodes = [n for n in available_nodes if not n.is_apoptotic and n.fuel_gauge > 0]
        if not solvent_nodes:
            raise RuntimeError("No solvent nodes available to form an MoE coalition.")
        return solvent_nodes[:max_members]

    @classmethod
    def execute_wavefront(
        cls,
        coalition_id: str,
        topic: str,
        coalition_nodes: List[SovereignTileNode],
        input_vector: List[int],
        expected_invariant: str = "non_negative",
        quorum_threshold: float = 0.75,
    ) -> WavefrontExecutionResult:
        """
        Executes the 4-phase wavefront lifecycle across the coalition:
        Phase 1: Ingress Anchor fans out sub-tasks.
        Phase 2: Parallel atomic reasoning on local node hardware.
        Phase 3: In-lattice reduction (collecting verified lemmas).
        Phase 4: Super-Block Merkle seal via DAGAggregator.
        """
        t_start = time.time()
        ingress_anchor = coalition_nodes[0]

        # Phase 1 & 2: Parallel Atomic Reasoning
        # Each tile processes ingress vector with its INT8 policy and SpectreVM verifier
        micro_blocks: List[AtomicMicroBlock] = []
        raw_payload = json.dumps(input_vector).encode("utf-8")

        for idx, node in enumerate(coalition_nodes):
            # Create encrypted port wire packet from Ingress Anchor to node
            packet = PortPacket(
                source_address=ingress_anchor.address.to_string(),
                target_address=node.address.to_string(),
                egress_port=(idx % 14),
                ingress_port=((idx + 7) % 14),
                envelope=ingress_anchor.identity.encrypt_to_neighbor(node.identity.certificate, raw_payload),
                expected_invariant=expected_invariant,
            )

            # Node processes ingress atomically
            receipt = node.process_ingress(packet)
            if node.committed_micro_blocks:
                micro_blocks.append(node.committed_micro_blocks[-1])

        # Phase 3: Lattice Reduction (accumulate verified lemmas)
        composite_lemmas: List[int] = []
        for b in micro_blocks:
            status = b.payload.proof_status if hasattr(b, "payload") else b.status
            if status == "APPROVED":
                lemmas = b.payload.verified_lemmas if hasattr(b, "payload") else b.verified_lemmas
                composite_lemmas.extend(lemmas)

        # Phase 4: Macro Synthesis & Super-Block Merkle Seal
        macro_block = DAGAggregator.assemble_super_block(
            coalition_id=coalition_id,
            micro_blocks=micro_blocks,
            quorum_threshold=quorum_threshold,
        )

        t_elapsed = (time.time() - t_start) * 1000.0

        return WavefrontExecutionResult(
            coalition_id=coalition_id,
            topic=topic,
            participant_count=len(coalition_nodes),
            approved_count=macro_block.approved_count,
            macro_block=macro_block,
            composite_lemmas=composite_lemmas,
            is_consensus_reached=macro_block.is_quorate,
            execution_time_ms=round(t_elapsed, 2),
        )
