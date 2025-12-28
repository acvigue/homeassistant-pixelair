"""Light platform for the PixelAir integration.

This module provides the PixelAirLight entity which represents a PixelAir
LED device as a light in Home Assistant. It supports brightness control,
hue/saturation color control, and effect selection.
"""

from __future__ import annotations

import logging
from typing import Any

from libpixelair import DeviceState

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PixelAirConfigEntry
from .coordinator import PixelAirCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PixelAirConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PixelAir light entities from a config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry to set up.
        async_add_entities: Callback to add entities.
    """
    coordinator = entry.runtime_data.coordinator
    async_add_entities([PixelAirLight(coordinator)])


class PixelAirLight(CoordinatorEntity[PixelAirCoordinator], LightEntity):
    """Representation of a PixelAir light entity.

    This entity provides control over a PixelAir LED device including:
    - On/off control
    - Brightness adjustment (0-100%)
    - Hue and saturation color control
    - Effect selection (Auto, Scenes, Manual animations)

    Attributes:
        _attr_has_entity_name: Entity uses device name as prefix.
        _attr_name: Entity name (None to use device name only).
        _attr_color_mode: The color mode (HS for hue/saturation).
        _attr_supported_color_modes: Set of supported color modes.
        _attr_supported_features: Supported light features.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, coordinator: PixelAirCoordinator) -> None:
        """Initialize the PixelAir light entity.

        Args:
            coordinator: The data update coordinator for this device.
        """
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.mac_address}_light"

    @property
    def device_info(self):
        """Return device information for the device registry."""
        return self.coordinator.device_info

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        The entity is available when the coordinator has successfully
        updated and has valid data.
        """
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        """Return True if the light is on."""
        state: DeviceState | None = self.coordinator.data
        if state is None:
            return False
        return state.is_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0-255).

        Converts from device brightness (0.0-1.0) to Home Assistant
        brightness scale (0-255).
        """
        state: DeviceState | None = self.coordinator.data
        if state is None:
            return None
        return round(state.brightness * 255)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value.

        Converts from device scale (0.0-1.0 for both) to Home Assistant
        scale (0-360 for hue, 0-100 for saturation).
        """
        state: DeviceState | None = self.coordinator.data
        if state is None:
            return None
        hue = state.hue * 360
        saturation = state.saturation * 100
        return (hue, saturation)

    @property
    def effect(self) -> str | None:
        """Return the current effect name."""
        state: DeviceState | None = self.coordinator.data
        if state is None:
            return None
        return state.current_effect

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of available effects."""
        state: DeviceState | None = self.coordinator.data
        if state is None:
            return None
        return state.effect_list

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on.

        Handles optional brightness, color, and effect parameters.
        The device is turned on after applying any other changes.

        Args:
            **kwargs: Optional parameters including:
                - ATTR_BRIGHTNESS: Brightness level (0-255)
                - ATTR_HS_COLOR: Tuple of (hue, saturation)
                - ATTR_EFFECT: Effect name to activate
        """
        # Handle brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            device_brightness = brightness / 255.0
            await self.coordinator.async_set_brightness(device_brightness)

        # Handle HS color
        if ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            hue = hs_color[0] / 360.0
            saturation = hs_color[1] / 100.0
            await self.coordinator.async_set_hue(hue)
            await self.coordinator.async_set_saturation(saturation)

        # Handle effect
        if ATTR_EFFECT in kwargs:
            effect_name = kwargs[ATTR_EFFECT]
            state: DeviceState | None = self.coordinator.data
            if state:
                for effect in state.effects:
                    if effect.display_name == effect_name:
                        await self.coordinator.async_set_effect(effect.id)
                        break

        # Turn on the device
        await self.coordinator.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off.

        Args:
            **kwargs: Optional parameters (unused).
        """
        await self.coordinator.async_turn_off()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Called when the coordinator receives new data from the device.
        Updates the entity state in Home Assistant.
        """
        self.async_write_ha_state()
