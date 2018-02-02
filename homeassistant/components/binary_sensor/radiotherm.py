"""
Support for Radio Thermostat wifi-enabled home thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.radiotherm/

Example configuration for one thermostats:

    binary_sensor:
      - platform: radiotherm
        host: 192.168.1.1

Example configuration for two thermostats:

    binary_sensor:
      - platform: radiotherm
        host:
            - 192.168.1.1
            - 192.168.1.2
"""
import asyncio
import datetime
import logging
import threading

import voluptuous as vol

REQUIREMENTS = ['radiotherm==1.3']

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_HOST
from homeassistant.components.sensor.radiotherm import RadioThermostatSensor

CLIMATE_BINARY_TYPES = ['fan']

def setup_platform(hass, config, add_devices, discovery_info=None):
    import radiotherm
    hosts = []
    if CONF_HOST in config:
        hosts = config[CONF_HOST]
    else:
        hosts.append(radiotherm.discover.discover_address())

    if hosts is None:
        _LOGGER.error("No Radiotherm Thermostats detected")

    tstats = []
    for host in hosts:
        try:
            _LOGGER.info("Connecting to radiotherm at %s", host)
            tstat = radiotherm.get_thermostat(host)
            for s_type in CLIMATE_BINARY_TYPES:
                tstats.append(RadioThermostatBinarySensor(tstat, s_type))

        except OSError:
            _LOGGER.exception("Unable to connect to Radio Thermostat: %s",
                              host)
    add_devices(tstats, True)


class RadioThermostatBinarySensor(RadioThermostatSensor, BinarySensorDevice):
    """Representation a basic Nest sensor."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    def update(self):
        if self.variable == 'fan':
            self._state = bool(self.device.tstat['raw']['fstate'])
        else:
            self._state = None
