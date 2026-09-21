import unittest
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pqc_crypto.crypto_utils import (
    generate_kem_keypair,
    generate_dsa_keypair,
    sign_payload,
    verify_payload,
    encrypt_envelope,
    decrypt_envelope,
    encrypt_dual_envelope,
    decrypt_dual_envelope,
)


class TestPQCCrypto(unittest.TestCase):
    def test_kem_single_envelope(self):
        pk, sk = generate_kem_keypair()
        message = b"Quantum-safe memory payload for sovereign agent."
        envelope = encrypt_envelope(message, pk)
        decrypted = decrypt_envelope(envelope, sk)
        self.assertEqual(message, decrypted)

    def test_dsa_signatures(self):
        pk, sk = generate_dsa_keypair()
        message = b"Action: Sever edge 4 due to Byzantine violation."
        signature = sign_payload(sk, message)
        self.assertTrue(verify_payload(pk, message, signature))

        # Tampered message must fail
        self.assertFalse(verify_payload(pk, message + b"tampered", signature))

    def test_dual_recipient_envelope(self):
        agent_pk, agent_sk = generate_kem_keypair()
        auditor_pk, auditor_sk = generate_kem_keypair()

        cognitive_epoch_thought = (
            b'{"epoch": 1, "thought": "Analyzing sensor feed across Edge 2. No anomalies detected."}'
        )

        dual_envelope = encrypt_dual_envelope(
            cognitive_epoch_thought, agent_pk, auditor_pk
        )

        # 1. Agent decrypts its own thought stream
        agent_decrypted = decrypt_dual_envelope(
            dual_envelope, agent_sk, is_auditor=False
        )
        self.assertEqual(cognitive_epoch_thought, agent_decrypted)

        # 2. Colony Auditor decrypts the live thought stream
        auditor_decrypted = decrypt_dual_envelope(
            dual_envelope, auditor_sk, is_auditor=True
        )
        self.assertEqual(cognitive_epoch_thought, auditor_decrypted)

        # 3. Third-party attacker with unrelated key fails
        rogue_pk, rogue_sk = generate_kem_keypair()
        with self.assertRaises(Exception):
            decrypt_dual_envelope(dual_envelope, rogue_sk, is_auditor=False)


if __name__ == "__main__":
    unittest.main()
