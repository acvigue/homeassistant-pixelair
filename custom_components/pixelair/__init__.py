"""The PixelAir integration.

This integration provides support for Light+Color PixelAir LED devices
(Fluora, Monos, etc.), enabling control of brightness, color (hue/saturation),
and effects through Home Assistant.

The integration uses a shared UDP listener for efficient communication
with multiple devices and implements state_counter-based polling to
minimize network traffic while maintaining responsive state updates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from libpixelair import PixelAirDevice, UDPListener

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_MAC_ADDRESS,
    CONF_SERIAL_NUMBER,
    CONNECTION_TIMEOUT,
    DOMAIN,
)
from .coordinator import PixelAirCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]

type PixelAirConfigEntry = ConfigEntry[PixelAirRuntimeData]


@dataclass
class PixelAirRuntimeData:
    """Runtime data for a PixelAir config entry.

    Attributes:
        device: The PixelAirDevice instance for this entry.
        coordinator: The data update coordinator for this entry.
    """

    device: PixelAirDevice
    coordinator: PixelAirCoordinator


@dataclass
class PixelAirDomainData:
    """Domain-wide data for the PixelAir integration.

    Attributes:
        listener: The shared UDP listener for all devices.
        listener_ref_count: Number of config entries using the listener.
    """

    listener: UDPListener | None = None
    listener_ref_count: int = 0


def get_domain_data(hass: HomeAssistant) -> PixelAirDomainData:
    """Get or create domain data for the PixelAir integration.

    Args:
        hass: The Home Assistant instance.

    Returns:
        The domain data instance.
    """
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = PixelAirDomainData()
    return hass.data[DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: PixelAirConfigEntry) -> bool:
    """Set up PixelAir from a config entry.

    This function initializes the shared UDP listener (if needed),
    connects to the device, creates the coordinator, and starts
    state polling.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry to set up.

    Returns:
        True if setup was successful.

    Raises:
        ConfigEntryNotReady: If the device cannot be reached.
    """
    _LOGGER.debug("Setting up PixelAir entry: %s", entry.entry_id)

    domain_data = get_domain_data(hass)

    # Start shared UDP listener if not already running
    if domain_data.listener is None:
        listener = UDPListener()
        await listener.start()
        domain_data.listener = listener
        _LOGGER.debug("Started shared UDP listener")

    domain_data.listener_ref_count += 1
    listener = domain_data.listener

    # Get device identifiers from config entry
    mac_address: str | None = entry.data.get(CONF_MAC_ADDRESS)
    serial_number: str | None = entry.data.get(CONF_SERIAL_NUMBER)
    name: str = entry.data.get(CONF_NAME, "PixelAir Device")

    if not mac_address or not serial_number:
        _LOGGER.error("Missing device identifiers for entry %s", entry.entry_id)
        raise ConfigEntryNotReady("Missing device identifiers")

    # Create device from stored identifiers
    try:
        device = await PixelAirDevice.from_identifiers(
            mac_address=mac_address,
            serial_number=serial_number,
            listener=listener,
            timeout=CONNECTION_TIMEOUT,
        )
        if device is None:
            raise ConfigEntryNotReady(f"Could not find device {name}")
    except ConfigEntryNotReady:
        raise
    except Exception as err:
        _LOGGER.error("Failed to connect to device %s: %s", name, err)
        raise ConfigEntryNotReady(f"Failed to connect to device: {err}") from err

    # Register device with listener to receive updates
    await device.register()

    # Get initial state
    try:
        await device.get_state(timeout=CONNECTION_TIMEOUT)
    except Exception as err:
        _LOGGER.warning("Failed to get initial state for %s: %s", name, err)

    # Create coordinator
    coordinator = PixelAirCoordinator(hass, device, entry)

    # Do initial refresh
    await coordinator.async_config_entry_first_refresh()

    # Start state_counter polling (efficient: only fetches full state when changes)
    await coordinator.async_start_polling()

    # Store runtime data using the modern pattern
    entry.runtime_data = PixelAirRuntimeData(device=device, coordinator=coordinator)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PixelAirConfigEntry) -> bool:
    """Unload a config entry.

    This function stops polling, unregisters the device, and cleans up
    the shared UDP listener if no more entries are using it.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry to unload.

    Returns:
        True if unload was successful.
    """
    _LOGGER.debug("Unloading PixelAir entry: %s", entry.entry_id)

    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Stop polling and clean up device
        runtime_data = entry.runtime_data
        if runtime_data:
            await runtime_data.coordinator.async_stop_polling()
            await runtime_data.device.unregister()

        # Decrease listener reference count
        domain_data = get_domain_data(hass)
        domain_data.listener_ref_count -= 1

        # Stop listener if no more entries are using it
        if domain_data.listener_ref_count <= 0:
            if domain_data.listener:
                await domain_data.listener.stop()
                _LOGGER.debug("Stopped shared UDP listener")
            domain_data.listener = None
            domain_data.listener_ref_count = 0

            # Clean up domain data
            hass.data.pop(DOMAIN, None)

    return unload_ok


async def async_migrate_entry(
    _hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Migrate old entry to new version.

    Args:
        hass: The Home Assistant instance.
        config_entry: The config entry to migrate.

    Returns:
        True if migration was successful.
    """
    _LOGGER.debug("Migrating from version %s", config_entry.version)
    return True
