"""
Quorum & Convergence Oracle with Speculative Straggler Bypass.
Enforces multi-agent consensus thresholds (k-of-N >= 75%) and handles
speculative routing around slow, lagging, or apoptotic nodes to prevent pipeline stalls.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
from ledger.dag_aggregator import DynamicCoalitionBlock
from engine.node_runtime import SovereignTileNode

DEFAULT_QUORUM_THRESHOLD = 0.75


@dataclass
class QuorumCertificate:
    """Cryptographic certification that a multi-agent coalition achieved consensus."""
    coalition_id: str
    macro_root: str
    total_participants: int
    approved_participants: int
    approval_ratio: float
    is_quorate: bool
    bypassed_stragglers: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coalition_id": self.coalition_id,
            "macro_root": self.macro_root,
            "total_participants": self.total_participants,
            "approved_participants": self.approved_participants,
            "approval_ratio": round(self.approval_ratio, 4),
            "is_quorate": self.is_quorate,
            "bypassed_stragglers": self.bypassed_stragglers,
        }


class QuorumOracle:
    """Evaluates consensus thresholds and manages speculative straggler bypasses."""

    @staticmethod
    def evaluate_quorum(
        approved_count: int,
        total_count: int,
        threshold: float = DEFAULT_QUORUM_THRESHOLD,
    ) -> Tuple[bool, float]:
        """Calculates approval ratio and verifies whether quorum was attained."""
        if total_count == 0:
            return False, 0.0
        ratio = approved_count / float(total_count)
        return ratio >= threshold, ratio

    @classmethod
    def certify_macro_block(
        cls,
        macro_block: DynamicCoalitionBlock,
        bypassed_nodes: Optional[List[str]] = None,
    ) -> QuorumCertificate:
        """Issues an official QuorumCertificate for a completed thinking loop."""
        total = len(macro_block.participant_addresses)
        is_quorate, ratio = cls.evaluate_quorum(
            approved_count=macro_block.approved_count,
            total_count=total,
            threshold=macro_block.quorum_threshold,
        )

        return QuorumCertificate(
            coalition_id=macro_block.coalition_id,
            macro_root=macro_block.merkle_root,
            total_participants=total,
            approved_participants=macro_block.approved_count,
            approval_ratio=ratio,
            is_quorate=is_quorate,
            bypassed_stragglers=bypassed_nodes or [],
        )

    @classmethod
    def speculative_bypass(
        cls,
        stalled_node: SovereignTileNode,
        candidate_replacements: List[SovereignTileNode],
    ) -> Optional[SovereignTileNode]:
        """
        Dynamically selects a healthy replacement node if a participant stalls or times out.
        Prevents slow micro-boards from blocking the entire coalition.
        """
        for candidate in candidate_replacements:
            if (
                candidate.address != stalled_node.address
                and not candidate.is_apoptotic
                and candidate.fuel_gauge > 0
            ):
                return candidate
        return None
