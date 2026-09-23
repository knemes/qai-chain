"""
Unit tests for the Hardware Watchdog and Graceful Handoff Daemon.
"""

import json
import unittest
from daemon.edge_daemon import EdgeDaemon, DaemonConfig
from daemon.watchdog import HardwareWatchdog, WatchdogThresholds
from engine.node_runtime import PortPacket


class TestWatchdog(unittest.TestCase):

    def setUp(self):
        self.config_a = DaemonConfig(address="G0.M0.S0.T0", seed_domain="node_a")
        self.config_b = DaemonConfig(address="G0.M0.S0.T1", seed_domain="node_b")

        self.daemon_a = EdgeDaemon(self.config_a)
        self.daemon_b = EdgeDaemon(self.config_b)

        self.daemon_a.start()
        self.daemon_b.start()

        self.watchdog = HardwareWatchdog(self.daemon_a)

    def test_healthy_telemetry(self):
        report = self.watchdog.evaluate_metrics(
            cpu_temp_c=50.0,
            memory_headroom_kb=120,
            battery_pct=85.0,
        )
        self.assertTrue(report.is_healthy)
        self.assertIsNone(report.alert_message)

    def test_thermal_overheat_alert(self):
        report = self.watchdog.evaluate_metrics(
            cpu_temp_c=88.5,
            memory_headroom_kb=100,
            battery_pct=80.0,
        )
        self.assertFalse(report.is_healthy)
        self.assertIn("THERMAL_OVERHEAT", report.alert_message)

    def test_battery_critical_alert(self):
        report = self.watchdog.evaluate_metrics(
            cpu_temp_c=45.0,
            memory_headroom_kb=100,
            battery_pct=3.0,
        )
        self.assertFalse(report.is_healthy)
        self.assertIn("BATTERY_CRITICAL", report.alert_message)

    def test_memory_exhaustion_alert(self):
        report = self.watchdog.evaluate_metrics(
            cpu_temp_c=45.0,
            memory_headroom_kb=8,
            battery_pct=80.0,
        )
        self.assertFalse(report.is_healthy)
        self.assertIn("MEMORY_EXHAUSTION", report.alert_message)

    def test_graceful_handoff_with_traffic(self):
        # Enqueue packets on daemon_a
        for p in range(3):
            packet = PortPacket(
                source_address="G0.M0.S0.T2",
                target_address="G0.M0.S0.T0",
                egress_port=p,
                ingress_port=p,
                envelope={"data": f"packet_{p}"},
                expected_invariant="non_negative",
            )
            self.daemon_a.enqueue_ingress(p, packet)

        neighbors = {1: self.daemon_b}

        # Step watchdog with overheating CPU
        receipt = self.watchdog.step_watchdog(
            cpu_temp_c=92.0,
            neighbor_daemons=neighbors,
        )

        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.status, "COMPLETED")
        self.assertEqual(receipt.migrated_packets_count, 3)
        self.assertIn("G0.M0.S0.T1", receipt.target_neighbors)

        # daemon_a should have 0 packets left and be in OFFLINE_HANDOFF state
        for p in range(14):
            self.assertEqual(len(self.daemon_a.ingress_queues[p]), 0)
        self.assertEqual(self.daemon_a.state, "OFFLINE_HANDOFF")

        # daemon_b should have received the migrated packets
        self.assertEqual(len(self.daemon_b.ingress_queues[0]), 3)

    def test_graceful_handoff_empty_traffic(self):
        receipt = self.watchdog.execute_graceful_handoff(
            reason="MANUAL_MAINTENANCE",
            neighbor_daemons={1: self.daemon_b},
        )
        self.assertEqual(receipt.status, "NO_PENDING_TRAFFIC")
        self.assertEqual(receipt.migrated_packets_count, 0)
        self.assertEqual(self.daemon_a.state, "OFFLINE_HANDOFF")


if __name__ == "__main__":
    unittest.main()
