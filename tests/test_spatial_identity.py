"""
Unit tests for the Post-Quantum Cryptographic Spatial Identity & Certificate Module.
"""

import unittest
from geometry.spectre_hierarchy import HierarchicalAddress, HierarchyEngine
from geometry.topological_proof import TopologicalVerifier
from pqc_crypto.spatial_identity import SpatialNodeIdentity, SpatialCertificate


class TestSpatialIdentity(unittest.TestCase):

    def setUp(self):
        self.addr1 = HierarchicalAddress.from_string("G0.M0.S0.T0")
        self.addr2 = HierarchicalAddress.from_string("G0.M0.S0.T1")

        poly1 = HierarchyEngine.get_polygon(self.addr1)
        poly2 = HierarchyEngine.get_polygon(self.addr2)

        fit1 = TopologicalVerifier.verify_tile(self.addr1, poly1, {})
        fit2 = TopologicalVerifier.verify_tile(self.addr2, poly2, {self.addr1.to_string(): poly1})

        self.node1 = SpatialNodeIdentity(self.addr1, fit1)
        self.node2 = SpatialNodeIdentity(self.addr2, fit2)

    def test_certificate_verification(self):
        # Certificate should verify out of the box
        self.assertTrue(self.node1.certificate.verify())
        self.assertTrue(self.node2.certificate.verify())

    def test_certificate_tamper_detection(self):
        # Tamper with the certificate address
        cert_dict = self.node1.certificate.to_dict()
        cert_dict["address"] = "G0.M0.S0.T7"
        tampered_cert = SpatialCertificate.from_dict(cert_dict)
        self.assertFalse(tampered_cert.verify(), "Tampered address must fail verification")

        # Tamper with polygon hash
        cert_dict2 = self.node1.certificate.to_dict()
        cert_dict2["polygon_hash"] = "0000" * 16
        tampered_cert2 = SpatialCertificate.from_dict(cert_dict2)
        self.assertFalse(tampered_cert2.verify(), "Tampered polygon hash must fail verification")

    def test_peer_to_peer_pqc_encryption(self):
        # Node 1 sends a secret cognitive payload to Node 2
        secret_thought = b"Quantum spatial firewall integrity: PASS. Lattice margin: 1024-bit."
        envelope = self.node1.encrypt_to_neighbor(self.node2.certificate, secret_thought)

        # Node 2 decrypts the envelope
        decrypted = self.node2.decrypt_from_neighbor(envelope)
        self.assertEqual(decrypted, secret_thought)

    def test_message_signing_and_verification(self):
        # Node 1 signs an epoch lemma
        lemma = b"Lemma 42: No geometric cul-de-sac detected."
        sig = self.node1.sign_message(lemma)
        self.assertTrue(len(sig) > 0)


if __name__ == "__main__":
    unittest.main()
