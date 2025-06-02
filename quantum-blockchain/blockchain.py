from time import time
from typing import List, Optional, Dict, Any, Tuple
import binascii
import random
from transaction import Transaction
from block import Block
import hashlib
from ainode import AINode 
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

ADJUDICATION_MIN_VOTES_TO_RESOLVE = 3 # Example: minimum number of votes to resolve a case
ADJUDICATION_SUPERMAJORITY_THRESHOLD = 0.66 # Example: 2/3 needed to confirm misbehavior
ADJUDICATION_CASE_LIFESPAN_BLOCKS = 100 # Example: how many blocks a case stays open for voting

class Blockchain:
    def __init__(self, sig_alg: str = DEFAULT_SIG_ALG):
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.sig_alg = sig_alg
        # Validator Registry: {hex_public_key: {"private_key": bytes, "reputation": float, "public_key_bytes": bytes, "is_active": bool, "effective_max_reputation": float}}
        self.validators: Dict[str, Dict[str, Any]] = {}
        # MIN_REPUTATION_TO_PROPOSE is now a class-level constant

        # Adjudication Cases: {case_id: {"accused_pk_hex": str, "accuser_pk_hex": str, "evidence_cid": str, "rule_violated": str, "votes": {voter_pk_hex: bool}, "creation_block_index": int, "status": "open/closed"}}
        self.adjudication_cases: Dict[str, Dict[str, Any]] = {}
        
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
            print(f"Transaction from {binascii.hexlify(transaction.sender_public_key[:4]).decode()}... is not signed.")
            return False

        if transaction.is_valid(self.sig_alg):
            # Process specific transaction types before adding to general pending pool if needed
            if isinstance(transaction.data, dict):
                tx_type = transaction.data.get("type")
                if tx_type == "proof_of_misbehavior":
                    self._initiate_adjudication_case(transaction)
                    # This transaction is processed immediately and doesn't go to pending_transactions for block inclusion
                    # Or, it could be included in a block to make the accusation public and immutable
                    # For now, let's assume it's processed and logged, then maybe also added to pending.
                elif tx_type == "adjudication_vote":
                    self._process_adjudication_vote(transaction)
                    # Similar to above, processed immediately.
            self.pending_transactions.append(transaction) # Add all valid transactions to pending for now
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
            if validator_data["is_active"]: 
                print(f"Validator {hex_public_key[:10]}... marked as inactive. Applying decay.")
                validator_data["is_active"] = False
                self._update_validator_reputation(public_key_bytes, REPUTATION_DECAY_FOR_INACTIVITY_PERIOD)
        else:
            print(f"Attempted to process inactivity for unregistered validator {hex_public_key[:10]}...")

    def process_community_engagement(self, public_key_bytes: bytes, reward_amount: float = REPUTATION_REWARD_COMMUNITY_ENGAGEMENT_SMALL) -> None:
        """Processes a positive community engagement action by a validator."""
        hex_public_key = binascii.hexlify(public_key_bytes).decode('ascii')
        if hex_public_key in self.validators:
            self.validators[hex_public_key]["is_active"] = True
            self._update_validator_reputation(public_key_bytes, reward_amount)
            print(f"Validator {hex_public_key[:10]}... rewarded for community engagement.")
        else:
            print(f"Attempted to process community engagement for unregistered validator {hex_public_key[:10]}...")

    def _initiate_adjudication_case(self, accusation_transaction: Transaction) -> None:
        """Initiates a new adjudication case based on a 'proof_of_misbehavior' transaction."""
        data = accusation_transaction.data
        accuser_pk_hex = binascii.hexlify(accusation_transaction.sender_public_key).decode('ascii')
        accused_pk_hex = data.get("accused_node_pk_hex")
        evidence_cid = data.get("evidence_cid")
        rule_violated = data.get("rule_violated")

        if not all([accused_pk_hex, evidence_cid, rule_violated]):
            print(f"Invalid 'proof_of_misbehavior' transaction data from {accuser_pk_hex[:10]}...")
            return

        if accuser_pk_hex not in self.validators or not self.validators[accuser_pk_hex]["is_active"]:
            print(f"Accuser {accuser_pk_hex[:10]}... is not an active validator. Accusation ignored.")
            return
        
        if accused_pk_hex not in self.validators:
            print(f"Accused node {accused_pk_hex[:10]}... not found. Accusation ignored.")
            return

        case_id = hashlib.sha256(f"{accuser_pk_hex}{accused_pk_hex}{evidence_cid}{rule_violated}{time()}".encode()).hexdigest()
        self.adjudication_cases[case_id] = {
            "accused_pk_hex": accused_pk_hex,
            "accuser_pk_hex": accuser_pk_hex,
            "evidence_cid": evidence_cid,
            "rule_violated": rule_violated,
            "votes": {}, # voter_pk_hex: vote_is_substantiated (True/False)
            "creation_block_index": self.get_last_block().index if self.chain else 0,
            "status": "open"
        }
        print(f"New Adjudication Case {case_id[:8]}... initiated by {accuser_pk_hex[:10]}... against {accused_pk_hex[:10]}...")

    def _process_adjudication_vote(self, vote_transaction: Transaction) -> None:
        """Processes a vote for an ongoing adjudication case."""
        data = vote_transaction.data
        voter_pk_hex = binascii.hexlify(vote_transaction.sender_public_key).decode('ascii')
        case_id = data.get("case_id")
        vote_is_substantiated = data.get("vote_substantiated") # True or False

        if case_id not in self.adjudication_cases or self.adjudication_cases[case_id]["status"] != "open":
            print(f"Vote from {voter_pk_hex[:10]}... for invalid or closed case {case_id[:8]}...")
            return

        if voter_pk_hex not in self.validators or not self.validators[voter_pk_hex]["is_active"] or self.validators[voter_pk_hex]["reputation"] < MIN_REPUTATION_TO_PROPOSE:
            print(f"Vote from {voter_pk_hex[:10]}...: voter not eligible (inactive or low reputation).")
            return
        
        case = self.adjudication_cases[case_id]
        if voter_pk_hex == case["accused_pk_hex"] or voter_pk_hex == case["accuser_pk_hex"]:
            print(f"Vote from {voter_pk_hex[:10]}...: accuser/accused cannot vote on their own case.")
            return

        if voter_pk_hex in case["votes"]:
            print(f"Vote from {voter_pk_hex[:10]}...: already voted on case {case_id[:8]}...")
            return

        case["votes"][voter_pk_hex] = vote_is_substantiated
        print(f"Vote received from {voter_pk_hex[:10]}... for case {case_id[:8]}...: {'Substantiated' if vote_is_substantiated else 'Not Substantiated'}")
        # TODO: Add logic here to check if enough votes are in to resolve the case, or if case lifespan is exceeded.
        # If resolved, tally votes, apply penalties/rewards, and change case status to "closed".

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
        print(f"  Validator {pk_hex[:10]}... : {data['reputation']:.2f}, Effective Max: {data['effective_max_reputation']:.2f}")

    # Create AINode instances
    # The genesis proposer is already registered. Let's get its hex_pk to create an AINode object for it.
    genesis_hex_pk = binascii.hexlify(qai_blockchain.genesis_proposer_public_key).decode('ascii')
    node_genesis = AINode(qai_blockchain, "GenesisNode", 
                          existing_public_key=qai_blockchain.genesis_proposer_public_key, 
                          existing_private_key=qai_blockchain.genesis_proposer_private_key)

    node1 = AINode(qai_blockchain, "Node1")
    node1.register_as_validator()
    node2 = AINode(qai_blockchain, "Node2")
    node2.register_as_validator()
    node3 = AINode(qai_blockchain, "Node3")
    node3.register_as_validator()

    all_ai_nodes = [node_genesis, node1, node2, node3]

    # Node1 submits a generic transaction (e.g., data upload)
    tx1_data = {"type": "data_upload", "ipfs_cid": "QmExampleCID1", "description": "Node1's data"}
    node1_tx1 = node1.create_and_sign_transaction(recipient_pk_bytes=node2.public_key, data=tx1_data)
    if node1_tx1:
        node1.submit_transaction(node1_tx1)

    # Node2 submits a node registration type transaction (though it's already a validator)
    tx2_data = {"type": "node_info_update", "info": "Node2 updated info"}
    node2_tx1 = node2.create_and_sign_transaction(recipient_pk_bytes=None, data=tx2_data)
    if node2_tx1:
        node2.submit_transaction(node2_tx1)

    # Simulate a few rounds of block creation using Proof-of-Reputation
    for i in range(10): # Try to create 10 blocks
        print(f"\n--- Attempting to create block round {i+1} ---")
        
        # Add a new dummy transaction for each round if needed
        # (unless there are already pending transactions)
        if not qai_blockchain.pending_transactions:
            if all_ai_nodes:
                # Pick a random AINode to send a heartbeat
                random_node = random.choice(all_ai_nodes)
                heartbeat_data = {"type": "heartbeat", "round": i + 1, "message": f"{random_node.node_id} is alive"}
                heartbeat_tx = random_node.create_and_sign_transaction(None, heartbeat_data)
                if heartbeat_tx: random_node.submit_transaction(heartbeat_tx)
            else:
                print("No validators registered to create dummy transactions for block attempt.")
                break
        
        # Simulate some inactivity and community engagement randomly
        if i > 0 and i % 3 == 0 and qai_blockchain.validators: # Every 3 rounds
            inactive_candidate_hex = random.choice(list(qai_blockchain.validators.keys()))
            # Find the AINode object to call its method, or directly call blockchain method
            node_to_make_inactive = next((n for n in all_ai_nodes if n.hex_public_key == inactive_candidate_hex), None)
            if node_to_make_inactive:
                print(f"Simulating {node_to_make_inactive} reporting inactivity for itself (for test).") # Or another node reports it
                # In reality, another node would report this with evidence.
                # For simulation, we can directly call the blockchain's processing method.
                qai_blockchain.process_validator_inactivity(node_to_make_inactive.public_key)
        
        if i > 0 and i % 4 == 0 and qai_blockchain.validators: # Every 4 rounds
            engaged_candidate_hex = random.choice(list(qai_blockchain.validators.keys()))
            node_to_engage = next((n for n in all_ai_nodes if n.hex_public_key == engaged_candidate_hex), None)
            if node_to_engage:
                print(f"Simulating {node_to_engage} performing community engagement.")
                node_to_engage.propose_community_engagement({"action": "validated_helpful_analysis_xyz", "evidence_cid": "QmEngage"})

        # Simulate an accusation and voting (very simplified)
        if i == 2 and len(all_ai_nodes) >= 3: # At round 2, if enough nodes
            accuser_node, accused_node, voter_node = random.sample([n for n in all_ai_nodes if n.hex_public_key in qai_blockchain.validators and qai_blockchain.validators[n.hex_public_key]["is_active"]], 3)
            if accuser_node.submit_accusation(accused_node.hex_public_key, "QmEvidenceOfBadStuff", "Rule_101_Violation"):
                # Find the case_id (this is a simplification, real system needs better case tracking)
                open_cases = [cid for cid, case_data in qai_blockchain.adjudication_cases.items() if case_data["status"] == "open" and case_data["accused_pk_hex"] == accused_node.hex_public_key]
                if open_cases:
                    voter_node.submit_adjudication_vote(open_cases[0], vote_is_substantiated=True) # Voter agrees

        newly_created_block = qai_blockchain.attempt_create_and_add_block()
        if newly_created_block:
            print(f"Successfully created and added block {newly_created_block.index}.")
        else:
            print(f"Failed to create/add block in round {i+1}.")
        print("Current validator reputations:")
        for pk_hex, data in qai_blockchain.validators.items():
            print(f"  Validator {pk_hex[:10]}... : Rep={data['reputation']:.2f}, MaxRep={data['effective_max_reputation']:.2f}, Active={data['is_active']}")

    print(f"\nCurrent Blockchain length: {len(qai_blockchain.chain)}")
    for block_in_chain in qai_blockchain.chain:
        print(block_in_chain)
        for tx_in_block in block_in_chain.transactions:
            print(f"  ↳ {tx_in_block}")

    qai_blockchain.is_chain_valid()

    # Example of a potentially invalid transaction (e.g., wrong private key)
    print("\n--- Testing invalid transaction ---")
    # Use an existing node (node1) but try to sign with different keys
    rogue_node_for_test = AINode(qai_blockchain, "RogueTestNode") # This node is not registered as a validator
    invalid_tx_data = {"type": "tamper_attempt", "value": "secret_data"}
    invalid_transaction = Transaction(sender_public_key=node1.public_key, recipient_public_key=node2.public_key, data=invalid_tx_data)
    try:
        invalid_transaction.sign_transaction(rogue_node_for_test.private_key, DEFAULT_SIG_ALG) # Signed with wrong private key
        if not qai_blockchain.add_transaction(invalid_transaction):
            print("Correctly identified and rejected invalid transaction.")
    except Exception as e:
        print(f"Error during invalid transaction test: {e}")

    qai_blockchain.is_chain_valid()