import oqs
print(oqs.Signature)
from typing import Tuple

# --- PQC Configuration ---
DEFAULT_SIG_ALG = "ML-DSA-44" # Dilithium2 as a default

# --- PQC Helper Functions ---

def generate_pqc_keys(sig_alg: str = DEFAULT_SIG_ALG) -> Tuple[bytes, bytes]:
    """Generates a PQC public and private key pair."""
    with oqs.Signature(sig_alg) as signer:
        public_key = signer.generate_keypair()
        private_key = signer.export_secret_key()
        return public_key, private_key

def pqc_sign_message(private_key: bytes, message: bytes, sig_alg: str = DEFAULT_SIG_ALG) -> bytes:
    """Signs a message using a PQC private key."""
    with oqs.Signature(sig_alg, private_key) as signer:
        signature = signer.sign(message)
        return signature

def pqc_verify_signature(public_key: bytes, message: bytes, signature: bytes, sig_alg: str = DEFAULT_SIG_ALG) -> bool:
    """Verifies a PQC signature."""
    with oqs.Signature(sig_alg) as verifier:
        try:
            return verifier.verify(message, signature, public_key)
        except oqs.MechanismNotEnabledError:
            print(f"Error: OQS mechanism {sig_alg} not enabled.")
            return False
        except Exception as e:
            # It's often good to log the specific error for debugging
            # print(f"Verification failed: {e}")
            return False