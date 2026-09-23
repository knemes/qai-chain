"""
Consensus Fuel Ledger Engine.
Implements the continuous metabolic equation governing node survival and execution rights:
F_{t+1} = F_t - delta_{burn} + R_{verified} - C_{veto}
Enforces epoch rent, credits quorate proof rewards, and deducts veto penalties.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

# Metabolic Parameters
BASELINE_EPOCH_BURN = 10     # Idle rent per epoch; prunes inactive nodes
VERIFIED_LEMMA_REWARD = 250  # Fuel credited when a node's micro-block is quorate
SYMBOLIC_VETO_PENALTY = 500  # Penalty deducted when SpectreVM vetoes a proposal
DEFAULT_INITIAL_FUEL = 100_000


@dataclass
class NodeFuelAccount:
    """Account state tracking the metabolic fuel of a single monotile node."""
    address: str
    balance: int = DEFAULT_INITIAL_FUEL
    lifetime_gas_consumed: int = 0
    lifetime_lemmas_verified: int = 0
    lifetime_vetoes: int = 0
    status: str = "ACTIVE"       # ACTIVE | INSOLVENT | TOMBSTONE

    @property
    def is_solvent(self) -> bool:
        return self.balance > 0 and self.status == "ACTIVE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "balance": self.balance,
            "lifetime_gas_consumed": self.lifetime_gas_consumed,
            "lifetime_lemmas_verified": self.lifetime_lemmas_verified,
            "lifetime_vetoes": self.lifetime_vetoes,
            "status": self.status,
            "is_solvent": self.is_solvent,
        }


class FuelLedger:
    """Global metabolic registry managing fuel balances across the aperiodic lattice."""

    def __init__(
        self,
        epoch_burn: int = BASELINE_EPOCH_BURN,
        lemma_reward: int = VERIFIED_LEMMA_REWARD,
        veto_penalty: int = SYMBOLIC_VETO_PENALTY,
    ):
        self.epoch_burn = epoch_burn
        self.lemma_reward = lemma_reward
        self.veto_penalty = veto_penalty
        self.accounts: Dict[str, NodeFuelAccount] = {}
        self.current_epoch: int = 0

    def register_node(self, address: str, initial_fuel: int = DEFAULT_INITIAL_FUEL) -> NodeFuelAccount:
        """Registers a newly minted node into the fuel ledger."""
        account = NodeFuelAccount(address=address, balance=initial_fuel)
        self.accounts[address] = account
        return account

    def get_account(self, address: str) -> Optional[NodeFuelAccount]:
        return self.accounts.get(address)

    def apply_epoch_burn(self) -> List[str]:
        """
        Deducts baseline idle rent (delta_burn) across all active accounts.
        Returns a list of addresses that crossed the insolvency boundary (F <= 0).
        """
        self.current_epoch += 1
        newly_insolvent = []

        for addr, account in self.accounts.items():
            if account.status == "ACTIVE":
                account.balance -= self.epoch_burn
                if account.balance <= 0:
                    account.balance = 0
                    account.status = "INSOLVENT"
                    newly_insolvent.append(addr)

        return newly_insolvent

    def credit_verified_transition(self, address: str, gas_used: int) -> int:
        """
        Deducts gas consumed and credits verified lemma reward for a quorate transition:
        F = F - gas_used + R_{verified}
        """
        account = self.accounts.get(address)
        if not account or account.status != "ACTIVE":
            return 0

        account.lifetime_gas_consumed += gas_used
        account.lifetime_lemmas_verified += 1
        account.balance = account.balance - gas_used + self.lemma_reward
        return account.balance

    def penalize_veto(self, address: str, gas_used: int) -> int:
        """
        Penalizes a node when the SpectreVM vetoes a candidate state reduction:
        F = F - gas_used - C_{veto}
        """
        account = self.accounts.get(address)
        if not account or account.status != "ACTIVE":
            return 0

        account.lifetime_gas_consumed += gas_used
        account.lifetime_vetoes += 1
        account.balance = max(0, account.balance - gas_used - self.veto_penalty)

        if account.balance <= 0:
            account.status = "INSOLVENT"

        return account.balance

    def mark_tombstone(self, address: str):
        """Transitions an insolvent node into an officially designated tombstone slot."""
        account = self.accounts.get(address)
        if account:
            account.status = "TOMBSTONE"
            account.balance = 0
