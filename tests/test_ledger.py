import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from geometry.spectre import find_valid_open_sites
from pqc_crypto.crypto_utils import (
    generate_kem_keypair,
    generate_dsa_keypair,
    encrypt_envelope,
)
from quantum_blockchain.ledger import SpectreSwarmLedger
from quantum_blockchain.tile_block import RelayPacket, TileStatus


class TestSpectreSwarmLedger(unittest.TestCase):
    def test_full_colony_lifecycle(self):
        ledger = SpectreSwarmLedger()

        # 1. Birth of Genesis Sentinel
        genesis, g_kpk, g_ksk, g_dpk, g_dsk = ledger.create_genesis_agent("GenesisSentinel")
        self.assertEqual(len(ledger.tiles), 1)
        self.assertEqual(genesis.index, 0)
        self.assertTrue(genesis.verify_tile_signature())

        # 2. Discover open perimeter sites and mint Agent 1
        open_sites = find_valid_open_sites(ledger.spatial_mosaic, max_sites=3)
        self.assertGreater(len(open_sites), 0)

        a1_kpk, a1_ksk = generate_kem_keypair()
        a1_dpk, a1_dsk = generate_dsa_keypair()
        success1, msg1, agent1 = ledger.mint_agent(
            "ScraperAlpha",
            open_sites[0].transform,
            "Scrape and index public security bulletins.",
            a1_kpk,
            a1_dpk,
            a1_dsk,
        )
        self.assertTrue(success1, msg1)
        self.assertIsNotNone(agent1)
        self.assertGreater(len(agent1.edge_connections), 0)
        self.assertGreater(len(genesis.edge_connections), 0)

        # 3. Mint Agent 2 along next open perimeter site
        next_sites = find_valid_open_sites(ledger.spatial_mosaic, max_sites=5)
        self.assertGreater(len(next_sites), 0)

        a2_kpk, a2_ksk = generate_kem_keypair()
        a2_dpk, a2_dsk = generate_dsa_keypair()
        success2, msg2, agent2 = ledger.mint_agent(
            "AnalyzerBeta",
            next_sites[0].transform,
            "Analyze threat signatures and coordinate defense.",
            a2_kpk,
            a2_dpk,
            a2_dsk,
        )
        self.assertTrue(success2, msg2)
        self.assertIsNotNone(agent2)

        # 4. Cognitive Epochs: Test dual-recipient encryption
        thought_data = b'{"action": "SCAN", "target": "cve-2026-9912", "confidence": 0.98}'
        epoch = ledger.record_cognitive_epoch(
            agent1.tile_id, thought_data, a1_kpk, a1_dsk
        )
        self.assertTrue(epoch.verify(a1_dpk))

        # Agent reads its own memory
        agent_read = ledger.read_cognitive_epoch(epoch, a1_ksk, is_auditor=False)
        self.assertEqual(thought_data, agent_read)

        # Colony auditor reads live memory stream
        auditor_read = ledger.read_cognitive_epoch(epoch, ledger.auditor_kem_sk, is_auditor=True)
        self.assertEqual(thought_data, auditor_read)

        # 5. Spatial Firewall Relay
        # Encrypt secret payload intended ONLY for Agent 2
        secret_payload = b"CLASSIFIED_THREAT_SIGNATURE_0x9A"
        inner_envelope = encrypt_envelope(secret_payload, a2_kpk)

        # Test valid hop from Agent 1 -> touching neighbor
        touching_neighbor_id = list(agent1.edge_connections.values())[0]["neighbor_tile_id"]
        valid_packet = RelayPacket(
            source_tile_id=agent1.tile_id,
            destination_tile_id=touching_neighbor_id,
            hop_path=[agent1.tile_id, touching_neighbor_id],
            encrypted_payload_envelope=inner_envelope,
        )
        hop_ok, hop_msg = ledger.route_relay_packet(valid_packet, a1_dsk)
        self.assertTrue(hop_ok, hop_msg)

        # Test illegal non-touching hop rejection (Spatial Firewall)
        # Create an artificial non-existent hop
        fake_id = "0000000000000000000000000000000000000000000000000000000000000000"
        invalid_packet = RelayPacket(
            source_tile_id=agent1.tile_id,
            destination_tile_id=fake_id,
            hop_path=[agent1.tile_id, fake_id],
            encrypted_payload_envelope=inner_envelope,
        )
        illegal_hop_ok, _ = ledger.route_relay_packet(invalid_packet, a1_dsk)
        self.assertFalse(illegal_hop_ok, "Spatial firewall must reject non-touching hops")

        # 6. Byzantine Incident & Neighborhood Quarantine Airlock
        # Simulate neighbor detecting bad signature / tampering on Agent 1
        accuser_id = list(agent1.edge_connections.values())[0]["neighbor_tile_id"]
        accuser_sk = g_dsk if accuser_id == genesis.tile_id else a2_dsk

        q_ok, q_msg = ledger.submit_byzantine_incident(
            target_tile_id=agent1.tile_id,
            accuser_tile_id=accuser_id,
            incident_type="INVALID_SIGNATURE",
            details="Detected forged outer hop transport signature.",
            neighbor_attestations=[(accuser_id, accuser_sk)],
            quorum_threshold=1,  # 1 neighbor for unit test
        )
        self.assertTrue(q_ok)
        self.assertEqual(agent1.status, TileStatus.QUARANTINED)
        self.assertEqual(len(agent1.edge_connections), 0, "Quarantined agent edges must be severed")


if __name__ == "__main__":
    unittest.main()
