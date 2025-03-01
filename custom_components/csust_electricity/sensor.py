import logging
import json
import requests
import re
import voluptuous as vol

from datetime import timedelta
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import QUERY_URL, HEADERS, CAMPUS_IDS

_LOGGER = logging.getLogger(__name__)

CONF_CAMPUS = "campus"
CONF_BUILDING_ID = "building_id"
CONF_ROOM_ID = "room_id"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = timedelta(hours=2)  # 默认查询间隔 2 小时

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CAMPUS): vol.In(CAMPUS_IDS.keys()),
        vol.Required(CONF_BUILDING_ID): cv.string,
        vol.Required(CONF_ROOM_ID): cv.string,
        vol.Optional(CONF_NAME, default="CSUST Electricity"): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            cv.time_period, vol.Range(min=timedelta(minutes=5))
        ),
    }
)


def fetch_electricity_data(campus, building_id, room_id):
    """获取指定宿舍的电量信息"""
    aid = CAMPUS_IDS.get(campus)
    if not aid:
        _LOGGER.error("未知校区: %s", campus)
        return None

    query_params = {
        "jsondata": {
            "query_elec_roominfo": {
                "aid": aid,
                "account": "000001",
                "room": {"roomid": room_id, "room": room_id},
                "floor": {"floorid": "", "floor": ""},
                "area": {"area": f"{campus}校区", "areaname": f"{campus}校区"},
                "building": {"buildingid": building_id, "building": ""},
            }
        },
        "funname": "synjones.onecard.query.elec.roominfo",
        "json": "true",
    }

    try:
        response = requests.post(
            QUERY_URL, headers=HEADERS, data={"jsondata": json.dumps(query_params["jsondata"]), "funname": query_params["funname"], "json": query_params["json"]}
        )
        response.raise_for_status()

        result = response.json()
        info = result.get("query_elec_roominfo", {})
        electricity: str = info.get("errmsg", "未知电量")

        match = re.search(r"(\d+(\.\d+)?)", electricity)
        return float(match.group()) if match else electricity

    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        _LOGGER.error("电量查询失败: %s", e)
        return None


def setup_platform(hass, config, add_entities, discovery_info=None):
    """设置平台"""
    name = config.get(CONF_NAME)
    campus = config.get(CONF_CAMPUS)
    building_id = config.get(CONF_BUILDING_ID)
    room_id = config.get(CONF_ROOM_ID)
    scan_interval = config.get(CONF_SCAN_INTERVAL)

    add_entities([CSUSTElectricitySensor(name, campus, building_id, room_id, scan_interval)], True)


class CSUSTElectricitySensor(Entity):
    """宿舍电费传感器"""

    def __init__(self, name, campus, building_id, room_id, scan_interval):
        self._name = name
        self._campus = campus
        self._building_id = building_id
        self._room_id = room_id
        self._state = None
        self._scan_interval = scan_interval

    @property
    def name(self):
        """返回传感器名称"""
        return self._name

    @property
    def state(self):
        """返回电量状态"""
        return self._state

    @property
    def unit_of_measurement(self):
        """返回单位"""
        return "kWh"

    @property
    def should_poll(self):
        """返回 True，表示 Home Assistant 应该定期调用 update()"""
        return True

    @property
    def scan_interval(self):
        """返回用户配置的查询间隔"""
        return self._scan_interval

    def update(self):
        """更新传感器数据"""
        _LOGGER.info("正在更新电量数据: %s - %s - %s", self._campus, self._building_id, self._room_id)
        self._state = fetch_electricity_data(self._campus, self._building_id, self._room_id)
