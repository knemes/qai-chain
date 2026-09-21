#!/usr/bin/env python3
"""
QAI-Chain: Einstein Spectre Monotile Quantum Swarm Ledger
---------------------------------------------------------
A decentralized, quantum-cryptographic, aperiodic ledger where each block
is an autonomous AI agent represented as an Einstein Spectre 14-gon monotile.

Key Features:
- Proof of Geometric Fit: Aperiodic edge matching rules & non-overlap consensus.
- Quantum Privacy: ML-KEM-1024 (FIPS 203) dual-recipient cognitive epoch encryption.
- Quantum Provenance: ML-DSA-65 (FIPS 204) signatures for identity & relay hops.
- Spatial Firewall: Communication restricted to touching geometric edges.
- Byzantine Containment: Neighbor quorum consensus airlocks & severs rogue nodes.
- Portfolio Bridge: Exports complete 2D mosaic & telemetry to JSON for Three.js.
"""

import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from geometry.spectre import find_valid_open_sites
from pqc_crypto.crypto_utils import (
    generate_kem_keypair,
    generate_dsa_keypair,
    encrypt_envelope,
    decrypt_envelope,
)
from quantum_blockchain.ledger import SpectreSwarmLedger
from quantum_blockchain.tile_block import RelayPacket, TileStatus


def print_banner(text: str):
    line = "=" * 76
    print(f"\n{line}\n  {text}\n{line}")


def main():
    print_banner("QAI-CHAIN: EINSTEIN SPECTRE QUANTUM SWARM LEDGER")
    print("Initializing Ledger with Colony Auditor Keypair (ML-KEM-1024)...")
    ledger = SpectreSwarmLedger()

    # ---------------------------------------------------------
    # 1. Genesis Agent Birth (Block #0)
    # ---------------------------------------------------------
    print_banner("PHASE 1: GENESIS AGENT BIRTH (BLOCK #0)")
    genesis_tile, g_kpk, g_ksk, g_dpk, g_dsk = ledger.create_genesis_agent(
        alias="GenesisCore",
        system_prompt="Root orchestrator: Maintain aperiodic mosaic consensus and integrity.",
    )
    print(f"[*] Genesis Agent Born: [{genesis_tile.agent_alias}]")
    print(f"    Tile ID   : {genesis_tile.tile_id[:16]}...{genesis_tile.tile_id[-8:]}")
    print(f"    Position  : ({genesis_tile.transform.x}, {genesis_tile.transform.y}) at {genesis_tile.transform.rotation_index * 30}°")
    print(f"    ML-KEM PK : {genesis_tile._header_dict()['ml_kem_pk'][:24]}... (1568 bytes)")
    print(f"    ML-DSA PK : {genesis_tile._header_dict()['ml_dsa_pk'][:24]}... (1952 bytes)")

    # ---------------------------------------------------------
    # 2. Sovereign Agent Minting with Proof of Geometric Fit
    # ---------------------------------------------------------
    print_banner("PHASE 2: SOVEREIGN AGENT MINTING (PROOF OF GEOMETRIC FIT)")
    agent_specs = [
        ("ScraperAlpha", "Data ingestion node: Scan external threat intelligence feeds."),
        ("AnalyzerBeta", "Reasoning node: Correlation and threat vector analysis."),
        ("SentinelGamma", "Defensive node: Monitor spatial firewall edge telemetry."),
        ("ArchivistDelta", "Memory node: Cold-store serialized agent cognitive epochs."),
    ]

    agent_keys = {
        genesis_tile.tile_id: {
            "kem_pk": g_kpk, "kem_sk": g_ksk, "dsa_pk": g_dpk, "dsa_sk": g_dsk, "tile": genesis_tile
        }
    }

    for alias, prompt in agent_specs:
        # Discover mathematically valid open perimeter sites (preventing cul-de-sacs)
        open_sites = find_valid_open_sites(ledger.spatial_mosaic, max_sites=6)
        if not open_sites:
            print(f"[!] No open perimeter sites available for {alias}")
            break

        candidate_site = open_sites[0]
        kem_pk, kem_sk = generate_kem_keypair()
        dsa_pk, dsa_sk = generate_dsa_keypair()

        ok, msg, new_agent = ledger.mint_agent(
            alias=alias,
            transform=candidate_site.transform,
            system_prompt=prompt,
            kem_pk=kem_pk,
            dsa_pk=dsa_pk,
            proposer_dsa_sk=dsa_sk,
        )

        if ok and new_agent:
            agent_keys[new_agent.tile_id] = {
                "kem_pk": kem_pk, "kem_sk": kem_sk, "dsa_pk": dsa_pk, "dsa_sk": dsa_sk, "tile": new_agent
            }
            touching = [c["neighbor_alias"] for c in new_agent.edge_connections.values()]
            print(f"[+] Minted Block #{new_agent.index} [{new_agent.agent_alias}]")
            print(f"    Coords   : ({new_agent.transform.x}, {new_agent.transform.y}, {new_agent.transform.rotation_index * 30}°)")
            print(f"    Neighbors: {len(new_agent.edge_connections)} touching edge(s) -> {touching}")
        else:
            print(f"[-] Failed to mint {alias}: {msg}")

    # ---------------------------------------------------------
    # 3. Cognitive Epochs & Live Thought Auditing
    # ---------------------------------------------------------
    print_banner("PHASE 3: COGNITIVE EPOCHS & DUAL-KEM LIVE AUDITING")
    scraper_id = next(tid for tid, data in agent_keys.items() if data["tile"].agent_alias == "ScraperAlpha")
    scraper_data = agent_keys[scraper_id]

    thought_1 = json.dumps({
        "step": 1,
        "thought": "Observed abnormal packet burst on perimeter subnet. Extracting hashes.",
        "entropy_score": 7.94,
        "action": "DELEGATE_ANALYSIS"
    }).encode()

    epoch1 = ledger.record_cognitive_epoch(
        agent_tile_id=scraper_id,
        thought_payload=thought_1,
        agent_kem_pk=scraper_data["kem_pk"],
        agent_dsa_sk=scraper_data["dsa_sk"],
    )
    print(f"[*] Agent [ScraperAlpha] recorded Cognitive Epoch #{epoch1.epoch_index}")
    print(f"    Epoch Hash      : {epoch1.epoch_hash[:20]}...")
    print(f"    Dual Envelope CT: {epoch1.dual_envelope['ciphertext'][:32]}... (AES-256-GCM)")
    print(f"    Agent KEM CT    : {epoch1.dual_envelope['agent_slot']['kem_ct'][:24]}...")
    print(f"    Auditor KEM CT  : {epoch1.dual_envelope['auditor_slot']['kem_ct'][:24]}...")

    # Verify Agent self-decryption
    decrypted_by_agent = ledger.read_cognitive_epoch(epoch1, scraper_data["kem_sk"], is_auditor=False)
    print(f"[+] Agent Self-Recall Verified: {decrypted_by_agent.decode()[:60]}...")

    # Verify Colony Auditor live inspection
    decrypted_by_auditor = ledger.read_cognitive_epoch(epoch1, ledger.auditor_kem_sk, is_auditor=True)
    print(f"[+] Colony Auditor Live Stream Verified: {decrypted_by_auditor.decode()[:60]}...")

    # ---------------------------------------------------------
    # 4. Spatial Firewall: Quantum Hop-by-Hop Relaying
    # ---------------------------------------------------------
    print_banner("PHASE 4: SPATIAL FIREWALL & HOP-BY-HOP ROUTING")
    # Route from ScraperAlpha -> touching neighbor -> destination
    scraper_tile = scraper_data["tile"]
    first_neighbor_id = list(scraper_tile.edge_connections.values())[0]["neighbor_tile_id"]
    dest_id = next((tid for tid in agent_keys if tid not in [scraper_id, first_neighbor_id]), first_neighbor_id)
    dest_data = agent_keys[dest_id]

    secret_message = b"QUANTUM_TASK_PAYLOAD: Deep forensic trace on target node."
    sealed_inner_envelope = encrypt_envelope(secret_message, dest_data["kem_pk"])

    # Multi-hop route: [ScraperAlpha -> Neighbor -> Destination]
    hop_path = [scraper_id, first_neighbor_id]
    if dest_id != first_neighbor_id:
        hop_path.append(dest_id)

    packet = RelayPacket(
        source_tile_id=scraper_id,
        destination_tile_id=dest_id,
        hop_path=hop_path,
        encrypted_payload_envelope=sealed_inner_envelope,
    )

    print(f"[*] Dispatching RelayPacket {packet.packet_id[:12]}...")
    print(f"    Route: {' -> '.join([agent_keys[tid]['tile'].agent_alias for tid in hop_path])}")

    # Hop 1
    hop1_ok, hop1_msg = ledger.route_relay_packet(packet, scraper_data["dsa_sk"])
    print(f"    [Hop 1] {hop1_msg}")

    # Hop 2 (if multi-hop)
    if len(hop_path) > 2:
        inter_sk = agent_keys[first_neighbor_id]["dsa_sk"]
        hop2_ok, hop2_msg = ledger.route_relay_packet(packet, inter_sk)
        print(f"    [Hop 2] {hop2_msg}")

    # Destination decapsulates
    decrypted_secret = decrypt_envelope(packet.encrypted_payload_envelope, dest_data["kem_sk"])
    print(f"[+] Destination [{dest_data['tile'].agent_alias}] decrypted payload: {decrypted_secret.decode()}")

    # ---------------------------------------------------------
    # 5. Byzantine Containment & Neighbor Quorum Airlock
    # ---------------------------------------------------------
    print_banner("PHASE 5: BYZANTINE CONTAINMENT & AIRLOCK QUARANTINE")
    # Simulate a rogue agent exhibiting tampered/forged signatures
    rogue_id = scraper_id
    rogue_tile = scraper_tile
    touching_neighbors = list(rogue_tile.edge_connections.values())

    print(f"[!] Anomalous behavior flagged on Agent [{rogue_tile.agent_alias}]")
    print(f"    Touching neighbors evaluating perimeter quorum: {[n['neighbor_alias'] for n in touching_neighbors]}")

    # Touching neighbors sign attestations
    attestations = []
    for conn in touching_neighbors:
        n_id = conn["neighbor_tile_id"]
        n_sk = agent_keys[n_id]["dsa_sk"]
        attestations.append((n_id, n_sk))

    # Trigger Byzantine incident
    accuser_id = attestations[0][0]
    q_success, q_report = ledger.submit_byzantine_incident(
        target_tile_id=rogue_id,
        accuser_tile_id=accuser_id,
        incident_type="INVALID_SIGNATURE_INJECTION",
        details="Attempted illegal cross-perimeter payload injection with invalid ML-DSA signature.",
        neighbor_attestations=attestations,
        quorum_threshold=len(attestations),
    )

    print(f"[*] Quarantine Result: {q_report}")
    print(f"    Agent [{rogue_tile.agent_alias}] Status: {rogue_tile.status.value}")
    print(f"    Remaining Edges on [{rogue_tile.agent_alias}]: {len(rogue_tile.edge_connections)} (Completely Airlocked)")

    # ---------------------------------------------------------
    # 6. Export State for Three.js Portfolio Integration
    # ---------------------------------------------------------
    print_banner("PHASE 6: EXPORT COLONY MOSAIC FOR PORTFOLIO")
    state_file = os.path.join(os.path.dirname(__file__), "spectre_colony_state.json")
    ledger.export_colony_state(state_file)
    print(f"[+] Successfully exported {len(ledger.tiles)} tiles, {sum(len(e) for e in ledger.epochs_by_agent.values())} epochs, and {len(ledger.audit_records)} audit records.")

    print_banner("DEMO COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
