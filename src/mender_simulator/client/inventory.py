"""Mender Inventory Client."""

import aiohttp
import logging
from typing import Dict, Any, List, Optional

from .exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class InventoryClient:
    """Handles device inventory updates with Mender server."""

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

    def _format_inventory(self, inventory_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format inventory data for Mender API.

        Mender expects inventory as a list of {name, value} objects.
        """
        formatted = []
        for key, value in inventory_data.items():
            if isinstance(value, list):
                # Lists are sent as-is
                formatted.append({"name": key, "value": value})
            elif isinstance(value, bool):
                formatted.append({"name": key, "value": str(value).lower()})
            else:
                formatted.append({"name": key, "value": str(value)})
        return formatted

    async def update_inventory(
        self,
        token: str,
        inventory_data: Dict[str, Any]
    ) -> bool:
        """
        Send inventory update to Mender server.

        Args:
            token: Authentication JWT token
            inventory_data: Device inventory attributes

        Returns:
            True if successful, False otherwise
        """
        await self._ensure_session()

        url = f"{self.server_url}/api/devices/v1/inventory/device/attributes"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        formatted_inventory = self._format_inventory(inventory_data)

        try:
            async with self._session.patch(
                url, json=formatted_inventory, headers=headers
            ) as response:
                if response.status == 200:
                    logger.debug("Inventory updated successfully")
                    return True
                elif response.status == 401:
                    logger.warning("Authentication token expired or invalid")
                    raise AuthenticationError("Token expired")
                else:
                    error_text = await response.text()
                    logger.error(f"Inventory update failed ({response.status}): {error_text}")
                    return False

        except aiohttp.ClientError as e:
            logger.error(f"Inventory update request failed: {e}")
            return False

    async def get_inventory(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get current device inventory from server.

        Args:
            token: Authentication JWT token

        Returns:
            Inventory data dict or None if failed
        """
        await self._ensure_session()

        url = f"{self.server_url}/api/devices/v1/inventory/device/attributes"

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            async with self._session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    # Convert from list format back to dict
                    return {item["name"]: item["value"] for item in data}
                else:
                    return None

        except aiohttp.ClientError as e:
            logger.error(f"Get inventory request failed: {e}")
            return None
