"""Tests for industry profiles."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

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
            "oem_variant": ["standard", "premium"],
        },
        extra_config={"manufacturers": ["WVWZZZ", "3VWDP7"]},
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
            "compliance": ["FDA-510k", "CE-MDR"],
        },
        extra_config={"device_classes": ["II", "III"]},
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
            inventory={},
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
            inventory={},
        )
        profile = IndustryProfile(config)
        assert profile.get_success_probability() == 0.75

    def test_ev_charging_success_rate(self):
        """Test that EV charging devices have a specific success rate."""
        config = IndustryConfig(
            name="ev_charging",
            enabled=True,
            count=8,
            bandwidth_kbps=1000,
            id_prefix="EVC",
            id_format="EVC-{serial}",
            inventory={},
            extra_config={"networks": ["NET-WEST", "NET-EAST"]},
        )
        profile = IndustryProfile(config)
        assert profile.get_success_probability() == 0.78


class TestEVChargingProfile:
    """Tests for EV Charging profile."""

    @pytest.fixture
    def ev_charging_config(self):
        return IndustryConfig(
            name="ev_charging",
            enabled=True,
            count=8,
            bandwidth_kbps=1000,
            id_prefix="EVC",
            id_format="EVC-{serial}",
            inventory={
                "device_type": "ev-charger-ocpp-2.0",
                "artifact_name": "v1.2.0",
                "charger_types": ["ac-level2-7kW", "dc-fast-50kW"],
                "protocols": ["ocpp-2.0.1"],
                "connector_types": ["ccs2", "type2"],
            },
            extra_config={"networks": ["NET-WEST", "NET-EAST", "NET-CENTRAL"]},
        )

    def test_generate_ev_charging_identity(self, ev_charging_config):
        """Test EV charging station identity generation."""
        profile = IndustryProfile(ev_charging_config)

        identity = profile.generate_device_identity(0)

        assert "mac" in identity
        assert "evse_id" in identity
        assert identity["evse_id"].startswith("EVC-")

    def test_ev_charging_identity_unique(self, ev_charging_config):
        """Test that EV charging identities are unique."""
        profile = IndustryProfile(ev_charging_config)

        identities = [profile.generate_device_identity(i) for i in range(8)]
        evse_ids = [id["evse_id"] for id in identities]

        assert len(set(evse_ids)) == len(evse_ids)

    def test_ev_charging_static_inventory(self, ev_charging_config):
        """Test EV charging static inventory attributes."""
        profile = IndustryProfile(ev_charging_config)

        inventory = profile.generate_static_inventory("EVC-TEST-001")

        assert inventory["device_id"] == "EVC-TEST-001"
        assert inventory["industry"] == "ev_charging"
        assert inventory["device_type"] == "ev-charger-ocpp-2.0"
        assert "charger_type" in inventory
        assert "supported_protocols" in inventory
        assert "connector_type" in inventory
        assert "max_power_kw" in inventory
        assert "location_type" in inventory
        assert "sessions_total" in inventory

    def test_ev_charging_telemetry_update(self, ev_charging_config):
        """Test EV charging telemetry updates charger_status and sessions."""
        profile = IndustryProfile(ev_charging_config)

        inventory = profile.generate_static_inventory("EVC-TEST-001")
        inventory = profile.update_telemetry(inventory)

        assert "last_seen" in inventory
        assert "charger_status" in inventory
        assert inventory["charger_status"] in ["available", "charging", "faulted"]


class TestUASProfiles:
    """Tests for UAS airframe and ground control station profiles."""

    @pytest.fixture
    def uas_airframe_config(self):
        return IndustryConfig(
            name="uas_airframe",
            enabled=True,
            count=26,
            bandwidth_kbps=400,
            id_prefix="UAS",
            id_format="UAS-{tail_number}",
            inventory={
                "device_type": "quad-x",
                "artifact_name": "2.3",
                "kernel_version": "6.1.0-uas-rt",
                "system_type": "uas-mk2",
            },
            extra_config={
                "tail_number_start": 140,
                "os_name": "flight-os",
                "os_versions": ["2.1", "2.2", "2.3"],
            },
        )

    @pytest.fixture
    def uas_gcs_config(self):
        return IndustryConfig(
            name="uas_gcs",
            enabled=True,
            count=4,
            bandwidth_kbps=5000,
            id_prefix="GCS",
            id_format="GCS-{station_id}",
            inventory={
                "device_type": "gcs",
                "artifact_name": "5.0",
            },
            extra_config={
                "os_name": "gcs-os",
                "os_versions": ["4.8", "4.9", "5.0"],
            },
        )

    def test_generate_uas_airframe_identity(self, uas_airframe_config):
        """Test airframe tail-number identity generation."""
        profile = IndustryProfile(uas_airframe_config)

        identity = profile.generate_device_identity(2)

        assert "mac" in identity
        assert identity["tail_number"] == "UAS-0142"

    def test_uas_airframe_identity_unique(self, uas_airframe_config):
        """Test that airframe tail numbers are unique and sequential."""
        profile = IndustryProfile(uas_airframe_config)

        identities = [profile.generate_device_identity(i) for i in range(26)]
        tails = [i["tail_number"] for i in identities]

        assert len(set(tails)) == len(tails)
        assert tails[0] == "UAS-0140"
        assert tails[-1] == "UAS-0165"

    def test_generate_uas_gcs_identity(self, uas_gcs_config):
        """Test ground control station identity generation."""
        profile = IndustryProfile(uas_gcs_config)

        identities = [profile.generate_device_identity(i) for i in range(4)]
        stations = [i["station_id"] for i in identities]

        assert stations == ["GCS-01", "GCS-02", "GCS-03", "GCS-04"]

    def test_uas_airframe_static_inventory(self, uas_airframe_config):
        """Test airframe static inventory matches the demo proposal."""
        profile = IndustryProfile(uas_airframe_config)

        inventory = profile.generate_static_inventory("UAS-uas_airframe-000001")

        assert inventory["device_type"] == "quad-x"
        assert inventory["system_type"] == "uas-mk2"
        # Mixed-version fleet: flight-os-{2.1|2.2|2.3}
        assert inventory["artifact_name"] in [
            "flight-os-2.1",
            "flight-os-2.2",
            "flight-os-2.3",
        ]
        assert inventory["rootfs-image.version"] == inventory["artifact_name"]
        # A/B layout, TPM identity and signed-only installs
        assert inventory["update_scheme"] == "dual-rootfs-ab"
        assert inventory["active_partition"] in ["A", "B"]
        assert inventory["tpm_version"] == "2.0"
        assert inventory["identity_key_storage"] == "tpm"
        assert inventory["artifact_verification"] == "signed-only"
        # Orchestrator components
        for key in [
            "flight_controller_version",
            "gnss_receiver_version",
            "eo_ir_payload_version",
            "battery_mgmt_version",
            "mission_computer_version",
        ]:
            assert key in inventory
        # Environment determines the link type
        env_link = {
            "depot-maintenance": "wired-lan",
            "forward-deployed": "tactical-lte",
            "remote-outpost": "satcom",
        }
        assert env_link[inventory["network_environment"]] == inventory["link_type"]
        # Remotely managed configuration keys
        assert inventory["telemetry_rate_hz"] == 10
        assert inventory["geofence_profile"] == "training"
        assert inventory["datalink_channel"] == 4
        assert inventory["log_level"] == "info"

    def test_uas_gcs_static_inventory(self, uas_gcs_config):
        """Test ground control station static inventory."""
        profile = IndustryProfile(uas_gcs_config)

        inventory = profile.generate_static_inventory("GCS-uas_gcs-000001")

        assert inventory["device_type"] == "gcs"
        assert inventory["artifact_name"] in ["gcs-os-4.8", "gcs-os-4.9", "gcs-os-5.0"]
        assert inventory["rootfs-image.version"] == inventory["artifact_name"]
        assert inventory["station_role"] in ["primary", "backup"]
        assert inventory["link_type"] == "wired-lan"

    def test_uas_airframe_telemetry_update(self, uas_airframe_config):
        """Test airframe telemetry accumulates flight hours and link status."""
        profile = IndustryProfile(uas_airframe_config)

        inventory = profile.generate_static_inventory("UAS-uas_airframe-000001")
        hours_before = inventory["flight_hours"]
        inventory = profile.update_telemetry(inventory)

        assert "last_seen" in inventory
        assert inventory["flight_hours"] >= hours_before
        assert inventory["link_status"] in ["nominal", "degraded"]

    def test_uas_gcs_telemetry_update(self, uas_gcs_config):
        """Test ground control stations only refresh last_seen."""
        profile = IndustryProfile(uas_gcs_config)

        inventory = profile.generate_static_inventory("GCS-uas_gcs-000001")
        inventory = profile.update_telemetry(inventory)

        assert "last_seen" in inventory
