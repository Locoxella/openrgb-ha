"""Select platform for OpenRGB integration."""

from typing import override

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONNECTION_ERRORS, DOMAIN, UID_SEPARATOR
from .coordinator import OpenRGBConfigEntry, OpenRGBCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRGBConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OpenRGB select platform."""
    coordinator = config_entry.runtime_data
    async_add_entities([OpenRGBProfileSelect(coordinator, config_entry)])


class OpenRGBProfileSelect(
    CoordinatorEntity[OpenRGBCoordinator], SelectEntity, RestoreEntity
):
    """Representation of an OpenRGB profile select entity."""

    _attr_translation_key = "profile"
    _attr_has_entity_name = True

    _pending_profile: str | None = None

    def __init__(
        self, coordinator: OpenRGBCoordinator, entry: OpenRGBConfigEntry
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = UID_SEPARATOR.join([entry.entry_id, "profile"])
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )
        self._update_attrs()

    @override
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in self._attr_options:
                self._attr_current_option = last_state.state
                self.async_write_ha_state()
                return

        if "trabajo" in self._attr_options:
            self._attr_current_option = "trabajo"
            self.async_write_ha_state()
        elif self._attr_options:
            self._attr_current_option = self._attr_options[0]
            self.async_write_ha_state()

    @callback
    def _update_attrs(self) -> None:
        """Update the attributes based on the current profile list."""
        profiles = self.coordinator.client.profiles
        self._attr_options = [profile.name for profile in profiles]

        # If a profile was just applied, set it as current
        if self._pending_profile is not None:
            self._attr_current_option = self._pending_profile
            self._pending_profile = None

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()

    @property
    @override
    def available(self) -> bool:
        """Return if the select is available."""
        return super().available and bool(self._attr_options)

    @override
    async def async_select_option(self, option: str) -> None:
        """Load the selected profile."""
        async with self.coordinator.client_lock:
            try:
                await self.hass.async_add_executor_job(
                    self.coordinator.client.load_profile, option
                )
            except CONNECTION_ERRORS as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="communication_error",
                    translation_placeholders={
                        "server_address": self.coordinator.server_address,
                        "error": str(err),
                    },
                ) from err
            except ValueError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="openrgb_error",
                    translation_placeholders={
                        "error": str(err),
                    },
                ) from err

        self._pending_profile = option
        await self.coordinator.async_refresh()
