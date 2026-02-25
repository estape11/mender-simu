"""Device simulator for handling update lifecycle."""

import asyncio
import logging
import random
from datetime import datetime
from typing import Optional, List, Dict, Any

from ..db.models import Device, DeploymentStatus
from ..db.database import DatabaseManager
from ..client.auth import AuthClient
from ..client.inventory import InventoryClient
from ..client.deployments import DeploymentsClient, DeploymentState, Deployment
from ..client.exceptions import AuthenticationError
from ..utils.config import Config
from .profiles import IndustryProfile

logger = logging.getLogger(__name__)


class DeviceSimulator:
    """Simulates a single Mender device's behavior."""

    def __init__(
        self,
        device: Device,
        profile: IndustryProfile,
        config: Config,
        db: DatabaseManager
    ):
        self.device = device
        self.profile = profile
        self.config = config
        self.db = db

        self.auth_client = AuthClient(
            config.server.url,
            config.server.tenant_token
        )
        self.inventory_client = InventoryClient(config.server.url)
        self.deployments_client = DeploymentsClient(config.server.url)

        self._running = False
        self._current_deployment: Optional[Deployment] = None

    async def start(self) -> None:
        """Start the device simulation loop."""
        self._running = True
        logger.info(f"Device {self.device.device_id} starting simulation")

        try:
            # Initial authentication
            if not await self._authenticate():
                logger.warning(
                    f"Device {self.device.device_id} failed initial auth, "
                    "will retry on next poll"
                )

            # Main simulation loop
            while self._running:
                await self._poll_cycle()
                await asyncio.sleep(self.config.server.poll_interval)

        except asyncio.CancelledError:
            logger.info(f"Device {self.device.device_id} simulation cancelled")
        finally:
            await self._cleanup()

    async def stop(self) -> None:
        """Stop the device simulation."""
        self._running = False
        logger.info(f"Device {self.device.device_id} stopping")

    async def _cleanup(self) -> None:
        """Clean up resources."""
        await self.auth_client.close()
        await self.inventory_client.close()
        await self.deployments_client.close()

    async def _authenticate(self) -> bool:
        """Authenticate device with Mender server."""
        logger.debug(f"Device {self.device.device_id} authenticating")

        token = await self.auth_client.authenticate(
            self.device.identity_data,
            self.device.rsa_public_key,
            self.device.rsa_private_key
        )

        if token:
            self.device.auth_token = token
            await self.db.update_device_auth_token(self.device.device_id, token)
            logger.info(f"Device {self.device.device_id} authenticated successfully")
            return True

        return False

    async def _poll_cycle(self) -> None:
        """Execute one polling cycle."""
        # Ensure we have valid auth
        if not self.device.auth_token:
            if not await self._authenticate():
                return

        # Update last poll time
        await self.db.update_last_poll(self.device.device_id)

        try:
            # Send inventory update
            await self._update_inventory()

            # Check for deployments
            deployment = await self._check_deployment()
            if deployment:
                await self._process_deployment(deployment)

        except AuthenticationError:
            # Token expired or device decommissioned, clear token and re-auth next cycle
            logger.warning(f"Device {self.device.device_id} token invalid, will re-authenticate")
            self.device.auth_token = None
            await self.db.update_device_auth_token(self.device.device_id, None)

    async def _update_inventory(self) -> None:
        """Update device inventory on server."""
        if not self.device.auth_token:
            return

        # Update only telemetry, keep static attributes
        inventory = self.profile.update_telemetry(self.device.inventory_data)
        self.device.inventory_data = inventory

        success = await self.inventory_client.update_inventory(
            self.device.auth_token,
            inventory
        )

        if success:
            await self.db.save_device(self.device)
            logger.debug(f"Device {self.device.device_id} telemetry updated")

    async def _check_deployment(self) -> Optional[Deployment]:
        """Check for pending deployments."""
        if not self.device.auth_token:
            return None

        device_type = self.device.inventory_data.get("device_type", "unknown")
        artifact_name = self.device.inventory_data.get("artifact_name", "unknown")

        deployment = await self.deployments_client.check_for_deployment(
            self.device.auth_token,
            device_type,
            artifact_name
        )

        return deployment

    async def _process_deployment(self, deployment: Deployment) -> None:
        """Process a deployment through all stages."""
        logger.info(
            f"Device {self.device.device_id} processing deployment "
            f"{deployment.id} - {deployment.artifact_name}"
        )

        self._current_deployment = deployment
        self.device.current_status = "updating"
        await self.db.update_device_status(self.device.device_id, "updating")

        # Create deployment status record
        status = DeploymentStatus(
            device_id=self.device.device_id,
            deployment_id=deployment.id,
            artifact_name=deployment.artifact_name,
            status="downloading"
        )
        await self.db.save_deployment_status(status)

        # Determine if this update will succeed
        # Use config success_rate if set, otherwise use industry-specific rate
        success_rate = self.config.simulator.success_rate
        will_succeed = random.random() < success_rate

        try:
            # Stage 1: Downloading
            await self._stage_downloading(deployment, status)

            # Stage 2: Installing
            await self._stage_installing(deployment, status)

            # Stage 3: Rebooting
            await self._stage_rebooting(deployment, status)

            # Stage 4: Final status
            if will_succeed:
                await self._stage_success(deployment, status)
            else:
                error_msg = random.choice(self.config.error_messages)
                await self._stage_failure(deployment, status, error_msg)

        except Exception as e:
            logger.error(f"Deployment error: {e}")
            await self._stage_failure(deployment, status, str(e))

        finally:
            self._current_deployment = None
            self.device.current_status = "idle"
            await self.db.update_device_status(self.device.device_id, "idle")

    async def _stage_downloading(
        self,
        deployment: Deployment,
        status: DeploymentStatus
    ) -> None:
        """Simulate downloading stage."""
        logger.info(f"Device {self.device.device_id} - DOWNLOADING {deployment.artifact_name}")

        await self.deployments_client.update_deployment_status(
            self.device.auth_token,
            deployment.id,
            DeploymentState.DOWNLOADING
        )

        # Calculate download time based on virtual bandwidth
        download_time = self.profile.calculate_download_time(deployment.artifact_size)
        download_time = max(download_time, 2.0)  # Minimum 2 seconds

        # Simulate progress updates
        steps = 10
        for i in range(steps):
            progress = int((i + 1) / steps * 100)
            status.progress = progress
            status.status = "downloading"
            await self.db.save_deployment_status(status)

            logger.debug(
                f"Device {self.device.device_id} downloading: {progress}%"
            )

            await asyncio.sleep(download_time / steps)

    async def _stage_installing(
        self,
        deployment: Deployment,
        status: DeploymentStatus
    ) -> None:
        """Simulate installing stage."""
        logger.info(f"Device {self.device.device_id} - INSTALLING {deployment.artifact_name}")

        await self.deployments_client.update_deployment_status(
            self.device.auth_token,
            deployment.id,
            DeploymentState.INSTALLING
        )

        status.status = "installing"
        await self.db.save_deployment_status(status)

        # Simulate installation time (5-15 seconds)
        install_time = random.uniform(5, 15)
        await asyncio.sleep(install_time)

    async def _stage_rebooting(
        self,
        deployment: Deployment,
        status: DeploymentStatus
    ) -> None:
        """Simulate rebooting stage."""
        logger.info(f"Device {self.device.device_id} - REBOOTING")

        await self.deployments_client.update_deployment_status(
            self.device.auth_token,
            deployment.id,
            DeploymentState.REBOOTING
        )

        status.status = "rebooting"
        await self.db.save_deployment_status(status)

        # Simulate reboot time (3-8 seconds)
        reboot_time = random.uniform(3, 8)
        await asyncio.sleep(reboot_time)

    async def _stage_success(
        self,
        deployment: Deployment,
        status: DeploymentStatus
    ) -> None:
        """Handle successful deployment."""
        logger.info(
            f"Device {self.device.device_id} - SUCCESS - "
            f"Updated to {deployment.artifact_name}"
        )

        await self.deployments_client.update_deployment_status(
            self.device.auth_token,
            deployment.id,
            DeploymentState.SUCCESS
        )

        status.status = "success"
        status.completed_at = datetime.utcnow()
        await self.db.save_deployment_status(status)

        # Update device artifact name and rootfs-image.version
        # deployment.artifact_name already has full name (e.g., tcu-4g-lte-v1.1.0)
        self.device.inventory_data["artifact_name"] = deployment.artifact_name
        self.device.inventory_data["rootfs-image.version"] = deployment.artifact_name
        await self.db.save_device(self.device)

        # Send updated inventory immediately so Mender shows "Current software"
        await self.inventory_client.update_inventory(
            self.device.auth_token,
            self.device.inventory_data
        )
        logger.info(f"Device {self.device.device_id} - Inventory updated with new artifact_name")
        # Note: No logs sent on success, only on failure

    async def _stage_failure(
        self,
        deployment: Deployment,
        status: DeploymentStatus,
        error_message: str
    ) -> None:
        """Handle failed deployment."""
        logger.warning(
            f"Device {self.device.device_id} - FAILURE - {error_message}"
        )

        await self.deployments_client.update_deployment_status(
            self.device.auth_token,
            deployment.id,
            DeploymentState.FAILURE,
            substate=error_message[:128]  # Limit substate length
        )

        status.status = "failure"
        status.completed_at = datetime.utcnow()
        status.error_message = error_message
        await self.db.save_deployment_status(status)

        # Send failure logs
        logs = self._generate_failure_logs(deployment, error_message)
        await self.deployments_client.send_deployment_logs(
            self.device.auth_token,
            deployment.id,
            logs
        )

    def _generate_failure_logs(
        self,
        deployment: Deployment,
        error_message: str
    ) -> List[Dict[str, Any]]:
        """Generate realistic failure logs."""
        now = datetime.utcnow().isoformat() + "Z"  # RFC3339 format required by Mender
        return [
            {
                "timestamp": now,
                "level": "info",
                "message": f"Starting update to {deployment.artifact_name}"
            },
            {
                "timestamp": now,
                "level": "info",
                "message": "Artifact downloaded"
            },
            {
                "timestamp": now,
                "level": "warning",
                "message": "Potential issue detected during installation"
            },
            {
                "timestamp": now,
                "level": "error",
                "message": f"Update failed: {error_message}"
            },
            {
                "timestamp": now,
                "level": "info",
                "message": "Initiating rollback to previous version"
            },
            {
                "timestamp": now,
                "level": "info",
                "message": "Rollback completed, system stable"
            }
        ]
