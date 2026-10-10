"""Industry profiles for device identity and inventory generation."""

import random
from typing import Dict, Any
from datetime import datetime

from ..utils.config import IndustryConfig
from .geo_data import random_land_location


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
            "ev_charging": self._generate_ev_charging_identity,
            "uas_airframe": self._generate_uas_airframe_identity,
            "uas_gcs": self._generate_uas_gcs_identity,
        }

        generator = generators.get(self.name, self._generate_generic_identity)
        return generator(index)

    def generate_static_inventory(
        self, device_id: str, poll_interval: int = 30
    ) -> Dict[str, Any]:
        """
        Generate static inventory attributes (called once at device creation).

        Args:
            device_id: The device identifier
            poll_interval: Polling interval in seconds

        Returns:
            Static inventory data dictionary
        """
        base_inventory = dict(self.config.inventory)

        # Add common static attributes
        base_inventory["device_id"] = device_id
        base_inventory["industry"] = self.name
        base_inventory["simulator_version"] = "1.2.0"
        base_inventory["poll_interval_seconds"] = poll_interval

        # Assign a random real-world (land-based) location and a hostname,
        # matching the inventory attribute names real Mender devices report.
        base_inventory.update(random_land_location())
        base_inventory["hostname"] = f"{self.name}-{device_id[:8]}"

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
            "ev_charging": self._enrich_ev_charging_static,
            "uas_airframe": self._enrich_uas_airframe_static,
            "uas_gcs": self._enrich_uas_gcs_static,
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
            "ev_charging": self._update_ev_charging_telemetry,
            "uas_airframe": self._update_uas_airframe_telemetry,
            "uas_gcs": self._update_uas_gcs_telemetry,
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

    def _generate_ev_charging_identity(self, index: int) -> Dict[str, str]:
        """Generate identity for EV charging stations."""
        networks = self.config.extra_config.get(
            "networks", ["NET-WEST", "NET-EAST", "NET-CENTRAL"]
        )
        network = random.choice(networks)
        station_id = f"ST{index // 4:05d}"  # 4 ports per station
        port_id = f"P{(index % 4) + 1}"
        evse_id = f"EVC-{network}-{station_id}-{port_id}"

        return {
            "mac": self._generate_mac(),
            "evse_id": evse_id,
        }

    def _generate_uas_airframe_identity(self, index: int) -> Dict[str, str]:
        """Generate tail-number identity for UAS airframes."""
        start = self.config.extra_config.get("tail_number_start", 140)
        tail_number = f"UAS-{start + index:04d}"

        return {
            "mac": self._generate_mac(),
            "tail_number": tail_number,
        }

    def _generate_uas_gcs_identity(self, index: int) -> Dict[str, str]:
        """Generate identity for ground control stations."""
        station_id = f"GCS-{index + 1:02d}"

        return {
            "mac": self._generate_mac(),
            "station_id": station_id,
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

    def _enrich_ev_charging_static(self, inventory: Dict[str, Any]) -> None:
        """Add static EV charging station attributes."""
        charger_types = self.config.inventory.get(
            "charger_types", ["ac-level2-7kW", "dc-fast-50kW"]
        )
        inventory["charger_type"] = random.choice(charger_types)
        protocols = self.config.inventory.get("protocols", ["ocpp-2.0.1"])
        inventory["supported_protocols"] = protocols
        connectors = self.config.inventory.get("connector_types", ["ccs2", "type2"])
        inventory["connector_type"] = random.choice(connectors)
        inventory["max_power_kw"] = random.choice([3, 7, 11, 22, 50, 150])
        inventory["location_type"] = random.choice(
            ["highway", "urban", "shopping-center", "workplace", "residential"]
        )
        inventory["sessions_total"] = random.randint(0, 50000)

    def _enrich_uas_airframe_static(self, inventory: Dict[str, Any]) -> None:
        """Add static UAS airframe attributes (OTA UAS fleet demo)."""
        # Mixed-version fleet: each airframe boots a different flight-os
        # release, so a group-targeted deployment has real work to do.
        os_name = self.config.extra_config.get("os_name", "flight-os")
        versions = self.config.extra_config.get("os_versions", ["2.1", "2.2", "2.3"])
        artifact = f"{os_name}-{random.choice(versions)}"
        inventory["artifact_name"] = artifact
        inventory["rootfs-image.version"] = artifact
        # A/B dual-rootfs layout with an encrypted data partition.
        inventory["update_scheme"] = "dual-rootfs-ab"
        inventory["active_partition"] = random.choice(["A", "B"])
        inventory["data_partition"] = "luks-encrypted-key-sealed-in-tpm"
        # Identity key held in hardware; only signed artifacts are installed.
        inventory["tpm_version"] = "2.0"
        inventory["identity_key_storage"] = "tpm"
        inventory["artifact_verification"] = "signed-only"
        # System composition: one aircraft, per-component versions and buses.
        inventory["flight_controller_version"] = random.choice(["4.1", "4.2"])
        inventory["gnss_receiver_version"] = "2.0"
        inventory["eo_ir_payload_version"] = random.choice(["1.7", "1.8"])
        inventory["battery_mgmt_version"] = random.choice(["6.0", "6.1"])
        inventory["mission_computer_version"] = random.choice(["3.1", "3.2"])
        inventory["component_buses"] = ["can", "uart", "ethernet", "smbus"]
        # Where the airframe operates and the link it polls over (outbound
        # HTTPS only; the environment determines the link type).
        environment, link = random.choice(
            [
                ("depot-maintenance", "wired-lan"),
                ("forward-deployed", "tactical-lte"),
                ("remote-outpost", "satcom"),
            ]
        )
        inventory["network_environment"] = environment
        inventory["link_type"] = link
        # Remotely managed configuration (Configure add-on).
        inventory["telemetry_rate_hz"] = 10
        inventory["geofence_profile"] = "training"
        inventory["datalink_channel"] = 4
        inventory["log_level"] = "info"
        inventory["flight_hours"] = random.randint(50, 1200)

    def _enrich_uas_gcs_static(self, inventory: Dict[str, Any]) -> None:
        """Add static ground control station attributes."""
        os_name = self.config.extra_config.get("os_name", "gcs-os")
        versions = self.config.extra_config.get("os_versions", ["4.8", "4.9", "5.0"])
        artifact = f"{os_name}-{random.choice(versions)}"
        inventory["artifact_name"] = artifact
        inventory["rootfs-image.version"] = artifact
        inventory["station_role"] = random.choice(["primary", "backup"])
        inventory["operator_seats"] = random.choice([1, 2])
        inventory["link_type"] = "wired-lan"

    # Dynamic attribute updaters (called on each poll)
    # Note: Mender is NOT a real-time telemetry system. These are device
    # status attributes that change infrequently, not sensor readings.

    def _update_automotive_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update automotive status attributes."""
        # Odometer only increments slowly (device status, not real-time)
        current_km = inventory.get("odometer_km", 0)
        inventory["odometer_km"] = current_km + random.randint(0, 10)

    def _update_smart_buildings_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update smart building status attributes."""
        # HVAC mode changes infrequently
        if random.random() < 0.1:  # 10% chance to change
            inventory["hvac_mode"] = random.choice(
                ["cooling", "heating", "idle", "auto"]
            )

    def _update_medical_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update medical device status attributes."""
        # Device operational status, not patient data
        pass  # Medical devices report static inventory only

    def _update_industrial_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update industrial IoT status attributes."""
        # Uptime increments (hours since last boot)
        current_uptime = inventory.get("uptime_hours", 0)
        inventory["uptime_hours"] = current_uptime + round(random.uniform(0.5, 1), 2)

    def _update_retail_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update retail POS status attributes."""
        # Device operational status only
        pass  # POS terminals report static inventory only

    def _update_ev_charging_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update EV charging station status attributes."""
        # Charging session counter increments slowly
        current_sessions = inventory.get("sessions_total", 0)
        if random.random() < 0.3:  # 30% chance of a new session since last poll
            inventory["sessions_total"] = current_sessions + 1
        # Charger availability status
        inventory["charger_status"] = random.choice(
            ["available", "charging", "available", "available", "faulted"]
        )

    def _update_uas_airframe_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update UAS airframe status attributes."""
        # Flight hours accumulate slowly between check-ins.
        current_hours = inventory.get("flight_hours", 0)
        inventory["flight_hours"] = round(current_hours + random.uniform(0, 0.5), 1)
        # Tactical and SATCOM links degrade now and then; wired stays nominal.
        if inventory.get("link_type") != "wired-lan" and random.random() < 0.15:
            inventory["link_status"] = "degraded"
        else:
            inventory["link_status"] = "nominal"

    def _update_uas_gcs_telemetry(self, inventory: Dict[str, Any]) -> None:
        """Update ground control station status attributes."""
        pass  # Ground stations report static inventory only

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
        # EV chargers in outdoor/public locations are prone to connectivity issues
        if self.name == "ev_charging":
            return 0.78
        # Default
        return 0.80
