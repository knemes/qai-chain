"""
Unit tests for the SpectreVM 32 KB Deterministic Stack Machine.
"""

import unittest
from engine.spectre_vm import SpectreVM, Opcode


class TestSpectreVM(unittest.TestCase):

    def setUp(self):
        self.vm = SpectreVM()

    def test_stack_operations(self):
        # Push 10, Push 20, Swap -> (20, 10), Dup -> (20, 10, 10), Add -> (20, 20), Eq -> 1
        bytecode = [
            (Opcode.PUSH, 10),
            (Opcode.PUSH, 20),
            Opcode.SWAP,
            Opcode.DUP,
            Opcode.ADD,
            (Opcode.PUSH, 20),
            Opcode.EQ,
            Opcode.ASSERT,
            Opcode.HALT_PASS
        ]
        res = self.vm.execute(bytecode)
        self.assertTrue(res.is_verified)
        self.assertIsNone(res.error)
        self.assertEqual(res.gas_used, 9)

    def test_arithmetic_and_bitwise(self):
        # ((5 * 6) - 10) / 4 = (30 - 10) / 4 = 20 / 4 = 5
        bytecode = [
            (Opcode.PUSH, 5),
            (Opcode.PUSH, 6),
            Opcode.MUL,
            (Opcode.PUSH, 10),
            Opcode.SUB,
            (Opcode.PUSH, 4),
            Opcode.DIV,
            (Opcode.PUSH, 5),
            Opcode.EQ,
            Opcode.ASSERT,
            (Opcode.PUSH, 5),
            Opcode.EMIT_LEMMA,
            Opcode.HALT_PASS
        ]
        res = self.vm.execute(bytecode)
        self.assertTrue(res.is_verified)
        self.assertEqual(res.emitted_lemmas, [5])

    def test_assertion_failure_veto(self):
        # Assert 0 fails immediately
        bytecode = [
            (Opcode.PUSH, 0),
            Opcode.ASSERT,
            Opcode.HALT_PASS
        ]
        res = self.vm.execute(bytecode)
        self.assertFalse(res.is_verified)
        self.assertIn("ERR_ASSERTION_FAILED", res.error)

    def test_assert_range_verification(self):
        # Value 42 in range [10, 100] passes
        bytecode_pass = [
            (Opcode.PUSH, 42),
            (Opcode.PUSH, 10),
            (Opcode.PUSH, 100),
            Opcode.ASSERT_RANGE,
            Opcode.HALT_PASS
        ]
        res = self.vm.execute(bytecode_pass)
        self.assertTrue(res.is_verified)

        # Value 5 in range [10, 100] fails
        bytecode_fail = [
            (Opcode.PUSH, 5),
            (Opcode.PUSH, 10),
            (Opcode.PUSH, 100),
            Opcode.ASSERT_RANGE,
            Opcode.HALT_PASS
        ]
        res_fail = self.vm.execute(bytecode_fail)
        self.assertFalse(res_fail.is_verified)
        self.assertIn("ERR_RANGE_VIOLATION", res_fail.error)

    def test_gas_exhaustion_ceiling(self):
        # Exceeding 500 instructions triggers gas exhaustion
        long_bytecode = [(Opcode.PUSH, 1)] * 505
        res = self.vm.execute(long_bytecode)
        self.assertFalse(res.is_verified)
        self.assertIn("ERR_GAS_EXHAUSTION", res.error)
        self.assertEqual(res.gas_used, 501)

    def test_division_by_zero_veto(self):
        bytecode = [
            (Opcode.PUSH, 10),
            (Opcode.PUSH, 0),
            Opcode.DIV,
            Opcode.HALT_PASS
        ]
        res = self.vm.execute(bytecode)
        self.assertFalse(res.is_verified)
        self.assertIn("ERR_DIVISION_BY_ZERO", res.error)


if __name__ == "__main__":
    unittest.main()
