import os
import json
import binascii
from typing import Tuple, Dict, Any, Optional
import oqs
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Default Post-Quantum Cryptography Algorithms (NIST Standards)
DEFAULT_KEM_ALG = "ML-KEM-1024"  # FIPS 203 Level 5
DEFAULT_DSA_ALG = "ML-DSA-65"    # FIPS 204 Level 3


def generate_kem_keypair(alg: str = DEFAULT_KEM_ALG) -> Tuple[bytes, bytes]:
    """Generates an ML-KEM keypair (public encapsulation key, secret decapsulation key)."""
    with oqs.KeyEncapsulation(alg) as kem:
        public_key = kem.generate_keypair()
        secret_key = kem.export_secret_key()
        return public_key, secret_key


def generate_dsa_keypair(alg: str = DEFAULT_DSA_ALG) -> Tuple[bytes, bytes]:
    """Generates an ML-DSA keypair (public verification key, secret signing key)."""
    with oqs.Signature(alg) as signer:
        public_key = signer.generate_keypair()
        secret_key = signer.export_secret_key()
        return public_key, secret_key


def sign_payload(private_key: bytes, message: bytes, alg: str = DEFAULT_DSA_ALG) -> bytes:
    """Signs a message using an ML-DSA private key."""
    with oqs.Signature(alg, private_key) as signer:
        return signer.sign(message)


def verify_payload(public_key: bytes, message: bytes, signature: bytes, alg: str = DEFAULT_DSA_ALG) -> bool:
    """Verifies an ML-DSA signature against the message and public key."""
    with oqs.Signature(alg) as verifier:
        try:
            return verifier.verify(message, signature, public_key)
        except Exception:
            return False


def _derive_symmetric_key(shared_secret: bytes, salt: bytes, info: bytes = b"spectre_swarm_pqc_v1") -> bytes:
    """Derives a 256-bit AES symmetric key from an ML-KEM shared secret via HKDF-SHA256."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=info,
    )
    return hkdf.derive(shared_secret)


def encrypt_envelope(
    payload: bytes,
    recipient_kem_pk: bytes,
    kem_alg: str = DEFAULT_KEM_ALG
) -> Dict[str, str]:
    """
    Encrypts a payload for a single recipient using ML-KEM-1024 and AES-256-GCM.
    Returns a hex-encoded dictionary envelope.
    """
    with oqs.KeyEncapsulation(kem_alg) as kem:
        ciphertext_kem, shared_secret = kem.encap_secret(recipient_kem_pk)

    salt = os.urandom(16)
    aes_key = _derive_symmetric_key(shared_secret, salt)

    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)
    encrypted_payload = aesgcm.encrypt(nonce, payload, None)

    return {
        "kem_alg": kem_alg,
        "kem_ciphertext": binascii.hexlify(ciphertext_kem).decode("ascii"),
        "salt": binascii.hexlify(salt).decode("ascii"),
        "nonce": binascii.hexlify(nonce).decode("ascii"),
        "ciphertext": binascii.hexlify(encrypted_payload).decode("ascii")
    }


def decrypt_envelope(
    envelope: Dict[str, str],
    recipient_kem_sk: bytes
) -> bytes:
    """
    Decrypts an envelope using the recipient's ML-KEM-1024 secret decapsulation key.
    """
    kem_alg = envelope.get("kem_alg", DEFAULT_KEM_ALG)
    ciphertext_kem = binascii.unhexlify(envelope["kem_ciphertext"])
    salt = binascii.unhexlify(envelope["salt"])
    nonce = binascii.unhexlify(envelope["nonce"])
    encrypted_payload = binascii.unhexlify(envelope["ciphertext"])

    with oqs.KeyEncapsulation(kem_alg, recipient_kem_sk) as kem:
        shared_secret = kem.decap_secret(ciphertext_kem)

    aes_key = _derive_symmetric_key(shared_secret, salt)
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(nonce, encrypted_payload, None)


def encrypt_dual_envelope(
    payload: bytes,
    agent_kem_pk: bytes,
    auditor_kem_pk: bytes,
    kem_alg: str = DEFAULT_KEM_ALG
) -> Dict[str, Any]:
    """
    Dual-Recipient KEM-DEM Hybrid Encryption (NIST / RFC 9180 HPKE Pattern):
    Generates an ephemeral payload AES-256-GCM key, encrypts the payload,
    then encapsulates and key-wraps for both the Agent and the Colony Auditor.
    """
    # 1. Ephemeral Master Payload Key
    master_payload_key = os.urandom(32)
    payload_nonce = os.urandom(12)
    aesgcm_payload = AESGCM(master_payload_key)
    encrypted_payload = aesgcm_payload.encrypt(payload_nonce, payload, None)

    # 2. Key Encapsulation for Agent
    with oqs.KeyEncapsulation(kem_alg) as kem_agent:
        agent_ct, agent_ss = kem_agent.encap_secret(agent_kem_pk)
    agent_salt = os.urandom(16)
    agent_wrap_key = _derive_symmetric_key(agent_ss, agent_salt, b"agent_key_wrap")
    agent_wrap_nonce = os.urandom(12)
    wrapped_agent_key = AESGCM(agent_wrap_key).encrypt(agent_wrap_nonce, master_payload_key, None)

    # 3. Key Encapsulation for Colony Auditor
    with oqs.KeyEncapsulation(kem_alg) as kem_auditor:
        auditor_ct, auditor_ss = kem_auditor.encap_secret(auditor_kem_pk)
    auditor_salt = os.urandom(16)
    auditor_wrap_key = _derive_symmetric_key(auditor_ss, auditor_salt, b"auditor_key_wrap")
    auditor_wrap_nonce = os.urandom(12)
    wrapped_auditor_key = AESGCM(auditor_wrap_key).encrypt(auditor_wrap_nonce, master_payload_key, None)

    return {
        "kem_alg": kem_alg,
        "payload_nonce": binascii.hexlify(payload_nonce).decode("ascii"),
        "ciphertext": binascii.hexlify(encrypted_payload).decode("ascii"),
        "agent_slot": {
            "kem_ct": binascii.hexlify(agent_ct).decode("ascii"),
            "salt": binascii.hexlify(agent_salt).decode("ascii"),
            "wrap_nonce": binascii.hexlify(agent_wrap_nonce).decode("ascii"),
            "wrapped_key": binascii.hexlify(wrapped_agent_key).decode("ascii")
        },
        "auditor_slot": {
            "kem_ct": binascii.hexlify(auditor_ct).decode("ascii"),
            "salt": binascii.hexlify(auditor_salt).decode("ascii"),
            "wrap_nonce": binascii.hexlify(auditor_wrap_nonce).decode("ascii"),
            "wrapped_key": binascii.hexlify(wrapped_auditor_key).decode("ascii")
        }
    }


def decrypt_dual_envelope(
    dual_envelope: Dict[str, Any],
    private_kem_sk: bytes,
    is_auditor: bool = False
) -> bytes:
    """
    Decrypts a dual envelope using either the Agent's private key (default)
    or the Colony Auditor's private key (if is_auditor=True).
    """
    kem_alg = dual_envelope.get("kem_alg", DEFAULT_KEM_ALG)
    slot = dual_envelope["auditor_slot"] if is_auditor else dual_envelope["agent_slot"]

    kem_ct = binascii.unhexlify(slot["kem_ct"])
    salt = binascii.unhexlify(slot["salt"])
    wrap_nonce = binascii.unhexlify(slot["wrap_nonce"])
    wrapped_key = binascii.unhexlify(slot["wrapped_key"])

    # 1. Decapsulate shared secret
    with oqs.KeyEncapsulation(kem_alg, private_kem_sk) as kem:
        ss = kem.decap_secret(kem_ct)

    # 2. Unwrap master payload key
    info = b"auditor_key_wrap" if is_auditor else b"agent_key_wrap"
    wrap_key = _derive_symmetric_key(ss, salt, info)
    master_payload_key = AESGCM(wrap_key).decrypt(wrap_nonce, wrapped_key, None)

    # 3. Decrypt payload
    payload_nonce = binascii.unhexlify(dual_envelope["payload_nonce"])
    ciphertext = binascii.unhexlify(dual_envelope["ciphertext"])
    return AESGCM(master_payload_key).decrypt(payload_nonce, ciphertext, None)
