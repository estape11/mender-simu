"""Tests for System tier devices (Mender Orchestrator)."""

import io
import json
import tarfile

import pytest

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
        # the first spec defaults to the system component (orchestrator >= 1.0.0)
        assert components["GW-001"]["system_component"] == "true"
        assert "system_component" not in components["R-001-1"]

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
        # required by the GA server (orchestrator >= 1.0.0 wire format)
        assert extras["mender-orchestrator-manifest.system_component"] == [
            "GW-001/true"
        ]
        assert extras["mender-orchestrator-manifest.manifest_name"] == [
            "GW-001/system-core-v1"
        ]

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
        # the system component carries the new manifest name after the update
        assert pushed["mender-orchestrator-manifest.manifest_name"] == [
            "GW-001/system-core-v2"
        ]

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


class TestSystemComponentConstraint:
    """Orchestrator >= 1.0.0: exactly one system component per topology."""

    def test_two_marked_system_components_rejected(self):
        config = make_system_config()
        for spec in config.industries["system_core"].components:
            spec["system_component"] = True

        with pytest.raises(ValueError, match="at most one component"):
            _validate_config(config)


class TestOrchestratorUseCases:
    """Tests for the EV vehicle and charging hub system profiles."""

    def _industry(self, name, **kw):
        base = dict(
            name=name,
            enabled=True,
            count=1,
            bandwidth_kbps=1000,
            id_prefix="X",
            id_format="X-{id}",
            tier="system",
        )
        base.update(kw)
        return IndustryConfig(**base)

    @pytest.fixture
    def ev_vehicle_profile(self):
        return IndustryProfile(
            self._industry(
                "ev_vehicle",
                system_type="ev-platform",
                inventory={"device_type": "vcu", "artifact_name": "ev-platform-v1"},
                components=[
                    {
                        "component_type": "vcu",
                        "id_format": "VCU-{site_id}",
                        "count": 1,
                        "initial_version": "vcu-os-v1",
                        "system_component": True,
                    },
                    {
                        "component_type": "bms",
                        "id_format": "BMS-{site_id}",
                        "count": 1,
                        "initial_version": "bms-fw-v1",
                        "attrs": {"bus": "can"},
                    },
                    {
                        "component_type": "inverter",
                        "id_format": "INV-{site_id}-{n}",
                        "count": 2,
                        "initial_version": "inv-fw-v1",
                    },
                    {
                        "component_type": "adas",
                        "id_format": "ADAS-{site_id}",
                        "count": 1,
                        "initial_version": "adas-fw-v1",
                    },
                ],
                extra_config={"manufacturers": ["5YJEV1"]},
            )
        )

    @pytest.fixture
    def charging_hub_profile(self):
        return IndustryProfile(
            self._industry(
                "charging_hub",
                system_type="ev-charging-hub",
                inventory={
                    "device_type": "hub-controller",
                    "artifact_name": "ev-charging-hub-v1",
                },
                components=[
                    {
                        "component_type": "site-controller",
                        "id_format": "SC-{site_id}",
                        "count": 1,
                        "initial_version": "hubctl-v1",
                        "system_component": True,
                    },
                    {
                        "component_type": "charge-point",
                        "id_format": "CP-{site_id}-{n}",
                        "count": 4,
                        "initial_version": "cp-fw-v1",
                    },
                    {
                        "component_type": "power-cabinet",
                        "id_format": "PWR-{site_id}",
                        "count": 1,
                        "initial_version": "pwr-fw-v1",
                    },
                ],
            )
        )

    def test_ev_vehicle_identity_is_vin(self, ev_vehicle_profile):
        identity = ev_vehicle_profile.generate_device_identity(0)

        assert len(identity["vin"]) == 17
        assert identity["vin"].startswith("5YJEV1")

    def test_ev_vehicle_components(self, ev_vehicle_profile):
        components = ev_vehicle_profile.generate_components(0)

        assert set(components.keys()) == {
            "VCU-001",
            "BMS-001",
            "INV-001-1",
            "INV-001-2",
            "ADAS-001",
        }
        assert components["VCU-001"]["system_component"] == "true"
        assert "system_component" not in components["BMS-001"]
        # el bus fisico declarado en la config viaja como atributo del componente
        assert components["BMS-001"]["bus"] == "can"
        # artifact_name queda verbatim (manifest), sin formateo device_type-version
        inventory = ev_vehicle_profile.generate_static_inventory("EV-x-0")
        assert inventory["artifact_name"] == "ev-platform-v1"
        assert "platform_rev" in inventory and "battery_soh_pct" in inventory

    def test_ev_vehicle_component_telemetry_non_realtime(self, ev_vehicle_profile):
        components = ev_vehicle_profile.generate_components(0)
        ev_vehicle_profile.update_component_telemetry(components)

        assert "cell_delta_mv" in components["BMS-001"]
        assert components["INV-001-1"]["thermal_derate_events"] == 0
        # los sensores ya inicializados solo derivan ocasionalmente
        before = components["BMS-001"]["cell_delta_mv"]
        import random as _r

        _r.seed(7)
        ev_vehicle_profile.update_component_telemetry(components)
        assert abs(components["BMS-001"]["cell_delta_mv"] - before) <= 3

    def test_charging_hub_components_and_telemetry(self, charging_hub_profile):
        identity = charging_hub_profile.generate_device_identity(0)
        assert identity["hub_id"] == "HUB-001"

        components = charging_hub_profile.generate_components(0)
        assert len(components) == 6
        assert components["SC-001"]["system_component"] == "true"
        assert {f"CP-001-{n}" for n in range(1, 5)} <= set(components.keys())

        charging_hub_profile.update_component_telemetry(components)
        assert components["CP-001-1"]["connector_status"] == "available"
        assert "sessions_total" in components["CP-001-3"]
        assert "sessions_total" not in components["PWR-001"]


class TestAuditFixes:
    """Regression tests for the code-review findings."""

    def test_order_not_integer_raises_manifest_error(self):
        bad = MANIFEST_YAML.replace("order: 20", 'order: "ten"')
        with pytest.raises(ManifestError, match="update_strategy.order"):
            parse_manifest_yaml(bad)

    def test_null_order_defaults_to_zero(self):
        plan = parse_manifest_yaml(MANIFEST_YAML.replace("{ order: 20 }", "{ order: }"))
        assert any(u.order == 0 for u in plan.updates)

    def test_system_tier_requires_components(self):
        config = make_system_config()
        config.industries["system_core"].components = []
        with pytest.raises(ValueError, match="at least one component"):
            _validate_config(config)

    def test_explicit_optout_without_system_component_rejected(self):
        config = make_system_config()
        config.industries["system_core"].components[0]["system_component"] = False
        with pytest.raises(ValueError, match="exactly one component"):
            _validate_config(config)

    def test_custom_tier_system_industry_keeps_manifest_name_verbatim(self):
        # system-ness must key on tier, not on the hardcoded profile names
        industry = IndustryConfig(
            name="wind_farm",
            enabled=True,
            count=1,
            bandwidth_kbps=1000,
            id_prefix="WF",
            id_format="WF-{serial}",
            inventory={"device_type": "turbine-ctl", "artifact_name": "wind-farm-v1"},
            tier="system",
            system_type="wind-farm",
            components=[
                {
                    "component_type": "controller",
                    "id_format": "CTL-{site_id}",
                    "count": 1,
                    "initial_version": "ctl-v1",
                }
            ],
        )
        inventory = IndustryProfile(industry).generate_static_inventory("WF-x-0")
        assert inventory["artifact_name"] == "wind-farm-v1"
        assert "rootfs-image.version" not in inventory


class TestManifestDeploymentFailurePaths:
    """Download failures and mid-install exceptions must never report success."""

    def _simulator(self, artifact):
        from mender_simulator.client.deployments import Deployment

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
        device.auth_token = "jwt"
        simulator = SystemDeviceSimulator(device, profile, config, db=FakeDB())
        simulator.deployments_client = FakeDeploymentsClient(artifact)
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

    async def test_download_failure_reports_failure_not_success(self):
        simulator, deployment = self._simulator(artifact=None)

        await simulator._process_deployment(deployment)

        assert simulator.deployments_client.statuses[-1] == "failure"
        # nothing changed on the device
        assert simulator.device.inventory_data["artifact_name"] == "system-core-v1"
        assert simulator.device.components_data["GW-001"]["version"] == "gateway-v1"

    async def test_unparseable_manifest_reports_failure_not_success(self):
        # Artifact downloads fine but is not a valid manifest -> FAILURE,
        # never SUCCESS with the installed-manifest version advanced.
        simulator, deployment = self._simulator(artifact=b"not a manifest tar")

        await simulator._process_deployment(deployment)

        assert simulator.deployments_client.statuses[-1] == "failure"
        assert simulator.device.inventory_data["artifact_name"] == "system-core-v1"
        assert simulator.device.components_data["GW-001"]["version"] == "gateway-v1"

    async def test_midinstall_exception_rolls_back_components(self):
        simulator, deployment = self._simulator(
            artifact=build_manifest_artifact(MANIFEST_YAML)
        )

        orig = simulator.deployments_client.update_deployment_status

        async def flaky(token, dep_id, state, substate=None):
            value = state.value if hasattr(state, "value") else state
            if value == "rebooting":
                raise RuntimeError("token expired mid-deployment")
            return await orig(token, dep_id, state, substate)

        simulator.deployments_client.update_deployment_status = flaky

        await simulator._process_deployment(deployment)

        # the failure was reported and every component was restored
        assert simulator.deployments_client.statuses[-1] == "failure"
        for comp in simulator.device.components_data.values():
            assert comp["version"] in ("gateway-v1", "rtos-v1", "rtos-v2")
        assert simulator.device.components_data["GW-001"]["version"] == "gateway-v1"
        assert simulator.device.components_data["R-001-1"]["version"] == "rtos-v1"
        assert simulator.device.inventory_data["artifact_name"] == "system-core-v1"


class TestRescaleAndBackfillRegressions:
    """Regressions for the index/rescale bugs found in the correctness audit."""

    def test_device_index_parsed_from_id(self):
        from mender_simulator.main import _device_index

        assert _device_index("GRID-grid_site-000006") == 6
        assert _device_index("SYS-system_core-000000") == 0
        assert _device_index("weird") == 0  # no crash on unexpected shape

    def test_backfill_uses_device_own_index_not_list_position(self):
        # Components backfilled from a device's own index must align with the
        # identity that same index produces — regardless of list position.
        from mender_simulator.main import _device_index

        profile = IndustryProfile(make_system_config().industries["system_core"])
        idx = _device_index("SYS-system_core-000006")
        assert idx == 6
        identity = profile.generate_device_identity(idx)  # -> SYS-007 (start=1)
        comps = profile.generate_components(idx)
        site = identity["system_id"].split("-", 1)[1]  # "007"
        # every component id carries the same site token as the identity
        assert all(site in cid for cid in comps)
        assert set(comps.keys()) == {f"GW-{site}", f"R-{site}-1", f"R-{site}-2"}


class TestAuditFixesRound2:
    """Regressions for the second correctness-audit batch."""

    def test_count_gt_1_without_n_placeholder_rejected(self):
        config = make_system_config()
        # rtos has count 2; break its id_format by removing {n}
        for c in config.industries["system_core"].components:
            if c["component_type"] == "rtos":
                c["id_format"] = "R-{site_id}"
        with pytest.raises(ValueError, match="id_format"):
            _validate_config(config)

    def test_simulator_version_not_hardcoded(self):
        from mender_simulator import __version__

        profile = IndustryProfile(make_system_config().industries["system_core"])
        inv = profile.generate_static_inventory("SYS-system_core-000000")
        assert inv["simulator_version"] == __version__
