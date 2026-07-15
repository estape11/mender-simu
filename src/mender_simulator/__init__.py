"""
Mender Fleet Simulator - Professional Device Simulator for Mender.io
"""

from importlib import metadata as _metadata
from pathlib import Path


def _read_version() -> str:
    """Resuelve la versión: paquete instalado primero, archivo VERSION en dev."""
    try:
        return _metadata.version("mender-simulator")
    except _metadata.PackageNotFoundError:
        version_file = Path(__file__).resolve().parents[2] / "VERSION"
        try:
            return version_file.read_text(encoding="utf-8").strip()
        except OSError:
            return "0.0.0"


__version__ = _read_version()
__author__ = "Mender Simulator Team"
