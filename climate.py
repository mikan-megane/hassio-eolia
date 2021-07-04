"""Sensor for the Eolia Network."""
import json
import requests
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

from requests.models import Response
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import *
from homeassistant.const import TEMP_CELSIUS

_LOGGER = logging.getLogger(__name__)

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

_PRESET_MODES = {
    "Stop": "オフ",
    "Heating": "暖房",
    "Cooling": "冷房",
    "Auto": "オート",
    "Dehumidifying": "ドライ",
    "CoolDehumidifying": "冷房除湿",
    "Nanoe": "ファンのみ",
    "ClothesDryer": "衣類乾燥",
    "Cleaning": "おそうじ",
    "NanoexCleaning": "おでかけクリーン",
}

_FAN_MODES = {0: "自動", 2: "1", 3: "2", 4: "3", 5: "4"}
_SWING_MODES = {
    "auto": "自動",
    "to_left": "左",
    "nearby_left": "ちょっと左",
    "front": "中央",
    "nearby_right": "ちょっと右",
    "to_right": "右",
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Eolia platform."""
    add_entities(
        [EoliaClimate(hass, config)],
        True,
    )


def get_key(dict, val):
    for key, value in dict.items():
        if val == value:
            return key
    return None


class EoliaClimate(ClimateEntity):
    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._session = requests.Session()
        self._id = config.get("id")
        self._pass = config.get("pass")
        self._appliance_id = quote(config.get("appliance_id"))
        self._temp = 25
        self._hass = hass
        self._name = DOMAIN
        self._json = {}
        self._operation_token = None
        self._login()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def min_temp(self):
        return 16

    @property
    def max_temp(self):
        return 30

    @property
    def target_temperature(self):
        return self._temp

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def hvac_mode(self):
        """Return the state of the sensor."""
        return _HVAC_MODES.get(self._json.get("operation_mode"), HVAC_MODE_OFF)

    @property
    def hvac_modes(self):
        """Return the state of the sensor."""
        return list(_HVAC_MODES.values())

    @property
    def preset_mode(self):
        """Return the state of the sensor."""
        return _PRESET_MODES.get(self._json.get("operation_mode"))

    @property
    def preset_modes(self):
        """Return the state of the sensor."""
        return list(_PRESET_MODES.values())

    @property
    def fan_mode(self):
        """Return the state of the sensor."""
        return _FAN_MODES.get(self._json.get("wind_volume"))

    @property
    def fan_modes(self):
        """Return the state of the sensor."""
        return list(_FAN_MODES.values())

    @property
    def swing_mode(self):
        """Return the state of the sensor."""
        return _SWING_MODES.get(self._json.get("wind_direction_horizon"))

    @property
    def swing_modes(self):
        """Return the state of the sensor."""
        return list(_SWING_MODES.values())

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        return self._json.get("inside_temp")

    @property
    def supported_features(self):
        return (
            SUPPORT_TARGET_TEMPERATURE
            | SUPPORT_PRESET_MODE
            | SUPPORT_FAN_MODE
            | SUPPORT_SWING_MODE
        )

    @property
    def extra_state_attributes(self):
        outside_temp = self._json.get("outside_temp")
        return {
            "inside_humidity": self._json.get("inside_humidity"),
            "inside_temp": self._json.get("inside_temp"),
            "outside_temp": None if outside_temp == 999 else outside_temp,
            "timer_value": self._json.get("timer_value"),
            "_json": self._json,
        }

    def update(self):
        """Update device state."""
        self._set_json(
            self._get(
                f"https://app.rac.apws.panasonic.com/eolia/v2/devices/{self._appliance_id}/status"
            ).json()
        )

    def set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVAC_MODE_OFF:
            self._json["operation_status"] = False
        else:
            self._json["operation_status"] = True
            self._json["operation_mode"] = get_key(_HVAC_MODES, hvac_mode)
        self._set_put()

    def set_preset_mode(self, preset_mode):
        if preset_mode == HVAC_MODE_OFF or preset_mode == "オフ":
            self._json["operation_status"] = False
        else:
            self._json["operation_status"] = True
            self._json["operation_mode"] = get_key(_PRESET_MODES, preset_mode)
        self._set_put()

    def set_fan_mode(self, fan_mode):
        self._json["wind_volume"] = get_key(_FAN_MODES, fan_mode)
        self._set_put()

    def set_swing_mode(self, swing_mode):
        self._json["wind_direction_horizon"] = get_key(_SWING_MODES, swing_mode)
        self._set_put()

    def set_temperature(self, **kwargs):
        self._temp = kwargs.get("temperature")
        self._set_put()

    def _set_put(self):
        self._json["temperature"] = "0"
        if self._json["operation_mode"] in ["Heating","Cooling","Auto","CoolDehumidifying"]:
            if self._temp < self.min_temp:
                self._temp = self.min_temp
            if self._temp > self.max_temp:
                self._temp = self.max_temp
            self._json["temperature"] = str(self._temp)
        self._set_json(
            self._put(
                f"https://app.rac.apws.panasonic.com/eolia/v2/devices/{self._appliance_id}/status",
                self._get_json(),
            ).json()
        )

    def _get_json(self):
        keys = set(
            [
                "nanoex",
                "operation_status",
                "airquality",
                "wind_volume",
                "temperature",
                "operation_mode",
                "wind_direction",
                "timer_value",
                "air_flow",
                "wind_direction_horizon",
            ]
        )
        json = dict(filter(lambda item: item[0] in keys, self._json.items()))
        if self._operation_token:
            json["operation_token"] = self._operation_token
            json["appliance_id"] = self._appliance_id
        return json

    def _set_json(self, json):
        if "operation_token" in json:
            self._operation_token = json.get("operation_token")
        if json.get("temperature") != 0:
            self._temp = json.get("temperature")
        self._json = json

    def _post(self, url, data) -> Response:
        _LOGGER.debug(json.dumps(data))
        result = self._session.post(url, json.dumps(data), headers=self._headers())
        _LOGGER.debug(result.text)
        if result.status_code == 401:
            self._login()
            result = self._post(url, data)
        return result

    def _get(self, url) -> Response:
        result = self._session.get(url, headers=self._headers())
        _LOGGER.debug(result.text)
        if result.status_code == 401:
            self._login()
            result = self._get(url)
        return result

    def _put(self, url, data) -> Response:
        _LOGGER.debug(json.dumps(data))
        result = self._session.put(url, json.dumps(data), headers=self._headers())
        _LOGGER.debug(result.text)
        if result.status_code == 401:
            self._login()
            result = self._put(url, data)
        return result

    def _headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/Json; charset=UTF-8",
            "User-Agent": "%E3%82%A8%E3%82%AA%E3%83%AA%E3%82%A2/38 CFNetwork/1209 Darwin/20.2.0",
            "Accept-Language": "ja-jp",
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
