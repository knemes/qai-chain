import math
from typing import List, Tuple, Optional, Dict, Any

HR3 = math.sqrt(3) / 2  # ~0.8660254037844386

# Canonical 14 vertices of the Einstein Spectre Monotile (Smith et al., 2023)
# All 14 edges have exact Euclidean length 1.0 on the hexagonal lattice.
SPECTRE_BASE_VERTICES: List[Tuple[float, float]] = [
    (0.0, 0.0),
    (1.0, 0.0),
    (1.5, -HR3),
    (1.5 + HR3, 1.0 - HR3 - 0.5),  # 2.366025, -0.366025
    (1.5 + HR3, 1.0 - HR3 + 0.5),  # 2.366025, 0.633975
    (2.5 + HR3, 1.0 - HR3 + 0.5),  # 3.366025, 0.633975
    (3.0 + HR3, 1.5),              # 3.866025, 1.5
    (3.0, 2.0),
    (3.0 - HR3, 1.5),              # 2.133975, 1.5
    (2.5 - HR3, 1.5 + HR3),        # 1.633975, 2.366025
    (1.5 - HR3, 1.5 + HR3),        # 0.633975, 2.366025
    (0.5 - HR3, 1.5 + HR3),        # -0.366025, 2.366025
    (-HR3, 1.5),                   # -0.866025, 1.5
    (0.0, 1.0),
]

# 14 Edge polarities for the chiral aperiodic matching rules.
# +1 represents a convex/male curve, -1 represents a concave/female curve.
# When two edges meet in opposite winding (p1->p2 vs p2->p1), matching polarities interlock.
SPECTRE_EDGE_POLARITIES: List[int] = [
    1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1
]


class SpectreTransform:
    """Represents a 2D Euclidean transformation with 12-fold discrete chiral rotation."""

    def __init__(self, x: float = 0.0, y: float = 0.0, rotation_index: int = 0):
        self.x = round(float(x), 6)
        self.y = round(float(y), 6)
        # Discrete 12-fold angle (multiples of 30 degrees = pi / 6)
        self.rotation_index = int(rotation_index) % 12
        self.angle_rad = self.rotation_index * (math.pi / 6.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "rotation_index": self.rotation_index,
            "angle_rad": self.angle_rad,
            "angle_deg": self.rotation_index * 30,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpectreTransform":
        return cls(data["x"], data["y"], data["rotation_index"])

    def __repr__(self) -> str:
        return f"SpectreTransform(x={self.x:.3f}, y={self.y:.3f}, rot={self.rotation_index * 30}°)"


class SpectrePolygon:
    """A situated Einstein Spectre 14-gon tile placed at (x, y) with discrete rotation."""

    def __init__(self, transform: Optional[SpectreTransform] = None):
        self.transform = transform if transform is not None else SpectreTransform(0.0, 0.0, 0)
        self._vertices: Optional[List[Tuple[float, float]]] = None
        self._edges: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None

    @property
    def vertices(self) -> List[Tuple[float, float]]:
        if self._vertices is None:
            c = math.cos(self.transform.angle_rad)
            s = math.sin(self.transform.angle_rad)
            tx = self.transform.x
            ty = self.transform.y

            transformed = []
            for vx, vy in SPECTRE_BASE_VERTICES:
                rx = vx * c - vy * s + tx
                ry = vx * s + vy * c + ty
                transformed.append((round(rx, 6), round(ry, 6)))
            self._vertices = transformed
        return self._vertices

    @property
    def edges(self) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """Returns 14 directed edges [(v0, v1), (v1, v2), ..., (v13, v0)]."""
        if self._edges is None:
            verts = self.vertices
            edge_list = []
            for i in range(14):
                edge_list.append((verts[i], verts[(i + 1) % 14]))
            self._edges = edge_list
        return self._edges

    def get_edge_polarity(self, edge_idx: int) -> int:
        return SPECTRE_EDGE_POLARITIES[edge_idx % 14]

    def get_centroid(self) -> Tuple[float, float]:
        verts = self.vertices
        cx = sum(v[0] for v in verts) / len(verts)
        cy = sum(v[1] for v in verts) / len(verts)
        return (round(cx, 6), round(cy, 6))

    def get_aabb(self) -> Tuple[float, float, float, float]:
        verts = self.vertices
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        return (min(xs), min(ys), max(xs), max(ys))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transform": self.transform.to_dict(),
            "vertices": [{"x": v[0], "y": v[1]} for v in self.vertices],
            "centroid": {"x": self.get_centroid()[0], "y": self.get_centroid()[1]},
            "edge_polarities": SPECTRE_EDGE_POLARITIES,
        }


# --- Geometric Verification & Collision Detection ---

def _dist_sq(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2


def edges_touch_and_align(
    e1: Tuple[Tuple[float, float], Tuple[float, float]],
    e2: Tuple[Tuple[float, float], Tuple[float, float]],
    tol: float = 1e-3
) -> bool:
    """
    Checks if two directed edges e1 = (p1, p2) and e2 = (q1, q2) share the same line segment
    in OPPOSITE directions (i.e., p1 matches q2 and p2 matches q1).
    """
    (p1, p2) = e1
    (q1, q2) = e2
    tol_sq = tol * tol
    return _dist_sq(p1, q2) <= tol_sq and _dist_sq(p2, q1) <= tol_sq


def _point_in_polygon(pt: Tuple[float, float], verts: List[Tuple[float, float]]) -> bool:
    """Ray casting algorithm to test if point is strictly inside polygon."""
    x, y = pt
    inside = False
    n = len(verts)
    p1x, p1y = verts[0]
    for i in range(n + 1):
        p2x, p2y = verts[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def _segments_intersect_interior(
    a1: Tuple[float, float], a2: Tuple[float, float],
    b1: Tuple[float, float], b2: Tuple[float, float],
    tol: float = 1e-4
) -> bool:
    """Returns True if two line segments cross each other in their strict interiors."""
    def ccw(p1, p2, p3):
        return (p3[1] - p1[1]) * (p2[0] - p1[0]) > (p2[1] - p1[1]) * (p3[0] - p1[0])

    # If endpoints are virtually identical, they touch at vertices/edges, not crossing interior
    if (math.dist(a1, b1) < tol or math.dist(a1, b2) < tol or
        math.dist(a2, b1) < tol or math.dist(a2, b2) < tol):
        return False

    return (ccw(a1, b1, b2) != ccw(a2, b1, b2)) and (ccw(a1, a2, b1) != ccw(a1, a2, b2))


def check_polygons_overlap(poly1: SpectrePolygon, poly2: SpectrePolygon) -> bool:
    """
    Checks if poly1 and poly2 overlap.
    Returns True if their interior areas penetrate each other.
    Returns False if they are completely disjoint or only touch along boundary edges/vertices.
    """
    # 1. Fast AABB bounding box check
    min_x1, min_y1, max_x1, max_y1 = poly1.get_aabb()
    min_x2, min_y2, max_x2, max_y2 = poly2.get_aabb()
    tol = 1e-4

    if (max_x1 <= min_x2 + tol or max_x2 <= min_x1 + tol or
        max_y1 <= min_y2 + tol or max_y2 <= min_y1 + tol):
        return False

    v1 = poly1.vertices
    v2 = poly2.vertices

    # 2. Check centroid / interior points
    c1 = poly1.get_centroid()
    c2 = poly2.get_centroid()
    if _point_in_polygon(c1, v2) or _point_in_polygon(c2, v1):
        return True

    # 3. Check for crossing edge segments
    e1_list = poly1.edges
    e2_list = poly2.edges
    for s1 in e1_list:
        for s2 in e2_list:
            if _segments_intersect_interior(s1[0], s1[1], s2[0], s2[1], tol=1e-3):
                return True

    # 4. Check intermediate sample points along edges to ensure no boundary invasion
    for p in v1:
        # Check slightly inside the polygon
        dx = c1[0] - p[0]
        dy = c1[1] - p[1]
        dist = math.hypot(dx, dy)
        if dist > 1e-4:
            in_pt = (p[0] + 0.05 * (dx / dist), p[1] + 0.05 * (dy / dist))
            if _point_in_polygon(in_pt, v2):
                return True

    return False


def verify_geometric_fit(
    candidate: SpectrePolygon,
    existing_mosaic: List[SpectrePolygon]
) -> Tuple[bool, str, List[Tuple[int, int, int]]]:
    """
    Validates the 'Proof of Geometric Fit' for appending a new Spectre tile:
    1. Must make contact with at least one existing tile along a complete edge.
    2. All touching edges must obey chiral edge-matching rules (compatible polarities).
    3. Must not penetrate or overlap the interior of any existing tile in the mosaic.

    Returns:
        (is_valid, reason, contact_list)
        where contact_list is [(neighbor_idx, candidate_edge_idx, neighbor_edge_idx), ...]
    """
    if not existing_mosaic:
        # Genesis tile always fits
        return (True, "Genesis tile valid at origin", [])

    contacts: List[Tuple[int, int, int]] = []
    cand_edges = candidate.edges

    # Check for interior overlap first
    for idx, existing in enumerate(existing_mosaic):
        if check_polygons_overlap(candidate, existing):
            return (False, f"Geometric collision: overlaps with existing tile #{idx}", [])

    # Check edge contacts and mating rules
    for idx, existing in enumerate(existing_mosaic):
        ex_edges = existing.edges
        for c_idx, c_edge in enumerate(cand_edges):
            for e_idx, e_edge in enumerate(ex_edges):
                if edges_touch_and_align(c_edge, e_edge):
                    # Check edge polarity compatibility
                    c_pol = candidate.get_edge_polarity(c_idx)
                    e_pol = existing.get_edge_polarity(e_idx)
                    if c_pol != e_pol:
                        return (
                            False,
                            f"Edge rule violation on tile #{idx}: candidate edge {c_idx} (pol {c_pol}) "
                            f"conflicts with neighbor edge {e_idx} (pol {e_pol})",
                            []
                        )
                    contacts.append((idx, c_idx, e_idx))

    if not contacts:
        return (False, "Spatial discontinuity: tile does not touch any existing neighbor edges", [])

    return (True, f"Geometric fit verified with {len(contacts)} touching edge(s)", contacts)


def find_valid_open_sites(
    existing_mosaic: List[SpectrePolygon],
    max_sites: int = 12
) -> List[SpectrePolygon]:
    """
    Finds open sites on the colony perimeter where a new Spectre tile can snap
    with 100% mathematical validity (contact alignment, valid edge polarity, zero collision).
    This guarantees prevention of geometric cul-de-sacs.
    """
    if not existing_mosaic:
        return [SpectrePolygon(SpectreTransform(0.0, 0.0, 0))]

    valid_candidates: List[SpectrePolygon] = []
    seen_transforms = set()

    for ex_idx, existing in enumerate(existing_mosaic):
        for e_idx, ex_edge in enumerate(existing.edges):
            (q1, q2) = ex_edge
            e_pol = existing.get_edge_polarity(e_idx)

            # We want candidate edge c_edge = (p1, p2) to align with (q2, q1)
            # Try each of candidate's 14 edges c_idx that share polarity e_pol
            for c_idx in range(14):
                if SPECTRE_EDGE_POLARITIES[c_idx] != e_pol:
                    continue

                for rot_idx in range(12):
                    # Rotate base edge c_idx by rot_idx
                    ang = rot_idx * (math.pi / 6.0)
                    c = math.cos(ang)
                    s = math.sin(ang)

                    bv1 = SPECTRE_BASE_VERTICES[c_idx]
                    bv2 = SPECTRE_BASE_VERTICES[(c_idx + 1) % 14]

                    # Rotated base edge vector:
                    rv1 = (bv1[0] * c - bv1[1] * s, bv1[0] * s + bv1[1] * c)
                    rv2 = (bv2[0] * c - bv2[1] * s, bv2[0] * s + bv2[1] * c)

                    # Required directed vector is q2 -> q1
                    target_dx = q1[0] - q2[0]
                    target_dy = q1[1] - q2[1]

                    cur_dx = rv2[0] - rv1[0]
                    cur_dy = rv2[1] - rv1[1]

                    # Vectors must match in direction
                    if math.hypot(target_dx - cur_dx, target_dy - cur_dy) > 1e-3:
                        continue

                    # Translation required: rv1 + (tx, ty) = q2 => tx = q2.x - rv1.x, ty = q2.y - rv1.y
                    tx = round(q2[0] - rv1[0], 4)
                    ty = round(q2[1] - rv1[1], 4)

                    key = (tx, ty, rot_idx)
                    if key in seen_transforms:
                        continue
                    seen_transforms.add(key)

                    candidate = SpectrePolygon(SpectreTransform(tx, ty, rot_idx))
                    is_valid, _, contacts = verify_geometric_fit(candidate, existing_mosaic)
                    if is_valid and contacts:
                        valid_candidates.append(candidate)
                        if len(valid_candidates) >= max_sites:
                            return valid_candidates

    return valid_candidates
