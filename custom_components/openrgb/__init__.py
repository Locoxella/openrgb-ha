"""The OpenRGB integration."""

import logging
from typing import Any

import openrgb.utils

from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import AnyDeviceEntry

from .const import DOMAIN, UID_SEPARATOR
from .coordinator import OpenRGBConfigEntry, OpenRGBCoordinator, stable_location

_LOGGER = logging.getLogger(__name__)

# Monkeypatch openrgb.utils.parse_string to prevent UnicodeDecodeError on invalid bytes in serial/metadata
if getattr(openrgb.utils, "_ha_patched_parse_string", None) is None:
    _orig_parse_string = openrgb.utils.parse_string

    def _safe_parse_string(data):
        length = openrgb.utils.parse_var("H", data)
        return openrgb.utils.parse_var(f"{length}s", data).decode("utf-8", errors="replace").rstrip("\x00")

    openrgb.utils.parse_string = _safe_parse_string
    openrgb.utils._ha_patched_parse_string = True

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SELECT]


def _stable_key(old_key: str) -> str | None:
    """Replace the unstable part of a device key's location; see stable_location."""
    parts = old_key.split(UID_SEPARATOR)
    if len(parts) != 6:
        return None

    entry_id, device_type, vendor, description, serial, location = parts

    serial = serial.strip()
    if serial == "none":
        serial = ""

    vendor_lower = vendor.lower()
    if serial or vendor_lower in ("asus", "razer"):
        location = stable_location(location)

    new_key = UID_SEPARATOR.join(
        (entry_id, device_type, vendor, description, serial or "none", location)
    )
    return new_key if new_key != old_key else None


async def async_migrate_entry(hass: HomeAssistant, entry: OpenRGBConfigEntry) -> bool:
    """Migrate an old config entry from version 1 to version 2."""
    _LOGGER.info("Migrating OpenRGB configuration from version %s", entry.version)

    if entry.version == 1:
        entity_registry = er.async_get(hass)

        @callback
        def _migrate_entity(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
            new_key = _stable_key(entity_entry.unique_id)
            if new_key is None:
                return None
            if entity_registry.async_get_entity_id(
                entity_entry.domain, entity_entry.platform, new_key
            ):
                _LOGGER.debug(
                    "Not migrating %s, the stable unique ID is already in use",
                    entity_entry.entity_id,
                )
                return None
            return {"new_unique_id": new_key}

        await er.async_migrate_entries(hass, entry.entry_id, _migrate_entity)

        device_registry = dr.async_get(hass)
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            new_identifiers = set(device_entry.identifiers)

            for domain, identifier in device_entry.identifiers:
                if domain != DOMAIN:
                    continue
                new_key = _stable_key(identifier)
                if new_key is None:
                    continue
                if device_registry.async_get_device_by_identifier(
                    (DOMAIN, new_key), entry.entry_id
                ):
                    _LOGGER.debug(
                        "Not migrating device %s, the stable identifier is already in use",
                        device_entry.id,
                    )
                    continue
                new_identifiers -= {(domain, identifier)}
                new_identifiers |= {(DOMAIN, new_key)}

            if new_identifiers != device_entry.identifiers:
                device_registry.async_update_device(
                    device_entry.id, new_identifiers=new_identifiers
                )

        hass.config_entries.async_update_entry(entry, version=2)

    _LOGGER.info("Migration to OpenRGB configuration version %s successful", entry.version)
    return True



def _setup_server_device_registry(
    hass: HomeAssistant, entry: OpenRGBConfigEntry, coordinator: OpenRGBCoordinator
):
    """Set up device registry for the OpenRGB SDK server."""
    device_registry = dr.async_get(hass)

    # Create the parent OpenRGB SDK server device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data[CONF_NAME],
        model="OpenRGB SDK Server",
        manufacturer="OpenRGB",
        sw_version=coordinator.get_client_protocol_version(),
        entry_type=dr.DeviceEntryType.SERVICE,
    )


async def async_setup_entry(hass: HomeAssistant, entry: OpenRGBConfigEntry) -> bool:
    """Set up OpenRGB from a config entry."""
    coordinator = OpenRGBCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    # The server device must be created first as other devices are children of it
    _setup_server_device_registry(hass, entry, coordinator)

    # Clean up obsolete duplicate devices/entities from registry
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    for dev in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        for domain, identifier in dev.identifiers:
            if domain != DOMAIN:
                continue
            if identifier != entry.entry_id and identifier not in coordinator.data:
                # If identifier is an unstable duplicate of a Razer device, remove it
                parts = identifier.split(UID_SEPARATOR)
                if len(parts) == 6:
                    vendor_val = parts[2].lower()
                    loc_val = parts[5]
                    if vendor_val == "razer" and loc_val.startswith("HID: "):
                        _LOGGER.info(
                            "Removing obsolete duplicate OpenRGB device %s (%s)",
                            dev.name,
                            identifier,
                        )
                        # Remove any entities attached to this obsolete device
                        for ent in er.async_entries_for_device(entity_registry, dev.id):
                            entity_registry.async_remove(ent.entity_id)
                        device_registry.async_remove_device(dev.id)
                        break

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenRGBConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: OpenRGBConfigEntry, device_entry: AnyDeviceEntry
) -> bool:
    """Allows removal of device if it is no longer connected."""
    coordinator = entry.runtime_data

    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue

        # Block removal of the OpenRGB SDK Server device
        if identifier == entry.entry_id:
            return False

        # Block removal of the OpenRGB device if it is still connected
        if identifier in coordinator.data:
            return False

    # Device is not connected or is not an OpenRGB device, allow removal
    return True
