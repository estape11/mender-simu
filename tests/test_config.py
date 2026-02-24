"""Tests for configuration loading."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from mender_simulator.utils.config import (
    load_config,
    get_enabled_industries,
    Config,
    ServerConfig,
    SimulatorConfig,
    IndustryConfig
)


class TestLoadConfig:
    """Tests for configuration loading."""

    def test_load_valid_config(self, sample_config_yaml):
        """Test loading a valid configuration file."""
        config = load_config(str(sample_config_yaml))

        assert isinstance(config, Config)
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.simulator, SimulatorConfig)

    def test_load_config_server_settings(self, sample_config_yaml):
        """Test that server settings are loaded correctly."""
        config = load_config(str(sample_config_yaml))

        assert config.server.url == "https://test.mender.io"
        assert config.server.tenant_token == "test-token-12345"
        assert config.server.poll_interval == 10

    def test_load_config_simulator_settings(self, sample_config_yaml):
        """Test that simulator settings are loaded correctly."""
        config = load_config(str(sample_config_yaml))

        assert config.simulator.success_rate == 0.8
        assert config.simulator.log_level == "DEBUG"

    def test_load_config_industries(self, sample_config_yaml):
        """Test that industries are loaded correctly."""
        config = load_config(str(sample_config_yaml))

        assert "automotive" in config.industries
        assert "smart_buildings" in config.industries
        assert config.industries["automotive"].enabled is True
        assert config.industries["smart_buildings"].enabled is False

    def test_load_config_error_messages(self, sample_config_yaml):
        """Test that error messages are loaded."""
        config = load_config(str(sample_config_yaml))

        assert len(config.error_messages) == 2
        assert "Test error 1" in config.error_messages

    def test_load_config_file_not_found(self):
        """Test error handling for missing config file."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_load_config_invalid_poll_interval(self, temp_dir):
        """Test validation of poll interval."""
        config_content = """
server:
  url: "https://test.mender.io"
  tenant_token: "test"
  poll_interval: 2

simulator:
  success_rate: 0.8

industries: {}
"""
        config_path = temp_dir / "invalid_config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ValueError, match="Poll interval"):
            load_config(str(config_path))

    def test_load_config_invalid_success_rate(self, temp_dir):
        """Test validation of success rate."""
        config_content = """
server:
  url: "https://test.mender.io"
  tenant_token: "test"
  poll_interval: 30

simulator:
  success_rate: 1.5

industries: {}
"""
        config_path = temp_dir / "invalid_config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ValueError, match="Success rate"):
            load_config(str(config_path))


class TestGetEnabledIndustries:
    """Tests for filtering enabled industries."""

    def test_get_enabled_industries(self, sample_config_yaml):
        """Test getting only enabled industries."""
        config = load_config(str(sample_config_yaml))
        enabled = get_enabled_industries(config)

        assert "automotive" in enabled
        assert "smart_buildings" not in enabled
        assert len(enabled) == 1

    def test_get_enabled_industries_returns_industry_config(self, sample_config_yaml):
        """Test that returned values are IndustryConfig objects."""
        config = load_config(str(sample_config_yaml))
        enabled = get_enabled_industries(config)

        for name, industry in enabled.items():
            assert isinstance(industry, IndustryConfig)
            assert industry.name == name
