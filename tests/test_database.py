"""Tests for database operations."""

import pytest
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from mender_simulator.db.database import DatabaseManager
from mender_simulator.db.models import Device, DeploymentStatus


@pytest.fixture
async def db_manager(temp_db_path):
    """Create a database manager for testing."""
    manager = DatabaseManager(temp_db_path)
    await manager.connect()
    yield manager
    await manager.close()


@pytest.fixture
def sample_device():
    """Create a sample device for testing."""
    return Device(
        device_id="TEST-001",
        identity_data={"mac": "AA:BB:CC:DD:EE:FF"},
        rsa_private_key="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        rsa_public_key="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        industry_profile="automotive",
        current_status="idle",
        inventory_data={"device_type": "test-device"}
    )


class TestDatabaseManager:
    """Tests for DatabaseManager."""

    @pytest.mark.asyncio
    async def test_connect_creates_tables(self, temp_db_path):
        """Test that connecting creates required tables."""
        manager = DatabaseManager(temp_db_path)
        await manager.connect()

        # Verify tables exist by counting devices (should be 0)
        count = await manager.count_devices()
        assert count == 0

        await manager.close()

    @pytest.mark.asyncio
    async def test_save_and_get_device(self, db_manager, sample_device):
        """Test saving and retrieving a device."""
        await db_manager.save_device(sample_device)

        retrieved = await db_manager.get_device(sample_device.device_id)

        assert retrieved is not None
        assert retrieved.device_id == sample_device.device_id
        assert retrieved.industry_profile == "automotive"

    @pytest.mark.asyncio
    async def test_get_nonexistent_device(self, db_manager):
        """Test getting a device that doesn't exist."""
        result = await db_manager.get_device("NONEXISTENT")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_devices(self, db_manager, sample_device):
        """Test getting all devices."""
        # Save multiple devices
        await db_manager.save_device(sample_device)

        device2 = Device(
            device_id="TEST-002",
            identity_data={"mac": "11:22:33:44:55:66"},
            rsa_private_key="key",
            rsa_public_key="key",
            industry_profile="medical"
        )
        await db_manager.save_device(device2)

        devices = await db_manager.get_all_devices()

        assert len(devices) == 2

    @pytest.mark.asyncio
    async def test_get_devices_by_industry(self, db_manager, sample_device):
        """Test filtering devices by industry."""
        await db_manager.save_device(sample_device)

        device2 = Device(
            device_id="TEST-002",
            identity_data={"mac": "11:22:33:44:55:66"},
            rsa_private_key="key",
            rsa_public_key="key",
            industry_profile="medical"
        )
        await db_manager.save_device(device2)

        automotive_devices = await db_manager.get_devices_by_industry("automotive")
        medical_devices = await db_manager.get_devices_by_industry("medical")

        assert len(automotive_devices) == 1
        assert len(medical_devices) == 1
        assert automotive_devices[0].device_id == "TEST-001"

    @pytest.mark.asyncio
    async def test_update_device_status(self, db_manager, sample_device):
        """Test updating device status."""
        await db_manager.save_device(sample_device)

        await db_manager.update_device_status(sample_device.device_id, "updating")

        device = await db_manager.get_device(sample_device.device_id)
        assert device.current_status == "updating"

    @pytest.mark.asyncio
    async def test_delete_device(self, db_manager, sample_device):
        """Test deleting a device."""
        await db_manager.save_device(sample_device)

        deleted = await db_manager.delete_device(sample_device.device_id)
        assert deleted is True

        device = await db_manager.get_device(sample_device.device_id)
        assert device is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_device(self, db_manager):
        """Test deleting a device that doesn't exist."""
        deleted = await db_manager.delete_device("NONEXISTENT")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_count_devices(self, db_manager, sample_device):
        """Test counting devices."""
        assert await db_manager.count_devices() == 0

        await db_manager.save_device(sample_device)
        assert await db_manager.count_devices() == 1

    @pytest.mark.asyncio
    async def test_count_devices_by_industry(self, db_manager, sample_device):
        """Test counting devices grouped by industry."""
        await db_manager.save_device(sample_device)

        device2 = Device(
            device_id="TEST-002",
            identity_data={},
            rsa_private_key="key",
            rsa_public_key="key",
            industry_profile="automotive"
        )
        await db_manager.save_device(device2)

        counts = await db_manager.count_devices_by_industry()

        assert counts.get("automotive") == 2


class TestDeploymentStatus:
    """Tests for deployment status operations."""

    @pytest.mark.asyncio
    async def test_save_deployment_status(self, db_manager, sample_device):
        """Test saving deployment status."""
        await db_manager.save_device(sample_device)

        status = DeploymentStatus(
            device_id=sample_device.device_id,
            deployment_id="deploy-001",
            artifact_name="v2.0.0",
            status="downloading",
            progress=50
        )

        await db_manager.save_deployment_status(status)

        retrieved = await db_manager.get_deployment_status(
            sample_device.device_id, "deploy-001"
        )

        assert retrieved is not None
        assert retrieved.status == "downloading"
        assert retrieved.progress == 50

    @pytest.mark.asyncio
    async def test_get_active_deployments(self, db_manager, sample_device):
        """Test getting active deployments."""
        await db_manager.save_device(sample_device)

        # Active deployment
        status1 = DeploymentStatus(
            device_id=sample_device.device_id,
            deployment_id="deploy-001",
            artifact_name="v2.0.0",
            status="downloading"
        )
        await db_manager.save_deployment_status(status1)

        # Completed deployment
        status2 = DeploymentStatus(
            device_id=sample_device.device_id,
            deployment_id="deploy-002",
            artifact_name="v1.5.0",
            status="success"
        )
        await db_manager.save_deployment_status(status2)

        active = await db_manager.get_active_deployments()

        assert len(active) == 1
        assert active[0].deployment_id == "deploy-001"
