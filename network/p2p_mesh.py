"""
P2P Point-to-Point Mesh Transport.
Maps network links directly to the 14 touching contact edges of the aperiodic lattice.
Enforces the Spatial Firewall: connections are established ONLY between verified geometric neighbors.
Non-touching or spoofed nodes are rejected at the handshake layer with pure ML-KEM-1024 identity verification.
"""

import math
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional
from pqc_crypto.spatial_identity import SpatialCertificate, STRICT_KEM_ALG
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier
from engine.node_runtime import SovereignTileNode
from ledger.port_wire import pack_wire_frame, unpack_wire_frame, WireFrame


@dataclass
class HandshakeResult:
    """Receipt emitted upon attempting a point-to-point geometric port link."""
    is_connected: bool
    local_port: int
    remote_port: int
    remote_address: str
    rejection_reason: Optional[str] = None


class P2PMeshLink:
    """Point-to-point link connecting touching edges of two sovereign tiles."""

    def __init__(self, local_port: int, remote_port: int, remote_cert: SpatialCertificate):
        self.local_port = local_port
        self.remote_port = remote_port
        self.remote_cert = remote_cert
        self.is_active = True
        self.bytes_transmitted = 0

    def send_frame(self, frame_bytes: bytes):
        """Transmits a binary wire frame across the link."""
        if not self.is_active:
            raise ConnectionError("Cannot send: P2P link has been severed.")
        self.bytes_transmitted += len(frame_bytes)

    def close(self):
        """Closes the link."""
        self.is_active = False


class P2PMeshTransport:
    """Manages geometric handshakes and spatial firewall enforcement between edge nodes."""

    @classmethod
    def attempt_geometric_handshake(
        cls,
        node_a: SovereignTileNode,
        port_a: int,
        node_b: SovereignTileNode,
        port_b: int,
    ) -> HandshakeResult:
        """
        Executes the 3-step Spatial Firewall Handshake:
        1. Validate pure ML-KEM-1024 certificates for both nodes.
        2. Verify that Edge A and Edge B are geometrically touching in 2D space.
        3. Verify that edge polarities are complementary (pol_A + pol_B == 0).
        """
        # Step 1: Certificate Verification
        if not node_a.identity.certificate.verify():
            return HandshakeResult(False, port_a, port_b, node_b.address.to_string(), "ERR_CERT_INVALID: Node A cert failed verification.")
        if not node_b.identity.certificate.verify():
            return HandshakeResult(False, port_a, port_b, node_b.address.to_string(), "ERR_CERT_INVALID: Node B cert failed verification.")

        # Step 2: Geometric Contact Verification
        poly_a = HierarchyEngine.get_polygon(node_a.address)
        poly_b = HierarchyEngine.get_polygon(node_b.address)

        edge_a = poly_a.edges[port_a % 14]
        edge_b = poly_b.edges[port_b % 14]

        # Edges meet in opposite winding: edge_a[0] ≈ edge_b[1] and edge_a[1] ≈ edge_b[0]
        p1_dist = math.hypot(edge_a[0][0] - edge_b[1][0], edge_a[0][1] - edge_b[1][1])
        p2_dist = math.hypot(edge_a[1][0] - edge_b[0][0], edge_a[1][1] - edge_b[0][1])

        if p1_dist > 0.05 or p2_dist > 0.05:
            return HandshakeResult(
                False, port_a, port_b, node_b.address.to_string(),
                f"ERR_SPATIAL_FIREWALL: Port {port_a} of {node_a.address.to_string()} does not physically touch Port {port_b} of {node_b.address.to_string()}."
            )

        # Step 3: Polarity Verification
        pol_a = poly_a.get_edge_polarity(port_a)
        pol_b = poly_b.get_edge_polarity(port_b)

        if pol_a + pol_b != 0:
            return HandshakeResult(
                False, port_a, port_b, node_b.address.to_string(),
                f"ERR_POLARITY_MISMATCH: Edge polarities {pol_a} and {pol_b} do not interlock (sum != 0)."
            )

        # Successful handshake: lock mutual ports
        node_a.connect_neighbor(port_a, node_b.identity.certificate)
        node_b.connect_neighbor(port_b, node_a.identity.certificate)

        return HandshakeResult(
            is_connected=True,
            local_port=port_a,
            remote_port=port_b,
            remote_address=node_b.address.to_string(),
            rejection_reason=None,
        )
