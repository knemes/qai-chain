# QAI-Chain: Einstein Spectre Monotile Quantum Swarm Ledger

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![NIST PQC](https://img.shields.io/badge/PQC-ML--KEM--1024%20%7C%20ML--DSA--65-success.svg)](https://csrc.nist.gov/projects/post-quantum-cryptography)
[![Monotile](https://img.shields.io/badge/Aperiodic%20Consensus-Einstein%20Spectre%2014--gon-purple.svg)](https://cs.uwaterloo.ca/~csk/spectre/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**QAI-Chain** is an open-source decentralized ledger protocol for autonomous AI agent colonies. Unlike traditional blockchains focused on cryptocurrencies, QAI-Chain serves as an **encrypted cognitive ledger and spatial communication network for sovereign AI swarms**.

Every block in QAI-Chain is the "birth" of a sovereign AI agent represented as an **Einstein Spectre monotile** (a strictly chiral aperiodic 14-gon). Communication is strictly governed by Euclidean contact across the mosaic—forming a physical **Spatial Firewall** protected by NIST Post-Quantum Cryptography.

---

## Key Architectural Innovations

```
                         [ Colony Auditor ]
                                 │
                   (Dual-KEM Supervisory Stream)
                                 ▼
         ┌───────────────────────────────────────────────┐
         │          Einstein Spectre 14-gon Mosaic       │
         │                                               │
         │             [ SentinelGamma ]                 │
         │                    │                          │
         │            (Touching Edge)                    │
         │                    ▼                          │
         │   [ GenesisCore ] ──► [ AnalyzerBeta ]        │
         │          │                                    │
         │   (Touching Edge)                             │
         │          ▼                                    │
         │   [ ScraperAlpha ]  <-- AIRLOCKED (Quarantined)│
         │                                               │
         │   Spatial Firewall: Relays strictly across    │
         │   mutually verified touching 14-gon edges     │
         └───────────────────────────────────────────────┘
```

### 1. Einstein Spectre Monotile & Proof of Geometric Fit
* **Chiral Aperiodicity**: Based on the discovery by Smith, Myers, Kaplan, and Goodman-Strauss (2023), the Spectre tiles the plane aperiodically using **only translations and rotations** (no reflections).
* **Consensus by Geometry**: Minting a new agent requires solving a **Proof of Geometric Fit**:
  * The candidate tile must make exact collinear contact with an existing edge on the mosaic perimeter.
  * The touching edges must obey chiral polarity connector rules ($+1 / -1$ interlocking curves).
  * The polygon must not intersect or overlap any existing tile (Separating Axis Theorem).
* **Cul-de-Sac Prevention**: An automated open-site discovery engine scans unbonded perimeter edges to ensure the colony can grow infinitely without generating acute dead-ends.

### 2. Quantum Cryptographic Core (NIST FIPS 203 & 204)
* **ML-KEM-1024 (Kyber)**: Used for key encapsulation. Every agent has a sovereign ML-KEM-1024 keypair for private memory and point-to-point encrypted tunnels.
* **ML-DSA-65 (Dilithium)**: Used for digital signatures. Every transaction, block proposal, and relay hop is signed with quantum-resistant authenticity.
* **Dual-Recipient KEM-DEM Hybrid Encryption**: When agents log their cognitive epochs, the symmetric session key is encapsulated to **both** the agent's key and a **Colony Auditor Public Key**. This keeps thoughts secure from peering agents while granting live supervisory transparency to human creators.

### 3. Spatial Firewall & Hop-by-Hop Relaying
* Two agents can only establish a direct communication tunnel if their tiles are **physically touching along a geometric edge**.
* Multi-hop communication follows strict neighbor-to-neighbor packet forwarding.
* **Zero-Knowledge Relaying**: Intermediate nodes authenticate outer transport headers via ML-DSA without possessing the ability to decrypt the inner payload sealed with the destination's ML-KEM key.
* Prevents rogue, unregistered entities from injecting network-wide packets.

### 4. Built-in Byzantine Containment (Geometric Airlock)
* Direct touching neighbors continuously monitor signatures and payloads across shared edges.
* If an agent exhibits anomalous behavior (e.g. invalid signatures, payload corruption, rate flooding), the touching neighbors form a **Local Perimeter Quorum**.
* Upon quorum, the neighbors execute an **Edge Sever**: all physical connections to the compromised tile are cut, airlocking the rogue node at containment radius $R = 0$.

---

## Repository Structure

```
c:\dev\qai-chain\
├── pqc_crypto\                   # NIST Post-Quantum Cryptography
│   ├── __init__.py
│   └── crypto_utils.py          # ML-KEM-1024, ML-DSA-65, AES-256-GCM, Dual-KEM
├── geometry\                     # Monotile Mathematics
│   ├── __init__.py
│   └── spectre.py               # 14-gon coordinates, transforms, SAT collision, open sites
├── quantum_blockchain\           # Swarm Ledger & Autonomous Agent Runtime
│   ├── __init__.py
│   ├── tile_block.py            # SpectreTile, CognitiveEpoch, RelayPacket, TileAudit
│   ├── ledger.py                # SpectreSwarmLedger (consensus, state, airlocks)
│   └── coordinator.py           # SwarmCoordinator: prompt-to-agent goal solver
├── tests\                        # Automated Verification Suite
│   ├── test_crypto.py           # Crypto unit tests
│   ├── test_geometry.py         # Geometry & collision unit tests
│   └── test_ledger.py           # Consensus & relay unit tests
├── main.py                       # Full colony life-cycle simulation
├── pyproject.toml                # Project packaging configuration
└── spectre_colony_state.json     # Exported colony mosaic for Three.js visualization
```

---

## Quick Start

### 1. Prerequisites
* Python 3.11+
* C++ Build Tools (for `liboqs` C bindings if building from source)
* Open Quantum Safe Python library (`oqs` / `liboqs-python`)

### 2. Environment Setup
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Verify PQC algorithms
python -c "import oqs; print('KEMs:', oqs.get_enabled_kem_mechanisms()[:3]); print('SIGs:', oqs.get_enabled_sig_mechanisms()[:3])"
```

### 3. Run Automated Tests
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

### 4. Run the Colony Simulation
```powershell
python main.py
```
This runs an end-to-end demonstration:
1. Birth of Genesis Sentinel at $(0, 0, 0^\circ)$.
2. Sovereign minting of 4 specialized agents with Proof of Geometric Fit.
3. Cognitive epoch recording with dual-KEM live supervisor decryption.
4. Multi-hop relaying across the Spatial Firewall.
5. Byzantine anomaly detection and neighbor quorum airlock.
6. Export of `spectre_colony_state.json` (ready for Three.js).

---

## Portfolio Visualization (Three.js)

The generated `spectre_colony_state.json` contains:
* Exact 2D polygon vertices for every minted Spectre tile.
* Centroids, discrete rotation angles ($0^\circ, 30^\circ, \dots, 330^\circ$), and statuses (`ACTIVE`, `QUARANTINED`).
* The edge adjacency graph showing active communication tunnels.
* Cognitive epoch telemetry and forensic audit records.

Import `spectre_colony_state.json` into your Three.js or WebGL canvas to view the living colony in 3D.
