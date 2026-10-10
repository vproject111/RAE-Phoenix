import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from main import PhoenixRefactorer

def test_phoenix_closed_loop_success_on_second_attempt():
    async def run_test():
        # Instantiate refactorer
        with patch("main.SystemIndexer") as MockIndexer, \
             patch("main.PluginManager") as MockPluginManager, \
             patch("main.RAEMemoryBridge") as MockBridge:
            
            indexer_instance = MockIndexer.return_value
            indexer_instance.get_impact_zone.return_value = {"total_dependents": 0}
            
            plugin_manager_instance = MockPluginManager.return_value
            plugin_manager_instance.get_plugin_for_file.return_value = None  # Force LLM fallback
            plugin_manager_instance.list_available_plugins.return_value = []

            refactorer = PhoenixRefactorer()
            
            # Mock file history and log_decision
            refactorer._fetch_file_history = AsyncMock(return_value=[])
            refactorer.bridge.log_decision = MagicMock()
            
            # Mock LLM repair returns progressively modified code
            refactorer._fallback_llm_fix = AsyncMock()
            refactorer._fallback_llm_fix.side_effect = [
                "class Code: # attempt 1",
                "class Code: # attempt 2 (fixed)"
            ]
            
            # Mock quality audits
            refactorer._request_quality_re_audit = AsyncMock()
            refactorer._request_quality_re_audit.side_effect = [
                {"verdict": "REJECTED", "seniority_level": "junior", "reasoning": "Missing SOLID principles"},
                {"verdict": "PASSED", "seniority_level": "advanced_senior", "reasoning": "Perfect standard achieved"}
            ]
            
            initial_code = "class Code: # broken"
            result = await refactorer.process_repair_request(
                project="test-project",
                code=initial_code,
                reason="Fix formatting",
                file_path="service.py"
            )
            
            assert result["status"] == "SUCCESS"
            assert result["code"] == "class Code: # attempt 2 (fixed)"
            assert result["attempts_made"] == 2
            assert result["tokens_consumed"] == 2000
            
            # Verify initial code was NOT returned (no rollback)
            assert result["code"] != initial_code

    asyncio.run(run_test())


def test_phoenix_closed_loop_max_attempts_escalation_and_rollback():
    async def run_test():
        with patch("main.SystemIndexer") as MockIndexer, \
             patch("main.PluginManager") as MockPluginManager, \
             patch("main.RAEMemoryBridge") as MockBridge:
            
            indexer_instance = MockIndexer.return_value
            indexer_instance.get_impact_zone.return_value = {"total_dependents": 0}
            
            plugin_manager_instance = MockPluginManager.return_value
            plugin_manager_instance.get_plugin_for_file.return_value = None  # Force LLM fallback
            plugin_manager_instance.list_available_plugins.return_value = []

            refactorer = PhoenixRefactorer()
            
            # Mock file history and log_decision
            refactorer._fetch_file_history = AsyncMock(return_value=[])
            refactorer.bridge.log_decision = MagicMock()
            
            # Mock LLM repair returns different code each time, none of which pass
            refactorer._fallback_llm_fix = AsyncMock()
            refactorer._fallback_llm_fix.side_effect = [
                "code_1", "code_2", "code_3", "code_4", "code_5"
            ]
            
            # Mock quality audits (all failed)
            refactorer._request_quality_re_audit = AsyncMock(return_value={
                "verdict": "REJECTED", 
                "seniority_level": "mid", 
                "reasoning": "Still broken"
            })
            
            initial_code = "class Code: # broken"
            result = await refactorer.process_repair_request(
                project="test-project",
                code=initial_code,
                reason="Fix bug",
                file_path="service.py"
            )
            
            # Verify hard stop limit (5 attempts) and rollback to initial code
            assert result["status"] == "FAILED_ESCALATED"
            assert result["code"] == initial_code  # Rollback succeeded!
            assert result["attempts_made"] == 5
            assert result["tokens_consumed"] == 5000
            assert "FAILED_ESCALATED" in result["reason"]

    asyncio.run(run_test())
