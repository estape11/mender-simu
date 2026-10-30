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

        # Orchestrator >= 1.0.0 attaches the installed manifest name to the
        # system component; the GA server requires it (and system_component)
        # or the inventory PUT fails with 500.
        system_comp = next(
            (cid for cid, c in components.items() if c.get("system_component")),
            None,
        )
        if system_comp:
            installed = self.device.inventory_data.get("artifact_name", "")
            extras[ATTR_PREFIX + "manifest_name"] = [f"{system_comp}/{installed}"]

        return extras

    async def _submit_inventory(self, inventory: Dict[str, Any]) -> bool:
        """Send inventory via full replace (PUT), like the real client.

        The server only ingests the orchestrator component attributes on
        full replaces; partial updates (PATCH) drop them by design. If the
        replace fails (e.g. server-side errors), fall back to PATCH so the
        device keeps reporting — only the System components view is lost.
        """
        success = await self.inventory_client.replace_inventory(
            self.device.auth_token, inventory
        )
        if not success:
            logger.warning(
                f"Device {self.device.device_id} inventory replace (PUT) "
                "failed; falling back to PATCH (components won't be ingested)"
            )
            return await self.inventory_client.update_inventory(
                self.device.auth_token, inventory
            )
        return True

    async def _check_deployment(self):
        """Check for deployments, declaring system provides.

        The orchestrator stack reports the SYSTEM TYPE as device_type in
        deployments/next: manifest artifacts carry the system type as their
        compatible type, so the classic device_type match is what serves
        them (verified against staging — with the plain device_type the
        server resolves `noartifact`). The inventory device_type is only
        display data and stays untouched (e.g. "gateway").
        """
        if not self.device.auth_token:
            return None

        industry_cfg = self.config.industries.get(self.device.industry_profile)
        installed = self.device.inventory_data.get("artifact_name", "unknown")
        device_provides = {
            "device_type": industry_cfg.system_type if industry_cfg else "unknown",
            "artifact_name": installed,
            "system_type": industry_cfg.system_type if industry_cfg else "",
            INSTALLED_MANIFEST_ATTR: installed,
        }

        return await self.deployments_client.check_for_deployment(
            self.device.auth_token, device_provides
        )

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
        if artifact is None:
            # Unlike a parse error (benign fallback below), a failed download
            # must surface as a deployment FAILURE, never a silent success.
            raise RuntimeError(
                f"manifest artifact download failed ({deployment.artifact_name})"
            )

        try:
            plan = parse_manifest_artifact(artifact)
            steps = plan_component_updates(self.device.components_data, plan)
        except ManifestError as e:
            # A downloaded-but-unparseable manifest is a real failure: never
            # report SUCCESS and advance the installed-manifest version while
            # the components stay on their old versions (inconsistent state).
            raise RuntimeError(f"invalid manifest {deployment.artifact_name}: {e}")

        # Simulate the download pace from the virtual bandwidth, like the
        # base class does for standard devices
        download_time = max(
            self.profile.calculate_download_time(deployment.artifact_size), 1.0
        )
        progress_steps = 5
        for i in range(progress_steps):
            status.status = "downloading"
            status.progress = int((i + 1) / progress_steps * 100)
            await self.db.save_deployment_status(status)
            await asyncio.sleep(download_time / progress_steps)

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

        try:
            for step in steps:
                comp_id = step["component_id"]
                if step["skip"]:
                    logger.info(
                        f"Device {self.device.device_id} - component {comp_id} "
                        f"already at {step['to_version']}, skipping"
                    )
                    continue

                logger.info(
                    f"Device {self.device.device_id} - updating component "
                    f"{comp_id} ({step['component_type']}) "
                    f"{step['from_version']} -> {step['to_version']}"
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
        except Exception:
            # Unexpected error mid-install (e.g. token expiry): restore the
            # components already updated so the system never persists a
            # half-applied manifest, then let the caller report the failure.
            for step in reversed(updated):
                self.device.components_data[step["component_id"]]["version"] = step[
                    "from_version"
                ]
            await self.db.save_device(self.device)
            raise

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
