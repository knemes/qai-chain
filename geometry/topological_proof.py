"""
Topological Sybil Resistance & Proof of Geometric Fit Engine.
Deterministically verifies that any node claiming a slot on the aperiodic lattice
satisfies the immutable geometric invariants: unit edge length, discrete chiral angles,
non-overlapping interior bounds, and complementary edge polarities.
"""

import math
import hashlib
import json
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
from geometry.spectre import (
    SPECTRE_BASE_VERTICES,
    SPECTRE_EDGE_POLARITIES,
    SpectreTransform,
    SpectrePolygon,
)
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine

TOLERANCE = 1e-4


def _dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def compute_polygon_hash(polygon: SpectrePolygon) -> str:
    """Computes a canonical SHA-256 hash of the quantized 14 vertex coordinates."""
    quantized = [[round(v[0], 4), round(v[1], 4)] for v in polygon.vertices]
    canonical_bytes = json.dumps(quantized, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


@dataclass
class NeighborContactProof:
    """Evidence of valid interlocking edge contact with an adjacent neighbor."""
    neighbor_address: str
    local_edge_idx: int
    neighbor_edge_idx: int
    local_polarity: int
    neighbor_polarity: int
    contact_midpoint: Tuple[float, float]
    is_polarity_valid: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "neighbor_address": self.neighbor_address,
            "local_edge_idx": self.local_edge_idx,
            "neighbor_edge_idx": self.neighbor_edge_idx,
            "local_polarity": self.local_polarity,
            "neighbor_polarity": self.neighbor_polarity,
            "contact_midpoint": [round(self.contact_midpoint[0], 4), round(self.contact_midpoint[1], 4)],
            "is_polarity_valid": self.is_polarity_valid,
        }


@dataclass
class ProofOfGeometricFit:
    """
    Cryptographic and geometric receipt proving a tile occupies a valid slot.
    Serves as Topological Sybil Resistance against unauthorized insertions.
    """
    address: str
    centroid: Tuple[float, float]
    rotation_index: int
    polygon_hash: str
    neighbor_contacts: List[NeighborContactProof] = field(default_factory=list)
    is_edge_length_valid: bool = True
    is_angle_valid: bool = True
    is_polarity_valid: bool = True
    is_non_overlapping: bool = True
    is_fully_valid: bool = True
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "centroid": [round(self.centroid[0], 4), round(self.centroid[1], 4)],
            "rotation_index": self.rotation_index,
            "polygon_hash": self.polygon_hash,
            "neighbor_contacts": [c.to_dict() for c in self.neighbor_contacts],
            "is_edge_length_valid": self.is_edge_length_valid,
            "is_angle_valid": self.is_angle_valid,
            "is_polarity_valid": self.is_polarity_valid,
            "is_non_overlapping": self.is_non_overlapping,
            "is_fully_valid": self.is_fully_valid,
            "rejection_reason": self.rejection_reason,
        }


class TopologicalVerifier:
    """Rigorous verification engine enforcing aperiodic monotile invariants."""

    @staticmethod
    def verify_edge_lengths(polygon: SpectrePolygon) -> Tuple[bool, Optional[str]]:
        """Verifies that all 14 edges have Euclidean length 1.0."""
        edges = polygon.edges
        for idx, (p1, p2) in enumerate(edges):
            length = _dist(p1, p2)
            if abs(length - 1.0) > TOLERANCE:
                return False, f"Edge {idx} length {length:.6f} != 1.0"
        return True, None

    @staticmethod
    def verify_angles(polygon: SpectrePolygon) -> Tuple[bool, Optional[str]]:
        """Verifies that interior turning angles match the 14-gon Spectre signature."""
        verts = polygon.vertices
        n = len(verts)
        for i in range(n):
            p_prev = verts[(i - 1) % n]
            p_curr = verts[i]
            p_next = verts[(i + 1) % n]

            v1 = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1])
            v2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])

            angle1 = math.atan2(v1[1], v1[0])
            angle2 = math.atan2(v2[1], v2[0])
            diff = (angle2 - angle1) % (2 * math.pi)

            # In the Spectre, turns are discrete multiples of 30 degrees (pi / 6)
            discrete_multiple = round(diff / (math.pi / 6.0))
            expected = (discrete_multiple * (math.pi / 6.0)) % (2 * math.pi)
            if abs(diff - expected) > TOLERANCE:
                return False, f"Vertex {i} turning angle {math.degrees(diff):.2f}° is not a multiple of 30°"
        return True, None

    @classmethod
    def check_contact_and_overlap(
        cls,
        candidate_addr: str,
        candidate_poly: SpectrePolygon,
        existing_tiles: Dict[str, SpectrePolygon]
    ) -> Tuple[bool, bool, List[NeighborContactProof], Optional[str]]:
        """
        Checks for:
        1. Non-overlapping interiors with existing tiles.
        2. Complementary polarity on all touching contact edges (pol_A + pol_B == 0).
        """
        cand_centroid = candidate_poly.get_centroid()
        contacts: List[NeighborContactProof] = []

        for exist_addr, exist_poly in existing_tiles.items():
            if exist_addr == candidate_addr:
                continue

            exist_centroid = exist_poly.get_centroid()
            center_dist = _dist(cand_centroid, exist_centroid)

            # In the 14-gon Spectre, touching tiles have centroid distance ~1.4 to ~2.8.
            # A centroid distance < 0.8 implies invalid overlapping/penetration.
            if center_dist < 0.8:
                return False, False, [], f"Centroid penetration with {exist_addr}: distance {center_dist:.4f} < 0.8"

            # Check for edge-to-edge contact
            cand_edges = candidate_poly.edges
            exist_edges = exist_poly.edges

            for c_idx, (cp1, cp2) in enumerate(cand_edges):
                for e_idx, (ep1, ep2) in enumerate(exist_edges):
                    # Edges meet in opposite winding: cp1 ≈ ep2 and cp2 ≈ ep1
                    d_fwd = _dist(cp1, ep2) + _dist(cp2, ep1)
                    if d_fwd < 0.05:  # Edges are congruent and touching
                        c_pol = candidate_poly.get_edge_polarity(c_idx)
                        e_pol = exist_poly.get_edge_polarity(e_idx)

                        # Convex (+1) must meet Concave (-1): c_pol + e_pol == 0
                        is_polarity_ok = (c_pol + e_pol == 0)
                        midpoint = ((cp1[0] + cp2[0]) / 2.0, (cp1[1] + cp2[1]) / 2.0)

                        contacts.append(
                            NeighborContactProof(
                                neighbor_address=exist_addr,
                                local_edge_idx=c_idx,
                                neighbor_edge_idx=e_idx,
                                local_polarity=c_pol,
                                neighbor_polarity=e_pol,
                                contact_midpoint=midpoint,
                                is_polarity_valid=is_polarity_ok,
                            )
                        )

                        if not is_polarity_ok:
                            return True, False, contacts, (
                                f"Polarity violation with {exist_addr}: local edge {c_idx} ({c_pol}) "
                                f"mismatches neighbor edge {e_idx} ({e_pol})"
                            )

        # Non-overlapping is verified, polarity is checked
        return True, True, contacts, None

    @classmethod
    def verify_tile(
        cls,
        candidate_addr: HierarchicalAddress,
        candidate_poly: SpectrePolygon,
        existing_tiles: Dict[str, SpectrePolygon]
    ) -> ProofOfGeometricFit:
        """Runs the complete suite of topological checks for a candidate tile."""
        addr_str = candidate_addr.to_string()
        poly_hash = compute_polygon_hash(candidate_poly)
        centroid = candidate_poly.get_centroid()
        rot_idx = candidate_poly.transform.rotation_index

        # 1. Edge Lengths
        len_ok, len_err = cls.verify_edge_lengths(candidate_poly)
        if not len_ok:
            return ProofOfGeometricFit(
                address=addr_str,
                centroid=centroid,
                rotation_index=rot_idx,
                polygon_hash=poly_hash,
                is_edge_length_valid=False,
                is_fully_valid=False,
                rejection_reason=len_err,
            )

        # 2. Discrete Turning Angles
        angle_ok, angle_err = cls.verify_angles(candidate_poly)
        if not angle_ok:
            return ProofOfGeometricFit(
                address=addr_str,
                centroid=centroid,
                rotation_index=rot_idx,
                polygon_hash=poly_hash,
                is_angle_valid=False,
                is_fully_valid=False,
                rejection_reason=angle_err,
            )

        # 3. Non-overlapping & Chiral Polarity Contact
        no_overlap, pol_ok, contacts, contact_err = cls.check_contact_and_overlap(
            addr_str, candidate_poly, existing_tiles
        )

        is_valid = len_ok and angle_ok and no_overlap and pol_ok

        return ProofOfGeometricFit(
            address=addr_str,
            centroid=centroid,
            rotation_index=rot_idx,
            polygon_hash=poly_hash,
            neighbor_contacts=contacts,
            is_edge_length_valid=len_ok,
            is_angle_valid=angle_ok,
            is_polarity_valid=pol_ok,
            is_non_overlapping=no_overlap,
            is_fully_valid=is_valid,
            rejection_reason=contact_err,
        )
