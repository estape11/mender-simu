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

    def generate_inventory(self, device_id: str) -> Dict[str, Any]:
        """
        Generate device inventory based on industry profile.

        Args:
            device_id: The device identifier

        Returns:
            Inventory data dictionary
        """
        base_inventory = dict(self.config.inventory)

        # Add common attributes
        base_inventory["device_id"] = device_id
        base_inventory["industry"] = self.name
        base_inventory["simulator_version"] = "1.0.0"
        base_inventory["last_boot"] = datetime.utcnow().isoformat()

        # Add industry-specific dynamic attributes
        enrichers = {
            "automotive": self._enrich_automotive_inventory,
            "smart_buildings": self._enrich_smart_buildings_inventory,
            "medical": self._enrich_medical_inventory,
            "industrial_iot": self._enrich_industrial_inventory,
            "retail": self._enrich_retail_inventory,
        }

        enricher = enrichers.get(self.name)
        if enricher:
            enricher(base_inventory)

        return base_inventory

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
            "device_type": self.config.inventory.get("device_type", "automotive-gateway"),
        }

    def _generate_smart_buildings_identity(self, index: int) -> Dict[str, str]:
        """Generate MAC-based identity for smart buildings."""
        oui_prefixes = self.config.extra_config.get(
            "oui_prefixes", ["00:1A:2B", "DC:A6:32"]
        )
        oui = random.choice(oui_prefixes)
        device_part = ":".join([f"{random.randint(0, 255):02X}" for _ in range(3)])
        mac = f"{oui}:{device_part}"

        return {
            "mac": mac,
            "device_type": self.config.inventory.get("device_type", "building-controller"),
        }

    def _generate_medical_identity(self, index: int) -> Dict[str, str]:
        """Generate FDA-compliant identity for medical devices."""
        device_classes = self.config.extra_config.get("device_classes", ["II", "III"])
        device_class = random.choice(device_classes)
        serial = f"{index:08d}"

        fda_id = f"FDA-{device_class}-{serial}"

        return {
            "mac": self._generate_mac(),
            "fda_udi": fda_id,
            "serial_number": serial,
            "device_type": self.config.inventory.get("device_type", "medical-device"),
        }

    def _generate_industrial_identity(self, index: int) -> Dict[str, str]:
        """Generate plant/line/unit identity for industrial IoT."""
        plants = self.config.extra_config.get("plants", ["PLANT-A", "PLANT-B"])
        plant = random.choice(plants)
        line = random.randint(1, 10)
        unit = index % 100

        device_id = f"IND-{plant}-L{line:02d}-U{unit:03d}"

        return {
            "mac": self._generate_mac(),
            "plant_id": plant,
            "line": f"L{line:02d}",
            "unit": f"U{unit:03d}",
            "device_type": self.config.inventory.get("device_type", "industrial-gateway"),
        }

    def _generate_retail_identity(self, index: int) -> Dict[str, str]:
        """Generate POS terminal identity for retail."""
        regions = self.config.extra_config.get("regions", ["NA", "EU"])
        region = random.choice(regions)
        store = random.randint(1000, 9999)
        terminal = index % 100

        pos_id = f"POS-{region}-{store}-{terminal:02d}"

        return {
            "mac": self._generate_mac(),
            "pos_id": pos_id,
            "region": region,
            "store_id": str(store),
            "device_type": self.config.inventory.get("device_type", "pos-terminal"),
        }

    def _generate_generic_identity(self, index: int) -> Dict[str, str]:
        """Generate generic device identity."""
        return {
            "mac": self._generate_mac(),
            "serial": f"DEV-{index:08d}",
            "device_type": self.config.inventory.get("device_type", "generic-device"),
        }

    # Inventory enrichers

    def _enrich_automotive_inventory(self, inventory: Dict[str, Any]) -> None:
        """Add automotive-specific inventory attributes."""
        variants = self.config.inventory.get("oem_variant", ["standard"])
        inventory["oem_variant"] = random.choice(variants)
        inventory["odometer_km"] = random.randint(0, 200000)
        inventory["battery_voltage"] = round(random.uniform(11.5, 14.5), 2)

    def _enrich_smart_buildings_inventory(self, inventory: Dict[str, Any]) -> None:
        """Add smart building-specific inventory attributes."""
        zones = self.config.inventory.get("zone_types", ["hvac"])
        inventory["zone_type"] = random.choice(zones)
        inventory["floor"] = random.randint(1, 50)
        inventory["room_count"] = random.randint(1, 20)

    def _enrich_medical_inventory(self, inventory: Dict[str, Any]) -> None:
        """Add medical device-specific inventory attributes."""
        compliance = self.config.inventory.get("compliance", ["FDA-510k"])
        inventory["compliance_standards"] = compliance
        inventory["calibration_due"] = "2025-06-15"
        inventory["software_validated"] = True

    def _enrich_industrial_inventory(self, inventory: Dict[str, Any]) -> None:
        """Add industrial IoT-specific inventory attributes."""
        protocols = self.config.inventory.get("protocols", ["modbus"])
        inventory["supported_protocols"] = protocols
        inventory["plc_connected"] = random.choice([True, False])
        inventory["uptime_hours"] = random.randint(0, 8760)

    def _enrich_retail_inventory(self, inventory: Dict[str, Any]) -> None:
        """Add retail POS-specific inventory attributes."""
        modules = self.config.inventory.get("payment_modules", ["chip"])
        inventory["payment_modules"] = modules
        inventory["receipt_printer"] = random.choice([True, False])
        inventory["transactions_today"] = random.randint(0, 500)

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
