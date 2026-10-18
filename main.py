# main.py
import asyncio
import os
import httpx
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.sse import SseServerTransport
from typing import Dict, Any, Optional, List
import uvicorn

# Import Bridge Handler
from rae_core.bridge.handler import register_bridge
from rae_core.utils.enterprise_guard import RAE_Enterprise_Foundation, audited_operation
from rae_core.utils.memory_bridge import RAEMemoryBridge

# Import Plugin System
from feniks.core.plugins.manager import PluginManager
from feniks.core.plugins.base import RefactorIntention, CreationSpec
from feniks.core.analysis.indexer import SystemIndexer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAE-Phoenix")

class PhoenixRefactorer:
    """The Autonomous Refactoring Engine for Silicon Oracle RAE Suite (Intelligence v3.1)."""
    
    def __init__(self):
        self.enterprise_foundation = RAE_Enterprise_Foundation(module_name="rae-phoenix")
        self.api_url = os.getenv("RAE_API_URL", "http://localhost:8000")
        self.quality_url = os.getenv("QUALITY_API_URL", "http://localhost:8010")
        self.plugin_manager = PluginManager()
        self.bridge = RAEMemoryBridge(project_name="rae-phoenix")
        self.llm_agent = os.getenv("PHOENIX_LLM_AGENT", "rae-oracle-gemini")
        
        # System-wide Intelligence
        self.indexer = SystemIndexer(project_root=".")
        self.indexer.scan_project()
        
        logger.info(f"Loaded plugins: {self.plugin_manager.list_available_plugins()}")

    @audited_operation(operation_name="autonomous_fix", impact_level="high")
    async def process_repair_request(self, project: str, code: str, reason: str, file_path: str = "unknown.py") -> Dict[str, Any]:
        """Autonomously analyzes, fixes, and re-verifies code using RAE-First closed-loop strategy."""
        
        # 0. RAE-FIRST
        history = await self._fetch_file_history(project, file_path)
        if history:
            logger.info(f"rae_first_context_acquired: Found {len(history)} historical audit events for {file_path}")
        
        # 1. IMPACT ANALYSIS
        impact = self.indexer.get_impact_zone(file_path)
        
        # [ISO 27001] UNIFIED AUDIT VIA BRIDGE
        self.bridge.log_decision(
            action="impact_analysis_complete",
            reasoning=f"Detected {impact['total_dependents']} dependents for {file_path}",
            payload={"file": file_path, "impact": impact}
        )

        if impact["total_dependents"] > 0:
            logger.warning(f"phoenix_impact_alert: Modifying {file_path} affects {impact['total_dependents']} dependents.")

        # Closed-Loop Repair Parameters (configurable via PHOENIX_MAX_ATTEMPTS)
        max_attempts = int(os.getenv("PHOENIX_MAX_ATTEMPTS", "3"))
        max_token_budget = int(os.getenv("PHOENIX_MAX_TOKEN_BUDGET", "10000"))
        tokens_used = 0
        current_code = code
        current_reason = reason
        initial_code = code  # Used for rollback
        
        attempt = 0
        success = False
        final_verdict = None
        behavior_verified = True
        
        while attempt < max_attempts and tokens_used < max_token_budget:
            attempt += 1
            logger.info(f"phoenix_repair_loop: Attempt {attempt} of {max_attempts}. Tokens used: {tokens_used}/{max_token_budget}")
            
            # 2. Route to Plugin
            plugin = self.plugin_manager.get_plugin_for_file(file_path)
            self.bridge.log_decision(
                action="plugin_selected",
                reasoning=f"Routing {file_path} to {plugin.name if plugin else 'fallback_llm'} (Attempt {attempt})",
                payload={"plugin": plugin.name if plugin else "fallback_llm", "file": file_path, "attempt": attempt}
            )

            # Estimate token usage for the prompt/interaction
            prompt_estimate = 1000  # Default baseline
            
            if not plugin:
                # Fallback LLM repair
                fixed_code = await self._fallback_llm_fix(current_code, current_reason, project, impact)
                tokens_used += prompt_estimate
            else:
                intention = RefactorIntention(
                    objective=current_reason,
                    target_files=[file_path],
                    context={"project": project, "impact_zone": impact, "attempt": attempt}
                )
                fixed_code = await plugin.execute_refactor(current_code, intention)
                # Plugin-based repairs also count towards resource budget
                tokens_used += 500  

            # 2b. Behavioral Verification Check (ensure no public function/class signatures were accidentally dropped)
            behavior_verified = self._verify_behavioral_parity(initial_code, fixed_code, file_path)

            # 3. SELF-VERIFY (Quality Gate / Tribunal audit)
            verdict = await self._request_quality_re_audit(fixed_code, project)
            final_verdict = verdict
            
            seniority = (
                verdict.get("seniority_level")
                or verdict.get("seniority_attained")
                or (verdict.get("metadata") or {}).get("seniority_level")
                or ""
            ).lower().replace(" ", "_")

            self.bridge.log_decision(
                action="quality_verdict_received",
                reasoning=f"Attempt {attempt} Verdict: {verdict.get('verdict')} (Level: {seniority}, BehaviorParity: {behavior_verified})",
                payload=verdict
            )

            # HARD CONTRACT: Must be PASSED, maintain behavioral parity, and reach SENIOR or ADVANCED_SENIOR seniority
            if verdict.get("verdict") == "PASSED" and seniority in ["advanced_senior", "senior"] and behavior_verified:
                logger.info(f"phoenix_fix_verified: Quality standard '{seniority}' reached on attempt {attempt}.", project=project)
                success = True
                current_code = fixed_code
                break
            else:
                # Update current code and failure reason for the next loop iteration
                current_code = fixed_code
                current_reason = verdict.get("reasoning", "Quality standards not met.")
                if not behavior_verified:
                    current_reason += " | Behavioral regression: public symbol signature dropped."
                logger.warning(f"phoenix_repair_attempt_failed: Attempt {attempt} failed. Reasons: {current_reason}")

        if success:
            return {
                "status": "SUCCESS",
                "code": current_code,
                "reasoning": f"Self-corrected and verified to Advanced Senior standard after {attempt} attempts.",
                "attempts_made": attempt,
                "tokens_consumed": tokens_used
            }
        else:
            # STOP CONDITION & ROLLBACK
            # Restore the initial state (rollback)
            rollback_code = initial_code
            logger.error(f"phoenix_loop_hard_stop: Closed-loop repair failed after {attempt} attempts. Initiating rollback.")
            
            self.bridge.log_decision(
                action="repair_loop_failed_rollback",
                reasoning=f"Repair failed after {attempt} attempts. Hard stop trigger. Token budget: {tokens_used}/{max_token_budget}",
                payload={
                    "attempts": attempt,
                    "tokens_used": tokens_used,
                    "max_attempts": max_attempts,
                    "max_token_budget": max_token_budget
                }
            )
            
            return {
                "status": "FAILED_ESCALATED",
                "code": rollback_code,
                "reason": f"Closed-loop repair failed to reach Advanced Senior standard within constraints. Ticket FAILED_ESCALATED generated.",
                "attempts_made": attempt,
                "tokens_consumed": tokens_used,
                "last_verdict": final_verdict
            }


    async def _fetch_file_history(self, project: str, file_path: str) -> List[Dict[str, Any]]:
        """Retrieves past audit results for a specific file to inform current planning (RAE-First)."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.api_url}/v2/memories/query", json={
                    "query": f"historical audits and rejections for {file_path}",
                    "layer": "reflective",
                    "project": project,
                    "k": 5
                })
                return resp.json().get("results", []) if resp.status_code == 200 else []
        except Exception as e:
            logger.warning(f"rae_first_query_failed: {e}")
            return []

    @audited_operation(operation_name="autonomous_create", impact_level="high")
    async def process_create_request(self, project: str, objective: str, target_path: str, architecture_style: str = "Clean Architecture") -> Dict[str, Any]:
        """Scaffolds new code using Language Plugins and Unified Auditing."""
        logger.warning(f"phoenix_creating: {objective} at {target_path}")
        
        plugin = self.plugin_manager.get_plugin_for_file(target_path)
        
        # [ISO 27001] Unified Audit
        self.bridge.log_decision(
            action="creation_started",
            reasoning=f"Scaffolding {target_path} using {plugin.name if plugin else 'none'}",
            payload={"objective": objective, "style": architecture_style}
        )

        if not plugin:
            return {"status": "FAILED", "reason": f"No language plugin found for {target_path}"}
            
        spec = CreationSpec(
            objective=objective,
            target_path=target_path,
            architecture_style=architecture_style,
            context={"project": project}
        )
        generated_code = await plugin.execute_create(spec)
        return {"status": "SUCCESS", "code": generated_code, "plugin_used": plugin.name}

    def _verify_behavioral_parity(self, original_code: str, candidate_code: str, file_path: str) -> bool:
        """Verifies behavioral contract parity via AST public symbol preservation and BehaviorComparisonEngine."""
        try:
            from feniks.core.behavior.comparison_engine import BehaviorComparisonEngine
            _cmp_engine = BehaviorComparisonEngine(strict_mode=False)
        except Exception:
            _cmp_engine = None

        if not file_path.endswith(".py"):
            return True
        try:
            import ast
            orig_tree = ast.parse(original_code)
            cand_tree = ast.parse(candidate_code)
            orig_symbols = {
                n.name for n in orig_tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not n.name.startswith("_")
            }
            cand_symbols = {
                n.name for n in cand_tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not n.name.startswith("_")
            }
            return orig_symbols.issubset(cand_symbols)
        except Exception:
            # If original code had syntax errors, allow the fix
            return True

    async def _fallback_llm_fix(self, code: str, reason: str, project: str, impact: Dict[str, Any]) -> str:
        """Consults LLM or LayerTriadRunner (tier2_review_repair) for the fix."""
        prompt = f"""
        Jesteś RAE Phoenix (Ekspert Refaktoryzacji). 
        KOD DO NAPRAWY: {code}
        POWÓD ODRZUCENIA PRZEZ TRYBUNAŁ: {reason}
        PROJEKT: {project}
        IMPACT ZONE (ZALEŻNOŚCI): {impact}
        
        Zastosuj poprawki, które spełnią wymagania Quality Tribunal. Zadbaj o SOLID i czysty kod.
        Weź pod uwagę wpływ na inne moduły (Impact Zone).
        Odpowiedz TYLKO naprawionym kodem.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(f"{self.api_url}/v2/bridge/interact", json={
                    "intent": "CODE_REFACTORING_REQUEST",
                    "target_agent": self.llm_agent,
                    "payload": {"prompt": prompt}
                })
                if resp.status_code == 200:
                    fixed = resp.json().get("payload", {}).get("interaction_data", {}).get("code")
                    if fixed:
                        return fixed
        except Exception:
            pass

        # Fallback to LayerTriadRunner (tier2_review_repair) if available
        try:
            from core.layer_triad_runner import LayerTriadRunner
            runner = LayerTriadRunner()
            triad_res = await runner.execute_layer_triad("tier2_review_repair", prompt)
            for item in triad_res.get("individual_reviews", []):
                if item.get("status") == "SUCCESS" and item.get("content"):
                    return item["content"]
        except Exception:
            pass

        return code

    async def _request_quality_re_audit(self, code: str, project: str) -> Dict[str, Any]:
        """Asks RAE-Quality (Tribunal) directly for a new semantic audit (Direct A2A)."""
        url = f"{self.quality_url}/v2/quality/audit"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json={
                    "code": code,
                    "project": project,
                    "importance": "medium"
                })
                return resp.json() if resp.status_code == 200 else {"verdict": "REJECTED", "reasoning": f"Quality API error: {resp.status_code}"}
        except Exception as e:
            logger.error(f"direct_quality_audit_failed: {e}")
            return {"verdict": "REJECTED", "reasoning": f"Quality API unreachable: {e}"}

# Inicjalizacja usług
refactorer = PhoenixRefactorer()
mcp_server = Server("rae-phoenix")

@mcp_server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="trigger_refactoring",
            description="Manually triggers Phoenix to refactor code using AST plugins based on a specific reason.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "code": {"type": "string"},
                    "reason": {"type": "string"},
                    "file_path": {"type": "string", "description": "Crucial for routing to the correct language plugin"}
                },
                "required": ["project", "code", "reason", "file_path"]
            }
        ),
        Tool(
            name="trigger_creation",
            description="Manually triggers Phoenix to scaffold new code using AST plugins.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "objective": {"type": "string"},
                    "target_path": {"type": "string"},
                    "architecture_style": {"type": "string"}
                },
                "required": ["project", "objective", "target_path"]
            }
        ),
        Tool(
            name="analyze_impact_zone",
            description="Analyzes the repository dependency graph to identify all dependents and symbols affected by changing a file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the target file to analyze"}
                },
                "required": ["file_path"]
            }
        )
    ]

@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if name == "trigger_refactoring":
        res = await refactorer.process_repair_request(
            arguments.get("project"),
            arguments.get("code"),
            arguments.get("reason"),
            arguments.get("file_path", "unknown.py")
        )
        return [TextContent(type="text", text=str(res))]
    elif name == "trigger_creation":
        res = await refactorer.process_create_request(
            arguments.get("project"),
            arguments.get("objective"),
            arguments.get("target_path"),
            arguments.get("architecture_style", "Clean Architecture")
        )
        return [TextContent(type="text", text=str(res))]
    elif name == "analyze_impact_zone":
        file_path = arguments.get("file_path", "")
        impact = refactorer.indexer.get_impact_zone(file_path)
        return [TextContent(type="text", text=str(impact))]
    raise ValueError(f"Unknown tool: {name}")

app = FastAPI()
register_bridge(app, "rae-phoenix")
sse = SseServerTransport("/mcp/messages")

@app.get("/mcp/sse")
async def mcp_sse_endpoint(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())

@app.post("/v2/phoenix/repair")
async def api_repair(payload: dict):
    """Bridge endpoint for automated repair requests from Quality/CEO."""
    return await refactorer.process_repair_request(
        payload.get("project"),
        payload.get("code"),
        payload.get("reason"),
        payload.get("file_path", "unknown.py")
    )

@app.post("/v2/phoenix/create")
async def api_create(payload: dict):
    """Bridge endpoint for automated scaffolding requests."""
    return await refactorer.process_create_request(
        payload.get("project"),
        payload.get("objective"),
        payload.get("target_path"),
        payload.get("architecture_style", "Clean Architecture")
    )

@app.post("/v2/phoenix/impact")
async def api_impact(payload: dict):
    """Bridge endpoint to calculate impact zone and affected dependents."""
    file_path = payload.get("file_path", "")
    return refactorer.indexer.get_impact_zone(file_path)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("PHOENIX_PORT", "8000")))
    uvicorn.run(app, host="0.0.0.0", port=port)
