"""Decommission locally-tracked simulated devices from the Mender server.

Reads the local SQLite database to enumerate device identities created by the
simulator, then looks them up on the Mender Management API and deletes them.

Usage:
    python -m mender_simulator.decommission -c /path/to/config.yaml [--yes]
"""

import argparse
import asyncio
import json
import logging
import sys
from typing import Dict, List, Optional, Tuple

import aiohttp
import aiosqlite

from .utils.config import load_config


logger = logging.getLogger("mender_simulator.decommission")

# Pagination limit for the management devauth endpoint.
PAGE_SIZE = 500


def _identity_key(identity: Dict[str, str]) -> Tuple[Tuple[str, str], ...]:
    """Return a hashable, order-independent key for an identity dict."""
    return tuple(sorted((str(k), str(v)) for k, v in identity.items()))


async def _load_local_identities(db_path: str) -> List[Dict[str, str]]:
    """Read all identity_data blobs from the local devices table."""
    identities: List[Dict[str, str]] = []
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute("SELECT identity_data FROM devices") as cursor:
            async for row in cursor:
                raw = row[0]
                try:
                    identities.append(json.loads(raw))
                except (TypeError, json.JSONDecodeError):
                    logger.warning("Skipping device with invalid identity_data: %r", raw)
    return identities


async def _fetch_server_devices(
    session: aiohttp.ClientSession,
    server_url: str,
    pat: str,
) -> List[Dict]:
    """Fetch every device on the tenant via the management API (paginated)."""
    headers = {"Authorization": f"Bearer {pat}"}
    devices: List[Dict] = []
    page = 1
    base = f"{server_url.rstrip('/')}/api/management/v2/devauth/devices"
    while True:
        url = f"{base}?page={page}&per_page={PAGE_SIZE}"
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(
                    f"Failed to list devices (HTTP {resp.status}): {body}"
                )
            batch = await resp.json()
        if not batch:
            break
        devices.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        page += 1
    return devices


async def _delete_device(
    session: aiohttp.ClientSession,
    server_url: str,
    pat: str,
    device_id: str,
) -> bool:
    url = f"{server_url.rstrip('/')}/api/management/v2/devauth/devices/{device_id}"
    headers = {"Authorization": f"Bearer {pat}"}
    async with session.delete(url, headers=headers) as resp:
        if resp.status in (204, 200, 404):
            return True
        body = await resp.text()
        logger.error("DELETE %s -> %s: %s", device_id, resp.status, body)
        return False


async def decommission(
    config_path: str,
    assume_yes: bool = False,
) -> int:
    """Decommission every local device on the server. Returns the process exit code."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    config = load_config(config_path)
    pat = config.server.personal_access_token
    server_url = config.server.url
    db_path = config.simulator.database_path

    if not pat:
        logger.warning(
            "personal_access_token is not configured; cannot decommission remote devices."
        )
        return 0

    try:
        local_identities = await _load_local_identities(db_path)
    except FileNotFoundError:
        logger.warning("Local database not found at %s; nothing to decommission.", db_path)
        return 0
    except aiosqlite.OperationalError as e:
        logger.warning("Cannot open local database %s: %s", db_path, e)
        return 0

    if not local_identities:
        logger.info("No devices recorded locally; nothing to decommission.")
        return 0

    local_keys = {_identity_key(i) for i in local_identities}
    logger.info(
        "Found %d local device(s) to decommission on %s",
        len(local_keys),
        server_url,
    )

    if not assume_yes:
        try:
            answer = input(
                f"Proceed with decommissioning {len(local_keys)} device(s)? [y/N] "
            ).strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("y", "yes"):
            logger.info("Aborted by user.")
            return 0

    async with aiohttp.ClientSession() as session:
        try:
            server_devices = await _fetch_server_devices(session, server_url, pat)
        except Exception as e:  # noqa: BLE001 - best-effort cleanup
            logger.error("Failed to list server devices: %s", e)
            return 1

        matched: List[str] = []
        for dev in server_devices:
            identity = dev.get("identity_data") or {}
            if _identity_key(identity) in local_keys:
                matched.append(dev.get("id"))

        if not matched:
            logger.info("No matching devices found on the server.")
            return 0

        logger.info("Deleting %d device(s) on the server...", len(matched))
        ok = 0
        fail = 0
        for device_id in matched:
            if not device_id:
                continue
            if await _delete_device(session, server_url, pat, device_id):
                ok += 1
            else:
                fail += 1

        logger.info("Decommission complete: %d succeeded, %d failed.", ok, fail)
        return 0 if fail == 0 else 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Decommission simulator devices from the Mender server."
    )
    parser.add_argument(
        "-c", "--config",
        default="/opt/mender-simulator/config/config.yaml",
        help="Path to configuration file.",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Do not prompt for confirmation.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    sys.exit(asyncio.run(decommission(args.config, assume_yes=args.yes)))


if __name__ == "__main__":
    main()
