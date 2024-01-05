"""Sensor for the Eolia Network."""
from datetime import datetime, timedelta, timezone
import json
import logging
from urllib.parse import quote

import aiohttp

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

_HVAC_MODES = {
    "Auto": HVACMode.AUTO,
    "Nanoe": HVACMode.FAN_ONLY,
    "Cooling": HVACMode.COOL,
    "Dehumidifying": HVACMode.DRY,
    "Heating": HVACMode.HEAT,
    "Stop": HVACMode.OFF,
}

_PRESET_MODES = {
    "Auto": "オート",
    "Nanoe": "ナノイー送風",
    "Blast": "送風",
    "Cooling": "冷房",
    "Dehumidifying": "ドライ",
    "Heating": "暖房",
    "CoolDehumidifying": "冷房除湿",
    "ClothesDryer": "衣類乾燥",
    "KeepMode": "ダブル温度設定",
    "Cleaning": "おそうじ",
    "NanoexCleaning": "おでかけクリーン",
    "Stop": "オフ",
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit climate."""
    async_add_entities(
        [
            EoliaClimate(
                entry.data["username"],
                entry.data["password"],
                entry.data["appliance_id"],
            )
        ]
    )


def get_key(_dict, val):
    """Return the key corresponding to the given value in the dictionary."""
    for key, value in _dict.items():
        if val == value:
            return key
    return None


class EoliaClimate(ClimateEntity):
    """Representation of a Eolia Network."""

    def __init__(self, username, password, appliance_id) -> None:
        """Initialize the sensor."""
        _LOGGER.debug("EoliaClimate init")
        _LOGGER.debug(
            {"username": username, "password": password, "appliance_id": appliance_id}
        )
        self._session = aiohttp.ClientSession()
        self._id = username
        self._pass = password
        self._appliance_id = quote(appliance_id)
        self._temp = 25.0
        self._name = DOMAIN
        self._json = {}
        self._operation_token = None
        self._login()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 16.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 30.0

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return self._temp

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def hvac_mode(self):  # -> Any:
        """Return the state of the sensor."""
        return _HVAC_MODES.get(self._json.get("operation_mode"), HVACMode.OFF)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the state of the sensor."""
        return list(_HVAC_MODES.values())

    @property
    def preset_mode(self) -> str | None:
        """Return the state of the sensor."""
        return _PRESET_MODES.get(self._json.get("operation_mode"))

    @property
    def preset_modes(self) -> list[str]:
        """Return the state of the sensor."""
        return list(_PRESET_MODES.values())

    @property
    def fan_mode(self) -> str | None:
        """Return the state of the sensor."""
        return _FAN_MODES.get(self._json.get("wind_volume"))

    @property
    def fan_modes(self) -> list[str]:
        """Return the state of the sensor."""
        return list(_FAN_MODES.values())

    @property
    def swing_mode(self) -> str | None:
        """Return the state of the sensor."""
        return _SWING_MODES.get(self._json.get("wind_direction_horizon"))

    @property
    def swing_modes(self) -> list[str]:
        """Return the state of the sensor."""
        return list(_SWING_MODES.values())

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._json.get("inside_temp")

    @property
    def supported_features(self):
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
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

    async def update(self):
        """Update device state."""
        self._set_json(
            await self._get(
                f"https://app.rac.apws.panasonic.com/eolia/v2/devices/{self._appliance_id}/status"
            ).json()
        )

    async def set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            self._json["operation_status"] = False
        else:
            self._json["operation_status"] = True
            self._json["operation_mode"] = get_key(_HVAC_MODES, hvac_mode)
        await self._set_put()

    async def set_preset_mode(self, preset_mode):
        if preset_mode in (HVACMode.OFF, "オフ"):
            self._json["operation_status"] = False
        else:
            self._json["operation_status"] = True
            self._json["operation_mode"] = get_key(_PRESET_MODES, preset_mode)
        await self._set_put()

    async def set_fan_mode(self, fan_mode):
        self._json["wind_volume"] = get_key(_FAN_MODES, fan_mode)
        await self._set_put()

    async def set_swing_mode(self, swing_mode):
        self._json["wind_direction_horizon"] = get_key(_SWING_MODES, swing_mode)
        await self._set_put()

    async def set_temperature(self, **kwargs):
        self._temp = kwargs.get("temperature")
        await self._set_put()

    async def _set_put(self):
        self._json["temperature"] = "0"
        if self._json["operation_mode"] in [
            "Heating",
            "Cooling",
            "Auto",
            "CoolDehumidifying",
        ]:
            if float(self._temp) < self.min_temp:
                self._temp = self.min_temp
            if float(self._temp) > self.max_temp:
                self._temp = self.max_temp
            self._json["temperature"] = str(self._temp)
        self._set_json(
            await self._put(
                f"https://app.rac.apws.panasonic.com/eolia/v2/devices/{self._appliance_id}/status",
                await self._get_json(),
            ).json()
        )

    def _get_json(self):
        keys = {
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
        }
        filtered_json = dict(filter(lambda item: item[0] in keys, self._json.items()))
        if self._operation_token:
            filtered_json["operation_token"] = self._operation_token
            filtered_json["appliance_id"] = self._appliance_id
        return json

    def _set_json(self, json_data):
        if "operation_token" in json_data:
            self._operation_token = json_data.get("operation_token")
        if json_data.get("temperature") != 0:
            self._temp = json_data.get("temperature")
        self._json = json_data

    async def _post(self, url, data):
        _LOGGER.debug(json.dumps(data))
        result = await self._session.post(
            url, json.dumps(data), headers=self._headers()
        )
        _LOGGER.debug(result)
        if result.status_code == 401:
            await self._login()
            result = await self._post(url, data)
        return result

    async def _get(self, url):
        result = await self._session.get(url, headers=self._headers())
        _LOGGER.debug(result.text)
        if result.status_code == 401:
            await self._login()
            result = await self._get(url)
        return result

    async def _put(self, url, data):
        _LOGGER.debug(json.dumps(data))
        result = await self._session.put(url, json.dumps(data), headers=self._headers())
        _LOGGER.debug(result.text)
        if result.status_code == 401:
            await self._login()
            result = await self._put(url, data)
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

    async def _login(self):
        return await self._post(
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
