import hashlib
import json
from time import time
from typing import Dict, Any, Optional
import binascii # For converting keys to hex for display/storage if needed
from pqs_utils import DEFAULT_SIG_ALG, pqc_sign_message, pqc_verify_signature, generate_pqc_keys

class Transaction:
    def __init__(self, sender_public_key: bytes, recipient_public_key: Optional[bytes], data: Any, timestamp: Optional[float] = None):
        self.sender_public_key = sender_public_key # Bytes
        self.recipient_public_key = recipient_public_key # Bytes (can be None or a special address for data uploads)
        self.data = data # Could be IPFS CIDs, AI model updates, etc.
        self.timestamp = timestamp or time()
        self.signature: Optional[bytes] = None

    def __repr__(self) -> str:
        return (f"Transaction(Sender: {binascii.hexlify(self.sender_public_key[:8]).decode()}..., "
                f"Recipient: {binascii.hexlify(self.recipient_public_key[:8]).decode() if self.recipient_public_key else 'N/A'}..., "
                f"Data: {str(self.data)[:30]}..., Signed: {'Yes' if self.signature else 'No'})")

    def to_ordered_dict(self) -> Dict[str, Any]:
        """Returns an ordered dictionary representation of the transaction for consistent hashing/signing."""
        return {
            'sender_public_key': binascii.hexlify(self.sender_public_key).decode('ascii'),
            'recipient_public_key': binascii.hexlify(self.recipient_public_key).decode('ascii') if self.recipient_public_key else None,
            'data': self.data,
            'timestamp': self.timestamp
        }

    def calculate_hash_for_signing(self) -> bytes:
        """Calculates the hash of the transaction content that will be signed."""
        transaction_string = json.dumps(self.to_ordered_dict(), sort_keys=True).encode('utf-8')
        return hashlib.sha256(transaction_string).digest() # Using sha256 for the message digest before PQC signing

    def sign_transaction(self, sender_private_key: bytes, sig_alg: str = DEFAULT_SIG_ALG) -> None:
        """Signs the transaction with the sender's private key."""
        if self.signature:
            raise ValueError("Transaction already signed.")
        message_to_sign = self.calculate_hash_for_signing()
        self.signature = pqc_sign_message(sender_private_key, message_to_sign, sig_alg)

    def is_valid(self, sig_alg: str = DEFAULT_SIG_ALG) -> bool:
        """Validates the transaction's signature."""
        if not self.sender_public_key: # Genesis transactions might not have a sender
            return True
        if not self.signature:
            print("Transaction has no signature.")
            return False
        
        message_to_verify = self.calculate_hash_for_signing()
        return pqc_verify_signature(self.sender_public_key, message_to_verify, self.signature, sig_alg)