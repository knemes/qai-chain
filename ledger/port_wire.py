"""
Transparent Port Wire Protocol.
Binary framing specification for streaming encrypted cognitive state packets
strictly across touching 14-gon edges of the aperiodic monotile lattice.
Zero-copy serialization with pure ML-KEM-1024 envelope integration.
"""

import struct
from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional

WIRE_MAGIC_BYTE = 0x51  # ASCII 'Q' (QAI-Chain)
ML_KEM_1024_CIPHERTEXT_SIZE = 1568


@dataclass
class WireFrame:
    """Decoded binary wire frame received across an edge port."""
    source_address: str
    target_address: str
    egress_port: int
    ingress_port: int
    kem_ciphertext: bytes
    aead_payload: bytes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_address": self.source_address,
            "target_address": self.target_address,
            "egress_port": self.egress_port,
            "ingress_port": self.ingress_port,
            "kem_ciphertext_len": len(self.kem_ciphertext),
            "payload_len": len(self.aead_payload),
        }


def pack_wire_frame(
    source_address: str,
    target_address: str,
    egress_port: int,
    ingress_port: int,
    kem_ciphertext: bytes,
    aead_payload: bytes,
) -> bytes:
    """
    Serializes a wire packet into a compact binary frame:
    [MAGIC: 1B] [SRC_LEN: 1B] [SRC: NB] [DST_LEN: 1B] [DST: NB]
    [EGRESS: 1B] [INGRESS: 1B] [KEM_LEN: 2B] [KEM_CT: 1568B] [PAYLOAD_LEN: 4B] [PAYLOAD: NB]
    """
    if not (0 <= egress_port < 14):
        raise ValueError(f"Invalid egress port: {egress_port}. Must be 0..13.")
    if not (0 <= ingress_port < 14):
        raise ValueError(f"Invalid ingress port: {ingress_port}. Must be 0..13.")
    if len(kem_ciphertext) != ML_KEM_1024_CIPHERTEXT_SIZE:
        raise ValueError(f"Invalid ML-KEM-1024 ciphertext size: {len(kem_ciphertext)}. Must be {ML_KEM_1024_CIPHERTEXT_SIZE} bytes.")

    src_bytes = source_address.encode("utf-8")
    dst_bytes = target_address.encode("utf-8")

    if len(src_bytes) > 255 or len(dst_bytes) > 255:
        raise ValueError("Address string exceeds 255 byte maximum.")

    header = struct.pack(
        ">BB",
        WIRE_MAGIC_BYTE,
        len(src_bytes),
    ) + src_bytes + struct.pack(
        ">B",
        len(dst_bytes),
    ) + dst_bytes + struct.pack(
        ">BBH",
        egress_port,
        ingress_port,
        len(kem_ciphertext),
    )

    body = kem_ciphertext + struct.pack(">I", len(aead_payload)) + aead_payload
    return header + body


def unpack_wire_frame(raw_bytes: bytes) -> WireFrame:
    """
    Deserializes a binary frame received on a physical edge port.
    Enforces magic byte and length invariants.
    """
    if len(raw_bytes) < 1 + 1 + 1 + 1 + 1 + 2 + ML_KEM_1024_CIPHERTEXT_SIZE + 4:
        raise ValueError(f"Frame truncated: {len(raw_bytes)} bytes is too short for minimal wire header.")

    offset = 0
    magic = raw_bytes[offset]
    offset += 1
    if magic != WIRE_MAGIC_BYTE:
        raise ValueError(f"Invalid wire frame magic byte: 0x{magic:02X}. Expected 0x{WIRE_MAGIC_BYTE:02X}.")

    src_len = raw_bytes[offset]
    offset += 1
    src_bytes = raw_bytes[offset:offset + src_len]
    offset += src_len
    source_address = src_bytes.decode("utf-8")

    dst_len = raw_bytes[offset]
    offset += 1
    dst_bytes = raw_bytes[offset:offset + dst_len]
    offset += dst_len
    target_address = dst_bytes.decode("utf-8")

    egress_port, ingress_port, kem_len = struct.unpack_from(">BBH", raw_bytes, offset)
    offset += 4

    if kem_len != ML_KEM_1024_CIPHERTEXT_SIZE:
        raise ValueError(f"Frame has invalid ML-KEM-1024 ciphertext length: {kem_len} != {ML_KEM_1024_CIPHERTEXT_SIZE}.")

    kem_ciphertext = raw_bytes[offset:offset + kem_len]
    offset += kem_len

    payload_len, = struct.unpack_from(">I", raw_bytes, offset)
    offset += 4

    aead_payload = raw_bytes[offset:offset + payload_len]
    if len(aead_payload) != payload_len:
        raise ValueError(f"Truncated payload: expected {payload_len} bytes, got {len(aead_payload)}.")

    return WireFrame(
        source_address=source_address,
        target_address=target_address,
        egress_port=egress_port,
        ingress_port=ingress_port,
        kem_ciphertext=kem_ciphertext,
        aead_payload=aead_payload,
    )
