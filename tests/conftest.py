"""Test fixtures for tool-memory module."""

import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_db():
    """Create a temporary database file for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_memories.db"
        yield db_path
