"""
Unit tests for the Static Memory Edge Daemon (512 KB pre-allocation, non-blocking FIFO queues).
"""

import json
import unittest
from daemon.edge_daemon import EdgeDaemon, DaemonConfig
from engine.node_runtime import SovereignTileNode, PortPacket
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier


class TestEdgeDaemon(unittest.TestCase):

    def setUp(self):
        self.config = DaemonConfig(
            address="G0.M0.S0.T0",
            seed_domain="edge_sensing",
            initial_fuel=50_000,
            max_queue_depth_per_port=4,
        )
        self.daemon = EdgeDaemon(self.config)

    def test_boot_and_memory_audit(self):
        self.daemon.start()
        self.assertEqual(self.daemon.state, "RUNNING")

        status = self.daemon.status_report()
        self.assertEqual(status["state"], "RUNNING")
        self.assertTrue(status["memory_audit"]["under_512kb_limit"])
        self.assertLessEqual(status["memory_audit"]["total_kb"], 512.0)

    def test_enqueue_and_queue_saturation(self):
        packet = PortPacket(
            source_address="G0.M0.S0.T1",
            target_address="G0.M0.S0.T0",
            egress_port=1,
            ingress_port=0,
            envelope={"data": "test"},
            expected_invariant="non_negative",
        )

        # Enqueue up to max depth (4)
        for i in range(4):
            enqueued = self.daemon.enqueue_ingress(0, packet)
            self.assertTrue(enqueued)

        # 5th packet should hit backpressure limit
        rejected = self.daemon.enqueue_ingress(0, packet)
        self.assertFalse(rejected)

        # Invalid port
        invalid_port = self.daemon.enqueue_ingress(14, packet)
        self.assertFalse(invalid_port)

    def test_poll_and_step_execution(self):
        self.daemon.start()
        # Connect neighbor so node can process envelope
        sender_addr = HierarchicalAddress.from_string("G0.M0.S0.T1")
        sender_poly = HierarchyEngine.get_polygon(sender_addr)
        sender_fit = TopologicalVerifier.verify_tile(sender_addr, sender_poly, {})
        sender_node = SovereignTileNode(sender_addr, sender_fit, seed_domain="sender")

        self.daemon.node.connect_neighbor(0, sender_node.identity.certificate)
        sender_node.connect_neighbor(7, self.daemon.node.identity.certificate)

        packet = sender_node.send_to_port(7, json.dumps([10, 20, 30]).encode("utf-8"), "non_negative")
        self.daemon.enqueue_ingress(0, packet)

        receipt = self.daemon.poll_and_step()
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.status, "APPROVED")
        self.assertEqual(self.daemon.processed_transitions, 1)

        # Empty poll returns None
        empty_receipt = self.daemon.poll_and_step()
        self.assertIsNone(empty_receipt)

    def test_daemon_stop(self):
        self.daemon.start()
        self.assertEqual(self.daemon.state, "RUNNING")
        self.daemon.stop()
        self.assertEqual(self.daemon.state, "STOPPED")
        # Step when stopped returns None
        self.assertIsNone(self.daemon.poll_and_step())


if __name__ == "__main__":
    unittest.main()
