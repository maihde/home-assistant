"""
Support for Radio Thermostat wifi-enabled home thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.radiotherm/

Example configuration for one thermostats:

    sensor:
      - platform: radiotherm
        host: 192.168.1.1

Example configuration for two thermostats:

    sensor:
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

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

SENSOR_TYPES = ['hvac_state']

SENSOR_UNITS = {}

# Active thermostat state (is it heating or cooling?).  In the future
# this should probably made into heat and cool binary sensors.
CODE_TO_TEMP_STATE = {0: 'idle', 1: 'heating', 2: 'cooling'}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): vol.All(cv.ensure_list, [cv.string])
})

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
            for s_type in SENSOR_TYPES:
                tstats.append(RadioThermostatBasicSensor(tstat, s_type))

        except OSError:
            _LOGGER.exception("Unable to connect to Radio Thermostat: %s",
                              host)
    add_devices(tstats, True)

class CachedRadioThermostat(object):
    _CACHE = {}
    _LOCK = threading.Lock()

    def __init__(self, device):
        super(CachedRadioThermostat, self).__setattr__("_device", device)
        super(CachedRadioThermostat, self).__setattr__("_name", None)

    @property
    def name(self):
        if self._name is None:
            super(CachedRadioThermostat, self).__setattr__("_name", self._device.name)
        return self._name
       
    @property
    def tstat(self):
        with RadioThermostatSensor._LOCK:
            # Check the cache
            state, last_updated = \
                RadioThermostatSensor._CACHE.get(self._device.host,
                                                       (None, None))

            now = datetime.datetime.now()
            tdelta = datetime.timedelta(seconds=10)

            if (state is None) or (last_updated is None):
                state = self._device.tstat
                last_updated = now
            else:
                time_since_last_updated = now - last_updated
                if time_since_last_updated > tdelta:
                    state = self._device.tstat
                    last_updated = datetime.datetime.now()

            # Update the cache
            RadioThermostatSensor._CACHE[self._device.host] = \
                    (state, last_updated)

        return state

    def __getattr__(self, attr):
        return getattr(self._device, attr)

    def __setattr__(self, attr, value):
        return setattr(self._device, attr, value)

class RadioThermostatSensor(Entity):
    _CACHE = {}
    _LOCK = threading.Lock()

    def __init__(self, device, variable):
        self.device = CachedRadioThermostat(device)
        self.variable = variable

        self._name = self.device.name['raw']

        self._state = False
        self._unit = None

    @property
    def name(self):
        return self._name + "." + self.variable

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def should_poll(self):
        return True

    @property
    def is_on(self):
        return self._state

    @property
    def available(self):
        return self._state is not None


class RadioThermostatBasicSensor(RadioThermostatSensor):
    """Representation a basic Nest sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        self._unit = SENSOR_UNITS.get(self.variable, None)

        if self.variable == 'hvac_state':
            self._state = CODE_TO_TEMP_STATE.get(self.device.tstat['raw']['tstate'])
        else:
            self._state = None
