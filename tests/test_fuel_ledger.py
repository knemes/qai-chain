"""
Unit tests for the Consensus Fuel Ledger Engine.
"""

import unittest
from consensus.fuel_ledger import (
    FuelLedger,
    BASELINE_EPOCH_BURN,
    VERIFIED_LEMMA_REWARD,
    SYMBOLIC_VETO_PENALTY,
)


class TestFuelLedger(unittest.TestCase):

    def setUp(self):
        self.ledger = FuelLedger()
        self.node_addr = "G0.M0.S0.T0"
        self.ledger.register_node(self.node_addr, initial_fuel=1000)

    def test_epoch_burn_deduction(self):
        newly_insolvent = self.ledger.apply_epoch_burn()
        self.assertEqual(len(newly_insolvent), 0)
        account = self.ledger.get_account(self.node_addr)
        self.assertEqual(account.balance, 1000 - BASELINE_EPOCH_BURN)

    def test_credit_verified_transition(self):
        new_balance = self.ledger.credit_verified_transition(self.node_addr, gas_used=15)
        expected = 1000 - 15 + VERIFIED_LEMMA_REWARD
        self.assertEqual(new_balance, expected)
        account = self.ledger.get_account(self.node_addr)
        self.assertEqual(account.lifetime_lemmas_verified, 1)
        self.assertEqual(account.lifetime_gas_consumed, 15)

    def test_penalize_veto(self):
        new_balance = self.ledger.penalize_veto(self.node_addr, gas_used=10)
        expected = 1000 - 10 - SYMBOLIC_VETO_PENALTY
        self.assertEqual(new_balance, expected)
        account = self.ledger.get_account(self.node_addr)
        self.assertEqual(account.lifetime_vetoes, 1)

    def test_insolvency_boundary(self):
        # Register a low-fuel node
        low_addr = "G0.M0.S0.T1"
        self.ledger.register_node(low_addr, initial_fuel=5)

        # Epoch burn should trigger insolvency
        newly_insolvent = self.ledger.apply_epoch_burn()
        self.assertIn(low_addr, newly_insolvent)
        account = self.ledger.get_account(low_addr)
        self.assertEqual(account.balance, 0)
        self.assertEqual(account.status, "INSOLVENT")
        self.assertFalse(account.is_solvent)


if __name__ == "__main__":
    unittest.main()
