import hashlib
import json
from time import time
from typing import List, Dict, Any, Optional
import binascii # For converting keys to hex for display/storage if needed
from transaction import Transaction
from pqs_utils import DEFAULT_SIG_ALG, pqc_sign_message, pqc_verify_signature, generate_pqc_keys

class Block:
    def __init__(self, index: int, transactions: List[Transaction], timestamp: float, previous_hash: str, proposer_public_key: bytes, nonce: int = 0):
        self.index = index
        self.transactions = transactions
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.proposer_public_key = proposer_public_key
        self.nonce = nonce # For PoW, can be adapted for PoS later
        
        self.block_signature: Optional[bytes] = None # Signature of the block hash by the proposer
        self.hash = self.calculate_block_hash() # Hash of the block header + transactions

    def __repr__(self):
        return (f"Block(Index: {self.index}, PrevHash: {self.previous_hash[:8]}..., "
                f"Hash: {self.hash[:8]}..., TxCount: {len(self.transactions)}, "
                f"Signed: {'Yes' if self.block_signature else 'No'})")

    def _header_data_for_hashing(self) -> Dict[str, Any]:
        """Returns an ordered dictionary of block header data for consistent hashing."""
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'previous_hash': self.previous_hash,
            'proposer_public_key': binascii.hexlify(self.proposer_public_key).decode('ascii'),
            'nonce': self.nonce,
            'transactions_merkle_root': self._calculate_transactions_merkle_root()
        }

    def _calculate_transactions_merkle_root(self) -> str:
        """Calculates a simple Merkle root for the transactions in the block."""
        if not self.transactions:
            return hashlib.sha256(b'').hexdigest()
        
        transaction_hashes = [
            json.dumps(tx.to_ordered_dict(), sort_keys=True) + (binascii.hexlify(tx.signature).decode('ascii') if tx.signature else "")
            for tx in self.transactions
        ]
        
        # Simple way to combine hashes for now (not a full Merkle tree for brevity)
        combined_hashes = "".join(transaction_hashes)
        return hashlib.sha256(combined_hashes.encode('utf-8')).hexdigest()

    def calculate_block_hash(self) -> str:
        """Calculates the hash of the block (header + transaction merkle root)."""
        block_header_string = json.dumps(self._header_data_for_hashing(), sort_keys=True).encode('utf-8')
        return hashlib.sha256(block_header_string).hexdigest()

    def sign_block(self, proposer_private_key: bytes, sig_alg: str = DEFAULT_SIG_ALG) -> None:
        """Signs the block's hash with the proposer's private key."""
        if self.block_signature:
            raise ValueError("Block already signed.")
        # The message to sign is the block's own calculated hash
        message_to_sign = bytes.fromhex(self.hash) 
        self.block_signature = pqc_sign_message(proposer_private_key, message_to_sign, sig_alg)

    def verify_block_signature(self, sig_alg: str = DEFAULT_SIG_ALG) -> bool:
        """Verifies the block's signature."""
        if not self.block_signature:
            print(f"Block {self.index} has no signature.")
            return False
        message_to_verify = bytes.fromhex(self.hash)
        return pqc_verify_signature(self.proposer_public_key, message_to_verify, self.block_signature, sig_alg)
    