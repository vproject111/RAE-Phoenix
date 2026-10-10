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
Unit tests for Enhanced RAE Client.
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from feniks.adapters.rae_client.client import RAEError
from feniks.adapters.rae_client.enhanced_client import EnhancedRAEClient, create_enhanced_rae_client
from feniks.core.models.types import (
    MetaReflection,
    ReflectionImpact,
    ReflectionLevel,
    ReflectionScope,
)


class TestEnhancedRAEClient:
    """Test Enhanced RAE Client functionality."""

    @pytest.fixture
    def mock_rae_response(self):
        """Mock successful RAE API response."""
        return {"id": "test_id_123", "status": "success", "results": []}

    @pytest.fixture
    def enhanced_client(self):
        """Create Enhanced RAE Client with mocked session."""
        with patch("feniks.adapters.rae_client.client.requests.Session"):
            client = EnhancedRAEClient(base_url="http://localhost:8000", api_key="test-key", tenant_id="test-tenant")
            return client

    @pytest.fixture
    def sample_reflection(self):
        """Create sample MetaReflection for testing."""
        return MetaReflection(
            id="test_refl_001",
            timestamp=datetime.now().isoformat(),
            project="test_project",
            level=ReflectionLevel.REFLECTION,
            scope=ReflectionScope.CODEBASE,
            impact=ReflectionImpact.REFACTOR_RECOMMENDED,
            title="Test Reflection",
            content="Test reflection content about code quality issues",
            recommendations=["Recommendation 1", "Recommendation 2"],
            metadata={"test_key": "test_value", "refactor_type": "extract-method"},
            tags=["test", "code-quality"],
        )

    def test_client_initialization(self, enhanced_client):
        """Test client initializes with correct parameters."""
        assert enhanced_client.base_url == "http://localhost:8000"
        assert enhanced_client.api_key == "test-key"
        assert enhanced_client.tenant_id == "test-tenant"

    def test_query_reflections_success(self, enhanced_client, mock_rae_response):
        """Test querying reflections from RAE."""
        mock_rae_response["results"] = [
            {"id": "refl_1", "content": {"summary": "Result 1"}, "similarity_score": 0.95},
            {"id": "refl_2", "content": {"summary": "Result 2"}, "similarity_score": 0.85},
        ]

        with patch.object(enhanced_client, "_make_request", return_value=mock_rae_response):
            results = enhanced_client.query_reflections(
                project="test_project", query="test query", layer="semantic", top_k=10
            )

            assert len(results) == 2
            assert results[0]["id"] == "refl_1"
            assert results[1]["similarity_score"] == 0.85

    def test_query_reflections_with_filters(self, enhanced_client):
        """Test query reflections with filtering parameters."""
        with patch.object(enhanced_client, "_make_request", return_value={"results": []}) as mock_request:
            enhanced_client.query_reflections(
                project="test_project",
                query="authentication patterns",
                layer="semantic",
                top_k=5,
                min_similarity=0.8,
            )

            # Verify request payload
            call_args = mock_request.call_args
            assert call_args[1]["data"]["query"] == "authentication patterns"
            assert call_args[1]["data"]["top_k"] == 5
            assert call_args[1]["data"]["min_similarity"] == 0.8

    def test_get_cross_project_patterns_success(self, enhanced_client):
        """Test retrieving cross-project patterns."""
        mock_patterns = {
            "results": [
                {
                    "pattern_type": "refactoring",
                    "confidence": 0.85,
                    "project_count": 5,
                    "description": "Extract method pattern",
                },
                {"pattern_type": "architecture", "confidence": 0.92, "project_count": 8, "description": "CQRS pattern"},
            ]
        }

        with patch.object(enhanced_client, "_make_request", return_value=mock_patterns):
            patterns = enhanced_client.get_cross_project_patterns(
                pattern_type="refactoring", min_confidence=0.7, limit=20
            )

            assert len(patterns) == 2
            assert patterns[0]["confidence"] == 0.85
            assert patterns[1]["project_count"] == 8

    def test_get_historical_refactorings_success(self, enhanced_client):
        """Test retrieving historical refactorings."""
        mock_refactorings = {
            "results": [
                {
                    "refactor_type": "extract-method",
                    "success_rate": 0.85,
                    "project": "proj_1",
                    "outcome": {"metrics": {}},
                },
                {
                    "refactor_type": "extract-method",
                    "success_rate": 0.78,
                    "project": "proj_2",
                    "outcome": {"metrics": {}},
                },
            ]
        }

        with patch.object(enhanced_client, "_make_request", return_value=mock_refactorings):
            refactorings = enhanced_client.get_historical_refactorings(
                refactor_type="extract-method", project_tags=["python"], min_success_rate=0.6
            )

            assert len(refactorings) == 2
            assert refactorings[0]["success_rate"] == 0.85

    def test_enrich_reflection_success(self, enhanced_client, sample_reflection):
        """Test enriching reflection with RAE insights."""
        mock_insights = [
            {"id": "insight_1", "content": {"summary": "Similar pattern found"}, "similarity_score": 0.9},
            {"id": "insight_2", "content": {"summary": "Best practice recommendation"}, "similarity_score": 0.85},
        ]

        with patch.object(enhanced_client, "query_reflections", return_value=mock_insights):
            with patch.object(enhanced_client, "get_historical_refactorings", return_value=[]):
                enriched = enhanced_client.enrich_reflection(
                    local_reflection=sample_reflection, context={"project": "test_project"}
                )

                # Check enrichment metadata
                assert enriched.metadata.get("rae_enriched") is True
                assert enriched.metadata.get("rae_insights_count") == 2

                # Check recommendations were added
                assert len(enriched.recommendations) >= len(sample_reflection.recommendations)

    def test_enrich_reflection_with_refactor_insights(self, enhanced_client, sample_reflection):
        """Test enriching reflection includes refactoring insights."""
        mock_refactor_insights = [
            {"pattern_name": "Extract Method Pattern", "success_rate": 0.92, "project_count": 10},
            {"pattern_name": "Inline Method Pattern", "success_rate": 0.78, "project_count": 5},
        ]

        with patch.object(enhanced_client, "query_reflections", return_value=[]):
            with patch.object(enhanced_client, "get_historical_refactorings", return_value=mock_refactor_insights):
                enriched = enhanced_client.enrich_reflection(
                    local_reflection=sample_reflection, context={"project": "test_project"}
                )

                # Check refactor insights were added
                assert enriched.metadata.get("refactor_insights_count") == 2

                # Check historical patterns in recommendations
                has_historical = any("[Historical]" in rec for rec in enriched.recommendations)
                assert has_historical

    def test_enrich_reflection_fallback_on_error(self, enhanced_client, sample_reflection):
        """Test enrichment returns original reflection on error."""
        with patch.object(enhanced_client, "query_reflections", side_effect=RAEError("Connection failed")):
            enriched = enhanced_client.enrich_reflection(
                local_reflection=sample_reflection, context={"project": "test_project"}
            )

            # Should return original reflection unchanged
            assert enriched.id == sample_reflection.id
            assert enriched.metadata.get("rae_enriched") is None

    def test_store_refactor_outcome_success(self, enhanced_client):
        """Test storing refactor outcome for learning."""
        refactor_decision = {
            "refactor_id": "refactor_001",
            "project": "test_project",
            "refactor_type": "extract-method",
        }

        outcome = {"success": True, "metrics": {"complexity_reduction": 30}, "issues": []}

        with patch.object(enhanced_client, "_make_request", return_value={"id": "outcome_001", "status": "success"}):
            result = enhanced_client.store_refactor_outcome(refactor_decision=refactor_decision, outcome=outcome)

            assert result["id"] == "outcome_001"
            assert result["status"] == "success"

    def test_batch_enrich_reflections(self, enhanced_client, sample_reflection):
        """Test batch enrichment of multiple reflections."""
        reflections = [sample_reflection, sample_reflection, sample_reflection]

        with patch.object(enhanced_client, "enrich_reflection", return_value=sample_reflection) as mock_enrich:
            enriched_list = enhanced_client.batch_enrich_reflections(
                reflections=reflections, context={"project": "test_project"}
            )

            assert len(enriched_list) == 3
            assert mock_enrich.call_count == 3

    def test_batch_enrich_handles_partial_failures(self, enhanced_client, sample_reflection):
        """Test batch enrichment continues on individual failures."""
        reflections = [sample_reflection, sample_reflection, sample_reflection]

        # Mock first call succeeds, second fails, third succeeds
        with patch.object(
            enhanced_client,
            "enrich_reflection",
            side_effect=[sample_reflection, RAEError("Failed"), sample_reflection],
        ):
            enriched_list = enhanced_client.batch_enrich_reflections(reflections=reflections)

            # Should return all 3, with failed one being original
            assert len(enriched_list) == 3

    def test_build_enrichment_query(self, enhanced_client, sample_reflection):
        """Test building enrichment query from reflection."""
        query = enhanced_client._build_enrichment_query(sample_reflection)

        assert "code quality" in query
        assert "codebase" in query
        assert "Test Reflection" in query

    def test_extract_refactor_type(self, enhanced_client, sample_reflection):
        """Test extracting refactor type from reflection metadata."""
        refactor_type = enhanced_client._extract_refactor_type(sample_reflection)

        assert refactor_type == "extract-method"

    def test_factory_function_with_disabled_rae(self):
        """Test factory function returns None when RAE disabled."""
        with patch("feniks.adapters.rae_client.enhanced_client.settings") as mock_settings:
            mock_settings.rae_enabled = False

            client = create_enhanced_rae_client()

            assert client is None

    def test_factory_function_success(self):
        """Test factory function creates client successfully."""
        with patch("feniks.adapters.rae_client.enhanced_client.settings") as mock_settings:
            mock_settings.rae_enabled = True
            mock_settings.rae_base_url = "http://localhost:8000"
            mock_settings.rae_api_key = "test-key"
            mock_settings.rae_tenant_id = "test-tenant"

            with patch("feniks.adapters.rae_client.client.requests.Session"):
                client = create_enhanced_rae_client()

                assert client is not None
                assert isinstance(client, EnhancedRAEClient)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
