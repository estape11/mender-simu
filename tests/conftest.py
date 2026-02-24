"""Pytest fixtures for Mender Fleet Simulator tests."""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config_yaml(temp_dir):
    """Create a sample configuration file."""
    config_content = """
server:
  url: "https://test.mender.io"
  tenant_token: "test-token-12345"
  poll_interval: 10

simulator:
  success_rate: 0.8
  log_file: "test_simulator.log"
  log_level: "DEBUG"
  database_path: "test_devices.db"

industries:
  automotive:
    enabled: true
    count: 2
    bandwidth_kbps: 500
    id_prefix: "VIN"
    id_format: "VIN-{serial}"
    manufacturers: ["TEST"]
    inventory:
      device_type: "test-automotive"
      artifact_name: "v1.0.0"
      kernel_version: "5.0.0-test"

  smart_buildings:
    enabled: false
    count: 1
    bandwidth_kbps: 1000
    id_prefix: "MAC"
    id_format: "MAC-{serial}"
    inventory:
      device_type: "test-building"
      artifact_name: "v1.0.0"

error_messages:
  - "Test error 1"
  - "Test error 2"
"""
    config_path = temp_dir / "config.yaml"
    config_path.write_text(config_content)
    return config_path


@pytest.fixture
def temp_db_path(temp_dir):
    """Return a temporary database path."""
    return str(temp_dir / "test_devices.db")
