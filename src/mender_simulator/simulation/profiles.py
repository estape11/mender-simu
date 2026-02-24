"""Industry profiles for device identity and inventory generation."""

import random
import string
import hashlib
from typing import Dict, Any, Tuple
from datetime import datetime

from ..utils.config import IndustryConfig


class IndustryProfile:
    """Generates realistic device identities and inventory for each industry."""

    def __init__(self, config: IndustryConfig):
        self.config = config
        self.name = config.name

    def generate_device_identity(self, index: int) -> Dict[str, str]:
        """
        Generate unique device identity based on industry.

        Args:
            index: Device index within this industry

        Returns:
            Identity data dictionary
        """
        generators = {
            "automotive": self._generate_automotive_identity,
            "smart_buildings": self._generate_smart_buildings_identity,
            "medical": self._generate_medical_identity,
            "industrial_iot": self._generate_industrial_identity,
            "retail": self._generate_retail_identity,
        }

        generator = generators.get(self.name, self._generate_generic_identity)
        return generator(index)

    def generate_static_inventory(self, device_id: str) -> Dict[str, Any]:
        """
        Generate static inventory attributes (called once at device creation).

        Args:
            device_id: The device identifier

        Returns:
            Static inventory data dictionary
        """
        base_inventory = dict(self.config.inventory)

        # Add common static attributes
        base_inventory["device_id"] = device_id
        base_inventory["industry"] = self.name
        base_inventory["simulator_version"] = "1.0.0"

        # Format artifact_name as {device_type}-{version} for Mender compatibility
        version = base_inventory.get("artifact_name", "unknown")
        device_type = base_inventory.get("device_type", "unknown")
        full_artifact_name = f"{device_type}-{version}"
        base_inventory["artifact_name"] = full_artifact_name
        base_inventory["rootfs-image.version"] = full_artifact_name

        # Add industry-specific static attributes
        enrichers = {
            "automotive": self._enrich_automotive_static,
            "smart_buildings": self._enrich_smart_buildings_static,
            "medical": self._enrich_medical_static,
            "industrial_iot": self._enrich_industrial_static,
            "retail": self._enrich_retail_static,
        }

        enricher = enrichers.get(self.name)
        if enricher:
            enricher(base_inventory)

        return base_inventory

    def update_telemetry(self, inventory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update telemetry/dynamic attributes (called on each poll).

        Args:
            inventory: Existing inventory to update

        Returns:
            Updated inventory with new telemetry values
        """
        # Update common dynamic attributes
        inventory["last_seen"] = datetime.utcnow().isoformat()

        # Add industry-specific telemetry
        updaters = {
            "automotive": self._update_automotive_telemetry,
            "smart_buildings": self._update_smart_buildings_telemetry,
            "medical": self._update_medical_telemetry,
            "industrial_iot": self._update_industrial_telemetry,
            "retail": self._update_retail_telemetry,
        }

        updater = updaters.get(self.name)
        if updater:
            updater(inventory)

        return inventory

    def calculate_download_time(self, content_length_bytes: int) -> float:
        """
        Calculate simulated download time based on virtual bandwidth.

        Args:
            content_length_bytes: Size of artifact in bytes

        Returns:
            Download time in seconds
        """
        bandwidth_bytes_per_sec = self.config.bandwidth_kbps * 1024
        if bandwidth_bytes_per_sec <= 0:
            return 1.0

        base_time = content_length_bytes / bandwidth_bytes_per_sec

        # Add some jitter (±10%)
        jitter = random.uniform(0.9, 1.1)
        return base_time * jitter

    # Identity generators

    def _generate_automotive_identity(self, index: int) -> Dict[str, str]:
        """Generate VIN-based identity for automotive."""
        manufacturers = self.config.extra_config.get(
            "manufacturers", ["WVWZZZ", "3VWDP7"]
        )
        manufacturer = random.choice(manufacturers)
        year = random.choice("ABCDEFGHJKLMNPRSTVWXY")  # VIN year codes
        serial = f"{index:06d}"

        vin = f"{manufacturer}{year}{serial}"[:17].ljust(17, "0")

        return {
            "mac": self._generate_mac(),
            "vin": vin,
        }

    def _generate_smart_buildings_identity(self, index: int) -> Dict[str, str]:
        """Generate identity for smart buildings."""
        oui_prefixes = self.config.extra_config.get(
            "oui_prefixes", ["00:1A:2B", "DC:A6:32"]
        )
        oui = random.choice(oui_prefixes)
        device_part = ":".join([f"{random.randint(0, 255):02X}" for _ in range(3)])
        mac = f"{oui}:{device_part}"
        serial_number = f"BMS{index:08d}"

        return {
            "mac": mac,
            "serial_number": serial_number,
        }

    def _generate_medical_identity(self, index: int) -> Dict[str, str]:
        """Generate identity for medical devices."""
        serial_number = f"MED{index:08d}"

        return {
            "mac": self._generate_mac(),
            "serial_number": serial_number,
        }

    def _generate_industrial_identity(self, index: int) -> Dict[str, str]:
        """Generate identity for industrial IoT."""
        serial_number = f"IND{index:08d}"

        return {
            "mac": self._generate_mac(),
            "serial_number": serial_number,
        }

    def _generate_retail_identity(self, index: int) -> Dict[str, str]:
        """Generate POS terminal identity for retail."""
        pos_sn = f"POS{index:08d}"

        return {
            "mac": self._generate_mac(),
            "pos_sn": pos_sn,
        }

    def _generate_generic_identity(self, index: int) -> Dict[str, str]:
        """Generate generic device identity."""
        return {
            "mac": self._generate_mac(),
            "serial": f"DEV-{index:08d}",
        }

    # Inventory enrichers

    # Static inventory enrichers (called once at device creation)

    def _enrich_automotive_static(self, inventory: Dict[str, Any]) -> None:
        """Add static automotive attributes."""
        variants = self.config.inventory.get("oem_variant", ["standard"])
        inventory["oem_variant"] = random.choice(variants)
        # Initial odometer value (will increment in telemetry)
        inventory["odometer_km"] = random.randint(0, 200000)

    def _enrich_smart_buildings_static(self, inventory: Dict[str, Any]) -> None:
        """Add static smart building attributes."""
        zones = self.config.inventory.get("zone_types", ["hvac"])
        inventory["zone_type"] = random.choice(zones)
        inventory["floor"] = random.randint(1, 50)
        inventory["room_count"] = random.randint(1, 20)

    def _enrich_medical_static(self, inventory: Dict[str, Any]) -> None:
        """Add static medical device attributes."""
        device_classes = self.config.extra_config.get("device_classes", ["II", "III"])
        inventory["fda_device_class"] = random.choice(device_classes)
        compliance = self.config.inventory.get("compliance", ["FDA-510k"])
        inventory["compliance_standards"] = compliance
        inventory["calibration_due"] = "2025-06-15"
        inventory["software_validated"] = True

    def _enrich_industrial_static(self, inventory: Dict[str, Any]) -> None:
        """Add static industrial IoT attributes."""
        plants = self.config.extra_config.get("plants", ["PLANT-A", "PLANT-B"])
        inventory["plant_id"] = random.choice(plants)
        inventory["line"] = f"L{random.randint(1, 10):02d}"
        inventory["unit"] = f"U{random.randint(0, 99):03d}"
        protocols = self.config.inventory.get("protocols", ["modbus"])
        inventory["supported_protocols"] = protocols
        inventory["plc_connected"] = random.choice([True, False])

    def _enrich_retail_static(self, inventory: Dict[str, Any]) -> None:
        """Add static retail POS attributes."""
        regions = self.config.extra_config.get("regions", ["NA", "EU"])
        inventory["region"] = random.choice(regions)
        inventory["store_id"] = str(random.randint(1000, 9999))
        modules = self.config.inventory.get("payment_modules", ["chip"])
        inventory["payment_modules"] = modules
        inventory["receipt_printer"] = random.choice([True, False])

    # Telemetry updaters (called on each poll)

    def _update_automotive_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update automotive telemetry."""
        # Increment odometer slightly (0-50 km per poll)
        current_km = inventory.get("odometer_km", 0)
        inventory["odometer_km"] = current_km + random.randint(0, 50)
        # Battery voltage fluctuates
        inventory["battery_voltage"] = round(random.uniform(11.8, 14.4), 2)
        # Engine status
        inventory["engine_running"] = random.choice([True, False])

    def _update_smart_buildings_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update smart building telemetry."""
        inventory["temperature_c"] = round(random.uniform(18.0, 26.0), 1)
        inventory["humidity_pct"] = random.randint(30, 70)
        inventory["hvac_mode"] = random.choice(["cooling", "heating", "idle", "fan"])

    def _update_medical_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update medical device telemetry."""
        inventory["patients_monitored"] = random.randint(0, 10)
        inventory["active_alerts"] = random.randint(0, 3)
        inventory["cpu_usage_pct"] = random.randint(10, 80)

    def _update_industrial_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update industrial IoT telemetry."""
        # Increment uptime
        current_uptime = inventory.get("uptime_hours", 0)
        inventory["uptime_hours"] = current_uptime + round(random.uniform(0, 1), 2)
        inventory["cpu_temp_c"] = random.randint(35, 75)
        inventory["messages_per_min"] = random.randint(10, 500)

    def _update_retail_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update retail POS telemetry."""
        # Transactions increment during the day
        current_tx = inventory.get("transactions_today", 0)
        inventory["transactions_today"] = current_tx + random.randint(0, 5)
        inventory["last_transaction_mins_ago"] = random.randint(0, 60)
        inventory["drawer_open"] = random.choice([True, False])

    # Helpers

    def _generate_mac(self) -> str:
        """Generate random MAC address."""
        return ":".join([f"{random.randint(0, 255):02X}" for _ in range(6)])

    def get_success_probability(self) -> float:
        """Get success probability for updates based on industry."""
        # Medical devices should have higher success rate (more stable)
        if self.name == "medical":
            return 0.95
        # Industrial devices may have more failures due to harsh environments
        if self.name == "industrial_iot":
            return 0.75
        # Default
        return 0.80
