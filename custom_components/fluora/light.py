"""Light platform for Fluora integration."""

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FluoraDeviceCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fluora light from a config entry."""
    coordinator: FluoraDeviceCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    async_add_entities([FluoraLight(coordinator)])


class FluoraLight(CoordinatorEntity[FluoraDeviceCoordinator], LightEntity):
    """Representation of a Fluora light."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name

    def __init__(self, coordinator: FluoraDeviceCoordinator) -> None:
        """Initialize the light."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.mac_address}_light"
        self._attr_color_mode = ColorMode.HS
        self._attr_supported_color_modes = {ColorMode.HS}
        self._attr_supported_features = LightEntityFeature.EFFECT

    @property
    def device_info(self):
        """Return device information."""
        return self.coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        state: DeviceState | None = self.coordinator.data
        if state is None:
            return False
        return state.is_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0-255)."""
        state: DeviceState | None = self.coordinator.data
        if state is None:
            return None
        # Convert from device brightness (0.0-1.0) to Home Assistant brightness (0-255)
        return int(state.brightness * 255)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value."""
        state: DeviceState | None = self.coordinator.data
        if state is None:
            return None
        # Device uses 0.0-1.0 for both, HA uses 0-360 for hue and 0-100 for saturation
        hue = state.hue * 360
        saturation = state.saturation * 100
        return (hue, saturation)

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        state: DeviceState | None = self.coordinator.data
        if state is None:
            return None
        return state.current_effect

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        state: DeviceState | None = self.coordinator.data
        if state is None:
            return None
        return state.effect_list

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Handle brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            # Convert from HA brightness (0-255) to device brightness (0.0-1.0)
            device_brightness = brightness / 255.0
            await self.coordinator.async_set_brightness(device_brightness)

        # Handle HS color
        if ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            # Convert from HA (0-360, 0-100) to device (0.0-1.0, 0.0-1.0)
            hue = hs_color[0] / 360.0
            saturation = hs_color[1] / 100.0
            await self.coordinator.async_set_hue(hue)
            await self.coordinator.async_set_saturation(saturation)

        # Handle effect
        if ATTR_EFFECT in kwargs:
            effect_name = kwargs[ATTR_EFFECT]
            # Find the effect ID by name
            state: DeviceState | None = self.coordinator.data
            if state:
                for effect in state.effects:
                    if effect.display_name == effect_name:
                        await self.coordinator.async_set_effect(effect.id)
                        break

        # Turn on the device
        await self.coordinator.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.async_turn_off()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
