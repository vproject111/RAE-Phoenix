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
RAE Client - Integration with Reflective Agent Engine (RAE).
Handles storing meta-reflections and system capabilities to RAE memory.
"""
import json
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from feniks.config.settings import settings
from feniks.exceptions import FeniksError
from feniks.infra.logging import get_logger

log = get_logger("integrations.rae_client")


class RAEError(FeniksError):
    """Exception raised for RAE integration errors."""

    pass


class RAEClient:
    """
    Client for interacting with RAE (Reflective Agent Engine).

    Handles:
    - Storing meta-reflections as reflective/meta-reflective memory
    - Storing system capabilities as semantic memory
    - Authentication via API key or JWT
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 30):
        """
        Initialize RAE client.

        Args:
            base_url: RAE base URL (defaults to settings)
            api_key: RAE API key (defaults to settings)
            timeout: Request timeout in seconds
        """
        self.base_url = (
            base_url
            or settings.rae_base_url
            or os.getenv("RAE_API_URL")
            or os.getenv("RAE_BASE_URL")
            or "http://localhost:8000"
        ).rstrip("/")
        self.api_key = api_key or settings.rae_api_key or os.getenv("RAE_API_KEY")
        self.timeout = timeout

        if not self.base_url:
            raise RAEError("RAE base URL not configured. Set RAE_BASE_URL in .env or pass to constructor.")

        # Configure session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.session.headers.update({"Content-Type": "application/json", "User-Agent": "RAE-Feniks/0.1.0"})

        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

        log.info(f"RAEClient initialized: base_url={self.base_url}")

    def store_meta_reflection(self, reflection_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store a meta-reflection to RAE as reflective/meta-reflective memory.

        Args:
            reflection_payload: Meta-reflection data (formatted by RAEFormatter)

        Returns:
            Dict[str, Any]: Response from RAE

        Raises:
            RAEError: If request fails
        """
        log.info(f"Storing meta-reflection to RAE: {reflection_payload.get('id')}")

        try:
            # Map legacy payload to V2 format if needed
            # For V2, we use /v2/memories/ for all storage
            response = self._make_request(method="POST", endpoint="/v2/memories/", data=reflection_payload)

            log.info(f"Successfully stored meta-reflection: {reflection_payload.get('id')}")
            return response

        except Exception as e:
            raise RAEError(f"Failed to store meta-reflection: {e}") from e

    def store_system_capabilities(self, capabilities_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store system capabilities to RAE as semantic memory.

        Args:
            capabilities_payload: System capabilities data (formatted by RAEFormatter)

        Returns:
            Dict[str, Any]: Response from RAE

        Raises:
            RAEError: If request fails
        """
        log.info(f"Storing system capabilities to RAE: project={capabilities_payload.get('project')}")

        try:
            response = self._make_request(method="POST", endpoint="/v2/memories/", data=capabilities_payload)

            log.info(f"Successfully stored system capabilities for project: {capabilities_payload.get('project')}")
            return response

        except Exception as e:
            raise RAEError(f"Failed to store system capabilities: {e}") from e

    def store_system_model(self, system_model_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store complete system model to RAE as semantic memory.

        Args:
            system_model_payload: System model data (formatted by RAEFormatter)

        Returns:
            Dict[str, Any]: Response from RAE

        Raises:
            RAEError: If request fails
        """
        log.info(f"Storing system model to RAE: project={system_model_payload.get('project')}")

        try:
            response = self._make_request(
                method="POST", endpoint="/v2/memories/", data=system_model_payload
            )

            log.info(f"Successfully stored system model for project: {system_model_payload.get('project')}")
            return response

        except Exception as e:
            raise RAEError(f"Failed to store system model: {e}") from e

    def get_memory_for_project(
        self, project: str, memory_types: Optional[List[str]] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memory for a project from RAE.

        Args:
            project: Project identifier
            memory_types: Optional list of memory types to filter
            limit: Maximum number of memories to retrieve

        Returns:
            List[Dict[str, Any]]: List of memory entries

        Raises:
            RAEError: If request fails
        """
        log.info(f"Retrieving memory from RAE: project={project}")

        try:
            params = {"project": project, "limit": limit}
            # memory_types in V1 is replaced by layer or tags in V2
            
            response = self._make_request(method="GET", endpoint="/v2/memories/", params=params)

            memories = response.get("results", [])
            log.info(f"Retrieved {len(memories)} memories for project: {project}")
            return memories

        except Exception as e:
            raise RAEError(f"Failed to retrieve memory: {e}") from e

    def health_check(self) -> Dict[str, Any]:
        """
        Check RAE health status.

        Returns:
            Dict[str, Any]: Health status response

        Raises:
            RAEError: If health check fails
        """
        try:
            response = self._make_request(method="GET", endpoint="/health")
            log.info(f"RAE health check: {response.get('status')}")
            return response

        except Exception as e:
            raise RAEError(f"RAE health check failed: {e}") from e

    def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to RAE.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            data: Request body data
            params: Query parameters

        Returns:
            Dict[str, Any]: Parsed JSON response

        Raises:
            RAEError: If request fails
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(method=method, url=url, json=data, params=params, timeout=self.timeout)

            # Log request details
            log.debug(f"{method} {url} - Status: {response.status_code}")

            # Raise for HTTP errors
            response.raise_for_status()

            # Parse JSON response
            if response.content:
                return response.json()
            else:
                return {"status": "success"}

        except requests.exceptions.Timeout as e:
            raise RAEError(f"Request to RAE timed out: {url}") from e
        except requests.exceptions.ConnectionError as e:
            raise RAEError(f"Failed to connect to RAE: {url}") from e
        except requests.exceptions.HTTPError as e:
            error_msg = f"RAE API error: {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg += f" - {error_data.get('error', error_data)}"
            except Exception:
                error_msg += f" - {e.response.text}"
            raise RAEError(error_msg) from e
        except requests.exceptions.RequestException as e:
            raise RAEError(f"RAE request failed: {e}") from e
        except json.JSONDecodeError as e:
            raise RAEError(f"Failed to parse RAE response: {e}") from e


def create_rae_client() -> Optional[RAEClient]:
    """
    Factory function to create RAE client if enabled.

    Returns:
        Optional[RAEClient]: RAE client instance or None if disabled
    """
    if not settings.rae_enabled:
        log.debug("RAE integration is disabled")
        return None

    try:
        client = RAEClient(base_url=settings.rae_base_url, api_key=settings.rae_api_key, timeout=settings.rae_timeout)
        return client
    except RAEError as e:
        log.warning(f"Failed to create RAE client: {e}")
        return None
