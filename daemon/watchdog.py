"""
Hardware Watchdog & Graceful Handoff Daemon.
Monitors physical device health metrics (CPU temperature, memory headroom, battery, port latency).
Enforces Graceful Handoff: when a node overheats (> 85°C) or loses power, evacuates pending
micro-block queues to geometrically touching neighbors before cleanly disconnecting.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from daemon.edge_daemon import EdgeDaemon
from engine.node_runtime import PortPacket


@dataclass
class DeviceHealthReport:
    """Telemetry report describing edge hardware physical health."""
    cpu_temp_c: float
    memory_headroom_kb: int
    battery_pct: Optional[float] = None
    port_latencies_ms: Dict[int, float] = field(default_factory=dict)
    is_healthy: bool = True
    alert_message: Optional[str] = None


@dataclass
class WatchdogThresholds:
    """Thresholds determining emergency handoff conditions."""
    max_cpu_temp_c: float = 85.0
    min_battery_pct: float = 5.0
    min_memory_headroom_kb: int = 16


@dataclass
class GracefulHandoffReceipt:
    """Proof of successful queue evacuation and graceful shutdown."""
    evacuated_address: str
    migrated_packets_count: int
    target_neighbors: List[str]
    handoff_timestamp: float
    reason: str
    status: str  # "COMPLETED", "NO_PENDING_TRAFFIC", "SEVERED_NO_NEIGHBORS"


class HardwareWatchdog:
    """
    Watches hardware operational limits and drives emergency migration of node state
    to touching neighbors in the aperiodic lattice before physical failure.
    """

    def __init__(self, daemon: EdgeDaemon, thresholds: Optional[WatchdogThresholds] = None):
        self.daemon = daemon
        self.thresholds = thresholds or WatchdogThresholds()
        self.handoff_executed = False

    def evaluate_metrics(
        self,
        cpu_temp_c: float = 45.0,
        memory_headroom_kb: int = 100,
        battery_pct: Optional[float] = 100.0,
        port_latencies_ms: Optional[Dict[int, float]] = None,
    ) -> DeviceHealthReport:
        """
        Assesses given hardware telemetry against operating safety limits.
        Returns a DeviceHealthReport indicating whether safe execution can continue.
        """
        port_latencies = port_latencies_ms or {}
        alert = None
        is_healthy = True

        if cpu_temp_c >= self.thresholds.max_cpu_temp_c:
            is_healthy = False
            alert = f"THERMAL_OVERHEAT: CPU temperature {cpu_temp_c}°C exceeds limit {self.thresholds.max_cpu_temp_c}°C"
        elif battery_pct is not None and battery_pct <= self.thresholds.min_battery_pct:
            is_healthy = False
            alert = f"BATTERY_CRITICAL: Remaining battery {battery_pct}% is below {self.thresholds.min_battery_pct}%"
        elif memory_headroom_kb < self.thresholds.min_memory_headroom_kb:
            is_healthy = False
            alert = f"MEMORY_EXHAUSTION: Headroom {memory_headroom_kb} KB is below safe threshold {self.thresholds.min_memory_headroom_kb} KB"

        return DeviceHealthReport(
            cpu_temp_c=cpu_temp_c,
            memory_headroom_kb=memory_headroom_kb,
            battery_pct=battery_pct,
            port_latencies_ms=port_latencies,
            is_healthy=is_healthy,
            alert_message=alert,
        )

    def step_watchdog(
        self,
        cpu_temp_c: float = 45.0,
        memory_headroom_kb: int = 100,
        battery_pct: Optional[float] = 100.0,
        neighbor_daemons: Optional[Dict[int, EdgeDaemon]] = None,
    ) -> Optional[GracefulHandoffReceipt]:
        """
        Inspects metrics and automatically initiates graceful handoff if hardware fails.
        """
        report = self.evaluate_metrics(cpu_temp_c, memory_headroom_kb, battery_pct)
        if not report.is_healthy and not self.handoff_executed:
            return self.execute_graceful_handoff(
                reason=report.alert_message or "UNSPECIFIED_HEALTH_FAILURE",
                neighbor_daemons=neighbor_daemons,
            )
        return None

    def execute_graceful_handoff(
        self,
        reason: str,
        neighbor_daemons: Optional[Dict[int, EdgeDaemon]] = None,
    ) -> GracefulHandoffReceipt:
        """
        Executes Graceful Handoff:
        1. Identifies touching neighbors (from connected neighbor certs or attached neighbor daemons).
        2. Gathers all pending packets across the 14 ingress queues.
        3. Evacuates and reroutes pending traffic to available neighbor queues.
        4. Transitions daemon to OFFLINE state.
        """
        self.handoff_executed = True
        evacuated_addr = self.daemon.config.address
        migrated_packets: List[PortPacket] = []

        # 1. Drain all 14 ingress FIFO queues
        for port_idx in range(14):
            while self.daemon.ingress_queues[port_idx]:
                migrated_packets.append(self.daemon.ingress_queues[port_idx].pop(0))

        # 2. Identify eligible target neighbors
        target_neighbors: List[str] = []
        recipients: List[EdgeDaemon] = []

        if neighbor_daemons:
            for port_idx, n_daemon in neighbor_daemons.items():
                if n_daemon.state == "RUNNING" and not n_daemon.node.is_apoptotic:
                    recipients.append(n_daemon)
                    target_neighbors.append(n_daemon.config.address)
        else:
            # Check connected neighbor certs in node
            for port_idx, cert in self.daemon.node.port_neighbors.items():
                if cert:
                    target_neighbors.append(cert.address if isinstance(cert.address, str) else cert.address.to_string())

        # 3. Migrate packets across active neighbor daemons if available
        migrated_count = len(migrated_packets)
        if recipients and migrated_packets:
            for i, packet in enumerate(migrated_packets):
                # Distribute round-robin to available neighbor ingress port 0
                target_daemon = recipients[i % len(recipients)]
                target_daemon.enqueue_ingress(0, packet)

        # 4. Halt local daemon
        self.daemon.stop()
        self.daemon.state = "OFFLINE_HANDOFF"

        status = "COMPLETED"
        if migrated_count == 0:
            status = "NO_PENDING_TRAFFIC"
        elif not recipients and not target_neighbors:
            status = "SEVERED_NO_NEIGHBORS"

        return GracefulHandoffReceipt(
            evacuated_address=evacuated_addr,
            migrated_packets_count=migrated_count,
            target_neighbors=target_neighbors,
            handoff_timestamp=time.time(),
            reason=reason,
            status=status,
        )
