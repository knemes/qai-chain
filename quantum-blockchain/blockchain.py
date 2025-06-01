from time import time
from typing import List, Optional, Dict, Any, Tuple
import binascii
import random
from transaction import Transaction
from block import Block
from pqs_utils import DEFAULT_SIG_ALG, pqc_sign_message, pqc_verify_signature, generate_pqc_keys

# --- Reputation System Constants ---
INITIAL_VALIDATOR_REPUTATION = 1.0
GLOBAL_MAX_REPUTATION = 1.0
MIN_REPUTATION_TO_PROPOSE = 0.15

CRITICAL_REPUTATION_THRESHOLD = 0.5
REPUTATION_SCAR_DECREMENT = 0.01 

REPUTATION_REWARD_PROPOSE_VALID_BLOCK = 0.0
REPUTATION_REWARD_COMMUNITY_ENGAGEMENT_SMALL = 0.02 

REPUTATION_PENALTY_INVALID_BLOCK_SIGNATURE = -0.5
REPUTATION_PENALTY_HASH_MISMATCH = -0.5
REPUTATION_PENALTY_FAILED_ADD_BLOCK_GENERIC = -0.2
REPUTATION_DECAY_FOR_INACTIVITY_PERIOD = -0.1 

class Blockchain:
    def __init__(self, sig_alg: str = DEFAULT_SIG_ALG):
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.sig_alg = sig_alg
        # Validator Registry: {hex_public_key: {"private_key": bytes, "reputation": float, "public_key_bytes": bytes, "is_active": bool, "effective_max_reputation": float}}
        self.validators: Dict[str, Dict[str, Any]] = {}
        # MIN_REPUTATION_TO_PROPOSE is now a class-level constant
        
        # Create a dummy key pair for the genesis block proposer
        # In a real system, this would be a well-known or configured key
        self.genesis_proposer_public_key, self.genesis_proposer_private_key = generate_pqc_keys(self.sig_alg)
        self.register_validator(self.genesis_proposer_public_key, self.genesis_proposer_private_key) # Uses default INITIAL_VALIDATOR_REPUTATION
        
        self.create_genesis_block()

    def _update_validator_reputation(self, public_key_bytes: bytes, change: float) -> None:
        """Updates the reputation of a validator."""
        hex_public_key = binascii.hexlify(public_key_bytes).decode('ascii')
        if hex_public_key in self.validators:
            validator_data = self.validators[hex_public_key]
            old_reputation = validator_data["reputation"]
            new_reputation = old_reputation + change

            # Check for crossing critical threshold downwards to apply scar
            if old_reputation >= CRITICAL_REPUTATION_THRESHOLD and new_reputation < CRITICAL_REPUTATION_THRESHOLD:
                validator_data["effective_max_reputation"] = max(0, validator_data["effective_max_reputation"] - REPUTATION_SCAR_DECREMENT) # Ensure it doesn't go below 0
                print(f"Validator {hex_public_key[:10]}... scarred. Effective max reputation now: {validator_data['effective_max_reputation']:.2f}.")
                
                if validator_data["effective_max_reputation"] < MIN_REPUTATION_TO_PROPOSE:
                    self._replace_validator_due_to_severe_scarring(hex_public_key)
                    return # Re-initialization handles setting reputation and printing, so we exit early.

            validator_data["reputation"] = new_reputation

            # Ensure reputation doesn't go below a certain floor, e.g., 0
            if validator_data["reputation"] < 0:
                validator_data["reputation"] = 0
            
            if validator_data["reputation"] > validator_data["effective_max_reputation"]:
                validator_data["reputation"] = validator_data["effective_max_reputation"]
            print(f"Validator {hex_public_key[:10]}... reputation updated to {validator_data['reputation']:.2f}.")
        else:
            print(f"Attempted to update reputation for unregistered validator {hex_public_key[:10]}...")

    def _select_block_proposer(self) -> Optional[Tuple[bytes, bytes]]:
        """Selects a block proposer based on reputation (weighted random selection).
           Returns (public_key_bytes, private_key_bytes) or None.
           NOTE: Returning private_key is for simulation purposes ONLY.
        """
        eligible_validators = {
            pk_hex: data for pk_hex, data in self.validators.items()
            if data["is_active"] and data["reputation"] >= MIN_REPUTATION_TO_PROPOSE
        }
        if not eligible_validators:
            print(f"No eligible validators with reputation >= {MIN_REPUTATION_TO_PROPOSE} to propose a block.")
            return None

        weighted_list = []
        for pk_hex, data in eligible_validators.items():
            # Weighting: ensure even low positive reputation gets a chance.
            # A reputation of 1.0 (good standing) gets a decent weight.
            # A reputation of 0.1 (barely eligible) gets minimal weight.
            weight = max(1, int(data["reputation"] * 10)) # Scale reputation for weighting, ensure at least 1
            weighted_list.extend([pk_hex] * weight)

        selected_pk_hex = random.choice(weighted_list)
        selected_validator_data = self.validators[selected_pk_hex]
        print(f"Selected proposer: {selected_pk_hex[:10]}... (Reputation: {selected_validator_data['reputation']:.2f})")
        return selected_validator_data["public_key_bytes"], selected_validator_data["private_key"]

    def register_validator(self, public_key: bytes, private_key: bytes, initial_reputation: float = INITIAL_VALIDATOR_REPUTATION) -> None:
        """Registers a new validator with an initial reputation.
           NOTE: Storing private_key here is for simulation purposes ONLY."""
        hex_public_key = binascii.hexlify(public_key).decode('ascii')
        if hex_public_key in self.validators:
            print(f"Validator {hex_public_key[:10]}... already registered.")
            return
        self.validators[hex_public_key] = {
            "private_key": private_key, # For simulation ONLY
            "reputation": initial_reputation,
            "public_key_bytes": public_key,
            "is_active": True,
            "effective_max_reputation": GLOBAL_MAX_REPUTATION # Start with the global max
        }
        print(f"Validator {hex_public_key[:10]}... registered with reputation {initial_reputation:.2f}, active: True.")

    def _replace_validator_due_to_severe_scarring(self, old_hex_public_key: str) -> None:
        """Destroys a validator due to severe scarring and replaces it with a new one."""
        if old_hex_public_key in self.validators:
            print(f"Validator {old_hex_public_key[:10]}... DESTROYED due to severe scarring (effective max reputation too low).")
            del self.validators[old_hex_public_key]

            # Create and register a brand new validator to take its "slot" in the ecosystem
            new_public_key, new_private_key = generate_pqc_keys(self.sig_alg)
            print(f"Creating a new validator to replace the destroyed one.")
            self.register_validator(new_public_key, new_private_key) # Registers with default initial reputation
        else:
            print(f"Attempted to replace non-existent validator {old_hex_public_key[:10]}...")

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

    def _create_block_candidate(self, proposer_public_key: bytes, proposer_private_key: bytes) -> Optional[Block]:
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
        """Adds a new valid block to the chain and updates proposer reputation accordingly."""
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
            self._update_validator_reputation(block.proposer_public_key, REPUTATION_PENALTY_HASH_MISMATCH)
            return False
        if not block.verify_block_signature(self.sig_alg):
            print("Error: New block's signature is invalid.")
            self._update_validator_reputation(block.proposer_public_key, REPUTATION_PENALTY_INVALID_BLOCK_SIGNATURE)
            return False
        
        # Validate all transactions within the block
        for tx in block.transactions:
            if not tx.is_valid(self.sig_alg):
                print(f"Error: Block contains an invalid transaction: {tx}")
                # This could be complex: is it proposer's fault for including it, or sender's fault for creating it?
                # For now, let's assume proposer should do basic checks.
                self._update_validator_reputation(block.proposer_public_key, REPUTATION_PENALTY_FAILED_ADD_BLOCK_GENERIC)
                return False

        self.chain.append(block)
        print(f"Block added to chain: {block}")
        if REPUTATION_REWARD_PROPOSE_VALID_BLOCK != 0.0: # Only apply if there's a reward
            self._update_validator_reputation(block.proposer_public_key, REPUTATION_REWARD_PROPOSE_VALID_BLOCK)
        return True

    def process_validator_inactivity(self, public_key_bytes: bytes) -> None:
        """Processes a validator that has been deemed inactive."""
        hex_public_key = binascii.hexlify(public_key_bytes).decode('ascii')
        if hex_public_key in self.validators:
            validator_data = self.validators[hex_public_key]
            if validator_data["is_active"]: # Only penalize if they were previously active
                print(f"Validator {hex_public_key[:10]}... marked as inactive. Applying decay.")
                validator_data["is_active"] = False
                self._update_validator_reputation(public_key_bytes, REPUTATION_DECAY_FOR_INACTIVITY_PERIOD)
        else:
            print(f"Attempted to process inactivity for unregistered validator {hex_public_key[:10]}...")

    def process_community_engagement(self, public_key_bytes: bytes, reward_amount: float = REPUTATION_REWARD_COMMUNITY_ENGAGEMENT_SMALL) -> None:
        """Processes a positive community engagement action by a validator."""
        hex_public_key = binascii.hexlify(public_key_bytes).decode('ascii')
        if hex_public_key in self.validators:
            self.validators[hex_public_key]["is_active"] = True # Engagement implies activity
            self._update_validator_reputation(public_key_bytes, reward_amount)
            print(f"Validator {hex_public_key[:10]}... rewarded for community engagement.")
        else:
            print(f"Attempted to process community engagement for unregistered validator {hex_public_key[:10]}...")

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

    def attempt_create_and_add_block(self) -> Optional[Block]:
        """Attempts to create and add a new block using Proof-of-Reputation."""
        if not self.pending_transactions:
            # print("No pending transactions to form a block.") # Can be noisy if called in a loop
            return None

        proposer_keys = self._select_block_proposer()
        if not proposer_keys:
            # print("Failed to select a block proposer in this round.") # Can be noisy
            return None
        
        proposer_public_key, proposer_private_key = proposer_keys

        block_candidate = self._create_block_candidate(proposer_public_key, proposer_private_key)

        if block_candidate:
            if self.add_block(block_candidate): # add_block now handles reputation updates
                return block_candidate
            # else: add_block returned False, and it should have handled penalizing the proposer if it was their fault.
        return None

if __name__ == '__main__':
    print(f"Using PQC Signature Algorithm: {DEFAULT_SIG_ALG}")

    # Create a blockchain instance
    qai_blockchain = Blockchain(sig_alg=DEFAULT_SIG_ALG)
    print(f"Genesis block created: {qai_blockchain.get_last_block()}")
    print("Initial Validator reputations:")
    for pk_hex, data in qai_blockchain.validators.items():
        print(f"  Validator {pk_hex[:10]}... : {data['reputation']:.2f}")


    # Create some users (nodes) with PQC key pairs
    user1_pub, user1_priv = generate_pqc_keys(DEFAULT_SIG_ALG)
    user2_pub, user2_priv = generate_pqc_keys(DEFAULT_SIG_ALG)
    user3_pub, user3_priv = generate_pqc_keys(DEFAULT_SIG_ALG)
    qai_blockchain.register_validator(user1_pub, user1_priv) # Uses default INITIAL_VALIDATOR_REPUTATION
    qai_blockchain.register_validator(user2_pub, user2_priv)
    qai_blockchain.register_validator(user3_pub, user3_priv)
    
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

    # Simulate a few rounds of block creation using Proof-of-Reputation
    for i in range(10): # Try to create 10 blocks
        print(f"\n--- Attempting to create block round {i+1} ---")
        
        # Add a new dummy transaction for each round if needed
        # (unless there are already pending transactions)
        if not qai_blockchain.pending_transactions:
            if qai_blockchain.validators:
                # Pick a random validator to be the sender of a dummy tx
                # This is just for testing block creation, not a real scenario
                dummy_sender_hex = random.choice(list(qai_blockchain.validators.keys()))
                dummy_sender_data = qai_blockchain.validators[dummy_sender_hex]
                
                dummy_tx_data = {"type": "heartbeat", "round": i+1, "node_id": f"node_{dummy_sender_hex[:6]}"}
                dummy_transaction = Transaction(sender_public_key=dummy_sender_data["public_key_bytes"], 
                                                recipient_public_key=None, data=dummy_tx_data)
                dummy_transaction.sign_transaction(dummy_sender_data["private_key"])
                qai_blockchain.add_transaction(dummy_transaction)
            else:
                print("No validators registered to create dummy transactions for block attempt.")
                break
        
        # Simulate some inactivity and community engagement randomly
        if i > 0 and i % 3 == 0 and qai_blockchain.validators: # Every 3 rounds
            inactive_candidate_hex = random.choice(list(qai_blockchain.validators.keys()))
            print(f"Simulating inactivity for {inactive_candidate_hex[:10]}...")
            qai_blockchain.process_validator_inactivity(qai_blockchain.validators[inactive_candidate_hex]["public_key_bytes"])
        
        if i > 0 and i % 4 == 0 and qai_blockchain.validators: # Every 4 rounds
            engaged_candidate_hex = random.choice(list(qai_blockchain.validators.keys()))
            print(f"Simulating community engagement for {engaged_candidate_hex[:10]}...")
            qai_blockchain.process_community_engagement(qai_blockchain.validators[engaged_candidate_hex]["public_key_bytes"])
        
        newly_created_block = qai_blockchain.attempt_create_and_add_block()
        if newly_created_block:
            print(f"Successfully created and added block {newly_created_block.index}.")
        else:
            print(f"Failed to create/add block in round {i+1}.")
        print("Current validator reputations:")
        for pk_hex, data in qai_blockchain.validators.items():
            print(f"  Validator {pk_hex[:10]}... : {data['reputation']:.2f}")

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