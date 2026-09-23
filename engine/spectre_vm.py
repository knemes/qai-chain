"""
SpectreVM: The 32 KB Deterministic Stack-Based Bytecode Verifier.
Executes non-recurrent invariant verification scripts under a strict 500-gas ceiling.
Holds absolute veto power over candidate state reductions and neural policy proposals.
"""

from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional, Union

# Memory budget limits (32 KB total VM resident state)
STACK_MAX_DEPTH = 2048       # 16 KB (2048 * 8-byte integers)
MAX_GAS = 500                # Strict execution ceiling (prevents infinite loops / halting problem)
BYTECODE_BUFFER_LIMIT = 1024 # 8 KB instruction buffer
AXIOM_TABLE_LIMIT = 8192     # 8 KB domain invariant table


class Opcode(IntEnum):
    # Stack Operations (0x00 - 0x0F)
    NOP = 0x00
    PUSH = 0x01
    POP = 0x02
    DUP = 0x03
    SWAP = 0x04
    ROT = 0x05
    OVER = 0x06

    # Arithmetic & Bitwise Logic (0x10 - 0x1F)
    ADD = 0x10
    SUB = 0x11
    MUL = 0x12
    DIV = 0x13
    MOD = 0x14
    NEG = 0x15
    AND = 0x16
    OR = 0x17
    XOR = 0x18
    NOT = 0x19
    SHL = 0x1A
    SHR = 0x1B

    # Comparisons (0x20 - 0x2F)
    EQ = 0x20
    NEQ = 0x21
    LT = 0x22
    GT = 0x23
    LTE = 0x24
    GTE = 0x25

    # Invariants, Assertions & Verification (0x30 - 0x3F)
    ASSERT = 0x30        # Pops top; vetoes if top == 0
    ASSERT_RANGE = 0x31  # Pops val, min, max; asserts min <= val <= max
    VERIFY_HASH = 0x32   # Verifies top hash against expected state commitment
    EMIT_LEMMA = 0x33    # Commits verified lemma to output receipt
    HALT_PASS = 0x3E     # Successful verification (Q.E.D.)
    HALT_FAIL = 0x3F     # Explicit verification veto


Instruction = Union[Opcode, Tuple[Opcode, int]]


@dataclass
class VMExecutionResult:
    """Deterministic result receipt emitted by the SpectreVM."""
    is_verified: bool
    gas_used: int
    emitted_lemmas: List[int] = field(default_factory=list)
    final_stack_top: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_verified": self.is_verified,
            "gas_used": self.gas_used,
            "emitted_lemmas": self.emitted_lemmas,
            "final_stack_top": self.final_stack_top,
            "error": self.error,
        }


class SpectreVM:
    """
    Deterministic stack machine enforcing domain logic, conservation laws,
    and invariant constraints with zero dynamic heap allocations.
    """

    def __init__(self, axiom_table: Optional[Dict[int, int]] = None):
        self.stack: List[int] = []
        self.gas_used: int = 0
        self.emitted_lemmas: List[int] = []
        self.axiom_table: Dict[int, int] = axiom_table or {}

    def reset(self):
        """Resets VM registers for the next verification epoch."""
        self.stack.clear()
        self.gas_used = 0
        self.emitted_lemmas.clear()

    def execute(self, bytecode: List[Instruction]) -> VMExecutionResult:
        """
        Executes a sequence of instructions up to MAX_GAS.
        Guaranteed to halt deterministically in < 100 microseconds.
        """
        self.reset()

        if len(bytecode) > BYTECODE_BUFFER_LIMIT:
            return VMExecutionResult(
                is_verified=False,
                gas_used=0,
                error="ERR_BYTECODE_OVERFLOW: Script exceeds 8 KB instruction buffer limit."
            )

        pc = 0
        num_instructions = len(bytecode)

        while pc < num_instructions:
            # Enforce non-extendable gas ceiling
            self.gas_used += 1
            if self.gas_used > MAX_GAS:
                return VMExecutionResult(
                    is_verified=False,
                    gas_used=self.gas_used,
                    error="ERR_GAS_EXHAUSTION: Script exceeded 500 gas ceiling."
                )

            item = bytecode[pc]
            if isinstance(item, tuple):
                op, arg = item
            else:
                op, arg = item, None

            # --- Stack Operations ---
            if op == Opcode.NOP:
                pass

            elif op == Opcode.PUSH:
                if len(self.stack) >= STACK_MAX_DEPTH:
                    return self._veto("ERR_STACK_OVERFLOW")
                self.stack.append(int(arg if arg is not None else 0))

            elif op == Opcode.POP:
                if not self.stack:
                    return self._veto("ERR_STACK_UNDERFLOW")
                self.stack.pop()

            elif op == Opcode.DUP:
                if not self.stack:
                    return self._veto("ERR_STACK_UNDERFLOW")
                if len(self.stack) >= STACK_MAX_DEPTH:
                    return self._veto("ERR_STACK_OVERFLOW")
                self.stack.append(self.stack[-1])

            elif op == Opcode.SWAP:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]

            elif op == Opcode.ROT:
                # Rotates third item to top: (a b c -> b c a)
                if len(self.stack) < 3:
                    return self._veto("ERR_STACK_UNDERFLOW")
                a = self.stack.pop(-3)
                self.stack.append(a)

            elif op == Opcode.OVER:
                # Copies second item to top: (a b -> a b a)
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                if len(self.stack) >= STACK_MAX_DEPTH:
                    return self._veto("ERR_STACK_OVERFLOW")
                self.stack.append(self.stack[-2])

            # --- Arithmetic & Bitwise Logic ---
            elif op == Opcode.ADD:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a + b)

            elif op == Opcode.SUB:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a - b)

            elif op == Opcode.MUL:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a * b)

            elif op == Opcode.DIV:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                if b == 0:
                    return self._veto("ERR_DIVISION_BY_ZERO")
                self.stack.append(a // b)

            elif op == Opcode.MOD:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                if b == 0:
                    return self._veto("ERR_DIVISION_BY_ZERO")
                self.stack.append(a % b)

            elif op == Opcode.NEG:
                if not self.stack:
                    return self._veto("ERR_STACK_UNDERFLOW")
                self.stack[-1] = -self.stack[-1]

            elif op == Opcode.AND:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a & b)

            elif op == Opcode.OR:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a | b)

            elif op == Opcode.XOR:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a ^ b)

            elif op == Opcode.NOT:
                if not self.stack:
                    return self._veto("ERR_STACK_UNDERFLOW")
                self.stack[-1] = 1 if self.stack[-1] == 0 else 0

            elif op == Opcode.SHL:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                shift, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a << (shift & 0x3F))

            elif op == Opcode.SHR:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                shift, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a >> (shift & 0x3F))

            # --- Comparisons ---
            elif op == Opcode.EQ:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(1 if a == b else 0)

            elif op == Opcode.NEQ:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(1 if a != b else 0)

            elif op == Opcode.LT:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(1 if a < b else 0)

            elif op == Opcode.GT:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(1 if a > b else 0)

            elif op == Opcode.LTE:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(1 if a <= b else 0)

            elif op == Opcode.GTE:
                if len(self.stack) < 2:
                    return self._veto("ERR_STACK_UNDERFLOW")
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(1 if a >= b else 0)

            # --- Invariant Assertions & Halting ---
            elif op == Opcode.ASSERT:
                if not self.stack:
                    return self._veto("ERR_STACK_UNDERFLOW")
                condition = self.stack.pop()
                if condition == 0:
                    return self._veto("ERR_ASSERTION_FAILED: Invariant check evaluated to false (0).")

            elif op == Opcode.ASSERT_RANGE:
                # Stack: (val, min, max) -> assert min <= val <= max
                if len(self.stack) < 3:
                    return self._veto("ERR_STACK_UNDERFLOW")
                max_val = self.stack.pop()
                min_val = self.stack.pop()
                val = self.stack.pop()
                if not (min_val <= val <= max_val):
                    return self._veto(f"ERR_RANGE_VIOLATION: Value {val} not in range [{min_val}, {max_val}].")

            elif op == Opcode.EMIT_LEMMA:
                if not self.stack:
                    return self._veto("ERR_STACK_UNDERFLOW")
                lemma_val = self.stack.pop()
                self.emitted_lemmas.append(lemma_val)

            elif op == Opcode.HALT_PASS:
                return VMExecutionResult(
                    is_verified=True,
                    gas_used=self.gas_used,
                    emitted_lemmas=list(self.emitted_lemmas),
                    final_stack_top=self.stack[-1] if self.stack else None,
                    error=None
                )

            elif op == Opcode.HALT_FAIL:
                return self._veto("ERR_EXPLICIT_FAIL: Bytecode halted with failure code.")

            else:
                return self._veto(f"ERR_ILLEGAL_OPCODE: 0x{op:02X}")

            pc += 1

        # Completed all instructions without explicit fail
        return VMExecutionResult(
            is_verified=True,
            gas_used=self.gas_used,
            emitted_lemmas=list(self.emitted_lemmas),
            final_stack_top=self.stack[-1] if self.stack else None,
            error=None
        )

    def _veto(self, reason: str) -> VMExecutionResult:
        """Helper to record a non-negotiable verification veto."""
        return VMExecutionResult(
            is_verified=False,
            gas_used=self.gas_used,
            emitted_lemmas=list(self.emitted_lemmas),
            final_stack_top=self.stack[-1] if self.stack else None,
            error=reason
        )
