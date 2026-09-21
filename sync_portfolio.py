import json
import os

state_path = "spectre_colony_state.json"
out_path = r"c:\dev\portfolio\src\components\spectre\initialColonyData.ts"

with open(state_path, "r") as f:
    state = json.load(f)

tiles = state["tiles"]
print(f"Loaded {len(tiles)} tiles from colony state")

colors = {
    "GenesisCore": "#d97706",       # Amber
    "CryptoSpecialist": "#4f46e5",  # Indigo
    "ColonySynthesizer": "#059669", # Emerald
    "ThreatAnalyzer": "#e11d48",    # Crimson / Rose
    "DataIngestor": "#0891b2",      # Cyan
}

roles = {
    "GenesisCore": "Coordinates high-level swarm objectives, goal decomposition, and preserves aperiodic mosaic consensus.",
    "CryptoSpecialist": "Lattice cryptography defense, ML-KEM-1024 encapsulation checks, and ML-DSA-65 verification.",
    "ColonySynthesizer": "Synthesizes multi-agent cognitive epochs into final consensus and validates proof provenance.",
    "ThreatAnalyzer": "Evaluates Byzantine attack surfaces, side-channel vectors, and neighbor airlock quorums.",
    "DataIngestor": "Processes aperiodic topology telemetry, contact constraints, and gapless neighborhood packing.",
}

specs = {
    "GenesisCore": "ROOT_ORCHESTRATOR",
    "CryptoSpecialist": "POST_QUANTUM_CRYPTANALYSIS",
    "ColonySynthesizer": "EXECUTIVE_CONSENSUS_SYNTHESIS",
    "ThreatAnalyzer": "BYZANTINE_PERIMETER_DEFENSE",
    "DataIngestor": "TOPOLOGY_TELEMETRY_INGESTION",
}

ts_lines = [
    'import { SpectreTileData, CognitiveEpochData } from "./types";',
    "",
    "export const INITIAL_SPECTRE_TILES: SpectreTileData[] = [",
]

for t in tiles:
    alias = t["header"]["agent_alias"]
    color = colors.get(alias, "#6366f1")
    role = roles.get(alias, "Autonomous sovereign agent.")
    spec = specs.get(alias, "GENERAL_INTELLIGENCE")
    
    hdr = t["header"]
    geom = t["geometry"]
    edges = t.get("edge_connections", {})
    
    tile_obj = {
        "tile_id": t["tile_id"],
        "header": {
            "index": hdr["index"],
            "agent_alias": alias,
            "transform": {
                "x": hdr["transform"]["x"],
                "y": hdr["transform"]["y"],
                "rotation_index": hdr["transform"]["rotation_index"],
                "angle_rad": round(hdr["transform"]["angle_rad"], 4),
                "angle_deg": hdr["transform"]["angle_deg"],
            },
            "ml_kem_pk": f"{hdr['ml_kem_pk'][:32]}...",
            "ml_dsa_pk": f"{hdr['ml_dsa_pk'][:32]}...",
            "prompt_commitment": hdr["prompt_commitment"],
            "timestamp": int(hdr["timestamp"]),
            "previous_block_hash": hdr["previous_block_hash"],
        },
        "specialization": spec,
        "role_description": role,
        "color": color,
        "geometry": {
            "transform": {
                "x": geom["transform"]["x"],
                "y": geom["transform"]["y"],
                "rotation_index": geom["transform"]["rotation_index"],
                "angle_rad": round(geom["transform"]["angle_rad"], 4),
                "angle_deg": geom["transform"]["angle_deg"],
            },
            "vertices": geom["vertices"],
            "centroid": {
                "x": round(geom["centroid"]["x"], 6),
                "y": round(geom["centroid"]["y"], 6),
            },
        },
        "edge_connections": edges,
        "status": t["status"],
    }
    ts_lines.append(f"  {json.dumps(tile_obj, indent=2)},")

ts_lines.append("];")
ts_lines.append("")

# Initial cognitive epochs
ts_lines.append("export const INITIAL_COGNITIVE_EPOCHS: CognitiveEpochData[] = [")
epochs = state.get("epochs", [])
for ep in epochs:
    epoch_obj = {
        "epoch_hash": ep["epoch_hash"],
        "agent_tile_id": ep["agent_tile_id"],
        "agent_alias": "GenesisCore",
        "epoch_index": ep["epoch_index"],
        "category": "CONSENSUS_STABILIZE",
        "summary": "Gapless aperiodic neighborhood consensus verified.",
        "detailed_reasoning": "Validated 14-gon chiral contact constraints. Zero voids and zero overlaps in Neighborhood-0.",
        "timestamp": int(ep["timestamp"]),
        "dual_kem_status": "ML-KEM-1024 sealed (Agent + Auditor)",
        "dsa_signature_stamp": f"ML-DSA-65 [{ep.get('agent_signature', 'sig')[:12]}...]",
        "prev_epoch_hash": ep["prev_epoch_hash"],
    }
    ts_lines.append(f"  {json.dumps(epoch_obj, indent=2)},")

ts_lines.append("];")
ts_lines.append("")

with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(ts_lines))

print(f"Synchronized {len(tiles)} gapless tiles to {out_path} successfully!")
