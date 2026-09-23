"""
Airlock Severing & Apoptosis Protocol.
Enforces biological cellular death when a node exhausts its fuel balance (F <= 0).
Surrounding neighbor nodes independently sever edge port connections during inter-prompt sweeps.
Insolvent agents cannot protest, dispute, or continue participating in thinking loops.
"""

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
from consensus.fuel_ledger import FuelLedger
from engine.node_runtime import SovereignTileNode


@dataclass
class ApoptosisEvent:
    """Audit record of an unprotestable port severing and apoptosis execution."""
    insolvent_address: str
    epoch: int
    severed_neighbors: List[str]
    tombstone_slot_created: bool


class ApoptosisEngine:
    """Manages unilateral edge port disconnects and tombstone lifecycle between prompt epochs."""

    def __init__(self, fuel_ledger: FuelLedger):
        self.fuel_ledger = fuel_ledger
        self.tombstone_slots: Set[str] = set()
        self.apoptosis_history: List[ApoptosisEvent] = []

    def run_inter_prompt_sweep(
        self,
        node_cluster: Dict[str, SovereignTileNode]
    ) -> List[ApoptosisEvent]:
        """
        Executes strictly between prompt epochs (never mid-flight):
        1. Applies baseline epoch rent burn.
        2. Detects nodes that crossed the insolvency boundary (F <= 0).
        3. Unilaterally drops edge port connections from all touching neighbors.
        4. Designates vacant slots as Tombstone Slots available for evolutionary re-minting.
        """
        newly_insolvent = self.fuel_ledger.apply_epoch_burn()

        # Also collect nodes that were penalized to 0 by vetoes
        for addr, account in self.fuel_ledger.accounts.items():
            if account.status == "INSOLVENT" and addr not in newly_insolvent and addr not in self.tombstone_slots:
                newly_insolvent.append(addr)

        events: List[ApoptosisEvent] = []

        for dead_addr in newly_insolvent:
            severed_peers = []
            dead_node = node_cluster.get(dead_addr)
            if dead_node:
                dead_node.is_apoptotic = True

            # Scan all other nodes in the cluster to sever touching port connections
            for peer_addr, peer_node in node_cluster.items():
                if peer_addr == dead_addr:
                    continue

                for port_idx, neighbor_cert in peer_node.port_neighbors.items():
                    if neighbor_cert and neighbor_cert.address == dead_addr:
                        # Unilateral port severing: drop connection
                        peer_node.port_neighbors[port_idx] = None
                        severed_peers.append(peer_addr)

            # Mark in fuel ledger and register tombstone
            self.fuel_ledger.mark_tombstone(dead_addr)
            self.tombstone_slots.add(dead_addr)

            event = ApoptosisEvent(
                insolvent_address=dead_addr,
                epoch=self.fuel_ledger.current_epoch,
                severed_neighbors=severed_peers,
                tombstone_slot_created=True,
            )
            self.apoptosis_history.append(event)
            events.append(event)

        return events

    def is_tombstone(self, address: str) -> bool:
        return address in self.tombstone_slots

    def reclaim_tombstone(self, address: str):
        """Removes a tombstone designation after successful evolutionary re-minting."""
        self.tombstone_slots.discard(address)
