# Copyright 2025 Grzegorz Leśniowski
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Feniks Memory Router - Intelligent routing between local (Qdrant) and global (RAE) storage.

This module implements the Dual-Memory Strategy for synergistic use of:
- Local storage (Qdrant): Fast, project-specific, ephemeral
- Global storage (RAE): Intelligent, cross-project, persistent
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from feniks.adapters.rae_client.enhanced_client import EnhancedRAEClient, create_enhanced_rae_client
from feniks.infra.logging import get_logger

log = get_logger("core.memory.router")


class RoutingStrategy(str, Enum):
    """Memory routing strategies."""

    LOCAL_ONLY = "local"  # Store only in Qdrant
    GLOBAL_ONLY = "global"  # Store only in RAE
    DUAL_WRITE = "dual"  # Store in both (recommended for important data)
    HYBRID = "hybrid"  # Intelligent routing based on data characteristics


@dataclass
class RoutingDecision:
    """Represents a routing decision with reasoning."""

    strategy: RoutingStrategy
    store_local: bool
    store_global: bool
    reason: str
    metadata: Dict[str, Any]


_UNDEFINED = object()


class FeniksMemoryRouter:
    """
    Routes memory operations between local (Qdrant) and global (RAE) storage.

    Implements intelligent routing logic to optimize for:
    - Performance (local for fast retrieval)
    - Learning (global for cross-project insights)
    - Reliability (dual-write for critical data)
    """

    def __init__(
        self,
        qdrant_client: Any,  # QdrantClient instance
        rae_client: Any = _UNDEFINED,
        default_strategy: RoutingStrategy = RoutingStrategy.HYBRID,
        project: str = "default",
    ):
        """
        Initialize memory router.

        Args:
            qdrant_client: Local Qdrant client for fast storage
            rae_client: Enhanced RAE client for global storage (optional)
            default_strategy: Default routing strategy
            project: Project identifier for context
        """
        self.qdrant = qdrant_client
        self.rae = create_enhanced_rae_client() if rae_client is _UNDEFINED else rae_client
        self.default_strategy = default_strategy
        self.project = project

        log.info(f"FeniksMemoryRouter initialized: strategy={default_strategy}, rae_enabled={self.rae is not None}")

    def route_storage(self, data_type: str, metadata: Optional[Dict[str, Any]] = None) -> RoutingDecision:
        """
        Decide where to store data based on type and metadata.

        Routing logic:
        - System models, refactor outcomes → Dual-write (learning value)
        - Meta-reflections with high severity → Dual-write
        - Temporary analysis results → Local only
        - Cross-project patterns → Global only
        - Default → Hybrid (based on metadata)

        Args:
            data_type: Type of data (reflection, refactor, analysis, pattern)
            metadata: Optional metadata for routing decisions

        Returns:
            RoutingDecision: Where to store the data
        """
        metadata = metadata or {}

        # RAE unavailable → Local only
        if not self.rae:
            return RoutingDecision(
                strategy=RoutingStrategy.LOCAL_ONLY,
                store_local=True,
                store_global=False,
                reason="RAE client unavailable, falling back to local storage",
                metadata={"fallback": True},
            )

        # Critical data types → Dual-write
        if data_type in ["system_model", "refactor_outcome", "cross_project_pattern"]:
            return RoutingDecision(
                strategy=RoutingStrategy.DUAL_WRITE,
                store_local=True,
                store_global=True,
                reason=f"{data_type} is critical for learning",
                metadata={"priority": "high"},
            )

        # High severity reflections → Dual-write
        if data_type == "reflection" and metadata.get("severity") in ["high", "critical"]:
            return RoutingDecision(
                strategy=RoutingStrategy.DUAL_WRITE,
                store_local=True,
                store_global=True,
                reason="High severity reflection valuable for cross-project learning",
                metadata={"priority": "high", "severity": metadata.get("severity")},
            )

        # Temporary/ephemeral data → Local only
        if metadata.get("ephemeral") or metadata.get("temporary"):
            return RoutingDecision(
                strategy=RoutingStrategy.LOCAL_ONLY,
                store_local=True,
                store_global=False,
                reason="Ephemeral data doesn't need global persistence",
                metadata={"ttl": metadata.get("ttl", 3600)},
            )

        # Cross-project insights → Global only (avoid local redundancy)
        if metadata.get("cross_project") or data_type == "global_pattern":
            return RoutingDecision(
                strategy=RoutingStrategy.GLOBAL_ONLY,
                store_local=False,
                store_global=True,
                reason="Cross-project data belongs in global storage",
                metadata={"scope": "cross_project"},
            )

        # Default hybrid strategy
        return self._hybrid_routing_decision(data_type, metadata)

    def store(
        self,
        data: Any,
        data_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        collection_name: str = "feniks_memory",
    ) -> Dict[str, Any]:
        """
        Store data with smart routing.

        Args:
            data: Data to store
            data_type: Type of data (reflection, refactor, analysis, pattern)
            metadata: Optional metadata
            collection_name: Qdrant collection name for local storage

        Returns:
            Dict with storage results (local_id, global_id, routing_decision)
        """
        decision = self.route_storage(data_type, metadata)
        result = {"routing_decision": decision, "local_id": None, "global_id": None, "errors": []}

        log.info(f"Storing {data_type}: {decision.reason}")

        # Store locally if decided
        if decision.store_local:
            try:
                local_id = self._store_local(data, data_type, metadata, collection_name)
                result["local_id"] = local_id
                log.debug(f"Stored locally: {local_id}")
            except Exception as e:
                log.error(f"Local storage failed: {e}")
                result["errors"].append(f"Local: {e}")

        # Store globally if decided
        if decision.store_global and self.rae:
            try:
                global_id = self._store_global(data, data_type, metadata)
                result["global_id"] = global_id
                log.debug(f"Stored globally: {global_id}")
            except Exception as e:
                log.error(f"Global storage failed: {e}")
                result["errors"].append(f"Global: {e}")

        return result

    def retrieve(
        self,
        query: str,
        strategy: Literal["local", "global", "hybrid"] = "hybrid",
        top_k: int = 10,
        data_type: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve data with smart strategy.

        Args:
            query: Search query (natural language or vector)
            strategy: Retrieval strategy (local, global, hybrid)
            top_k: Maximum results to return
            data_type: Optional filter by data type
            metadata_filter: Optional metadata filters

        Returns:
            List of search results with scores and sources
        """
        log.info(f"Retrieving data: strategy={strategy}, query='{query[:50]}...'")

        if strategy == "local":
            return self._retrieve_local(query, top_k, data_type, metadata_filter)
        elif strategy == "global":
            return self._retrieve_global(query, top_k, data_type)
        else:  # hybrid
            return self._retrieve_hybrid(query, top_k, data_type, metadata_filter)

    def enrich_with_global_context(self, local_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich local search result with global RAE context.

        Args:
            local_result: Result from local Qdrant search

        Returns:
            Enriched result with RAE insights
        """
        if not self.rae:
            return local_result

        try:
            # Build query from local result
            query = self._build_enrichment_query(local_result)

            # Query RAE for context
            rae_context = self.rae.query_reflections(
                project=self.project, query=query, layer="semantic", top_k=3, min_similarity=0.7
            )

            # Merge context
            enriched = local_result.copy()
            enriched["rae_context"] = rae_context
            enriched["enriched"] = True

            return enriched

        except Exception as e:
            log.warning(f"Failed to enrich with global context: {e}")
            return local_result

    # Private methods

    def _hybrid_routing_decision(self, data_type: str, metadata: Dict[str, Any]) -> RoutingDecision:
        """Intelligent hybrid routing based on data characteristics."""

        # Scoring factors
        learning_value = self._calculate_learning_value(data_type, metadata)
        frequency_score = metadata.get("access_frequency", 0.5)
        scope_score = 1.0 if metadata.get("project_specific") else 0.5

        # Decision logic
        if learning_value > 0.7:
            strategy = RoutingStrategy.DUAL_WRITE
            store_local, store_global = True, True
            reason = f"High learning value ({learning_value:.2f})"
        elif frequency_score > 0.7 and scope_score > 0.7:
            strategy = RoutingStrategy.LOCAL_ONLY
            store_local, store_global = True, False
            reason = "High frequency access to project-specific data"
        else:
            strategy = RoutingStrategy.DUAL_WRITE
            store_local, store_global = True, True
            reason = "Balanced hybrid approach"

        return RoutingDecision(
            strategy=strategy,
            store_local=store_local,
            store_global=store_global,
            reason=reason,
            metadata={"learning_value": learning_value, "frequency_score": frequency_score, "scope_score": scope_score},
        )

    def _calculate_learning_value(self, data_type: str, metadata: Dict[str, Any]) -> float:
        """Calculate learning value score (0.0-1.0) for routing decisions."""
        score = 0.5  # Base score

        # Data type value
        type_values = {
            "reflection": 0.7,
            "refactor_outcome": 0.9,
            "system_model": 0.8,
            "pattern": 0.8,
            "analysis": 0.4,
        }
        score += type_values.get(data_type, 0.5) * 0.3

        # Metadata signals
        if metadata.get("success_rate"):
            score += 0.2
        if metadata.get("cross_project_applicable"):
            score += 0.2
        if metadata.get("severity") in ["high", "critical"]:
            score += 0.1

        return min(score, 1.0)

    def _store_local(self, data: Any, data_type: str, metadata: Optional[Dict], collection_name: str) -> str:
        """Store data in local Qdrant storage."""
        # Implementation depends on Feniks Qdrant adapter
        # This is a placeholder showing the interface
        log.debug(f"Storing in Qdrant: collection={collection_name}, type={data_type}")

        # In real implementation, this would use Feniks' existing Qdrant client
        # For now, return a mock ID
        import uuid

        return f"local_{uuid.uuid4().hex[:8]}"

    def _store_global(self, data: Any, data_type: str, metadata: Optional[Dict]) -> str:
        """Store data in global RAE storage."""
        if not self.rae:
            raise Exception("RAE client not available")

        # Route to appropriate RAE endpoint based on data type
        if data_type == "reflection":
            response = self.rae.store_meta_reflection(self._format_reflection_for_rae(data, metadata))
        elif data_type == "refactor_outcome":
            response = self.rae.store_refactor_outcome(data, metadata or {})
        elif data_type == "system_model":
            response = self.rae.store_system_model(self._format_system_model_for_rae(data, metadata))
        else:
            # Generic storage via semantic memory
            payload = {
                "project": self.project,
                "content": str(data),
                "data_type": data_type,
                "metadata": metadata or {},
            }
            response = self.rae.store_system_capabilities(payload)

        return response.get("id", "unknown")

    def _retrieve_local(
        self, query: str, top_k: int, data_type: Optional[str], metadata_filter: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """Retrieve from local Qdrant storage."""
        log.debug(f"Retrieving from Qdrant: query='{query[:30]}...', top_k={top_k}")

        # Placeholder - real implementation would use Feniks Qdrant adapter
        return []

    def _retrieve_global(self, query: str, top_k: int, data_type: Optional[str]) -> List[Dict[str, Any]]:
        """Retrieve from global RAE storage."""
        if not self.rae:
            return []

        results = self.rae.query_reflections(
            project=self.project, query=query, layer="semantic", top_k=top_k, min_similarity=0.6
        )

        # Format results
        return [{"source": "rae", "score": r.get("similarity_score", 0), "data": r} for r in results]

    def _retrieve_hybrid(
        self, query: str, top_k: int, data_type: Optional[str], metadata_filter: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """Hybrid retrieval combining local and global results."""
        # Get results from both sources
        local_results = self._retrieve_local(query, top_k // 2, data_type, metadata_filter)
        global_results = self._retrieve_global(query, top_k // 2, data_type)

        # Merge and re-rank
        all_results = local_results + global_results
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return all_results[:top_k]

    def _build_enrichment_query(self, result: Dict[str, Any]) -> str:
        """Build query for enrichment from search result."""
        # Extract relevant fields for query
        if "content" in result:
            return str(result["content"])[:200]
        elif "summary" in result:
            return str(result["summary"])
        else:
            return str(result)[:200]

    def _format_reflection_for_rae(self, data: Any, metadata: Optional[Dict]) -> Dict[str, Any]:
        """Format reflection data for RAE storage."""
        return {
            "project": self.project,
            "reflection_id": getattr(data, "reflection_id", "unknown"),
            "content": str(data),
            "metadata": metadata or {},
        }

    def _format_system_model_for_rae(self, data: Any, metadata: Optional[Dict]) -> Dict[str, Any]:
        """Format system model data for RAE storage."""
        return {"project": self.project, "model": data, "metadata": metadata or {}}


def create_memory_router(
    qdrant_client: Any, project: str = "default", strategy: RoutingStrategy = RoutingStrategy.HYBRID
) -> FeniksMemoryRouter:
    """
    Factory function to create memory router with RAE integration.

    Args:
        qdrant_client: Local Qdrant client instance
        project: Project identifier
        strategy: Default routing strategy

    Returns:
        FeniksMemoryRouter: Configured memory router
    """
    rae_client = create_enhanced_rae_client()

    router = FeniksMemoryRouter(
        qdrant_client=qdrant_client, rae_client=rae_client, default_strategy=strategy, project=project
    )

    log.info(f"Memory router created: project={project}, strategy={strategy}")
    return router
