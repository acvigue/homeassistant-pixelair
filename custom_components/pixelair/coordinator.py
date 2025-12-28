"""Data update coordinator for the PixelAir integration.

This module provides the PixelAirCoordinator class which manages
communication with PixelAir devices and coordinates state updates
across all entities.
"""

from __future__ import annotations

import logging

from libpixelair import DeviceMode, DeviceState, PixelAirDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MAC_ADDRESS,
    CONF_SERIAL_NUMBER,
    CONNECTION_TIMEOUT,
    DOMAIN,
    MANUFACTURER,
    POLL_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class PixelAirCoordinator(DataUpdateCoordinator[DeviceState]):
    """Coordinator to manage PixelAir device state updates.

    This coordinator uses the library's efficient state_counter-based polling:
    - Polls device every 2.5 seconds with lightweight discovery request
    - Only fetches full state when state_counter changes
    - State changes trigger callbacks that update the coordinator

    Attributes:
        device: The PixelAirDevice instance being managed.
        entry: The config entry for this device.
        mac_address: The device's MAC address.
        serial_number: The device's serial number.
        name: The device's display name.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        device: PixelAirDevice,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: The Home Assistant instance.
            device: The PixelAirDevice to coordinate.
            entry: The config entry for this device.
        """
        self.device = device
        self.entry = entry
        self.mac_address: str = entry.data.get(CONF_MAC_ADDRESS, "")
        self.serial_number: str = entry.data.get(CONF_SERIAL_NUMBER, "")
        self.name: str = entry.data.get(CONF_NAME, "PixelAir Device")
        self._state_callback_registered = False
        self._polling_started = False

        # No update_interval - we use the library's polling instead
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.serial_number}",
            update_interval=None,
        )

    async def async_start_polling(self) -> None:
        """Start the device polling and state callbacks.

        This registers a callback for state updates and starts
        the library's efficient state_counter-based polling.
        """
        if self._polling_started:
            return

        # Register state callback for updates
        if not self._state_callback_registered:
            self.device.add_state_callback(self._on_device_state_change)
            self._state_callback_registered = True
            _LOGGER.debug("Registered state callback for %s", self.name)

        # Start the library's efficient state_counter polling
        try:
            await self.device.start_polling(interval=POLL_INTERVAL)
            self._polling_started = True
            _LOGGER.debug("Started polling for %s", self.name)
        except Exception as err:
            _LOGGER.error("Failed to start polling for %s: %s", self.name, err)

    async def async_stop_polling(self) -> None:
        """Stop the device polling and remove state callbacks.

        Safe to call even if polling is not running.
        """
        # Stop polling
        if self._polling_started:
            try:
                await self.device.stop_polling()
                self._polling_started = False
                _LOGGER.debug("Stopped polling for %s", self.name)
            except Exception as err:
                _LOGGER.warning("Error stopping polling for %s: %s", self.name, err)

        # Remove state callback
        if self._state_callback_registered:
            self.device.remove_state_callback(self._on_device_state_change)
            self._state_callback_registered = False
            _LOGGER.debug("Removed state callback for %s", self.name)

    def _on_device_state_change(
        self, device: PixelAirDevice, new_state: DeviceState
    ) -> None:
        """Handle state change from device.

        This callback is invoked from the library's async context
        when the device state is updated (after state_counter changes).

        Args:
            device: The device that changed state.
            new_state: The new device state.
        """
        self.async_set_updated_data(new_state)

    def _update_optimistic_state(self) -> None:
        """Update coordinator with device's current optimistic state.

        The library updates its internal state optimistically after
        control commands. This method propagates that update to the
        coordinator and UI immediately for responsive feedback.
        """
        self.async_set_updated_data(self.device.state)

    async def _async_update_data(self) -> DeviceState:
        """Fetch data from the device.

        This is called for the initial refresh. Subsequent updates
        come via the polling mechanism and state callbacks.

        Returns:
            The current device state.

        Raises:
            UpdateFailed: If communication with the device fails.
        """
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
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information for the device registry.

        Returns:
            Device information including identifiers, name, manufacturer,
            model, firmware version, and network connection.
        """
        state = self.data

        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.mac_address)},
            name=state.nickname if state and state.nickname else self.name,
            manufacturer=MANUFACTURER,
            model=state.model if state else "PixelAir",
            sw_version=state.firmware_version if state else None,
            serial_number=self.serial_number,
            connections={(dr.CONNECTION_NETWORK_MAC, self.mac_address)},
        )

    async def async_turn_on(self) -> None:
        """Turn the device on.

        Raises:
            Exception: If the command fails.
        """
        await self.device.turn_on()
        self._update_optimistic_state()

    async def async_turn_off(self) -> None:
        """Turn the device off.

        Raises:
            Exception: If the command fails.
        """
        await self.device.turn_off()
        self._update_optimistic_state()

    async def async_set_brightness(self, brightness: float) -> None:
        """Set device brightness.

        Args:
            brightness: Brightness value from 0.0 to 1.0.

        Raises:
            Exception: If the command fails.
        """
        await self.device.set_brightness(brightness)
        self._update_optimistic_state()

    async def async_set_hue(self, hue: float) -> None:
        """Set device hue.

        Args:
            hue: Hue value from 0.0 to 1.0.

        Raises:
            Exception: If the command fails.
        """
        await self.device.set_hue(hue)
        self._update_optimistic_state()

    async def async_set_saturation(self, saturation: float) -> None:
        """Set device saturation.

        Args:
            saturation: Saturation value from 0.0 to 1.0.

        Raises:
            Exception: If the command fails.
        """
        await self.device.set_saturation(saturation)
        self._update_optimistic_state()

    async def async_set_effect(self, effect_id: str) -> None:
        """Set device effect by ID.

        Args:
            effect_id: The effect ID to set (e.g., "auto", "scene:0", "manual:1").

        Raises:
            Exception: If the command fails.
        """
        await self.device.set_effect(effect_id)
        self._update_optimistic_state()

    async def async_set_mode(self, mode: DeviceMode) -> None:
        """Set device mode.

        Args:
            mode: The device mode (AUTO, SCENE, or MANUAL).

        Raises:
            Exception: If the command fails.
        """
        await self.device.set_mode(mode)
        self._update_optimistic_state()
