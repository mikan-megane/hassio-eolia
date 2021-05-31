"""Sensor for the Open Sky Network."""
import json
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

from requests.models import Response
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import *
from homeassistant.const import TEMP_CELSIUS

DOMAIN = "eolia"

SCAN_INTERVAL = timedelta(minutes=1)

_HVAC_MODES = {
    "Stop": HVAC_MODE_OFF,
    "Heating": HVAC_MODE_HEAT,
    "Cooling": HVAC_MODE_COOL,
    "Auto": HVAC_MODE_AUTO,
    "Dehumidifying": HVAC_MODE_DRY,
    "Nanoe": HVAC_MODE_FAN_ONLY,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Open Sky platform."""
    add_entities(
        [EoliaClimate(hass, config)],
        True,
    )


class EoliaClimate(ClimateEntity):
    """Open Sky Network Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._session = requests.Session()
        self._id = config.get("id")
        self._pass = config.get("pass")
        self._appliance_id = quote(config.get("appliance_id"))
        self._hass = hass
        self._name = DOMAIN
        self._json = {}
        self._login()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def hvac_mode(self):
        """Return the state of the sensor."""
        return _HVAC_MODES.get(self._json.get("operation_mode"))

    @property
    def hvac_modes(self):
        """Return the state of the sensor."""
        return list(_HVAC_MODES.values())

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        return self._json.get("temperature")

    @property
    def supported_features(self):
        # (
        #     SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE,
        #     SUPPORT_PRESET_MODE,
        #     SUPPORT_SWING_MODE,
        # )
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def extra_state_attributes(self):
        return {
            "inside_humidity": self._json.get("inside_humidity"),
            "inside_temp": self._json.get("inside_temp"),
            "outside_temp": self._json.get("outside_temp"),
        }

    def update(self):
        """Update device state."""
        self._json = self._get(
            f"https://app.rac.apws.panasonic.com/eolia/v2/devices/{self._appliance_id}/status"
        ).json()

    def set_hvac_mode(self, hvac_mode):
        self._json["operation_mode"] = _HVAC_MODES.keys()[
            _HVAC_MODES.values().index(hvac_mode)
        ]
        self._json = self._put(
            f"https://app.rac.apws.panasonic.com/eolia/v2/devices/{self._appliance_id}/status",
            self._json,
        )

    def set_temperature(self, **kwargs):
        print(kwargs)
        self._json = self._put(
            f"https://app.rac.apws.panasonic.com/eolia/v2/devices/{self._appliance_id}/status",
            self._json,
        )

    def _post(self, url, data) -> Response:
        result = self._session.post(url, json.dumps(data), headers=self._headers())
        print(result.text)
        if result.status_code == 401:
            self._login()
            result = self._post(url, data)
        return result

    def _get(self, url) -> Response:
        result = self._session.get(url, headers=self._headers())
        print(result.text)
        if result.status_code == 401:
            self._login()
            result = self._get(url)
        return result

    def _put(self, url, data) -> Response:
        result = self._session.post(url, json.dumps(data), headers=self._headers())
        print(result.text)
        if result.status_code == 401:
            self._login()
            result = self._put(url, data)
        return result

    def _headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/Json; charset=UTF-8",
            "x-eolia-date": str.split(
                datetime.now(tz=timezone(timedelta(hours=+9), "JST")).isoformat(), "."
            )[0],
        }

    def _login(self):
        return self._post(
            "https://app.rac.apws.panasonic.com/eolia/v2/auth/login",
            {
                "idpw": {
                    "id": self._id,
                    "pass": self._pass,
                    "terminal_type": 3,
                    "next_easy": "true",
                }
            },
        )
