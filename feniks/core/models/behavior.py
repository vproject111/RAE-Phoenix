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
Behavior Contract Models for Legacy System Analysis.

These models enable Feniks to:
- Describe behavior of legacy systems without traditional tests
- Create behavior contracts from observed snapshots
- Detect regressions by comparing new behavior against contracts
- Provide a "safety umbrella" over refactoring legacy systems
"""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ============================================================================
# Input Models - Describe how to execute a scenario
# ============================================================================


class UIAction(BaseModel):
    """
    Single user action in a UI scenario.

    Examples:
    - Click button: UIAction(action_type="click", selector="#submit-btn")
    - Type text: UIAction(action_type="type", selector="input[name='email']", text="user@example.com")
    - Navigate: UIAction(action_type="navigate", url="/dashboard")
    """

    action_type: Literal["click", "type", "navigate", "select", "wait"]
    selector: Optional[str] = None  # CSS/XPath selector
    text: Optional[str] = None  # Text to type
    url: Optional[str] = None  # URL for navigate
    extra: dict[str, Any] = Field(default_factory=dict)  # Extensible metadata


class APIRequest(BaseModel):
    """
    API request specification for API scenario.

    Example:
    APIRequest(
        method="POST",
        url="/api/orders",
        headers={"Authorization": "Bearer token"},
        body={"product_id": 123, "quantity": 2}
    )
    """

    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    body: Optional[dict[str, Any] | str] = None


class CLICommand(BaseModel):
    """
    CLI command specification for batch/CLI scenario.

    Example:
    CLICommand(
        command="python",
        args=["main.py", "--config", "config.yml"],
        env={"ENV": "test"}
    )
    """

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class BehaviorInput(BaseModel):
    """
    Input specification for a behavior scenario.
    Depending on scenario category, different fields are used.
    """

    ui_actions: Optional[list[UIAction]] = None
    api_request: Optional[APIRequest] = None
    cli_command: Optional[CLICommand] = None

    # Additional context (user role, feature flags, etc.)
    context: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Success Criteria Models - Define what "success" means
# ============================================================================


class HTTPCriteria(BaseModel):
    """
    HTTP-level success criteria for API scenarios.
    """

    expected_status_codes: list[int] = Field(default_factory=lambda: [200])
    allowed_status_codes: list[int] = Field(default_factory=lambda: [200, 201, 204])
    forbidden_status_codes: list[int] = Field(default_factory=lambda: [500, 502, 503])

    # JSONPath patterns for response validation
    must_contain_json_paths: list[str] = Field(default_factory=list)  # e.g., "$.data.id"
    must_not_contain_json_paths: list[str] = Field(default_factory=list)


class DOMCriteria(BaseModel):
    """
    DOM-level success criteria for UI scenarios.
    """

    required_selectors: list[str] = Field(default_factory=list)  # Must exist in DOM
    forbidden_selectors: list[str] = Field(default_factory=list)  # Must NOT exist (e.g., ".error-banner")
    required_text_snippets: list[str] = Field(default_factory=list)  # Text must be present
    forbidden_text_snippets: list[str] = Field(default_factory=list)  # Text must NOT be present


class LogCriteria(BaseModel):
    """
    Log-level success criteria - patterns to check in logs.
    """

    forbidden_patterns: list[str] = Field(default_factory=list)  # e.g., ["ERROR", "Exception", "Traceback"]
    required_patterns: list[str] = Field(default_factory=list)  # e.g., ["Request successful"]


class CLISuccessCriteria(BaseModel):
    """
    CLI-level success criteria.
    """

    expected_exit_codes: list[int] = Field(default_factory=lambda: [0])
    forbidden_exit_codes: list[int] = Field(default_factory=list)
    required_stdout_patterns: list[str] = Field(default_factory=list)
    forbidden_stdout_patterns: list[str] = Field(default_factory=list)
    required_stderr_patterns: list[str] = Field(default_factory=list)
    forbidden_stderr_patterns: list[str] = Field(default_factory=list)


class BehaviorSuccessCriteria(BaseModel):
    """
    Multi-layered success criteria for a behavior scenario.
    Combines HTTP, DOM, and log-level checks.
    """

    http: Optional[HTTPCriteria] = None
    dom: Optional[DOMCriteria] = None
    logs: Optional[LogCriteria] = None
    cli: Optional[CLISuccessCriteria] = None

    # Custom rules for advanced validation (evaluated by Feniks/RAE)
    custom_rules: list[str] = Field(default_factory=list)


# ============================================================================
# BehaviorScenario - Describes what to test
# ============================================================================


class BehaviorScenario(BaseModel):
    """
    Description of a legacy system behavior scenario (user flow or technical path).

    A scenario describes:
    - What actions to perform (UI clicks, API calls, CLI commands)
    - What success looks like (status codes, DOM elements, log patterns)
    - Context metadata (environment, tags)

    Scenarios are reusable and can be executed multiple times to collect snapshots.
    """

    id: str
    project: str

    # Scenario classification
    category: Literal["ui", "api", "cli", "batch", "mixed"]
    name: str
    description: str

    # Execution context
    environment: Literal["legacy", "candidate", "production", "staging", "test"]
    tags: list[str] = Field(default_factory=list)

    # What to execute
    input: BehaviorInput

    # What success means
    success_criteria: BehaviorSuccessCriteria

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Audit metadata
    created_at: datetime
    created_by: Optional[str] = None  # user/agent ID


# ============================================================================
# Observation Models - Captured from execution
# ============================================================================


class ObservedHTTP(BaseModel):
    """
    Observed HTTP response from an API scenario execution.
    """

    status_code: int
    headers: dict[str, str]
    body: Optional[str | dict[str, Any]] = None


class DOMElement(BaseModel):
    """
    Metadata of a captured DOM element.
    """
    selector: Optional[str] = None
    tag_name: str
    text_content: str
    is_visible: bool
    attributes: dict[str, str] = Field(default_factory=dict)


class ObservedDOM(BaseModel):
    """
    Minimal DOM snapshot from UI scenario execution.
    We don't store full HTML - just key selectors and text.
    """

    present_selectors: list[str] = Field(default_factory=list)
    missing_selectors: list[str] = Field(default_factory=list)
    present_text_snippets: list[str] = Field(default_factory=list)
    missing_text_snippets: list[str] = Field(default_factory=list)
    elements: list[DOMElement] = Field(default_factory=list)



class ObservedLogs(BaseModel):
    """
    Observed logs from scenario execution.
    """

    lines: list[str] = Field(default_factory=list)
    matched_forbidden_patterns: list[str] = Field(default_factory=list)
    matched_required_patterns: list[str] = Field(default_factory=list)


class ObservedCLI(BaseModel):
    """
    Observed CLI execution result.
    """

    command: str
    exit_code: int
    stdout: str
    stderr: str


# ============================================================================
# BehaviorViolation - Specific contract breach
# ============================================================================


class BehaviorViolation(BaseModel):
    """
    Specific point where behavior deviates from contract.

    Examples:
    - HTTP_STATUS_MISMATCH: Expected 200, got 500
    - DOM_ELEMENT_MISSING: Required selector "#success-message" not found
    - LOG_FORBIDDEN_PATTERN: Found "Exception" in logs
    """

    code: str  # e.g., "HTTP_STATUS_MISMATCH", "DOM_ELEMENT_MISSING"
    message: str  # Human-readable description
    severity: Literal["low", "medium", "high", "critical"]
    details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# BehaviorSnapshot - Single execution instance
# ============================================================================


class BehaviorSnapshot(BaseModel):
    """
    Concrete execution of a BehaviorScenario (one run).

    Contains:
    - What was observed (HTTP, DOM, logs)
    - Technical metrics (duration, errors)
    - Success assessment against criteria
    - Any violations detected
    """

    id: str
    scenario_id: str
    project: str

    environment: Literal["legacy", "candidate", "production", "staging", "test"]

    # Observed data
    observed_http: Optional[ObservedHTTP] = None
    observed_dom: Optional[ObservedDOM] = None
    observed_logs: Optional[ObservedLogs] = None
    observed_cli: Optional[ObservedCLI] = None

    # Technical metrics
    duration_ms: Optional[int] = None
    error_count: int = 0
    warning_count: int = 0

    # Success assessment
    success: bool
    violations: list[BehaviorViolation] = Field(default_factory=list)

    # Audit metadata
    created_at: datetime
    recorded_by: Optional[str] = None  # agent/user ID


# ============================================================================
# Contract Models - Generalized behavior expectations
# ============================================================================


class HTTPContract(BaseModel):
    """
    Generalized HTTP contract derived from multiple snapshots.
    """

    required_status_codes: list[int] = Field(default_factory=lambda: [200])
    allowed_status_codes: list[int] = Field(default_factory=lambda: [200, 201, 204])
    forbidden_status_codes: list[int] = Field(default_factory=lambda: [500, 502, 503])

    # JSONPath patterns
    required_json_paths: list[str] = Field(default_factory=list)
    forbidden_json_paths: list[str] = Field(default_factory=list)


class DOMContract(BaseModel):
    """
    Generalized DOM contract - minimal set of elements visible to user.
    """

    must_have_selectors: list[str] = Field(default_factory=list)
    must_not_have_selectors: list[str] = Field(default_factory=list)
    must_have_text_snippets: list[str] = Field(default_factory=list)
    must_not_have_text_snippets: list[str] = Field(default_factory=list)


class LogContract(BaseModel):
    """
    Log contract - what we absolutely don't want to see after refactoring.
    """

    forbidden_patterns: list[str] = Field(default_factory=lambda: ["Exception", "Traceback", "ERROR"])
    required_patterns: list[str] = Field(default_factory=list)


class CLIContract(BaseModel):
    """
    Generalized CLI contract for Python/PHP/Batch execution.
    """
    expected_exit_codes: list[int] = Field(default_factory=lambda: [0])
    required_stdout_patterns: list[str] = Field(default_factory=list)
    forbidden_stderr_patterns: list[str] = Field(default_factory=lambda: ["Error", "Traceback", "Fatal"])


class BehaviorContract(BaseModel):
    """
    Behavior contract for a scenario - derived from multiple snapshots.

    Represents the "expected behavior" that must be preserved during refactoring.
    Acts as a substitute for regression tests when no tests exist.
    """

    id: str
    scenario_id: str
    project: str

    # Contract scope
    version: Optional[str] = "1.0.0"
    environment_scope: list[Literal["legacy", "candidate", "production", "staging", "test"]] = Field(
        default_factory=lambda: ["legacy", "candidate"]
    )

    # Generalized behavior rules
    http_contract: Optional[HTTPContract] = None
    dom_contract: Optional[DOMContract] = None
    log_contract: Optional[LogContract] = None
    cli_contract: Optional[CLIContract] = None

    # Tolerance thresholds
    max_error_rate: Optional[float] = 0.0  # Allowed % of failed snapshots
    max_duration_ms_p95: Optional[int] = None  # Expected 95th percentile duration

    # Provenance
    derived_from_snapshot_ids: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0  # Confidence in the generated contract (0.0-1.0)
    created_at: datetime
    created_by: Optional[str] = None


# ============================================================================
# BehaviorCheckResult - Comparison result
# ============================================================================


class BehaviorCheckResult(BaseModel):
    """
    Result of comparing a BehaviorSnapshot against a BehaviorContract.

    Used by Legacy Behavior Guard to detect regressions during refactoring.
    Feeds into FeniksReport for risk assessment.
    """

    snapshot_id: str
    contract_id: str
    project: str

    passed: bool
    violations: list[BehaviorViolation] = Field(default_factory=list)

    # Synthesized risk score:
    # 0.0-0.3: low, 0.3-0.7: medium, 0.7-1.0: high/critical
    risk_score: float = Field(ge=0.0, le=1.0)

    checked_at: datetime
    checked_by: Optional[str] = None  # agent/user ID


# ============================================================================
# BehaviorChecksSummary - Aggregate report data
# ============================================================================


class BehaviorChecksSummary(BaseModel):
    """
    Summary of behavior checks for inclusion in FeniksReport.

    Aggregates results from multiple BehaviorCheckResult instances.
    """

    total_scenarios_checked: int
    total_snapshots_checked: int
    total_passed: int
    total_failed: int
    max_risk_score: float = Field(ge=0.0, le=1.0)


# Alias for backward compatibility
ScenarioInput = BehaviorInput
SuccessCriteria = BehaviorSuccessCriteria
HTTPSuccessCriteria = HTTPCriteria
DOMSuccessCriteria = DOMCriteria
LogSuccessCriteria = LogCriteria

class BehaviorChecksSummary(BaseModel):
    """
    Aggregated summary of behavior checks for a report.
    """
    total_scenarios_checked: int
    total_snapshots_checked: int
    total_passed: int
    total_failed: int
    max_risk_score: float
