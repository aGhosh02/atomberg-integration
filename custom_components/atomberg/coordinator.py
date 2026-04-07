"""Data update coordinator for the Atomberg integration."""

from datetime import timedelta
from logging import getLogger

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AtombergCloudAPI
from .const import CLOUD_POLL_INTERVAL, MANUFACTURER
from .device import ATTR_IS_ONLINE, AtombergDevice
from .udp_listener import UDPListener

_LOGGER = getLogger(__name__)


class AtombergDataUpdateCoordinator(DataUpdateCoordinator):
    """Atomberg data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: AtombergCloudAPI,
        udp_listener: UDPListener,
        config_entry: ConfigEntry,
    ) -> None:
        """Init data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{MANUFACTURER} Coordinator",
            config_entry=config_entry,
            update_interval=timedelta(seconds=CLOUD_POLL_INTERVAL),
        )

        self.api = api
        self.udp_listener = udp_listener
        self.devices = [
            AtombergDevice(data=data, api=self.api, config_entry=self.config_entry)
            for data in self.api.device_list.values()
        ]

        for device in self.devices:
            device.update_state({ATTR_IS_ONLINE: True})

        # Add callback on udp listener
        self.udp_listener.add_callback(self.config_entry, self.async_set_updated_data)

    async def _async_update_data(self) -> dict:
        """Fetch latest device states from the cloud API."""
        try:
            device_ids = list(self.api.device_list.keys())
            states = await self.api.async_get_device_state(device_ids)
        except Exception as err:
            raise UpdateFailed(f"Error fetching device state from cloud: {err}") from err

        if not states:
            raise UpdateFailed("Cloud API returned no device states")

        for state in states:
            device_id = state.pop("device_id", None)
            if not device_id:
                continue
            state.pop("is_online", None)
            for device in self.devices:
                if device.id == device_id:
                    device.update_state(state)
                    break

        return {"source": "cloud_poll"}
