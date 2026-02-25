"""Tests for industry profiles."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from mender_simulator.simulation.profiles import IndustryProfile
from mender_simulator.utils.config import IndustryConfig


@pytest.fixture
def automotive_config():
    """Create automotive industry config."""
    return IndustryConfig(
        name="automotive",
        enabled=True,
        count=10,
        bandwidth_kbps=500,
        id_prefix="VIN",
        id_format="VIN-{serial}",
        inventory={
            "device_type": "tcu-4g-lte",
            "artifact_name": "v1.0.0",
            "kernel_version": "5.0.0",
            "oem_variant": ["standard", "premium"]
        },
        extra_config={
            "manufacturers": ["WVWZZZ", "3VWDP7"]
        }
    )


@pytest.fixture
def medical_config():
    """Create medical industry config."""
    return IndustryConfig(
        name="medical",
        enabled=True,
        count=5,
        bandwidth_kbps=2000,
        id_prefix="FDA",
        id_format="FDA-{serial}",
        inventory={
            "device_type": "patient-monitor-icu",
            "artifact_name": "v5.0.0",
            "compliance": ["FDA-510k", "CE-MDR"]
        },
        extra_config={
            "device_classes": ["II", "III"]
        }
    )


class TestIndustryProfile:
    """Tests for IndustryProfile."""

    def test_generate_automotive_identity(self, automotive_config):
        """Test automotive identity generation."""
        profile = IndustryProfile(automotive_config)

        identity = profile.generate_device_identity(0)

        assert "mac" in identity
        assert "vin" in identity
        assert "device_type" not in identity  # device_type is inventory only
        assert len(identity["vin"]) == 17  # VIN is 17 characters

    def test_generate_medical_identity(self, medical_config):
        """Test medical device identity generation."""
        profile = IndustryProfile(medical_config)

        identity = profile.generate_device_identity(0)

        # Medical identity only has mac and serial_number
        assert "mac" in identity
        assert "serial_number" in identity
        assert identity["serial_number"].startswith("MED")
        # fda_udi is NOT in identity (moved to inventory)
        assert "fda_udi" not in identity

    def test_generate_unique_identities(self, automotive_config):
        """Test that identities are unique."""
        profile = IndustryProfile(automotive_config)

        identities = [profile.generate_device_identity(i) for i in range(10)]
        vins = [id["vin"] for id in identities]

        # All VINs should be unique
        assert len(set(vins)) == len(vins)

    def test_generate_static_inventory(self, automotive_config):
        """Test static inventory generation."""
        profile = IndustryProfile(automotive_config)

        inventory = profile.generate_static_inventory("TEST-001")

        assert inventory["device_id"] == "TEST-001"
        assert inventory["industry"] == "automotive"
        assert inventory["device_type"] == "tcu-4g-lte"
        assert "simulator_version" in inventory
        # last_seen is telemetry, not in static inventory
        assert "last_seen" not in inventory

    def test_generate_static_inventory_enrichment(self, automotive_config):
        """Test that industry-specific static attributes are added."""
        profile = IndustryProfile(automotive_config)

        inventory = profile.generate_static_inventory("TEST-001")

        # Automotive-specific static attributes
        assert "oem_variant" in inventory
        assert "odometer_km" in inventory
        # battery_voltage is telemetry, not in static inventory
        assert "battery_voltage" not in inventory

    def test_update_telemetry(self, automotive_config):
        """Test telemetry update adds dynamic attributes."""
        profile = IndustryProfile(automotive_config)

        inventory = profile.generate_static_inventory("TEST-001")
        inventory = profile.update_telemetry(inventory)

        # Dynamic attributes should be present
        # Note: Mender is NOT real-time telemetry, only device status
        assert "last_seen" in inventory
        assert "odometer_km" in inventory


class TestDownloadTimeCalculation:
    """Tests for download time calculation."""

    def test_calculate_download_time(self, automotive_config):
        """Test download time calculation."""
        profile = IndustryProfile(automotive_config)

        # 500 KB/s bandwidth, 5MB file = ~10 seconds
        artifact_size = 5 * 1024 * 1024  # 5 MB
        download_time = profile.calculate_download_time(artifact_size)

        # Should be approximately 10 seconds (with jitter)
        assert 9 < download_time < 12

    def test_calculate_download_time_zero_bandwidth(self):
        """Test handling of zero bandwidth."""
        config = IndustryConfig(
            name="test",
            enabled=True,
            count=1,
            bandwidth_kbps=0,
            id_prefix="TST",
            id_format="TST-{serial}",
            inventory={}
        )
        profile = IndustryProfile(config)

        download_time = profile.calculate_download_time(1000000)

        assert download_time == 1.0  # Default minimum

    def test_calculate_download_time_small_file(self, automotive_config):
        """Test download time for small files."""
        profile = IndustryProfile(automotive_config)

        # Very small file
        download_time = profile.calculate_download_time(1024)

        # Should be very quick
        assert download_time < 1


class TestSuccessProbability:
    """Tests for success probability."""

    def test_medical_higher_success_rate(self, medical_config):
        """Test that medical devices have higher success rate."""
        profile = IndustryProfile(medical_config)
        assert profile.get_success_probability() == 0.95

    def test_automotive_default_success_rate(self, automotive_config):
        """Test default success rate for automotive."""
        profile = IndustryProfile(automotive_config)
        assert profile.get_success_probability() == 0.80

    def test_industrial_lower_success_rate(self):
        """Test that industrial devices have lower success rate."""
        config = IndustryConfig(
            name="industrial_iot",
            enabled=True,
            count=10,
            bandwidth_kbps=250,
            id_prefix="IND",
            id_format="IND-{serial}",
            inventory={}
        )
        profile = IndustryProfile(config)
        assert profile.get_success_probability() == 0.75
