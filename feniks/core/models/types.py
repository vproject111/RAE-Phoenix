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
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Literal
from pydantic import BaseModel, Field

@dataclass
class GitInfo:
    hash: str
    author: str
    date: str
    summary: str


@dataclass
class MigrationSuggestion:
    target: str
    notes: str


@dataclass
class Evidence:
    source: str
    rule: str
    confidence: float
    file: str
    start_line: int
    end_line: int


@dataclass
class ApiEndpoint:
    url: str
    method: str
    data_keys: List[str] = field(default_factory=list)
    param_keys: List[str] = field(default_factory=list)


@dataclass
class Dependency:
    type: str
    value: str


@dataclass
class Chunk:
    id: str
    file_path: str
    start_line: int
    end_line: int
    text: str
    chunk_name: str
    language: str

    @property
    def content(self) -> str:
        return self.text


    # --- Wzbogacone Metadane ---
    module: Optional[str] = None
    kind: Optional[str] = None  # service, controller, directive, filter, route, template
    ast_node_type: Optional[str] = None

    # Relacje
    dependencies: List[Dependency] = field(default_factory=list)
    calls_functions: List[str] = field(default_factory=list)
    api_endpoints: List[ApiEndpoint] = field(default_factory=list)
    ui_routes: List[str] = field(default_factory=list)

    # Jakość i Kontekst
    cyclomatic_complexity: int = 0
    business_tags: List[str] = field(default_factory=list)
    git_last_commit: Optional[GitInfo] = None

    # --- Nowe Pola IR ---
    evidence: List[Evidence] = field(default_factory=list)
    confidence: float = 1.0
    criticality_score: float = 0.0
    migration_target: Optional[str] = None
    migration_suggestion: Optional[MigrationSuggestion] = None
    invariants: List[str] = field(default_factory=list)
    io_contract: Dict[str, Any] = field(default_factory=dict)
    api_contract_ref: Optional[str] = None


# --- System Model Types (Iteration 3) ---


class ModuleType(Enum):
    """Type of module in the system."""

    FRONTEND = "frontend"
    BACKEND = "backend"
    CORE = "core"
    LIBRARY = "library"
    UTILITY = "utility"
    UNKNOWN = "unknown"


@dataclass
class ModuleDependency:
    """Represents a dependency relationship between modules."""

    source: str  # Source module name
    target: str  # Target module name
    dependency_type: str  # injection, import, call, etc.
    count: int = 1  # Number of times this dependency appears
    chunks: List[str] = field(default_factory=list)  # Chunk IDs where dependency appears


@dataclass
class Module:
    """Represents a module/component in the system."""

    name: str
    module_type: ModuleType
    file_paths: List[str] = field(default_factory=list)
    chunks: List[str] = field(default_factory=list)  # Chunk IDs

    # Dependencies
    dependencies_in: List[str] = field(default_factory=list)  # Modules that depend on this
    dependencies_out: List[str] = field(default_factory=list)  # Modules this depends on

    # Metrics
    total_lines: int = 0
    total_complexity: int = 0
    avg_complexity: float = 0.0
    chunk_count: int = 0

    # Classification
    business_tags: Set[str] = field(default_factory=set)
    capabilities: Set[str] = field(default_factory=set)

    # Graph metrics (computed by system model builder)
    in_degree: int = 0
    out_degree: int = 0
    centrality: float = 0.0
    is_central: bool = False
    is_boundary: bool = False
    is_hotspot: bool = False


@dataclass
class Capability:
    """Represents a system capability detected from code analysis."""

    name: str
    description: str
    capability_type: str  # feature, integration, pattern, etc.
    confidence: float = 1.0

    # Evidence
    modules: List[str] = field(default_factory=list)
    chunks: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)

    # Context
    business_domain: Optional[str] = None
    complexity_score: float = 0.0


@dataclass
class SystemModel:
    """Complete model of the analyzed system."""

    project: str
    timestamp: str

    # Core components
    modules: Dict[str, Module] = field(default_factory=dict)
    dependencies: List[ModuleDependency] = field(default_factory=list)
    capabilities: List[Capability] = field(default_factory=list)

    # API/Routes
    api_endpoints: List[ApiEndpoint] = field(default_factory=list)
    ui_routes: List[str] = field(default_factory=list)

    # Statistics
    total_chunks: int = 0
    total_modules: int = 0
    total_files: int = 0
    avg_module_complexity: float = 0.0

    # Analysis results
    central_modules: List[str] = field(default_factory=list)
    boundary_modules: List[str] = field(default_factory=list)
    hotspot_modules: List[str] = field(default_factory=list)
    god_modules: List[str] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


# --- Meta-Reflection Types (Iteration 4) ---


class ReflectionLevel(Enum):
    """Level of reflection."""

    OBSERVATION = 0  # Pure observations from data
    REFLECTION = 1  # Conclusions and insights
    META_REFLECTION = 2  # Reflections about reflections/processes


class ReflectionScope(Enum):
    """Scope of the reflection."""

    CODEBASE = "codebase"  # Entire codebase
    MODULE = "module"  # Single module
    SYSTEM = "system"  # System architecture
    PATTERN = "pattern"  # Code pattern
    TECHNICAL_DEBT = "technical_debt"  # Technical debt


class ReflectionImpact(Enum):
    """Impact level of the reflection."""

    CRITICAL = "critical"  # Requires immediate attention
    REFACTOR_RECOMMENDED = "refactor-recommended"  # Should be addressed
    MONITOR = "monitor"  # Keep an eye on it
    INFORMATIONAL = "informational"  # Just FYI


@dataclass
class ReflectionEvidence:
    """Evidence supporting a meta-reflection."""

    type: str  # metric, pattern, analysis, etc.
    source: str  # Where the evidence comes from
    value: Any  # The actual evidence value
    context: Optional[str] = None  # Additional context


@dataclass
class MetaReflection:
    """
    Represents a meta-reflection about the codebase.

    Levels:
    - 0 (OBSERVATION): Pure data observations
    - 1 (REFLECTION): Insights and conclusions
    - 2 (META_REFLECTION): Reflections about the quality of code/architecture
    """

    id: str
    timestamp: str
    project: str
    level: ReflectionLevel
    scope: ReflectionScope
    impact: ReflectionImpact

    # Content
    title: str
    content: str

    # Evidence and context
    evidence: List[ReflectionEvidence] = field(default_factory=list)
    related_modules: List[str] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)

    # Recommendations
    recommendations: List[str] = field(default_factory=list)

    # Metadata
    origin: str = "feniks"
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

# --- Operational Types ---

class OperationalMode(str, Enum):
    """
    Defines how Feniks operates on code.
    """
    REFACTOR = "refactor"  # Legacy preservation & regression protection
    CREATE = "create"      # Green-field development from requirements
    AUDIT = "audit"        # Pure analysis without modification

class TargetLanguage(str, Enum):
    """
    Supported languages for refactoring and creation.
    """
    PYTHON = "python"
    PHP = "php"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    GENERIC = "generic"

class ComplianceLevel(str, Enum):
    """
    Enforcement levels for ISO standards.
    """
    STRICT = "strict"      # Block on any violation (ISO 42001)
    ADVISORY = "warning"   # Log violation but proceed
    NONE = "none"

class OperationalState(BaseModel):
    """
    Global state of the Feniks engine for a specific task.
    Ensures ISO 27001 traceability.
    """
    mode: OperationalMode
    language: TargetLanguage
    trace_id: str = Field(..., description="OpenTelemetry Trace ID for audit")
    agent_id: str = Field(..., description="ID of the agent/user responsible")
    compliance: ComplianceLevel = ComplianceLevel.STRICT
    
    # ISO 42001 Provenance tracking
    provenance_link: Optional[str] = Field(None, description="Link to source memory in RAE")

