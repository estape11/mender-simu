"""Mender Deployments Client."""

import aiohttp
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from .exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class DeploymentState(Enum):
    """Possible deployment states."""
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    REBOOTING = "rebooting"
    SUCCESS = "success"
    FAILURE = "failure"
    ALREADY_INSTALLED = "already-installed"


@dataclass
class Deployment:
    """Represents a pending deployment."""
    id: str
    artifact_name: str
    artifact_uri: str
    artifact_size: int


class DeploymentsClient:
    """Handles deployment checks and status updates with Mender server."""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip('/')
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _ensure_session(self) -> None:
        """Ensure HTTP session is created."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def check_for_deployment(
        self,
        token: str,
        device_type: str,
        artifact_name: str
    ) -> Optional[Deployment]:
        """
        Check for pending deployments.

        Args:
            token: Authentication JWT token
            device_type: Current device type
            artifact_name: Currently installed artifact

        Returns:
            Deployment object if available, None otherwise
        """
        await self._ensure_session()

        url = f"{self.server_url}/api/devices/v1/deployments/device/deployments/next"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        params = {
            "device_type": device_type,
            "artifact_name": artifact_name
        }

        try:
            async with self._session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    artifact = data.get("artifact", {})

                    deployment = Deployment(
                        id=data.get("id", ""),
                        artifact_name=artifact.get("artifact_name", ""),
                        artifact_uri=artifact.get("source", {}).get("uri", ""),
                        artifact_size=artifact.get("source", {}).get("size", 0)
                    )

                    logger.info(f"Deployment available: {deployment.artifact_name}")
                    return deployment

                elif response.status == 204:
                    # No deployment available
                    return None
                elif response.status == 401:
                    logger.warning("Authentication token expired or invalid")
                    raise AuthenticationError("Token expired")
                else:
                    error_text = await response.text()
                    logger.error(f"Deployment check failed ({response.status}): {error_text}")
                    return None

        except aiohttp.ClientError as e:
            logger.error(f"Deployment check request failed: {e}")
            return None

    async def update_deployment_status(
        self,
        token: str,
        deployment_id: str,
        state: DeploymentState,
        substate: Optional[str] = None
    ) -> bool:
        """
        Update deployment status.

        Args:
            token: Authentication JWT token
            deployment_id: Deployment ID
            state: New deployment state
            substate: Optional substate message

        Returns:
            True if successful, False otherwise
        """
        await self._ensure_session()

        url = f"{self.server_url}/api/devices/v1/deployments/device/deployments/{deployment_id}/status"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload: Dict[str, Any] = {
            "status": state.value
        }
        if substate:
            payload["substate"] = substate

        try:
            async with self._session.put(url, json=payload, headers=headers) as response:
                if response.status in (200, 204):
                    logger.debug(f"Deployment {deployment_id} status updated to {state.value}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Status update failed ({response.status}): {error_text}")
                    return False

        except aiohttp.ClientError as e:
            logger.error(f"Status update request failed: {e}")
            return False

    async def send_deployment_logs(
        self,
        token: str,
        deployment_id: str,
        logs: List[Dict[str, Any]]
    ) -> bool:
        """
        Send deployment logs to server.

        Args:
            token: Authentication JWT token
            deployment_id: Deployment ID
            logs: List of log entries with timestamp, level, message

        Returns:
            True if successful, False otherwise
        """
        await self._ensure_session()

        url = f"{self.server_url}/api/devices/v1/deployments/device/deployments/{deployment_id}/log"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "messages": logs
        }

        try:
            async with self._session.put(url, json=payload, headers=headers) as response:
                if response.status in (200, 204):
                    logger.debug(f"Logs sent for deployment {deployment_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Log upload failed ({response.status}): {error_text}")
                    return False

        except aiohttp.ClientError as e:
            logger.error(f"Log upload request failed: {e}")
            return False

    async def download_artifact(
        self,
        token: str,
        artifact_uri: str,
        progress_callback=None
    ) -> bool:
        """
        Simulate downloading an artifact (reads headers for size, doesn't actually download).

        Args:
            token: Authentication JWT token
            artifact_uri: URI to download artifact from
            progress_callback: Optional callback for progress updates

        Returns:
            True if artifact is accessible, False otherwise
        """
        await self._ensure_session()

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            async with self._session.head(artifact_uri, headers=headers) as response:
                if response.status == 200:
                    content_length = response.headers.get("Content-Length", "0")
                    logger.debug(f"Artifact accessible, size: {content_length} bytes")
                    return True
                else:
                    logger.error(f"Artifact not accessible ({response.status})")
                    return False

        except aiohttp.ClientError as e:
            logger.error(f"Artifact download check failed: {e}")
            return False
