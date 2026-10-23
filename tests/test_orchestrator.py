"""Tests for System tier devices (Mender Orchestrator)."""

import io
import json
import tarfile

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mender_simulator.db.models import Device
from mender_simulator.simulation.manifest import (
    ManifestError,
    parse_manifest_yaml,
    extract_manifest_yaml,
    parse_manifest_artifact,
    plan_component_updates,
)
from mender_simulator.simulation.profiles import IndustryProfile
from mender_simulator.simulation.system_simulator import SystemDeviceSimulator
from mender_simulator.utils.config import (
    Config,
    IndustryConfig,
    ServerConfig,
    SimulatorConfig,
    _validate_config,
)

MANIFEST_YAML = """\
api_version: "mender/v1"
kind: "manifest"
name: "system-core-v2"
system_types_compatible: ["system-core"]
component_types:
  rtos:
    artifact_name: rtos-v2
    update_strategy: { order: 20 }
  gateway:
    artifact_name: gateway-v2
    update_strategy: { order: 10 }
"""


def build_manifest_artifact(yaml_text: str, gzip_payload: bool = True) -> bytes:
    """Build a minimal .mender artifact (tar) wrapping a manifest YAML."""

    def tar_bytes(members, mode):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode=mode) as tar:
            for name, data in members:
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return buf.getvalue()

    inner = tar_bytes(
        [("manifest.yaml", yaml_text.encode())], "w:gz" if gzip_payload else "w"
    )
    payload_name = "data/0000.tar.gz" if gzip_payload else "data/0000.tar"
    return tar_bytes(
        [("version", b'{"format":"mender","version":3}'), (payload_name, inner)],
        "w",
    )


class TestManifestParsing:
    """Tests for manifest extraction and parsing."""

    def test_parse_manifest_yaml_orders_updates(self):
        plan = parse_manifest_yaml(MANIFEST_YAML)

        assert plan.name == "system-core-v2"
        assert plan.system_types_compatible == ["system-core"]
        assert [(u.component_type, u.artifact_name) for u in plan.updates] == [
            ("gateway", "gateway-v2"),
            ("rtos", "rtos-v2"),
        ]

    def test_parse_manifest_yaml_rejects_non_manifest(self):
        with pytest.raises(ManifestError):
            parse_manifest_yaml("kind: release\nname: x")

    def test_parse_manifest_yaml_rejects_empty_components(self):
        with pytest.raises(ManifestError):
            parse_manifest_yaml("kind: manifest\nname: x\ncomponent_types: {}")

    def test_parse_manifest_yaml_rejects_invalid_yaml(self):
        with pytest.raises(ManifestError):
            parse_manifest_yaml("kind: [unclosed")

    @pytest.mark.parametrize("gzip_payload", [True, False])
    def test_extract_manifest_yaml_from_artifact(self, gzip_payload):
        artifact = build_manifest_artifact(MANIFEST_YAML, gzip_payload)

        assert extract_manifest_yaml(artifact) == MANIFEST_YAML

    def test_parse_manifest_artifact_end_to_end(self):
        plan = parse_manifest_artifact(build_manifest_artifact(MANIFEST_YAML))

        assert plan.name == "system-core-v2"
        assert len(plan.updates) == 2

    def test_extract_rejects_garbage(self):
        with pytest.raises(ManifestError):
            extract_manifest_yaml(b"not a tar archive at all")

    def test_extract_rejects_artifact_without_payload(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name="version")
            info.size = 2
            tar.addfile(info, io.BytesIO(b"{}"))
        with pytest.raises(ManifestError):
            extract_manifest_yaml(buf.getvalue())


class TestPlanComponentUpdates:
    """Tests for resolving a manifest plan against device components."""

    @pytest.fixture
    def components(self):
        return {
            "GW-001": {"component_type": "gateway", "version": "gateway-v1"},
            "R-001-1": {"component_type": "rtos", "version": "rtos-v1"},
            "R-001-2": {"component_type": "rtos", "version": "rtos-v2"},
            "WX-001": {"component_type": "weather-station", "version": "wx-fw-v1"},
        }

    def test_plan_orders_and_skips(self, components):
        plan = parse_manifest_yaml(MANIFEST_YAML)

        steps = plan_component_updates(components, plan)

        # gateway (order 10) first, then the two rtos
        assert [s["component_id"] for s in steps] == ["GW-001", "R-001-1", "R-001-2"]
        # R-001-2 already at target -> skip
        assert [s["skip"] for s in steps] == [False, False, True]
        # weather-station is not in the manifest -> untouched
        assert all(s["component_type"] != "weather-station" for s in steps)


def make_system_config(**overrides):
    industry = IndustryConfig(
        name="system_core",
        enabled=True,
        count=2,
        bandwidth_kbps=1000,
        id_prefix="SYS",
        id_format="SYS-{system_id}",
        inventory={"device_type": "gateway", "artifact_name": "system-core-v1"},
        tier="system",
        system_type="system-core",
        components=[
            {
                "component_type": "gateway",
                "id_format": "GW-{site_id}",
                "count": 1,
                "initial_version": "gateway-v1",
            },
            {
                "component_type": "rtos",
                "id_format": "R-{site_id}-{n}",
                "count": 2,
                "initial_version": "rtos-v1",
            },
        ],
        **overrides,
    )
    return Config(
        server=ServerConfig(url="https://test.mender.io", tenant_token="t"),
        simulator=SimulatorConfig(),
        industries={"system_core": industry},
        error_messages=["boom"],
    )


class TestSystemConfig:
    """Tests for tier/system config parsing and validation."""

    def test_valid_system_config_passes_validation(self):
        _validate_config(make_system_config())

    def test_invalid_tier_rejected(self):
        config = make_system_config()
        config.industries["system_core"].tier = "mega"

        with pytest.raises(ValueError, match="invalid tier"):
            _validate_config(config)

    def test_system_tier_requires_system_type(self):
        config = make_system_config()
        config.industries["system_core"].system_type = ""

        with pytest.raises(ValueError, match="requires system_type"):
            _validate_config(config)


class TestSystemProfile:
    """Tests for system profiles (identity + components)."""

    def test_system_core_identity(self):
        profile = IndustryProfile(make_system_config().industries["system_core"])

        identity = profile.generate_device_identity(0)

        assert identity["system_id"] == "SYS-001"

    def test_generate_components(self):
        profile = IndustryProfile(make_system_config().industries["system_core"])

        components = profile.generate_components(0)

        assert set(components.keys()) == {"GW-001", "R-001-1", "R-001-2"}
        assert components["GW-001"]["component_type"] == "gateway"
        assert components["GW-001"]["version"] == "gateway-v1"
        assert components["R-001-2"]["version"] == "rtos-v1"

    def test_grid_site_identity_and_component_telemetry(self):
        industry = IndustryConfig(
            name="grid_site",
            enabled=True,
            count=1,
            bandwidth_kbps=800,
            id_prefix="LV",
            id_format="GRID-SITE-{site_id}",
            inventory={"device_type": "grid-gateway", "artifact_name": "grid-site-v1"},
            tier="system",
            system_type="grid-monitoring-site",
            components=[
                {
                    "component_type": "line-sensor",
                    "id_format": "LS-{site_id}-{n}",
                    "count": 2,
                    "initial_version": "lsensor-fw-v1",
                }
            ],
            extra_config={"site_number_start": 401},
        )
        profile = IndustryProfile(industry)

        assert profile.generate_device_identity(0)["site_id"] == "GRID-SITE-0401"

        components = profile.generate_components(0)
        profile.update_component_telemetry(components)

        for comp in components.values():
            assert "conductor_temp_c" in comp
            assert "sag_m" in comp
        # system enricher reports the manifest name verbatim
        inventory = profile.generate_static_inventory("GRID-grid_site-000000")
        assert inventory["artifact_name"] == "grid-site-v1"
        assert "rootfs-image.version" not in inventory


class TestDeviceModel:
    """Tests for components_data persistence."""

    def test_components_data_roundtrip(self):
        device = Device(
            device_id="SYS-system_core-000000",
            identity_data={"mac": "AA:BB"},
            rsa_private_key="priv",
            rsa_public_key="pub",
            industry_profile="system_core",
            components_data={
                "GW-001": {"component_type": "gateway", "version": "gateway-v1"}
            },
        )

        data = device.to_dict()
        restored = Device.from_dict(data)

        assert json.loads(data["components_data"])["GW-001"]["version"] == "gateway-v1"
        assert restored.components_data == device.components_data

    def test_components_data_defaults_empty_for_old_rows(self):
        device = Device(
            device_id="D",
            identity_data={},
            rsa_private_key="p",
            rsa_public_key="p",
            industry_profile="automotive",
        )
        row = device.to_dict()
        row.pop("components_data")  # row from a pre-migration database

        assert Device.from_dict(row).components_data == {}


class TestSystemDeviceSimulator:
    """Tests for the System simulator inventory and logs."""

    @pytest.fixture
    def simulator(self):
        config = make_system_config()
        profile = IndustryProfile(config.industries["system_core"])
        device = Device(
            device_id="SYS-system_core-000000",
            identity_data={"mac": "AA:BB", "system_id": "SYS-001"},
            rsa_private_key="priv",
            rsa_public_key="pub",
            industry_profile="system_core",
            inventory_data={"artifact_name": "system-core-v1"},
            components_data=profile.generate_components(0),
        )
        return SystemDeviceSimulator(device, profile, config, db=None)

    def test_tier_is_system(self, simulator):
        assert simulator._tier == "system"

    def test_inventory_extras_wire_format(self, simulator):
        extras = simulator._inventory_extras()

        assert extras["system_type"] == "system-core"
        assert "mender-orchestrator-manifest" in extras["update_modules"]
        assert (
            extras["data-partition.mender-orchestrator-manifest.version"]
            == "system-core-v1"
        )
        assert sorted(extras["mender-orchestrator-manifest.component_id"]) == [
            "GW-001",
            "R-001-1",
            "R-001-2",
        ]
        assert "GW-001/gateway" in extras["mender-orchestrator-manifest.component_type"]
        assert "R-001-1/rtos-v1" in extras["mender-orchestrator-manifest.version"]

    def test_inventory_extras_custom_component_attrs(self, simulator):
        simulator.device.components_data["GW-001"]["serial_number"] = "SN42"

        extras = simulator._inventory_extras()

        assert extras["mender-orchestrator-manifest.serial_number"] == ["GW-001/SN42"]

    def test_orchestrator_failure_logs_name_component(self, simulator):
        from mender_simulator.client.deployments import Deployment

        deployment = Deployment(
            id="dep-1",
            artifact_name="system-core-v2",
            artifact_uri="https://x",
            artifact_size=1024,
        )
        failed = {
            "component_id": "R-001-1",
            "component_type": "rtos",
            "from_version": "rtos-v1",
            "to_version": "rtos-v2",
            "skip": False,
        }
        updated = [
            {
                "component_id": "GW-001",
                "component_type": "gateway",
                "from_version": "gateway-v1",
                "to_version": "gateway-v2",
                "skip": False,
            }
        ]

        logs = simulator._generate_orchestrator_logs(deployment, failed, updated)
        messages = [log["message"] for log in logs]

        assert any("Failing ArtifactCommit" in m for m in messages)
        assert any("R-001-1" in m and "rtos" in m for m in messages)
        assert any(
            "Rollback: component GW-001" in m and "gateway-v1" in m for m in messages
        )


class FakeDB:
    """Minimal async stand-in for DatabaseManager."""

    def __init__(self):
        self.deployment_statuses = []
        self.saved_devices = []

    async def save_deployment_status(self, status):
        self.deployment_statuses.append(status.status)

    async def update_device_status(self, device_id, status):
        pass

    async def save_device(self, device):
        self.saved_devices.append(device.device_id)

    async def update_last_poll(self, device_id):
        pass


class FakeDeploymentsClient:
    """Records status updates and serves a prebuilt manifest artifact."""

    def __init__(self, artifact_bytes):
        self.artifact_bytes = artifact_bytes
        self.statuses = []
        self.logs = None

    async def fetch_artifact(self, uri):
        return self.artifact_bytes

    async def update_deployment_status(self, token, dep_id, state, substate=None):
        self.statuses.append(state.value if hasattr(state, "value") else state)
        return True

    async def send_deployment_logs(self, token, dep_id, logs):
        self.logs = logs
        return True


class FakeInventoryClient:
    def __init__(self, replace_ok=True):
        self.last_inventory = None
        self.methods = []
        self.replace_ok = replace_ok

    async def update_inventory(self, token, inventory):
        self.methods.append("patch")
        self.last_inventory = inventory
        return True

    async def replace_inventory(self, token, inventory):
        self.methods.append("put")
        if not self.replace_ok:
            return False
        self.last_inventory = inventory
        return True


class TestManifestDeploymentFlow:
    """End-to-end manifest processing with fake clients (no network)."""

    def make_simulator(self, success_rate):
        from mender_simulator.client.deployments import Deployment

        config = make_system_config()
        config.simulator.success_rate = success_rate
        profile = IndustryProfile(config.industries["system_core"])
        device = Device(
            device_id="SYS-system_core-000000",
            identity_data={"mac": "AA:BB", "system_id": "SYS-001"},
            rsa_private_key="priv",
            rsa_public_key="pub",
            industry_profile="system_core",
            inventory_data={"artifact_name": "system-core-v1"},
            components_data=profile.generate_components(0),
        )
        device.auth_token = "jwt"
        simulator = SystemDeviceSimulator(device, profile, config, db=FakeDB())
        simulator.deployments_client = FakeDeploymentsClient(
            build_manifest_artifact(MANIFEST_YAML)
        )
        simulator.inventory_client = FakeInventoryClient()
        deployment = Deployment(
            id="dep-1",
            artifact_name="system-core-v2",
            artifact_uri="https://artifacts/x",
            artifact_size=2048,
        )
        return simulator, deployment

    @pytest.fixture(autouse=True)
    def fast_sleep(self, monkeypatch):
        import mender_simulator.simulation.system_simulator as mod

        async def no_sleep(_):
            pass

        monkeypatch.setattr(mod.asyncio, "sleep", no_sleep)

    async def test_manifest_success_updates_components(self):
        simulator, deployment = self.make_simulator(success_rate=1.0)

        await simulator._process_deployment(deployment)

        assert simulator.deployments_client.statuses[-1] == "success"
        components = simulator.device.components_data
        assert components["GW-001"]["version"] == "gateway-v2"
        assert components["R-001-1"]["version"] == "rtos-v2"
        assert simulator.device.inventory_data["artifact_name"] == "system-core-v2"
        # inventory pushed immediately with the new manifest version
        pushed = simulator.inventory_client.last_inventory
        assert (
            pushed["data-partition.mender-orchestrator-manifest.version"]
            == "system-core-v2"
        )

    async def test_manifest_failure_rolls_back_components(self):
        simulator, deployment = self.make_simulator(success_rate=0.0)

        await simulator._process_deployment(deployment)

        assert simulator.deployments_client.statuses[-1] == "failure"
        # first component (gateway, order 10) failed -> nothing changed
        components = simulator.device.components_data
        assert components["GW-001"]["version"] == "gateway-v1"
        assert components["R-001-1"]["version"] == "rtos-v1"
        assert simulator.device.inventory_data["artifact_name"] == "system-core-v1"
        # failure logs name the culprit component
        messages = [log["message"] for log in simulator.deployments_client.logs]
        assert any("GW-001" in m and "gateway" in m for m in messages)

    async def test_inventory_submitted_via_put_with_patch_fallback(self):
        simulator, deployment = self.make_simulator(success_rate=1.0)

        await simulator._process_deployment(deployment)
        assert "put" in simulator.inventory_client.methods
        assert "patch" not in simulator.inventory_client.methods

        # If the full replace fails, the device falls back to PATCH
        simulator.inventory_client = FakeInventoryClient(replace_ok=False)
        await simulator._update_inventory()
        assert simulator.inventory_client.methods == ["put", "patch"]

    async def test_check_deployment_reports_system_type_as_device_type(self):
        simulator, _ = self.make_simulator(success_rate=1.0)
        seen = {}

        class FakeDeps:
            async def check_for_deployment(self, token, provides):
                seen.update(provides)
                return None

        simulator.deployments_client = FakeDeps()
        await simulator._check_deployment()

        # Manifest matching is the device_type check against the system type
        assert seen["device_type"] == "system-core"
        assert seen["system_type"] == "system-core"
        assert (
            seen["data-partition.mender-orchestrator-manifest.version"]
            == "system-core-v1"
        )
