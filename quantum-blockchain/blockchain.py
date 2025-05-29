from time import time
from typing import List, Optional
from transaction import Transaction
from block import Block
from pqs_utils import DEFAULT_SIG_ALG, pqc_sign_message, pqc_verify_signature, generate_pqc_keys

class Blockchain:
    def __init__(self, sig_alg: str = DEFAULT_SIG_ALG):
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.sig_alg = sig_alg
        
        # Create a dummy key pair for the genesis block proposer
        # In a real system, this would be a well-known or configured key
        self.genesis_proposer_public_key, self.genesis_proposer_private_key = generate_pqc_keys(self.sig_alg)
        
        self.create_genesis_block()

    def create_genesis_block(self) -> None:
        """Creates the first block in the chain (genesis block)."""
        genesis_transactions = [Transaction(self.genesis_proposer_public_key, self.genesis_proposer_public_key, "Genesis Block Data", timestamp=time())]
        # Sign the genesis transaction (self-signed for simplicity)
        genesis_transactions[0].sign_transaction(self.genesis_proposer_private_key, self.sig_alg)

        genesis_block = Block(index=0, 
                              transactions=genesis_transactions,
                              timestamp=time(), 
                              previous_hash="0", 
                              proposer_public_key=self.genesis_proposer_public_key)
        genesis_block.sign_block(self.genesis_proposer_private_key, self.sig_alg)
        self.chain.append(genesis_block)

    def get_last_block(self) -> Block:
        """Returns the last block in the chain."""
        return self.chain[-1]

    def add_transaction(self, transaction: Transaction) -> bool:
        """Adds a new transaction to the list of pending transactions if it's valid."""
        if not transaction.sender_public_key: # Should not happen for normal tx
            print("Transaction sender public key is missing.")
            return False
        if not transaction.signature:
            print("Transaction is not signed.")
            return False # Or attempt to sign if private key is available, but better to have it pre-signed

        if transaction.is_valid(self.sig_alg):
            self.pending_transactions.append(transaction)
            print(f"Transaction added to pending: {transaction}")
            return True
        else:
            print(f"Invalid transaction discarded: {transaction}")
            return False

    def create_new_block(self, proposer_public_key: bytes, proposer_private_key: bytes) -> Optional[Block]:
        """Creates a new block with pending transactions (simplified 'mining')."""
        if not self.pending_transactions:
            print("No pending transactions to add to a new block.")
            return None

        last_block = self.get_last_block()
        new_block = Block(index=last_block.index + 1,
                          transactions=list(self.pending_transactions), # Take a copy
                          timestamp=time(),
                          previous_hash=last_block.hash,
                          proposer_public_key=proposer_public_key)
        
        new_block.sign_block(proposer_private_key, self.sig_alg)
        
        # Clear pending transactions after they are included in a block
        self.pending_transactions = []
        return new_block

    def add_block(self, block: Block) -> bool:
        """Adds a new valid block to the chain."""
        last_block = self.get_last_block()

        # Basic validation
        if block.previous_hash != last_block.hash:
            print("Error: New block's previous_hash does not match last block's hash.")
            return False
        if block.index != last_block.index + 1:
            print("Error: New block's index is not sequential.")
            return False
        if block.hash != block.calculate_block_hash(): # Recalculate to ensure integrity
            print("Error: New block's hash is incorrect or has been tampered with.")
            return False
        if not block.verify_block_signature(self.sig_alg):
            print("Error: New block's signature is invalid.")
            return False
        
        # Validate all transactions within the block
        for tx in block.transactions:
            if not tx.is_valid(self.sig_alg):
                print(f"Error: Block contains an invalid transaction: {tx}")
                return False

        self.chain.append(block)
        print(f"Block added to chain: {block}")
        return True

    def is_chain_valid(self) -> bool:
        """Validates the integrity of the entire blockchain."""
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]

            if current_block.hash != current_block.calculate_block_hash():
                print(f"Chain invalid: Block {current_block.index} hash mismatch.")
                return False
            if current_block.previous_hash != previous_block.hash:
                print(f"Chain invalid: Block {current_block.index} previous_hash mismatch.")
                return False
            if not current_block.verify_block_signature(self.sig_alg):
                print(f"Chain invalid: Block {current_block.index} signature invalid.")
                return False
            for tx in current_block.transactions:
                if not tx.is_valid(self.sig_alg):
                    print(f"Chain invalid: Transaction in block {current_block.index} is invalid: {tx}")
                    return False
        print("Chain is valid.")
        return True

if __name__ == '__main__':
    print(f"Using PQC Signature Algorithm: {DEFAULT_SIG_ALG}")

    # Create a blockchain instance
    qai_blockchain = Blockchain(sig_alg=DEFAULT_SIG_ALG)
    print(f"Genesis block created: {qai_blockchain.get_last_block()}")

    # Create some users (nodes) with PQC key pairs
    user1_pub, user1_priv = generate_pqc_keys(DEFAULT_SIG_ALG)
    user2_pub, user2_priv = generate_pqc_keys(DEFAULT_SIG_ALG)
    
    # User1 wants to send some data (e.g., an IPFS CID) to User2 (or just record it)
    tx1_data = {"type": "data_upload", "ipfs_cid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco"}
    transaction1 = Transaction(sender_public_key=user1_pub, recipient_public_key=user2_pub, data=tx1_data)
    transaction1.sign_transaction(user1_priv, DEFAULT_SIG_ALG)
    
    if qai_blockchain.add_transaction(transaction1):
        print("Transaction 1 successfully added to pending pool.")

    # Another transaction
    tx2_data = {"type": "node_registration", "node_id": "node_abc_123"}
    transaction2 = Transaction(sender_public_key=user2_pub, recipient_public_key=None, data=tx2_data) # Recipient can be None
    transaction2.sign_transaction(user2_priv, DEFAULT_SIG_ALG)
    qai_blockchain.add_transaction(transaction2)

    # A "miner" or block proposer creates a new block
    # For this example, let's say user1 is the proposer for the next block
    block_proposer_pub, block_proposer_priv = user1_pub, user1_priv 
    
    new_block_candidate = qai_blockchain.create_new_block(proposer_public_key=block_proposer_pub, 
                                                        proposer_private_key=block_proposer_priv)

    if new_block_candidate:
        if qai_blockchain.add_block(new_block_candidate):
            print(f"New block {new_block_candidate.index} successfully added to the chain.")
        else:
            print(f"Failed to add new block {new_block_candidate.index} to the chain.")

    print(f"\nCurrent Blockchain length: {len(qai_blockchain.chain)}")
    for block_in_chain in qai_blockchain.chain:
        print(block_in_chain)
        for tx_in_block in block_in_chain.transactions:
            print(f"  ↳ {tx_in_block}")

    qai_blockchain.is_chain_valid()

    # Example of a potentially invalid transaction (e.g., wrong private key)
    print("\n--- Testing invalid transaction ---")
    rogue_pub, rogue_priv = generate_pqc_keys(DEFAULT_SIG_ALG) # Different key
    invalid_tx_data = {"type": "tamper_attempt", "value": "secret_data"}
    invalid_transaction = Transaction(sender_public_key=user1_pub, recipient_public_key=user2_pub, data=invalid_tx_data)
    try:
        invalid_transaction.sign_transaction(rogue_priv, DEFAULT_SIG_ALG) # Signed with wrong private key
        if not qai_blockchain.add_transaction(invalid_transaction):
            print("Correctly identified and rejected invalid transaction.")
    except Exception as e:
        print(f"Error during invalid transaction test: {e}")

    qai_blockchain.is_chain_valid()