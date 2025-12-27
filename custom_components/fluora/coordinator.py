"""Device coordinator for Fluora integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from libpixelair import PixelAirDevice, DeviceState, DeviceMode

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_MAC_ADDRESS,
    CONF_SERIAL_NUMBER,
    UPDATE_INTERVAL,
    CONNECTION_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class FluoraDeviceCoordinator(DataUpdateCoordinator[DeviceState]):
    """Coordinator to manage device state updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: PixelAirDevice,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.device = device
        self.entry = entry
        self.mac_address = entry.data.get(CONF_MAC_ADDRESS, "")
        self.serial_number = entry.data.get(CONF_SERIAL_NUMBER, "")
        self.name = entry.data.get(CONF_NAME, "Fluora Device")

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.serial_number}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> DeviceState:
        """Fetch data from the device."""
        try:
            # Try to resolve IP if needed (handles DHCP changes)
            try:
                await self.device.resolve_ip(timeout=CONNECTION_TIMEOUT)
            except Exception as err:
                _LOGGER.debug("Could not resolve IP for %s: %s", self.name, err)

            # Get current state
            state = await self.device.get_state(timeout=CONNECTION_TIMEOUT)
            if state is None:
                raise UpdateFailed("Failed to get device state")

            return state
        except Exception as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information for device registry."""
        state = self.data

        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.mac_address)},
            name=state.nickname if state and state.nickname else self.name,
            manufacturer="PixelAir",
            model=state.model if state else "PixelAir Device",
            sw_version=state.firmware_version if state else None,
            serial_number=self.serial_number,
            connections={(dr.CONNECTION_NETWORK_MAC, self.mac_address)},
        )

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        try:
            await self.device.turn_on()
            await self.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error turning on device: %s", err)
            raise

    async def async_turn_off(self) -> None:
        """Turn the device off."""
        try:
            await self.device.turn_off()
            await self.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error turning off device: %s", err)
            raise

    async def async_set_brightness(self, brightness: float) -> None:
        """Set device brightness (0.0-1.0)."""
        try:
            await self.device.set_brightness(brightness)
            await self.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error setting brightness: %s", err)
            raise

    async def async_set_hue(self, hue: float) -> None:
        """Set device hue (0.0-1.0)."""
        try:
            await self.device.set_hue(hue)
            await self.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error setting hue: %s", err)
            raise

    async def async_set_saturation(self, saturation: float) -> None:
        """Set device saturation (0.0-1.0)."""
        try:
            await self.device.set_saturation(saturation)
            await self.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error setting saturation: %s", err)
            raise

    async def async_set_effect(self, effect_id: str) -> None:
        """Set device effect by ID."""
        try:
            await self.device.set_effect(effect_id)
            await self.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error setting effect: %s", err)
            raise

    async def async_set_mode(self, mode: DeviceMode) -> None:
        """Set device mode."""
        try:
            await self.device.set_mode(mode)
            await self.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error setting mode: %s", err)
            raise
