"""
Hierarchical Substitution Grammar Engine for the Aperiodic Monotile Lattice.
Maps discrete hierarchical addresses (Giga.Mega.Super.Tile) to exact 2D Cartesian
geometry using recursive Craig Kaplan substitution transforms.
"""

import math
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
from geometry.spectre import (
    SPECTRE_BASE_VERTICES,
    SPECTRE_EDGE_POLARITIES,
    NEIGHBORHOOD_SLOT_TRANSFORMS,
    SpectreTransform,
    SpectrePolygon,
)

# Inflation scale factor between substitution levels (~2.732)
SUPER_TILE_SCALE = 1.0 + math.sqrt(3.0)

# Canonical 8-cluster transforms for Level 2 (Mega-Tile consisting of 8 Super-Tiles)
# Derived by applying the substitution inflation matrix to the base cluster centroids.
MEGA_SLOT_TRANSFORMS: List[Dict[str, Any]] = [
    {"slot": 0, "rot_idx": 0, "tx": 0.0, "ty": 0.0},
    {"slot": 1, "rot_idx": 2, "tx": -5.2, "ty": -3.0},
    {"slot": 2, "rot_idx": 2, "tx": -11.2, "ty": 3.0},
    {"slot": 3, "rot_idx": 4, "tx": -11.2, "ty": -3.0},
    {"slot": 4, "rot_idx": 6, "tx": -6.0, "ty": -6.0},
    {"slot": 5, "rot_idx": 6, "tx": -8.2, "ty": -14.2},
    {"slot": 6, "rot_idx": 8, "tx": -3.0, "ty": -11.2},
    {"slot": 7, "rot_idx": 4, "tx": 11.2, "ty": -9.0},
]

# Canonical Level 3 (Giga-Tile consisting of 8 Mega-Tiles)
GIGA_SLOT_TRANSFORMS: List[Dict[str, Any]] = [
    {"slot": 0, "rot_idx": 0, "tx": 0.0, "ty": 0.0},
    {"slot": 1, "rot_idx": 2, "tx": -18.0, "ty": -10.4},
    {"slot": 2, "rot_idx": 2, "tx": -38.8, "ty": 10.4},
    {"slot": 3, "rot_idx": 4, "tx": -38.8, "ty": -10.4},
    {"slot": 4, "rot_idx": 6, "tx": -20.8, "ty": -20.8},
    {"slot": 5, "rot_idx": 6, "tx": -28.4, "ty": -49.2},
    {"slot": 6, "rot_idx": 8, "tx": -10.4, "ty": -38.8},
    {"slot": 7, "rot_idx": 4, "tx": 38.8, "ty": -31.2},
]


def compose_transforms(parent: SpectreTransform, child: SpectreTransform) -> SpectreTransform:
    """
    Composes two 2D Euclidean transforms with discrete 12-fold rotations:
    T_composite(v) = parent(child(v))
    """
    rot = (parent.rotation_index + child.rotation_index) % 12
    c = math.cos(parent.angle_rad)
    s = math.sin(parent.angle_rad)
    tx = parent.x + (child.x * c - child.y * s)
    ty = parent.y + (child.x * s + child.y * c)
    return SpectreTransform(x=tx, y=ty, rotation_index=rot)


@dataclass(frozen=True)
class HierarchicalAddress:
    """
    Hierarchical substitution tree address in the form Giga.Mega.Super.Tile.
    Example: G0.M1.S3.T5
    """
    giga_idx: int = 0   # Level 3 (0..N)
    mega_idx: int = 0   # Level 2 (0..7)
    super_idx: int = 0  # Level 1 (0..7)
    tile_idx: int = 0   # Level 0 (0..7)

    def to_string(self) -> str:
        return f"G{self.giga_idx}.M{self.mega_idx}.S{self.super_idx}.T{self.tile_idx}"

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"HierarchicalAddress({self.to_string()})"

    @classmethod
    def from_string(cls, addr_str: str) -> "HierarchicalAddress":
        """Parses 'G0.M1.S2.T3' into a HierarchicalAddress."""
        clean = addr_str.strip().upper()
        parts = clean.split(".")
        if len(parts) != 4:
            raise ValueError(f"Invalid HierarchicalAddress format: '{addr_str}'. Expected 'G#.M#.S#.T#'")

        g = int(parts[0].replace("G", ""))
        m = int(parts[1].replace("M", ""))
        s = int(parts[2].replace("S", ""))
        t = int(parts[3].replace("T", ""))

        if not (0 <= m < 8):
            raise ValueError(f"mega_idx out of range [0..7]: {m}")
        if not (0 <= s < 8):
            raise ValueError(f"super_idx out of range [0..7]: {s}")
        if not (0 <= t < 8):
            raise ValueError(f"tile_idx out of range [0..7]: {t}")

        return cls(giga_idx=g, mega_idx=m, super_idx=s, tile_idx=t)

    @property
    def super_tile_address(self) -> str:
        """Returns the parent Super-Tile identifier: G#.M#.S#."""
        return f"G{self.giga_idx}.M{self.mega_idx}.S{self.super_idx}"

    @property
    def mega_tile_address(self) -> str:
        """Returns the parent Mega-Tile identifier: G#.M#."""
        return f"G{self.giga_idx}.M{self.mega_idx}"

    @property
    def giga_tile_address(self) -> str:
        """Returns the parent Giga-Tile identifier: G#."""
        return f"G{self.giga_idx}"

    def is_sibling(self, other: "HierarchicalAddress") -> bool:
        """Returns True if both tiles belong to the exact same Super-Tile."""
        return (
            self.giga_idx == other.giga_idx
            and self.mega_idx == other.mega_idx
            and self.super_idx == other.super_idx
        )

    def is_cousin(self, other: "HierarchicalAddress") -> bool:
        """Returns True if tiles belong to the same Mega-Tile but different Super-Tiles."""
        return (
            self.giga_idx == other.giga_idx
            and self.mega_idx == other.mega_idx
            and self.super_idx != other.super_idx
        )

    def linear_index(self) -> int:
        """Returns a contiguous zero-based global index."""
        return (
            self.giga_idx * 512
            + self.mega_idx * 64
            + self.super_idx * 8
            + self.tile_idx
        )


class HierarchyEngine:
    """Computes exact geometric polygons and transforms for any HierarchicalAddress."""

    @staticmethod
    def get_tile_slot_transform(tile_idx: int) -> SpectreTransform:
        data = NEIGHBORHOOD_SLOT_TRANSFORMS[tile_idx % 8]
        return SpectreTransform(x=data["tx"], y=data["ty"], rotation_index=data["rot_idx"])

    @staticmethod
    def get_super_slot_transform(super_idx: int) -> SpectreTransform:
        data = MEGA_SLOT_TRANSFORMS[super_idx % 8]
        return SpectreTransform(x=data["tx"], y=data["ty"], rotation_index=data["rot_idx"])

    @staticmethod
    def get_mega_slot_transform(mega_idx: int) -> SpectreTransform:
        data = GIGA_SLOT_TRANSFORMS[mega_idx % 8]
        return SpectreTransform(x=data["tx"], y=data["ty"], rotation_index=data["rot_idx"])

    @classmethod
    def compute_transform(cls, address: HierarchicalAddress) -> SpectreTransform:
        """
        Computes the global 2D transform by composing:
        T_global = T_giga * T_mega * T_super * T_tile
        """
        # Offset for multiple Giga-tiles if giga_idx > 0
        giga_offset = SpectreTransform(
            x=address.giga_idx * 80.0,
            y=address.giga_idx * -45.0,
            rotation_index=0
        )
        t_mega_slot = cls.get_mega_slot_transform(address.mega_idx)
        t_super_slot = cls.get_super_slot_transform(address.super_idx)
        t_tile_slot = cls.get_tile_slot_transform(address.tile_idx)

        t_giga = compose_transforms(giga_offset, t_mega_slot)
        t_super = compose_transforms(t_giga, t_super_slot)
        return compose_transforms(t_super, t_tile_slot)

    @classmethod
    def get_polygon(cls, address: HierarchicalAddress) -> SpectrePolygon:
        """Returns the situated SpectrePolygon for a given HierarchicalAddress."""
        transform = cls.compute_transform(address)
        return SpectrePolygon(transform)

    @classmethod
    def get_supertile_polygons(cls, giga_idx: int = 0, mega_idx: int = 0, super_idx: int = 0) -> List[Tuple[HierarchicalAddress, SpectrePolygon]]:
        """Returns all 8 atomic tiles in a Super-Tile."""
        tiles = []
        for t in range(8):
            addr = HierarchicalAddress(giga_idx=giga_idx, mega_idx=mega_idx, super_idx=super_idx, tile_idx=t)
            poly = cls.get_polygon(addr)
            tiles.append((addr, poly))
        return tiles

    @classmethod
    def get_megatile_polygons(cls, giga_idx: int = 0, mega_idx: int = 0) -> List[Tuple[HierarchicalAddress, SpectrePolygon]]:
        """Returns all 64 atomic tiles in a Mega-Tile."""
        tiles = []
        for s in range(8):
            tiles.extend(cls.get_supertile_polygons(giga_idx=giga_idx, mega_idx=mega_idx, super_idx=s))
        return tiles


# Port Classification Types
PORT_INTERNAL = "INTERNAL"               # Touches a sibling in the same Super-Tile
PORT_SUPER_BOUNDARY = "SUPER_BOUNDARY"   # Touches a tile in an adjacent Super-Tile (Macro-Edge L1)
PORT_MEGA_BOUNDARY = "MEGA_BOUNDARY"     # Touches a tile in an adjacent Mega-Tile (Macro-Edge L2)
PORT_OPEN_PERIMETER = "OPEN_PERIMETER"   # Faces open space (candidate expansion port)


@dataclass
class EdgePortInfo:
    """Represents one of the 14 physical ports of a Spectre tile."""
    port_index: int                       # 0..13
    edge_coords: Tuple[Tuple[float, float], Tuple[float, float]]
    polarity: int                         # +1 (male/convex), -1 (female/concave)
    port_type: str                        # INTERNAL | SUPER_BOUNDARY | MEGA_BOUNDARY | OPEN_PERIMETER
    neighbor_address: Optional[HierarchicalAddress] = None
    neighbor_port_index: Optional[int] = None
