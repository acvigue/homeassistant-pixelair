"""Config flow for Fluora integration."""

from __future__ import annotations

import logging
from typing import Any

from libpixelair import UDPListener, DiscoveryService, DiscoveredDevice
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_NAME

from .const import (
    DOMAIN,
    CONF_MAC_ADDRESS,
    CONF_SERIAL_NUMBER,
    DISCOVERY_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fluora."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: DiscoveredDevice | None = None
        self._listener: UDPListener | None = None

    async def _get_listener(self) -> UDPListener:
        """Get or create a UDP listener for discovery."""
        if self._listener is None:
            self._listener = UDPListener()
            await self._listener.start()
        return self._listener

    async def _cleanup_listener(self) -> None:
        """Clean up the UDP listener."""
        if self._listener is not None:
            await self._listener.stop()
            self._listener = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated discovery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # User clicked submit - start discovery
            return await self.async_step_discovery()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def async_step_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device discovery."""
        errors: dict[str, str] = {}

        try:
            listener = await self._get_listener()
            discovery = DiscoveryService(listener)

            # Discover devices with full info
            devices = await discovery.discover_with_info(
                timeout=DISCOVERY_TIMEOUT,
                state_timeout=DISCOVERY_TIMEOUT,
            )
            await self._cleanup_listener()

            if not devices:
                return self.async_abort(reason="no_devices_found")

            # Filter out already configured devices
            new_devices: list[DiscoveredDevice] = []
            for device in devices:
                if device.mac_address:
                    existing_entry = await self.async_set_unique_id(
                        device.mac_address.lower()
                    )
                    if existing_entry is None:
                        new_devices.append(device)
                    # Reset unique_id for next iteration
                    self._async_abort_entries_match({})

            if not new_devices:
                return self.async_abort(reason="all_devices_configured")

            # If only one device, go directly to confirmation
            if len(new_devices) == 1:
                self._discovered_device = new_devices[0]
                await self.async_set_unique_id(
                    self._discovered_device.mac_address.lower()
                )
                self._abort_if_unique_id_configured()
                return await self.async_step_confirm_discovery()

            # Multiple devices - let user select
            return await self.async_step_select_device(new_devices)

        except Exception as err:
            _LOGGER.error("Error during discovery: %s", err)
            await self._cleanup_listener()
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors=errors,
            )

    async def async_step_select_device(
        self, devices: list[DiscoveredDevice] | None = None
    ) -> ConfigFlowResult:
        """Handle device selection when multiple devices found."""
        if devices is None:
            return self.async_abort(reason="no_devices_found")

        # Store devices for selection
        self.context["devices"] = {
            device.serial_number: device for device in devices
        }

        device_options = {
            device.serial_number: f"{device.display_name} ({device.ip_address})"
            for device in devices
        }

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(device_options),
                }
            ),
        )

    async def async_step_select_device_submit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device selection submission."""
        if user_input is None:
            return self.async_abort(reason="no_device_selected")

        serial = user_input.get("device")
        devices = self.context.get("devices", {})
        self._discovered_device = devices.get(serial)

        if self._discovered_device is None:
            return self.async_abort(reason="device_not_found")

        await self.async_set_unique_id(self._discovered_device.mac_address.lower())
        self._abort_if_unique_id_configured()

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding the discovered device."""
        if self._discovered_device is None:
            return self.async_abort(reason="device_not_found")

        if user_input is not None:
            # User confirmed - create the entry
            return self.async_create_entry(
                title=self._discovered_device.display_name,
                data={
                    CONF_NAME: self._discovered_device.display_name,
                    CONF_MAC_ADDRESS: self._discovered_device.mac_address.lower(),
                    CONF_SERIAL_NUMBER: self._discovered_device.serial_number,
                },
            )

        # Show confirmation form
        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "name": self._discovered_device.display_name,
                "model": self._discovered_device.model or "Unknown",
                "serial": self._discovered_device.serial_number,
                "ip": self._discovered_device.ip_address,
            },
        )
