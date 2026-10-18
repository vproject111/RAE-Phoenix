import sys
import uuid
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

# Correct the path to allow imports from the project root and scripts directory
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))

from feniks_cli import run_build_process  # noqa: E402

from feniks.config.settings import settings  # noqa: E402


@pytest.mark.e2e
def test_full_end_to_end_pipeline(monkeypatch):
    """
    An end-to-end test that runs the full data processing pipeline on the actual
    frontend-master data and verifies the outcome in a real Qdrant instance.
    """
    # Check if frontend-master exists
    if not (settings.project_root / "frontend-master").exists():
        pytest.skip("frontend-master directory not found, skipping E2E test")

    import shutil
    if not shutil.which("node"):
        pytest.skip("Node.js binary not installed on host, skipping E2E test")

    # 1. Setup: Define a unique collection name for this test run
    collection_name = f"test-collection-{uuid.uuid4()}"

    qdrant_client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    try:
        # 2. Execute: Run the full build process with the unique collection name
        run_build_process(reset_collection=True, collection_name=collection_name)

        # 3. Verify: Check the results in Qdrant
        collection_info = qdrant_client.get_collection(collection_name=collection_name)

        # Assert that the collection was created and is not empty
        assert collection_info is not None
        assert collection_info.points_count > 0

        print(
            f"\n✅ E2E test passed: Successfully ingested {collection_info.points_count} points into collection '{collection_name}'."
        )

    finally:
        # 4. Cleanup: Delete the test collection from Qdrant
        qdrant_client.delete_collection(collection_name=collection_name)
        print(f"\n🧹 Cleaned up test collection '{collection_name}'.")
