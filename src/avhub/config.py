"""Load devices and automations from a YAML config file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from avhub.automation.rules import Rule
from avhub.core.device import Device
from avhub.core.events import EventBus
from avhub.drivers import DRIVERS


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_devices(config: dict[str, Any], bus: EventBus) -> dict[str, Device]:
    devices: dict[str, Device] = {}
    for device_id, spec in (config.get("devices") or {}).items():
        spec = dict(spec)
        driver_name = spec.pop("driver")
        driver = DRIVERS.get(driver_name)
        if driver is None:
            raise ValueError(f"Device '{device_id}': unknown driver '{driver_name}'")
        devices[device_id] = driver(device_id, bus, **spec)
    return devices


def build_rules(config: dict[str, Any]) -> list[Rule]:
    return [Rule.from_dict(r) for r in (config.get("automations") or [])]
