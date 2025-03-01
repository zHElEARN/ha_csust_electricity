from homeassistant.core import HomeAssistant

from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    """设置组件"""
    hass.data[DOMAIN] = {}
    return True
