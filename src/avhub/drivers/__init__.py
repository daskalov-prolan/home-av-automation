"""Device drivers. Register each driver here so it can be used from config.yaml."""

from avhub.core.device import Device
from avhub.drivers.denon_avr import DenonAvr

DRIVERS: dict[str, type[Device]] = {
    "denon_avr": DenonAvr,
}

__all__ = ["DRIVERS"]
