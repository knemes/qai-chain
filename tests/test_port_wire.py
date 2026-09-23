"""
Unit tests for the Port Wire Protocol.
"""

import unittest
from ledger.port_wire import (
    pack_wire_frame,
    unpack_wire_frame,
    WIRE_MAGIC_BYTE,
    ML_KEM_1024_CIPHERTEXT_SIZE,
)


class TestPortWire(unittest.TestCase):

    def test_pack_and_unpack_roundtrip(self):
        src = "G0.M0.S0.T0"
        dst = "G0.M0.S0.T1"
        egress = 1
        ingress = 8
        kem_ct = b"K" * ML_KEM_1024_CIPHERTEXT_SIZE
        payload = b"Cognitive state vector: [12, 45, 99, 108]"

        frame_bytes = pack_wire_frame(
            source_address=src,
            target_address=dst,
            egress_port=egress,
            ingress_port=ingress,
            kem_ciphertext=kem_ct,
            aead_payload=payload,
        )

        self.assertGreater(len(frame_bytes), ML_KEM_1024_CIPHERTEXT_SIZE)
        self.assertEqual(frame_bytes[0], WIRE_MAGIC_BYTE)

        unpacked = unpack_wire_frame(frame_bytes)
        self.assertEqual(unpacked.source_address, src)
        self.assertEqual(unpacked.target_address, dst)
        self.assertEqual(unpacked.egress_port, egress)
        self.assertEqual(unpacked.ingress_port, ingress)
        self.assertEqual(unpacked.kem_ciphertext, kem_ct)
        self.assertEqual(unpacked.aead_payload, payload)

    def test_invalid_magic_byte_rejection(self):
        kem_ct = b"K" * ML_KEM_1024_CIPHERTEXT_SIZE
        frame_bytes = bytearray(pack_wire_frame("G0.T0", "G0.T1", 0, 7, kem_ct, b"data"))
        frame_bytes[0] = 0xAA  # Corrupt magic byte

        with self.assertRaises(ValueError) as ctx:
            unpack_wire_frame(bytes(frame_bytes))
        self.assertIn("magic byte", str(ctx.exception).lower())

    def test_invalid_port_range(self):
        kem_ct = b"K" * ML_KEM_1024_CIPHERTEXT_SIZE
        with self.assertRaises(ValueError):
            pack_wire_frame("G0.T0", "G0.T1", 14, 7, kem_ct, b"data")  # Port 14 is invalid (0..13)

    def test_invalid_kem_ciphertext_length(self):
        with self.assertRaises(ValueError):
            pack_wire_frame("G0.T0", "G0.T1", 1, 8, b"short_key", b"data")


if __name__ == "__main__":
    unittest.main()
