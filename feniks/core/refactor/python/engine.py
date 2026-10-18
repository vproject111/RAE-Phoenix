# Copyright 2025 Grzegorz Leśniowski
"""
Python Refactor Engine - Specialized logic for Python codebase modernization.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional

from feniks.core.models.types import OperationalState
from feniks.core.behavior.contract_engine import ContractEngine
from feniks.adapters.runners.python_runner import PythonRunner
from feniks.core.models.behavior import BehaviorScenario
from feniks.infra.logging import get_logger
from feniks.infra.tracing import span
from feniks.core.refactor.python.tools import RuffWrapper, MyPyWrapper, BowlerWrapper, LibCSTWrapper

log = get_logger("core.refactor.python.engine")


class PythonRefactorEngine:
    def __init__(self, state: Optional[OperationalState] = None):
        self.state = state
        self.contract_engine = ContractEngine(state) if state else None
        self.runner = PythonRunner(state) if state else None

        # Tools
        self.ruff = RuffWrapper()
        self.mypy = MyPyWrapper()
        self.bowler = BowlerWrapper()
        self.libcst = LibCSTWrapper()

    def run_pipeline(self, target: str, strategies: List[str]) -> Dict[str, Any]:
        """
        Runs a sequence of analysis and refactoring tools.
        """
        results = {
            "target": target,
            "actions": [],
            "static_analysis": self.ruff.check(target),
            "structure": self.libcst.analyze_structure(target),
            "refactoring": {"actions_taken": []}
        }

        for strategy in strategies:
            if strategy == "auto-fix":
                self.ruff.fix(target)
                results["refactoring"]["actions_taken"].append("ruff-fix")
                results["actions"].append("ruff-fix")
            elif strategy == "typing-check":
                results["typing"] = self.mypy.check(target)
                results["actions"].append("mypy-check")
            elif strategy == "structure-audit":
                results["structure"] = self.libcst.analyze_structure(target)
                results["actions"].append("libcst-audit")

        return results

    def stage_structural_analysis(self, target: str) -> Dict[str, Any]:
        """
        Prepares structural analysis for a target (file or directory).
        """
        path = Path(target)
        if path.is_file():
            return self.libcst.analyze_structure(target)

        return {
            "directory": target,
            "analysis_type": "structural-staging",
            "status": "ready",
            "info": f"Ready to analyze {target}"
        }

    async def execute_refactor(self, file_path: str, recipe: str, scenarios: List[BehaviorScenario]) -> Dict[str, Any]:
        """
        Executes a Python-specific refactor recipe with contract protection.
        """
        with span("python_execute_refactor", attributes={"file": file_path, "recipe": recipe}):
            log.info("starting_python_refactor", file=file_path, recipe=recipe)

            # 1. Establish Baseline Contract
            baseline_snapshots = []
            if self.runner:
                for scenario in scenarios:
                    snap = self.runner.execute_scenario(scenario, environment="legacy")
                    baseline_snapshots.append(snap)

            # 2. Apply Recipe (AI logic would go here to modify the file)
            # await self._apply_ai_recipe(file_path, recipe)
            log.info("applied_ai_recipe_placeholder")

            # 3. Capture Candidate Snapshot (post-change)
            validation_results = []
            all_passed = True

            if self.runner and self.contract_engine:
                for scenario in scenarios:
                    candidate_snap = self.runner.execute_scenario(scenario, environment="candidate")
                    dummy_contract = self.contract_engine.generate_empty_contract(scenario.id, "project-id")

                    result = await self.contract_engine.validate_candidate(dummy_contract, candidate_snap)
                    validation_results.append(result)
                    if not result.passed:
                        all_passed = False

            log.info("python_refactor_complete", file=file_path, all_passed=all_passed)
            return {
                "status": "success" if all_passed else "failed",
                "file": file_path,
                "validation_results": [r.model_dump() for r in validation_results] if validation_results else []
            }

