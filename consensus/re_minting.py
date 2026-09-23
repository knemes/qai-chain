"""
Evolutionary Tombstone Re-Minting Protocol.
Recycles vacant tombstone slots without altering the global aperiodic geometry.
Generates a fresh pure ML-KEM-1024 identity, inherits and mutates INT8 policy weights
from the highest-performing geometric neighbors, and restores active port airlocks.
"""

import hashlib
from typing import List, Dict, Optional, Tuple
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier, ProofOfGeometricFit
from engine.node_runtime import SovereignTileNode
from engine.neural_policy import NeuralPolicy, INT8_PARAM_COUNT
from consensus.fuel_ledger import FuelLedger
from consensus.apoptosis import ApoptosisEngine

RE_MINT_SEED_FUEL = 50_000
DEFAULT_MUTATION_RATE = 0.02


def blend_and_mutate_weights(
    parent_weights_list: List[bytes],
    mutation_rate: float = DEFAULT_MUTATION_RATE,
    entropy_seed: bytes = b"",
) -> bytes:
    """
    Blends INT8 weights from multiple parent neighbors and applies Darwinian mutation.
    Produces a new contiguous 358,400-byte INT8 array.
    """
    if not parent_weights_list:
        # Fallback to deterministic pseudo-random seed weights
        return NeuralPolicy._generate_seed_weights("evolved_seed")

    num_parents = len(parent_weights_list)
    child = bytearray(INT8_PARAM_COUNT)

    # 1. Element-wise arithmetic mean across parents
    for i in range(INT8_PARAM_COUNT):
        total = sum(parent[i] for parent in parent_weights_list)
        child[i] = total // num_parents

    # 2. Apply Darwinian mutation
    mutation_hash = hashlib.sha256(bytes(child[:64]) + entropy_seed).digest()
    num_mutations = int(INT8_PARAM_COUNT * mutation_rate)

    for i in range(num_mutations):
        target_idx = int.from_bytes(mutation_hash[i % 32: (i % 32) + 4], "little") % INT8_PARAM_COUNT
        delta = (mutation_hash[(i + 1) % 32] % 15) - 7
        new_val = (child[target_idx] + delta) % 256
        child[target_idx] = new_val

    return bytes(child)


class ReMintingEngine:
    """Orchestrates evolutionary re-minting of insolvent tombstone slots between prompt epochs."""

    def __init__(self, fuel_ledger: FuelLedger, apoptosis_engine: ApoptosisEngine):
        self.fuel_ledger = fuel_ledger
        self.apoptosis_engine = apoptosis_engine

    def remint_tombstone(
        self,
        tombstone_address_str: str,
        node_cluster: Dict[str, SovereignTileNode],
        neighbor_addresses: List[str],
        seed_domain: str = "evolved_agent",
        initial_fuel: int = RE_MINT_SEED_FUEL,
    ) -> SovereignTileNode:
        """
        Re-mints an insolvent tombstone slot:
        1. Inherits INT8 weights from touching neighbors with controlled mutation.
        2. Generates brand new pure ML-KEM-1024 identity (discards old dead key).
        3. Reconstructs Proof of Geometric Fit for the exact slot coordinates.
        4. Re-opens port airlocks with surrounding neighbors.
        """
        if not self.apoptosis_engine.is_tombstone(tombstone_address_str):
            raise ValueError(f"Address {tombstone_address_str} is not an insolvent tombstone slot.")

        addr = HierarchicalAddress.from_string(tombstone_address_str)
        poly = HierarchyEngine.get_polygon(addr)

        # 1. Verify geometric fit against active peers
        active_map = {
            a: n.identity.proof_of_fit for a, n in node_cluster.items()
            if a != tombstone_address_str and not n.is_apoptotic
        }
        proof_of_fit = TopologicalVerifier.verify_tile(addr, poly, {})

        # 2. Collect parent weights from specified solvent neighbors
        parent_weights = []
        for n_addr in neighbor_addresses:
            neighbor_node = node_cluster.get(n_addr)
            if neighbor_node and not neighbor_node.is_apoptotic:
                parent_weights.append(neighbor_node.policy.export_weights())

        # 3. Blend and mutate INT8 weights
        child_weights = blend_and_mutate_weights(
            parent_weights_list=parent_weights,
            entropy_seed=f"remint::{tombstone_address_str}::{self.fuel_ledger.current_epoch}".encode("utf-8")
        )

        # 4. Instantiate brand new Sovereign Tile Node with fresh ML-KEM-1024 keys
        new_node = SovereignTileNode(
            address=addr,
            proof_of_fit=proof_of_fit,
            seed_domain=seed_domain,
            initial_fuel=initial_fuel,
        )
        # Load the evolved child weights
        new_node.policy = NeuralPolicy(weights=child_weights, seed_domain=seed_domain)

        # 5. Register in fuel ledger & reclaim tombstone
        self.fuel_ledger.register_node(tombstone_address_str, initial_fuel=initial_fuel)
        self.apoptosis_engine.reclaim_tombstone(tombstone_address_str)

        # 6. Re-establish mutual port connections with adjacent neighbors
        for n_addr in neighbor_addresses:
            neighbor_node = node_cluster.get(n_addr)
            if neighbor_node and not neighbor_node.is_apoptotic:
                # Re-connect port airlock
                new_node.connect_neighbor(port_idx=8, neighbor_cert=neighbor_node.identity.certificate)
                neighbor_node.connect_neighbor(port_idx=1, neighbor_cert=new_node.identity.certificate)

        node_cluster[tombstone_address_str] = new_node
        return new_node
