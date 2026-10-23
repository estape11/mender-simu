"""Simulator for System tier devices (Mender Orchestrator).

A System device authenticates with tier="system", reports its components as
`mender-orchestrator-manifest.*` inventory attributes, and processes
deployments of manifest artifacts: components update in manifest order, a
component failure triggers a coordinated rollback of the ones already updated.
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Any, Dict, List

from ..client.deployments import Deployment, DeploymentState
from ..db.models import DeviceStatus, DeploymentStatus
from .device_simulator import DeviceSimulator
from .manifest import (
    ManifestError,
    parse_manifest_artifact,
    plan_component_updates,
)

logger = logging.getLogger(__name__)

# update modules a real orchestrator-enabled client reports
UPDATE_MODULES = [
    "directory",
    "mender-orchestrator-manifest",
    "rootfs-image",
    "single-file",
]

# Inventory attribute names, per the real orchestrator inventory script
ATTR_PREFIX = "mender-orchestrator-manifest."
INSTALLED_MANIFEST_ATTR = "data-partition.mender-orchestrator-manifest.version"


class SystemDeviceSimulator(DeviceSimulator):
    """Simulates a Mender System device orchestrating component updates."""

    def _inventory_extras(self) -> Dict[str, Any]:
        """Report system_type and per-component attributes.

        Repeated per-component values are sent as lists of "<id>/<value>",
        matching the wire format of the real inventory script.
        """
        industry_cfg = self.config.industries.get(self.device.industry_profile)
        self.profile.update_component_telemetry(self.device.components_data)

        components = self.device.components_data
        extras: Dict[str, Any] = {
            "system_type": industry_cfg.system_type if industry_cfg else "",
            "update_modules": UPDATE_MODULES,
            INSTALLED_MANIFEST_ATTR: self.device.inventory_data.get(
                "artifact_name", ""
            ),
            ATTR_PREFIX + "component_id": list(components.keys()),
        }

        per_component: Dict[str, List[str]] = {}
        for comp_id, comp in components.items():
            for attr, value in comp.items():
                per_component.setdefault(attr, []).append(f"{comp_id}/{value}")
        for attr, values in per_component.items():
            extras[ATTR_PREFIX + attr] = values

        return extras

    async def _process_deployment(self, deployment: Deployment) -> None:
        """Process a manifest deployment component by component."""
        logger.info(
            f"Device {self.device.device_id} processing manifest deployment "
            f"{deployment.id} - {deployment.artifact_name}"
        )

        self._current_deployment = deployment
        self.device.current_status = DeviceStatus.UPDATING
        await self.db.update_device_status(self.device.device_id, DeviceStatus.UPDATING)

        status = DeploymentStatus(
            device_id=self.device.device_id,
            deployment_id=deployment.id,
            artifact_name=deployment.artifact_name,
            status="downloading",
        )
        await self.db.save_deployment_status(status)

        try:
            steps = await self._stage_download_manifest(deployment, status)
            await self._stage_install_components(deployment, status, steps)
        except Exception as e:
            logger.error(f"Manifest deployment error: {e}")
            await self._stage_failure(deployment, status, str(e))
        finally:
            self._current_deployment = None
            self.device.current_status = DeviceStatus.IDLE
            await self.db.update_device_status(self.device.device_id, DeviceStatus.IDLE)

    async def _stage_download_manifest(
        self, deployment: Deployment, status: DeploymentStatus
    ) -> List[Dict[str, Any]]:
        """Download the manifest artifact and resolve the component steps."""
        await self.deployments_client.update_deployment_status(
            self.device.auth_token, deployment.id, DeploymentState.DOWNLOADING
        )

        artifact = await self.deployments_client.fetch_artifact(deployment.artifact_uri)
        steps = None
        if artifact is not None:
            try:
                plan = parse_manifest_artifact(artifact)
                steps = plan_component_updates(self.device.components_data, plan)
            except ManifestError as e:
                logger.warning(
                    f"Device {self.device.device_id} could not parse manifest "
                    f"{deployment.artifact_name} ({e}); updating manifest "
                    "version only"
                )
        if steps is None:
            steps = []

        status.progress = 100
        await self.db.save_deployment_status(status)
        return steps

    async def _stage_install_components(
        self,
        deployment: Deployment,
        status: DeploymentStatus,
        steps: List[Dict[str, Any]],
    ) -> None:
        """Install components in manifest order; roll back on failure."""
        await self.deployments_client.update_deployment_status(
            self.device.auth_token, deployment.id, DeploymentState.INSTALLING
        )
        status.status = "installing"
        await self.db.save_deployment_status(status)

        success_rate = self.config.simulator.success_rate
        updated: List[Dict[str, Any]] = []

        for step in steps:
            comp_id = step["component_id"]
            if step["skip"]:
                logger.info(
                    f"Device {self.device.device_id} - component {comp_id} "
                    f"already at {step['to_version']}, skipping"
                )
                continue

            logger.info(
                f"Device {self.device.device_id} - updating component {comp_id} "
                f"({step['component_type']}) {step['from_version']} -> "
                f"{step['to_version']}"
            )
            # Per-component install time, kept short: a system may have many
            await asyncio.sleep(random.uniform(1, 3))

            if random.random() >= success_rate:
                await self._rollback_components(deployment, status, step, updated)
                return

            self.device.components_data[comp_id]["version"] = step["to_version"]
            updated.append(step)

        await self.deployments_client.update_deployment_status(
            self.device.auth_token, deployment.id, DeploymentState.REBOOTING
        )
        status.status = "rebooting"
        await self.db.save_deployment_status(status)
        await asyncio.sleep(random.uniform(2, 5))

        await self._stage_system_success(deployment, status, updated)

    async def _rollback_components(
        self,
        deployment: Deployment,
        status: DeploymentStatus,
        failed_step: Dict[str, Any],
        updated: List[Dict[str, Any]],
    ) -> None:
        """Restore already-updated components and report the failure."""
        comp_id = failed_step["component_id"]
        ctype = failed_step["component_type"]
        logger.warning(
            f"Device {self.device.device_id} - component {comp_id} ({ctype}) "
            f"failed, rolling back {len(updated)} component(s)"
        )

        for step in reversed(updated):
            self.device.components_data[step["component_id"]]["version"] = step[
                "from_version"
            ]

        await self.db.save_device(self.device)

        error_message = (
            f"component {comp_id} ({ctype}) failed to commit "
            f"{failed_step['to_version']}; rolled back to previous manifest"
        )
        logs = self._generate_orchestrator_logs(deployment, failed_step, updated)
        await self.deployments_client.update_deployment_status(
            self.device.auth_token,
            deployment.id,
            DeploymentState.FAILURE,
            substate=error_message[:128],
        )
        status.status = "failure"
        status.completed_at = datetime.utcnow()
        status.error_message = error_message
        await self.db.save_deployment_status(status)
        await self.deployments_client.send_deployment_logs(
            self.device.auth_token, deployment.id, logs
        )

    async def _stage_system_success(
        self,
        deployment: Deployment,
        status: DeploymentStatus,
        updated: List[Dict[str, Any]],
    ) -> None:
        """Report success and persist the new manifest + component versions."""
        logger.info(
            f"Device {self.device.device_id} - SUCCESS - Manifest "
            f"{deployment.artifact_name} applied ({len(updated)} component(s) "
            "updated)"
        )

        await self.deployments_client.update_deployment_status(
            self.device.auth_token, deployment.id, DeploymentState.SUCCESS
        )
        status.status = "success"
        status.completed_at = datetime.utcnow()
        await self.db.save_deployment_status(status)

        self.device.inventory_data["artifact_name"] = deployment.artifact_name
        await self.db.save_device(self.device)

        # Push inventory immediately so the System tab reflects the new state
        await self._update_inventory()

    def _generate_orchestrator_logs(
        self,
        deployment: Deployment,
        failed_step: Dict[str, Any],
        updated: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Generate orchestrator-style failure logs naming the component."""
        now = datetime.utcnow().isoformat() + "Z"
        comp_id = failed_step["component_id"]
        ctype = failed_step["component_type"]
        logs = [
            {
                "timestamp": now,
                "level": "info",
                "message": f"Installing manifest {deployment.artifact_name}",
            }
        ]
        for step in updated:
            logs.append(
                {
                    "timestamp": now,
                    "level": "info",
                    "message": (
                        f"Component {step['component_id']} "
                        f"({step['component_type']}) updated to "
                        f"{step['to_version']}"
                    ),
                }
            )
        logs.append(
            {
                "timestamp": now,
                "level": "error",
                "message": f"##### [{ctype}-interface] Failing ArtifactCommit",
            }
        )
        logs.append(
            {
                "timestamp": now,
                "level": "error",
                "message": (
                    f"Update failed: component {comp_id} ({ctype}) did not "
                    f"commit {failed_step['to_version']}"
                ),
            }
        )
        for step in reversed(updated):
            logs.append(
                {
                    "timestamp": now,
                    "level": "info",
                    "message": (
                        f"Rollback: component {step['component_id']} "
                        f"({step['component_type']}) restored to "
                        f"{step['from_version']}"
                    ),
                }
            )
        return logs
