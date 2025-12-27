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
        self._state_callback_registered = False

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.serial_number}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    def setup_state_callback(self) -> None:
        """Set up the state change callback from the device."""
        if not self._state_callback_registered:
            self.device.add_state_callback(self._on_device_state_change)
            self._state_callback_registered = True
            _LOGGER.debug("Registered state callback for %s", self.name)

    def remove_state_callback(self) -> None:
        """Remove the state change callback."""
        if self._state_callback_registered:
            self.device.remove_state_callback(self._on_device_state_change)
            self._state_callback_registered = False
            _LOGGER.debug("Removed state callback for %s", self.name)

    def _on_device_state_change(
        self, device: PixelAirDevice, new_state: DeviceState
    ) -> None:
        """Handle state change from device (called from library).

        This callback is invoked from the library's async context,
        so we can directly update the coordinator data.
        """
        self.async_set_updated_data(new_state)

    def _update_optimistic_state(self) -> None:
        """Update coordinator with device's current optimistic state.

        The library updates its internal state optimistically after
        control commands. This method propagates that update to the
        coordinator and UI immediately.
        """
        self.async_set_updated_data(self.device.state)

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
            # Immediately update with optimistic state
            self._update_optimistic_state()
        except Exception as err:
            _LOGGER.error("Error turning on device: %s", err)
            raise

    async def async_turn_off(self) -> None:
        """Turn the device off."""
        try:
            await self.device.turn_off()
            # Immediately update with optimistic state
            self._update_optimistic_state()
        except Exception as err:
            _LOGGER.error("Error turning off device: %s", err)
            raise

    async def async_set_brightness(self, brightness: float) -> None:
        """Set device brightness (0.0-1.0)."""
        try:
            await self.device.set_brightness(brightness)
            # Immediately update with optimistic state
            self._update_optimistic_state()
        except Exception as err:
            _LOGGER.error("Error setting brightness: %s", err)
            raise

    async def async_set_hue(self, hue: float) -> None:
        """Set device hue (0.0-1.0)."""
        try:
            await self.device.set_hue(hue)
            # Immediately update with optimistic state
            self._update_optimistic_state()
        except Exception as err:
            _LOGGER.error("Error setting hue: %s", err)
            raise

    async def async_set_saturation(self, saturation: float) -> None:
        """Set device saturation (0.0-1.0)."""
        try:
            await self.device.set_saturation(saturation)
            # Immediately update with optimistic state
            self._update_optimistic_state()
        except Exception as err:
            _LOGGER.error("Error setting saturation: %s", err)
            raise

    async def async_set_effect(self, effect_id: str) -> None:
        """Set device effect by ID."""
        try:
            await self.device.set_effect(effect_id)
            # Immediately update with optimistic state
            self._update_optimistic_state()
        except Exception as err:
            _LOGGER.error("Error setting effect: %s", err)
            raise

    async def async_set_mode(self, mode: DeviceMode) -> None:
        """Set device mode."""
        try:
            await self.device.set_mode(mode)
            # Immediately update with optimistic state
            self._update_optimistic_state()
        except Exception as err:
            _LOGGER.error("Error setting mode: %s", err)
            raise
