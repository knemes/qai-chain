#!/usr/bin/env python3
"""
Test Prompt-Driven Goal Solving & Swarm Adaptation
--------------------------------------------------
Demonstrates submitting prompts to the Spectre Swarm Colony:
- The swarm analyzes the prompt.
- Dynamically mints missing specialist agents on valid open perimeter edges (Proof of Geometric Fit).
- Routes encrypted directives hop-by-hop across touching edges (Spatial Firewall).
- Logs dual-encrypted Cognitive Epochs.
- Re-runs with a second prompt to demonstrate reusing existing agents without redundant births.
"""

import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from quantum_blockchain.coordinator import SwarmCoordinator


def print_section(title: str):
    print(f"\n{'=' * 75}\n  {title}\n{'=' * 75}")


def main():
    print_section("QAI-CHAIN: PROMPT-DRIVEN SWARM ADAPTATION TEST")
    coordinator = SwarmCoordinator()
    print(f"[*] Swarm initialized with Root Agent: [{coordinator.genesis_agent.tile.agent_alias}]")
    print(f"    Initial Tile Count: {len(coordinator.ledger.tiles)}")

    # Prompt 1: Requires Cryptography & Threat Analysis
    prompt_1 = "Evaluate quantum vulnerability of lattice signature ML-DSA against fault-injection attacks."
    print_section(f"PROMPT 1: \"{prompt_1}\"")
    
    result_1 = coordinator.dispatch_goal(prompt_1)
    
    print("[*] Adaptation & Minting Log:")
    for log in result_1["adaptation_log"]:
        print(f"    {log}")

    print("\n[*] Spatial Firewall Routing:")
    for r in result_1["routes"]:
        print(f"    {r}")

    print(f"\n[*] Cognitive Epochs Recorded: {len(result_1['epochs_logged'])}")
    print(f"[*] Total Spectre Tiles Now   : {result_1['total_tiles_now']}")
    print(f"\n[+] Final Swarm Answer:\n{result_1['final_answer']}")

    # Prompt 2: Ask a related question -> verify swarm REUSES existing agents rather than unnecessarily minting duplicates!
    prompt_2 = "Audit recent threat bulletins for lattice key encapsulation side-channel leaks."
    print_section(f"PROMPT 2 (REUSE TEST): \"{prompt_2}\"")

    result_2 = coordinator.dispatch_goal(prompt_2)

    print("[*] Adaptation & Minting Log:")
    for log in result_2["adaptation_log"]:
        print(f"    {log}")

    print("\n[*] Spatial Firewall Routing:")
    for r in result_2["routes"]:
        print(f"    {r}")

    print(f"\n[*] Total Spectre Tiles Now: {result_2['total_tiles_now']}")
    print(f"[+] Final Swarm Answer:\n{result_2['final_answer']}")

    # Save ledger state
    coordinator.ledger.save_to_file("spectre_ledger_data.json")
    coordinator.ledger.export_colony_state("spectre_colony_state.json")
    print_section("TEST COMPLETED & LEDGER PERSISTED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
