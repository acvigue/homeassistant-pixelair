"""The Fluora integration."""

from __future__ import annotations

import logging

from libpixelair import UDPListener, PixelAirDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN,
    CONF_MAC_ADDRESS,
    CONF_SERIAL_NUMBER,
    CONNECTION_TIMEOUT,
)
from .coordinator import FluoraDeviceCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fluora from a config entry."""
    _LOGGER.debug("Setting up Fluora entry: %s", entry.entry_id)

    # Initialize domain data if needed
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
            "listener": None,
            "listener_ref_count": 0,
        }

    # Start shared UDP listener if not already running
    if hass.data[DOMAIN]["listener"] is None:
        listener = UDPListener()
        await listener.start()
        hass.data[DOMAIN]["listener"] = listener
        _LOGGER.debug("Started shared UDP listener")

    hass.data[DOMAIN]["listener_ref_count"] += 1
    listener: UDPListener = hass.data[DOMAIN]["listener"]

    # Get device identifiers from config entry
    mac_address = entry.data.get(CONF_MAC_ADDRESS)
    serial_number = entry.data.get(CONF_SERIAL_NUMBER)
    name = entry.data.get(CONF_NAME, "Fluora Device")

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
    coordinator = FluoraDeviceCoordinator(hass, device, entry)

    # Do initial refresh
    await coordinator.async_config_entry_first_refresh()

    # Store entry-specific data
    hass.data[DOMAIN][entry.entry_id] = {
        "device": device,
        "coordinator": coordinator,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Fluora entry: %s", entry.entry_id)

    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Unregister and clean up device
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if entry_data:
            device: PixelAirDevice = entry_data.get("device")
            if device:
                await device.unregister()

        # Decrease listener reference count
        hass.data[DOMAIN]["listener_ref_count"] -= 1

        # Stop listener if no more entries are using it
        if hass.data[DOMAIN]["listener_ref_count"] <= 0:
            listener: UDPListener = hass.data[DOMAIN]["listener"]
            if listener:
                await listener.stop()
                _LOGGER.debug("Stopped shared UDP listener")
            hass.data[DOMAIN]["listener"] = None
            hass.data[DOMAIN]["listener_ref_count"] = 0

            # Clean up domain data if empty
            if len(hass.data[DOMAIN]) <= 2:  # Only listener keys remain
                hass.data.pop(DOMAIN, None)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)
    return True
