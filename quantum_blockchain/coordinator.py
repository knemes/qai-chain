import time
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple

from geometry.spectre import find_valid_open_sites
from pqc_crypto.crypto_utils import (
    generate_kem_keypair,
    generate_dsa_keypair,
    encrypt_envelope,
    decrypt_envelope,
)
from .ledger import SpectreSwarmLedger
from .tile_block import SpectreTile, CognitiveEpoch, RelayPacket, TileStatus
from .llm_client import GeminiLLMClient


class AgentRuntime:
    """
    Active runtime instance representing an autonomous AI agent occupying a Spectre Tile.
    Executes reasoning using its specialized LLM system instruction and logs dual-encrypted epochs.
    """

    def __init__(
        self,
        tile: SpectreTile,
        kem_sk: bytes,
        dsa_sk: bytes,
        specialization: str = "GENERAL_INTELLIGENCE",
        system_prompt: str = "",
        llm_client: Optional[GeminiLLMClient] = None,
    ):
        self.tile = tile
        self.kem_sk = kem_sk
        self.dsa_sk = dsa_sk
        self.specialization = specialization
        self.system_prompt = system_prompt
        self.llm_client = llm_client or GeminiLLMClient()

    def reason_and_record(
        self,
        ledger: SpectreSwarmLedger,
        directive_prompt: str,
    ) -> Tuple[str, CognitiveEpoch]:
        """
        Executes reasoning using the agent's LLM system instructions,
        then commits a dual-encrypted cognitive epoch to the ledger.
        """
        # Execute specialized inference
        llm_output = self.llm_client.generate_response(
            user_prompt=directive_prompt,
            system_instruction=self.system_prompt,
        )

        thought_dict = {
            "agent_alias": self.tile.agent_alias,
            "specialization": self.specialization,
            "directive_prompt": directive_prompt,
            "reasoning": llm_output,
            "timestamp": time.time(),
        }
        thought_bytes = json.dumps(thought_dict).encode("utf-8")

        epoch = ledger.record_cognitive_epoch(
            agent_tile_id=self.tile.tile_id,
            thought_payload=thought_bytes,
            agent_kem_pk=self.tile.ml_kem_public_key,
            agent_dsa_sk=self.dsa_sk,
        )
        return llm_output, epoch


class SwarmCoordinator:
    """
    Orchestrates swarm goal solving, dynamic Gemini agent decomposition,
    reuse of existing agents, autonomous gapless minting into Neighborhoods,
    and hop-by-hop spatial routing across the Einstein Spectre ledger.
    """

    def __init__(
        self,
        ledger: Optional[SpectreSwarmLedger] = None,
        llm_client: Optional[GeminiLLMClient] = None,
    ):
        self.ledger = ledger or SpectreSwarmLedger()
        self.llm_client = llm_client or GeminiLLMClient()
        self.agents: Dict[str, AgentRuntime] = {}

        # If ledger is empty, initialize Genesis agent
        if not self.ledger.tiles:
            genesis_sys = "Colony Root Orchestrator: Deconstructs user goals, coordinates specialist consensus, and maintains mosaic harmony."
            genesis_tile, g_kpk, g_ksk, g_dpk, g_dsk = self.ledger.create_genesis_agent(
                alias="GenesisCore",
                system_prompt=genesis_sys,
            )
            self.agents[genesis_tile.tile_id] = AgentRuntime(
                tile=genesis_tile,
                kem_sk=g_ksk,
                dsa_sk=g_dsk,
                specialization="ROOT_ORCHESTRATOR",
                system_prompt=genesis_sys,
                llm_client=self.llm_client,
            )

    @property
    def genesis_agent(self) -> AgentRuntime:
        genesis_tile = self.ledger.tiles[0]
        return self.agents[genesis_tile.tile_id]

    def _get_existing_agent_pool(self) -> List[Dict[str, str]]:
        return [
            {
                "tile_id": a.tile.tile_id,
                "alias": a.tile.agent_alias,
                "specialization": a.specialization,
            }
            for a in self.agents.values()
            if a.tile.status == TileStatus.ACTIVE
        ]

    def _find_or_mint_specialist(
        self,
        alias: str,
        specialization: str,
        system_prompt: str,
        reuse_agent_id: Optional[str] = None,
    ) -> Tuple[AgentRuntime, bool]:
        """
        Reuses an existing active agent if its specialization matches.
        Only mints a new sovereign Spectre tile if no matching agent exists.
        Returns (agent_runtime, was_minted).
        """
        # 1. Check direct reuse_agent_id
        if reuse_agent_id and reuse_agent_id in self.agents:
            agent = self.agents[reuse_agent_id]
            if agent.tile.status == TileStatus.ACTIVE:
                return agent, False

        # 2. Check all active agents by specialization or alias
        for agent in self.agents.values():
            if agent.tile.status != TileStatus.ACTIVE:
                continue
            if agent.specialization == specialization or agent.tile.agent_alias == alias:
                return agent, False

        # 3. Mint a new sovereign Spectre tile into the next gapless Neighborhood slot
        open_sites = find_valid_open_sites(self.ledger.spatial_mosaic, max_sites=6)
        if not open_sites:
            raise RuntimeError("Colony mosaic perimeter is blocked; no open sites available.")

        target_site = open_sites[0]
        kem_pk, kem_sk = generate_kem_keypair()
        dsa_pk, dsa_sk = generate_dsa_keypair()

        ok, msg, new_tile = self.ledger.mint_agent(
            alias=alias,
            transform=target_site.transform,
            system_prompt=system_prompt,
            kem_pk=kem_pk,
            dsa_pk=dsa_pk,
            proposer_dsa_sk=dsa_sk,
        )
        if not ok or not new_tile:
            raise RuntimeError(f"Failed to mint new agent [{alias}]: {msg}")

        runtime = AgentRuntime(
            tile=new_tile,
            kem_sk=kem_sk,
            dsa_sk=dsa_sk,
            specialization=specialization,
            system_prompt=system_prompt,
            llm_client=self.llm_client,
        )
        self.agents[new_tile.tile_id] = runtime
        return runtime, True

    def _find_hop_path(self, start_id: str, end_id: str) -> Optional[List[str]]:
        """Breadth-first search finding shortest hop path across physically touching edges."""
        if start_id == end_id:
            return [start_id]

        queue = [[start_id]]
        visited = {start_id}

        while queue:
            path = queue.pop(0)
            node_id = path[-1]
            node_tile = self.ledger.tiles_by_id.get(node_id)
            if not node_tile or node_tile.status == TileStatus.QUARANTINED:
                continue

            for conn in node_tile.edge_connections.values():
                nbr_id = conn["neighbor_tile_id"]
                nbr_tile = self.ledger.tiles_by_id.get(nbr_id)
                if not nbr_tile or nbr_tile.status == TileStatus.QUARANTINED:
                    continue

                if nbr_id == end_id:
                    return path + [nbr_id]

                if nbr_id not in visited:
                    visited.add(nbr_id)
                    queue.append(path + [nbr_id])
        return None

    def dispatch_goal(self, goal_prompt: str) -> Dict[str, Any]:
        """
        Dispatches a user goal to the swarm:
        1. Decomposes goal into required specialist domains using Gemini.
        2. Reuses existing active agents; mints new ones only when necessary into gapless Neighborhoods.
        3. Routes subtasks across the Spatial Firewall using ML-KEM sealed envelopes.
        4. Executes LLM reasoning per agent persona and logs dual-encrypted cognitive epochs.
        5. Synthesizes and delivers the collective answer.
        """
        adaptation_log: List[str] = []
        epochs_logged: List[str] = []
        routing_logs: List[str] = []
        intermediate_findings: List[str] = []

        genesis = self.genesis_agent

        # 1. Root Orchestrator Inception Epoch
        genesis_reasoning, root_epoch = genesis.reason_and_record(
            self.ledger,
            f"Ingest user prompt: '{goal_prompt}'. Decompose into specialist agent tasks."
        )
        epochs_logged.append(root_epoch.epoch_hash)

        # 2. Dynamic Goal Decomposition
        existing_pool = self._get_existing_agent_pool()
        subtasks = self.llm_client.decompose_goal(goal_prompt, existing_pool)
        adaptation_log.append(f"Decomposed goal into {len(subtasks)} specialized agent tasks.")

        # 3. Execute Subtasks
        for subtask in subtasks:
            alias = subtask["alias"]
            spec = subtask["specialization"]
            sys_prompt = subtask["system_prompt"]
            directive = subtask["subtask_directive"]
            reuse_id = subtask.get("reuse_agent_id")

            specialist, was_minted = self._find_or_mint_specialist(
                alias=alias,
                specialization=spec,
                system_prompt=sys_prompt,
                reuse_agent_id=reuse_id,
            )

            if was_minted:
                adaptation_log.append(
                    f"MINTED new sovereign agent [{alias}] (Block #{specialist.tile.index}, "
                    f"Neighborhood-{specialist.tile.neighborhood_index} Slot {specialist.tile.neighborhood_slot}) "
                    f"for role [{spec}]."
                )
            else:
                adaptation_log.append(
                    f"REUSED existing agent [{alias}] (Block #{specialist.tile.index}, "
                    f"Neighborhood-{specialist.tile.neighborhood_index}) for role [{spec}]."
                )

            # Route subtask from Genesis -> Specialist across Spatial Firewall
            hop_path = self._find_hop_path(genesis.tile.tile_id, specialist.tile.tile_id)
            if not hop_path:
                hop_path = [genesis.tile.tile_id, specialist.tile.tile_id]

            task_payload = f"TASK_DIRECTIVE: [{directive}] under goal: {goal_prompt}"
            sealed_envelope = encrypt_envelope(task_payload.encode(), specialist.tile.ml_kem_public_key)

            packet = RelayPacket(
                source_tile_id=genesis.tile.tile_id,
                destination_tile_id=specialist.tile.tile_id,
                hop_path=hop_path,
                encrypted_payload_envelope=sealed_envelope,
            )

            # Route across spatial hops
            for i in range(len(hop_path) - 1):
                sender_id = hop_path[i]
                sender_runtime = self.agents.get(sender_id)
                if sender_runtime:
                    self.ledger.route_relay_packet(packet, sender_runtime.dsa_sk)

            path_aliases = [
                self.agents[tid].tile.agent_alias for tid in hop_path if tid in self.agents
            ]
            routing_logs.append(f"Spatial Firewall Route: {' -> '.join(path_aliases)}")

            # Specialist executes reasoning with its persona
            reasoning_output, epoch = specialist.reason_and_record(
                self.ledger,
                directive,
            )
            epochs_logged.append(epoch.epoch_hash)
            intermediate_findings.append(f"[{alias}] ({spec}):\n{reasoning_output}")

        # 4. Swarm Consensus Synthesis
        synth_agent = next(
            (a for a in self.agents.values() if "Synth" in a.tile.agent_alias and a.tile.status == TileStatus.ACTIVE),
            genesis
        )
        synth_prompt = (
            f"Synthesize the following multi-agent findings into a final consensus response for query: '{goal_prompt}':\n"
            + "\n\n".join(intermediate_findings)
        )
        final_answer, synth_epoch = synth_agent.reason_and_record(
            self.ledger,
            synth_prompt,
        )
        epochs_logged.append(synth_epoch.epoch_hash)

        # Count active neighborhoods
        neighborhood_indices = set(t.neighborhood_index for t in self.ledger.tiles)

        return {
            "prompt": goal_prompt,
            "final_answer": final_answer,
            "adaptation_log": adaptation_log,
            "routes": routing_logs,
            "epochs_logged": epochs_logged,
            "total_tiles_now": len(self.ledger.tiles),
            "total_neighborhoods": len(neighborhood_indices),
        }

