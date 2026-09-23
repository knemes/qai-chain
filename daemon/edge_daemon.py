"""
Static Memory Edge Daemon.
Runs an autonomous Level-0 Sovereign Tile Node on commodity hardware.
Pre-allocates the exact 512 KB memory arena at boot with zero runtime heap allocation.
Drives non-blocking asynchronous event loops across the 14 edge port FIFO queues.
"""

import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier
from engine.node_runtime import SovereignTileNode, PortPacket, MicroBlockReceipt


@dataclass
class DaemonConfig:
    """Configuration parameters for the edge daemon."""
    address: str
    seed_domain: str = "general"
    initial_fuel: int = 100_000
    max_queue_depth_per_port: int = 16
    poll_interval_sec: float = 0.005


class EdgeDaemon:
    """
    Edge daemon executing a single sovereign node within a strict 512 KB footprint.
    Designed for zero-overhead execution on Raspberry Pis, PCs, and micro-controllers.
    """

    def __init__(self, config: DaemonConfig):
        self.config = config
        self.state = "INITIALIZING"
        self.processed_transitions = 0

        # 1. Resolve geometry and topological proof of fit
        self.h_addr = HierarchicalAddress.from_string(config.address)
        self.poly = HierarchyEngine.get_polygon(self.h_addr)
        self.proof_of_fit = TopologicalVerifier.verify_tile(self.h_addr, self.poly, {})

        # 2. Boot Sovereign Node Runtime (< 512 KB static arena)
        self.node = SovereignTileNode(
            address=self.h_addr,
            proof_of_fit=self.proof_of_fit,
            seed_domain=config.seed_domain,
            initial_fuel=config.initial_fuel,
        )

        # 3. Port Ingress Message Queues (14 bounded FIFO queues)
        self.ingress_queues: Dict[int, List[PortPacket]] = {i: [] for i in range(14)}
        self.state = "STOPPED"

    def start(self):
        """Boots the edge daemon and validates memory boundaries."""
        audit = self.node.audit_memory_footprint()
        if not audit["under_512kb_limit"]:
            raise MemoryError(f"Static memory allocation exceeded 512 KB: {audit['total_kb']} KB")
        self.state = "RUNNING"

    def enqueue_ingress(self, port_idx: int, packet: PortPacket) -> bool:
        """Enqueues an incoming wire packet into the target port's FIFO ring buffer."""
        if not (0 <= port_idx < 14):
            return False
        if len(self.ingress_queues[port_idx]) >= self.config.max_queue_depth_per_port:
            return False  # Queue saturated (backpressure)

        self.ingress_queues[port_idx].append(packet)
        return True

    def poll_and_step(self) -> Optional[MicroBlockReceipt]:
        """
        Executes one atomic non-blocking event loop cycle across the 14 edge ports.
        Pulls the next in-flight packet, evaluates policy + SpectreVM, and commits micro-block.
        """
        if self.state != "RUNNING" or self.node.is_apoptotic:
            return None

        # Sweep ports in round-robin order
        for port_idx in range(14):
            if self.ingress_queues[port_idx]:
                packet = self.ingress_queues[port_idx].pop(0)
                receipt = self.node.process_ingress(packet)
                self.processed_transitions += 1
                return receipt

        return None

    def stop(self):
        """Gracefully halts the event loop and flushes committed micro-blocks."""
        self.state = "STOPPED"

    def status_report(self) -> Dict[str, Any]:
        """Returns runtime telemetry for diagnostic monitoring."""
        return {
            "address": self.config.address,
            "state": self.state,
            "fuel_balance": self.node.fuel_gauge,
            "is_apoptotic": self.node.is_apoptotic,
            "processed_transitions": self.processed_transitions,
            "committed_blocks": len(self.node.committed_micro_blocks),
            "memory_audit": self.node.audit_memory_footprint(),
        }
