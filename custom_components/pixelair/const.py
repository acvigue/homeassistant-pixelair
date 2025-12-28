"""Constants for the PixelAir integration."""

from typing import Final

DOMAIN: Final = "pixelair"

# Manufacturer name for device registry
MANUFACTURER: Final = "Light+Color"

# Config entry data keys
CONF_MAC_ADDRESS: Final = "mac_address"
CONF_SERIAL_NUMBER: Final = "serial_number"

# Discovery timeout in seconds
DISCOVERY_TIMEOUT: Final = 10

# Device connection timeout in seconds
CONNECTION_TIMEOUT: Final = 10

# Polling interval for state_counter checks (seconds)
POLL_INTERVAL: Final = 2.5
