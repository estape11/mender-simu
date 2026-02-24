"""Tests for bash scripts."""

import os
import subprocess
import tempfile
import pytest


SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'scripts')


class TestCleanupDevicesScript:
    """Tests for cleanup-devices.sh script."""

    @property
    def script_path(self):
        return os.path.join(SCRIPTS_DIR, 'cleanup-devices.sh')

    def test_script_exists(self):
        """Test that the script exists."""
        assert os.path.exists(self.script_path)

    def test_script_is_executable(self):
        """Test that the script is executable."""
        assert os.access(self.script_path, os.X_OK)

    def test_usage_without_arguments(self):
        """Test that script shows usage without arguments."""
        result = subprocess.run(
            [self.script_path],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        assert "Usage:" in result.stdout
        assert "Actions:" in result.stdout
        assert "list" in result.stdout
        assert "decommission-all" in result.stdout

    def test_unknown_action(self):
        """Test that script handles unknown actions."""
        result = subprocess.run(
            [self.script_path, 'unknown-action'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        assert "Unknown action" in result.stdout

    def test_list_without_pat_shows_error(self):
        """Test that list action without PAT shows error."""
        env = os.environ.copy()
        env.pop('MENDER_PAT', None)

        result = subprocess.run(
            [self.script_path, 'list'],
            capture_output=True,
            text=True,
            env=env
        )
        assert result.returncode == 1
        assert "MENDER_PAT" in result.stdout
        assert "Personal Access Token" in result.stdout

    def test_list_pending_without_pat_shows_error(self):
        """Test that list-pending action without PAT shows error."""
        env = os.environ.copy()
        env.pop('MENDER_PAT', None)

        result = subprocess.run(
            [self.script_path, 'list-pending'],
            capture_output=True,
            text=True,
            env=env
        )
        assert result.returncode == 1
        assert "MENDER_PAT" in result.stdout

    def test_decommission_without_pat_shows_error(self):
        """Test that decommission action without PAT shows error."""
        env = os.environ.copy()
        env.pop('MENDER_PAT', None)

        result = subprocess.run(
            [self.script_path, 'decommission-pending'],
            capture_output=True,
            text=True,
            env=env
        )
        assert result.returncode == 1
        assert "MENDER_PAT" in result.stdout

    def test_cleanup_local_no_files(self):
        """Test cleanup-local when no files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [self.script_path, 'cleanup-local'],
                capture_output=True,
                text=True,
                cwd=tmpdir
            )
            assert result.returncode == 0
            assert "No database files found" in result.stdout
            assert "Local cleanup complete" in result.stdout

    def test_usage_shows_all_actions(self):
        """Test that usage shows all documented actions."""
        result = subprocess.run(
            [self.script_path],
            capture_output=True,
            text=True
        )
        expected_actions = [
            'list',
            'list-pending',
            'list-accepted',
            'list-rejected',
            'list-noauth',
            'decommission-all',
            'decommission-pending',
            'decommission-accepted',
            'decommission-rejected',
            'decommission-noauth',
            'cleanup-local'
        ]
        for action in expected_actions:
            assert action in result.stdout, f"Missing action: {action}"


class TestCreateDemoArtifactsScript:
    """Tests for create-demo-artifacts.sh script."""

    @property
    def script_path(self):
        return os.path.join(SCRIPTS_DIR, 'create-demo-artifacts.sh')

    def test_script_exists(self):
        """Test that the script exists."""
        assert os.path.exists(self.script_path)

    def test_script_is_executable(self):
        """Test that the script is executable."""
        assert os.access(self.script_path, os.X_OK)

    def test_usage_without_arguments(self):
        """Test that script shows usage without arguments."""
        result = subprocess.run(
            [self.script_path],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        assert "Usage:" in result.stdout
        assert "Industries:" in result.stdout

    def test_usage_shows_all_industries(self):
        """Test that usage shows all industries."""
        result = subprocess.run(
            [self.script_path],
            capture_output=True,
            text=True
        )
        expected_industries = [
            'automotive',
            'smart_buildings',
            'medical',
            'industrial_iot',
            'retail',
            'all'
        ]
        for industry in expected_industries:
            assert industry in result.stdout, f"Missing industry: {industry}"

    def test_usage_shows_device_types(self):
        """Test that usage shows device types."""
        result = subprocess.run(
            [self.script_path],
            capture_output=True,
            text=True
        )
        expected_device_types = [
            'tcu-4g-lte',
            'bms-controller-hvac',
            'patient-monitor-icu',
            'plc-gateway-modbus',
            'pos-terminal-emv'
        ]
        for device_type in expected_device_types:
            assert device_type in result.stdout, f"Missing device type: {device_type}"

    def test_unknown_industry_shows_error(self):
        """Test that script handles unknown industries."""
        result = subprocess.run(
            [self.script_path, 'unknown-industry'],
            capture_output=True,
            text=True
        )
        # Script will fail if mender-artifact not installed (expected in CI)
        # or show unknown industry error
        assert result.returncode != 0
        # Either mender-artifact not found or unknown industry
        assert "mender-artifact" in result.stdout or "Unknown industry" in result.stdout

    def test_mender_artifact_check(self):
        """Test behavior when mender-artifact is not installed."""
        # Create a modified PATH that doesn't include mender-artifact
        env = os.environ.copy()
        env['PATH'] = '/usr/bin:/bin'  # Minimal PATH

        result = subprocess.run(
            [self.script_path, 'automotive'],
            capture_output=True,
            text=True,
            env=env
        )

        # Should fail with helpful message about mender-artifact
        if result.returncode != 0:
            assert "mender-artifact" in result.stdout
