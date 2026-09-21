import json
import time
import binascii
from typing import List, Dict, Any, Optional, Tuple

from geometry.spectre import (
    SpectreTransform,
    SpectrePolygon,
    verify_geometric_fit,
    find_valid_open_sites,
)
from pqc_crypto.crypto_utils import (
    generate_kem_keypair,
    generate_dsa_keypair,
    encrypt_dual_envelope,
    decrypt_dual_envelope,
    verify_payload,
)
from .tile_block import (
    SpectreTile,
    CognitiveEpoch,
    RelayPacket,
    TileAuditRecord,
    TileStatus,
)


class SpectreSwarmLedger:
    """
    Decentralized quantum cryptographic ledger where each block is a sovereign
    AI Agent represented as an Einstein Spectre Monotile.
    """

    def __init__(self, auditor_kem_pk: Optional[bytes] = None, auditor_kem_sk: Optional[bytes] = None):
        self.tiles: List[SpectreTile] = []
        self.tiles_by_id: Dict[str, SpectreTile] = {}
        self.spatial_mosaic: List[SpectrePolygon] = []
        self.epochs_by_agent: Dict[str, List[CognitiveEpoch]] = {}
        self.audit_records: List[TileAuditRecord] = []

        # Colony Auditor Keypair (for real-time live supervisory inspection of thought streams)
        if auditor_kem_pk and auditor_kem_sk:
            self.auditor_kem_pk = auditor_kem_pk
            self.auditor_kem_sk = auditor_kem_sk
        else:
            self.auditor_kem_pk, self.auditor_kem_sk = generate_kem_keypair()

    def get_last_tile(self) -> Optional[SpectreTile]:
        return self.tiles[-1] if self.tiles else None

    def create_genesis_agent(
        self,
        alias: str = "GenesisSentinel",
        system_prompt: str = "Protect the colony and ensure aperiodic geometric consensus."
    ) -> Tuple[SpectreTile, bytes, bytes, bytes, bytes]:
        """
        Mints the seed Agent Tile (Block #0) at origin (0, 0, 0°).
        Returns (genesis_tile, kem_pk, kem_sk, dsa_pk, dsa_sk).
        """
        if self.tiles:
            raise ValueError("Genesis tile already exists.")

        kem_pk, kem_sk = generate_kem_keypair()
        dsa_pk, dsa_sk = generate_dsa_keypair()

        import hashlib
        prompt_hash = hashlib.sha256(system_prompt.encode()).hexdigest()

        genesis = SpectreTile(
            index=0,
            agent_alias=alias,
            transform=SpectreTransform(0.0, 0.0, 0),
            ml_kem_public_key=kem_pk,
            ml_dsa_public_key=dsa_pk,
            system_prompt_commitment=prompt_hash,
            previous_block_hash="0"
        )
        genesis.sign_tile(dsa_sk)

        self.tiles.append(genesis)
        self.tiles_by_id[genesis.tile_id] = genesis
        self.spatial_mosaic.append(genesis.polygon)
        self.epochs_by_agent[genesis.tile_id] = []

        return genesis, kem_pk, kem_sk, dsa_pk, dsa_sk

    def mint_agent(
        self,
        alias: str,
        transform: SpectreTransform,
        system_prompt: str,
        kem_pk: bytes,
        dsa_pk: bytes,
        proposer_dsa_sk: bytes,
    ) -> Tuple[bool, str, Optional[SpectreTile]]:
        """
        Mints a new sovereign agent block onto the ledger:
        1. Verifies Proof of Geometric Fit against the existing Spectre mosaic.
        2. Binds touching edges mutually between the new agent and neighbors.
        3. Appends block to the ledger chain and spatial index.
        """
        import hashlib
        candidate_poly = SpectrePolygon(transform)

        # 1. Consensus: Verify Proof of Geometric Fit
        is_valid, reason, contacts = verify_geometric_fit(candidate_poly, self.spatial_mosaic)
        if not is_valid:
            return False, f"Consensus fit failure: {reason}", None

        last_block = self.get_last_tile()
        prev_hash = last_block.tile_id if last_block else "0"
        prompt_hash = hashlib.sha256(system_prompt.encode()).hexdigest()

        new_tile = SpectreTile(
            index=len(self.tiles),
            agent_alias=alias,
            transform=transform,
            ml_kem_public_key=kem_pk,
            ml_dsa_public_key=dsa_pk,
            system_prompt_commitment=prompt_hash,
            previous_block_hash=prev_hash,
        )

        # 2. Mutually bind contacting edges
        for neighbor_idx, cand_edge_idx, neighbor_edge_idx in contacts:
            neighbor_tile = self.tiles[neighbor_idx]
            new_tile.edge_connections[cand_edge_idx] = {
                "neighbor_tile_id": neighbor_tile.tile_id,
                "neighbor_edge_idx": neighbor_edge_idx,
                "neighbor_alias": neighbor_tile.agent_alias,
            }
            neighbor_tile.edge_connections[neighbor_edge_idx] = {
                "neighbor_tile_id": new_tile.tile_id,
                "neighbor_edge_idx": cand_edge_idx,
                "neighbor_alias": new_tile.agent_alias,
            }

        # 3. Sign the block
        new_tile.sign_tile(proposer_dsa_sk)

        # 4. Commit to ledger
        self.tiles.append(new_tile)
        self.tiles_by_id[new_tile.tile_id] = new_tile
        self.spatial_mosaic.append(new_tile.polygon)
        self.epochs_by_agent[new_tile.tile_id] = []

        return True, f"Agent [{alias}] successfully minted at ({transform.x}, {transform.y})", new_tile

    def record_cognitive_epoch(
        self,
        agent_tile_id: str,
        thought_payload: bytes,
        agent_kem_pk: bytes,
        agent_dsa_sk: bytes,
    ) -> CognitiveEpoch:
        """
        Records an append-only cognitive epoch for an agent.
        Payload is dual-encrypted for the Agent and Colony Auditor.
        """
        if agent_tile_id not in self.tiles_by_id:
            raise ValueError("Agent tile not registered on ledger.")

        tile = self.tiles_by_id[agent_tile_id]
        if tile.status == TileStatus.QUARANTINED:
            raise PermissionError("Quarantined agents cannot append to cognitive streams.")

        agent_stream = self.epochs_by_agent[agent_tile_id]
        prev_hash = agent_stream[-1].epoch_hash if agent_stream else "0"
        epoch_idx = len(agent_stream)

        # Dual-Recipient KEM-DEM Hybrid Encryption
        dual_envelope = encrypt_dual_envelope(
            thought_payload, agent_kem_pk, self.auditor_kem_pk
        )

        epoch = CognitiveEpoch(
            agent_tile_id=agent_tile_id,
            epoch_index=epoch_idx,
            prev_epoch_hash=prev_hash,
            dual_envelope=dual_envelope,
        )
        epoch.sign(agent_dsa_sk)
        agent_stream.append(epoch)

        return epoch

    def read_cognitive_epoch(
        self,
        epoch: CognitiveEpoch,
        decapsulation_sk: bytes,
        is_auditor: bool = False,
    ) -> bytes:
        """Decrypts a cognitive epoch payload using either Agent SK or Colony Auditor SK."""
        return decrypt_dual_envelope(epoch.dual_envelope, decapsulation_sk, is_auditor=is_auditor)

    def route_relay_packet(
        self,
        packet: RelayPacket,
        current_sender_dsa_sk: bytes,
    ) -> Tuple[bool, str]:
        """
        Enforces the Spatial Firewall:
        Every hop step in hop_path must represent an active, unsevered touching edge.
        Intermediary agents cannot decrypt the inner payload sealed for the destination.
        """
        hop_idx = packet.current_hop_index
        if hop_idx >= len(packet.hop_path) - 1:
            return True, "Packet has already reached final destination."

        current_id = packet.hop_path[hop_idx]
        next_id = packet.hop_path[hop_idx + 1]

        current_tile = self.tiles_by_id.get(current_id)
        next_tile = self.tiles_by_id.get(next_id)

        if not current_tile or not next_tile:
            return False, "Spatial firewall violation: unknown agent in route."

        if current_tile.status == TileStatus.QUARANTINED or next_tile.status == TileStatus.QUARANTINED:
            return False, "Spatial firewall violation: edge traverses quarantined agent."

        # Verify physical edge contact in mosaic
        touching = False
        for edge_idx, conn in current_tile.edge_connections.items():
            if conn["neighbor_tile_id"] == next_id:
                touching = True
                break

        if not touching:
            return (
                False,
                f"Spatial firewall violation: Agent [{current_tile.agent_alias}] and "
                f"[{next_tile.agent_alias}] do not touch along any geometric edge."
            )

        # Authenticate hop
        packet.sign_hop(current_sender_dsa_sk)
        packet.current_hop_index += 1

        is_destination = (packet.current_hop_index == len(packet.hop_path) - 1)
        status_msg = (
            f"Relayed across touching edge to destination [{next_tile.agent_alias}]"
            if is_destination
            else f"Relayed across touching edge to intermediary [{next_tile.agent_alias}]"
        )
        return True, status_msg

    def submit_byzantine_incident(
        self,
        target_tile_id: str,
        accuser_tile_id: str,
        incident_type: str,
        details: str,
        neighbor_attestations: List[Tuple[str, bytes]],
        quorum_threshold: int = 2,
    ) -> Tuple[bool, str]:
        """
        Processes forensic neighbor reports. If >= quorum touching neighbors attest
        to violations (e.g. invalid signature, payload tampering), the target tile is
        airlocked and quarantined by severing all its perimeter connections.
        """
        target = self.tiles_by_id.get(target_tile_id)
        if not target:
            return False, "Target agent tile not found."

        # Get active direct neighbor IDs
        direct_neighbor_ids = {
            conn["neighbor_tile_id"] for conn in target.edge_connections.values()
        }

        audit = TileAuditRecord(target_tile_id, accuser_tile_id, incident_type, details)

        valid_attestation_count = 0
        for n_id, n_sk in neighbor_attestations:
            if n_id in direct_neighbor_ids:
                audit.add_attestation(n_id, n_sk)
                valid_attestation_count += 1

        self.audit_records.append(audit)

        if valid_attestation_count >= quorum_threshold:
            # Execute Quarantine & Airlock
            target.status = TileStatus.QUARANTINED

            # Sever mutual edge connections from all neighbors
            for c_edge_idx, conn in list(target.edge_connections.items()):
                n_id = conn["neighbor_tile_id"]
                n_tile = self.tiles_by_id.get(n_id)
                if n_tile:
                    # Remove reverse edge connection
                    n_tile.edge_connections = {
                        k: v for k, v in n_tile.edge_connections.items()
                        if v["neighbor_tile_id"] != target_tile_id
                    }

            target.edge_connections.clear()
            return True, f"Quorum of {valid_attestation_count} neighbors verified violation. Agent [{target.agent_alias}] QUARANTINED and AIRLOCKED."

        return False, f"Audit recorded. Insufficient neighbor quorum ({valid_attestation_count}/{quorum_threshold})."

    def save_to_file(self, filepath: str = "spectre_ledger_data.json") -> None:
        """Persists the complete ledger state to disk."""
        data = {
            "metadata": {
                "total_agents": len(self.tiles),
                "timestamp": time.time(),
                "auditor_kem_pk": binascii.hexlify(self.auditor_kem_pk).decode("ascii"),
                "auditor_kem_sk": binascii.hexlify(self.auditor_kem_sk).decode("ascii") if self.auditor_kem_sk else None,
            },
            "tiles": [t.to_dict() for t in self.tiles],
            "cognitive_epochs": {
                tid: [e.to_dict() for e in epochs]
                for tid, epochs in self.epochs_by_agent.items()
            },
            "audit_records": [a.to_dict() for a in self.audit_records],
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Ledger state successfully saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str = "spectre_ledger_data.json") -> "SpectreSwarmLedger":
        """Loads and reconstructs the complete ledger state and spatial mosaic from disk."""
        with open(filepath, "r") as f:
            data = json.load(f)

        meta = data["metadata"]
        auditor_pk = binascii.unhexlify(meta["auditor_kem_pk"])
        auditor_sk = binascii.unhexlify(meta["auditor_kem_sk"]) if meta.get("auditor_kem_sk") else None

        ledger = cls(auditor_kem_pk=auditor_pk, auditor_kem_sk=auditor_sk)

        # Restore tiles
        for t_data in data["tiles"]:
            tile = SpectreTile.from_dict(t_data)
            ledger.tiles.append(tile)
            ledger.tiles_by_id[tile.tile_id] = tile
            ledger.spatial_mosaic.append(tile.polygon)

        # Restore cognitive epochs
        for tid, epochs_data in data.get("cognitive_epochs", {}).items():
            ledger.epochs_by_agent[tid] = [CognitiveEpoch.from_dict(e) for e in epochs_data]

        # Restore audit records
        for a_data in data.get("audit_records", []):
            audit = TileAuditRecord(
                target_tile_id=a_data["target_tile_id"],
                accuser_tile_id=a_data["accuser_tile_id"],
                incident_type=a_data["incident_type"],
                details=a_data["details"],
                timestamp=a_data.get("timestamp"),
            )
            audit.audit_id = a_data["audit_id"]
            audit.supporting_neighbor_signatures = a_data.get("supporting_neighbor_signatures", {})
            ledger.audit_records.append(audit)

        print(f"Ledger loaded: {len(ledger.tiles)} tiles, {len(ledger.spatial_mosaic)} spatial polygons restored.")
        return ledger

    def export_colony_state(self, filepath: str = "spectre_colony_state.json") -> None:
        """Exports the entire colony state (geometry, edges, epochs, audits) for Three.js rendering."""
        data = {
            "metadata": {
                "total_agents": len(self.tiles),
                "timestamp": time.time(),
                "auditor_kem_pk": binascii.hexlify(self.auditor_kem_pk).decode("ascii"),
            },
            "tiles": [t.to_dict() for t in self.tiles],
            "cognitive_epochs": {
                tid: [e.to_dict() for e in epochs]
                for tid, epochs in self.epochs_by_agent.items()
            },
            "audit_records": [a.to_dict() for a in self.audit_records],
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Colony state exported to {filepath}")
