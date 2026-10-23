"""Parsing of Mender Orchestrator manifest artifacts.

A manifest artifact (`.mender`) is a tar archive whose payload
(`data/0000.tar` or `data/0000.tar.gz`) contains a single YAML file: the
manifest. The manifest declares the target `artifact_name` per
`component_type` and the update order (`update_strategy.order`).
"""

import io
import logging
import tarfile
from dataclasses import dataclass
from typing import Dict, List, Any

import yaml

logger = logging.getLogger(__name__)


class ManifestError(Exception):
    """Raised when a manifest artifact or YAML cannot be parsed."""


@dataclass
class ComponentUpdate:
    """Target state for one component type, in update order."""

    component_type: str
    artifact_name: str
    order: int


@dataclass
class ManifestPlan:
    """Parsed manifest: target versions per component type, ordered."""

    name: str
    system_types_compatible: List[str]
    updates: List[ComponentUpdate]


def parse_manifest_yaml(text: str) -> ManifestPlan:
    """Parse manifest YAML into an ordered update plan."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ManifestError(f"Invalid manifest YAML: {e}")

    if not isinstance(data, dict) or data.get("kind") != "manifest":
        raise ManifestError("Not a manifest document (missing kind: manifest)")

    component_types = data.get("component_types", {})
    if not isinstance(component_types, dict) or not component_types:
        raise ManifestError("Manifest has no component_types")

    updates = []
    for ctype, spec in component_types.items():
        spec = spec or {}
        strategy = spec.get("update_strategy") or {}
        updates.append(
            ComponentUpdate(
                component_type=ctype,
                artifact_name=spec.get("artifact_name", ""),
                order=int(strategy.get("order", 0)),
            )
        )
    updates.sort(key=lambda u: u.order)

    return ManifestPlan(
        name=data.get("name", ""),
        system_types_compatible=data.get("system_types_compatible", []),
        updates=updates,
    )


def extract_manifest_yaml(artifact_bytes: bytes) -> str:
    """Extract the manifest YAML text from a `.mender` artifact.

    The outer tar holds the payload at `data/0000.tar` (optionally gzipped);
    the inner tar's first regular file is the manifest YAML.
    """
    try:
        with tarfile.open(fileobj=io.BytesIO(artifact_bytes), mode="r:*") as outer:
            payload_member = next(
                (
                    m
                    for m in outer.getmembers()
                    if m.isfile() and m.name.startswith("data/0000.tar")
                ),
                None,
            )
            if payload_member is None:
                raise ManifestError("Artifact has no data/0000.tar payload")
            payload = outer.extractfile(payload_member).read()

        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as inner:
            yaml_member = next((m for m in inner.getmembers() if m.isfile()), None)
            if yaml_member is None:
                raise ManifestError("Manifest payload is empty")
            return inner.extractfile(yaml_member).read().decode("utf-8")
    except tarfile.TarError as e:
        raise ManifestError(f"Invalid artifact archive: {e}")


def parse_manifest_artifact(artifact_bytes: bytes) -> ManifestPlan:
    """Extract and parse the manifest from a `.mender` artifact."""
    return parse_manifest_yaml(extract_manifest_yaml(artifact_bytes))


def plan_component_updates(
    components_data: Dict[str, Dict[str, Any]], plan: ManifestPlan
) -> List[Dict[str, Any]]:
    """Resolve a manifest plan against a device's components.

    Returns one entry per component, in update order:
    {component_id, component_type, from_version, to_version, skip}
    Components already at the target version are marked skip (left alone).
    Component types not mentioned in the manifest are not touched.
    """
    steps = []
    for update in plan.updates:
        for comp_id, comp in components_data.items():
            if comp.get("component_type") != update.component_type:
                continue
            current = comp.get("version", "")
            steps.append(
                {
                    "component_id": comp_id,
                    "component_type": update.component_type,
                    "from_version": current,
                    "to_version": update.artifact_name,
                    "skip": current == update.artifact_name,
                }
            )
    return steps
