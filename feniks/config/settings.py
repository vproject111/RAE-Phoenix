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
Feniks configuration using pydantic BaseSettings.
Supports environment variables and .env files.
"""
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized configuration for the Feniks knowledge base builder.
    Reads settings from environment variables with sensible defaults.
    Uses pydantic BaseSettings for validation and type safety.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    # The root directory of the project.
    project_root: Path = Path(__file__).parent.parent.parent

    # Path to the frontend source code to be indexed.
    # Can be overridden by the FENIKS_FRONTEND_ROOT environment variable.
    feniks_frontend_root: Optional[Path] = None

    # Directory where all output artifacts will be stored.
    # Can be overridden by the FENIKS_OUTPUT_DIR environment variable.
    feniks_output_dir: Optional[Path] = None

    # --- Qdrant Settings ---
    qdrant_collection: str = "feniks_kb_test"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # --- Embedding Model Settings ---
    embedding_model: str = "all-MiniLM-L6-v2"

    # --- Profile (dev/prod) ---
    feniks_profile: str = "dev"

    # --- RAE Integration Settings (Iteration 5) ---
    rae_enabled: bool = True
    rae_base_url: Optional[str] = "http://localhost:8000"
    rae_api_key: Optional[str] = None
    rae_timeout: int = 30  # seconds

    # --- Enterprise Settings (Iteration 7) ---
    # Observability
    metrics_enabled: bool = True
    metrics_export_path: Optional[str] = None

    # Security
    auth_enabled: bool = False
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Governance
    cost_control_enabled: bool = False
    default_project_budget: float = 1000.0  # Default budget in cost units

    # --- Behavior Policy Settings (Phase 2 - Legacy Behavior Guard) ---
    # MaxBehaviorRiskPolicy thresholds
    behavior_max_risk_threshold: float = 0.5  # Maximum acceptable risk score (0.0-1.0)
    behavior_critical_threshold: float = 0.7  # Critical risk threshold

    # ZeroRegressionPolicy settings
    behavior_zero_regression_enabled: bool = False  # Strict no-regression enforcement

    # MinimumCoverageBehaviorPolicy thresholds
    behavior_min_coverage_scenarios: int = 5  # Minimum required scenarios
    behavior_min_coverage_checks: int = 3  # Minimum checks per scenario

    # Contract generation settings
    behavior_contract_min_snapshots: int = 3  # Minimum snapshots for contract generation
    behavior_contract_confidence_threshold: float = 0.8  # Pattern inclusion threshold
    behavior_contract_percentile: int = 95  # Duration percentile (p95)

    # Comparison engine settings
    behavior_comparison_strict_mode: bool = False  # Strict comparison mode

    @property
    def frontend_root(self) -> Path:
        """Returns the frontend root path, with default fallback."""
        if self.feniks_frontend_root:
            return self.feniks_frontend_root
        return self.project_root / "frontend-master"

    @property
    def output_dir(self) -> Path:
        """Returns the output directory path, with default fallback."""
        if self.feniks_output_dir:
            return self.feniks_output_dir
        return self.project_root / "output"

    @property
    def node_indexer_path(self) -> Path:
        """Returns the path to the Node.js indexer script."""
        return self.project_root / "scripts" / "js_html_indexer.mjs"


# Create a single, importable instance of the settings.
settings = Settings()
