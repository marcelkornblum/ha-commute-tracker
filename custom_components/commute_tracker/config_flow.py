"""Home Assistant Config Flow and Options Flow for Commute Tracker."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from custom_components.commute_tracker.const import (
    CONF_ACTIVE_SENSOR,
    CONF_ALIGHTING_STOP,
    CONF_BOARDING_STOP,
    CONF_BOARDING_WALK_SECONDS,
    CONF_COMMUTE_ID,
    CONF_COMMUTE_TITLE,
    CONF_CORRIDOR_STOPS,
    CONF_DESTINATION,
    CONF_DIRECTION,
    CONF_GRACE_SECONDS,
    CONF_LINE,
    CONF_MODE,
    CONF_PERSON_NAME,
    CONF_PERSON_PICTURE,
    CONF_POLL_INTERVAL,
    CONF_PREP_SECONDS,
    CONF_PROVIDER,
    CONF_PROVIDERS,
    CONF_ROLLUP_STRATEGY,
    CONF_ROUTE_COLOR,
    CONF_ROUTE_ID,
    CONF_ROUTE_LATE_BUFFER_SECONDS,
    CONF_ROUTE_NAME,
    CONF_ROUTES,
    CONF_TARGET_DESTINATION_TIME,
    CORRIDOR_UPSTREAM_HORIZON_SECONDS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_PREP_SECONDS,
    DEFAULT_PROVIDER,
    DEFAULT_ROLLUP_STRATEGY,
    DEFAULT_ROUTE_LATE_BUFFER_SECONDS,
    DOMAIN,
)
from custom_components.commute_tracker.models import (
    CommuteConfig,
    CorridorStop,
    RollupStrategy,
    RouteDirection,
    TransitMode,
)
from custom_components.commute_tracker.providers.base import (
    TransitProvider,
    TransitProviderRegistry,
)


class CommuteTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Commute Tracker."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise flow state."""
        self._commute_data: dict[str, Any] = {}
        self._routes: list[dict[str, Any]] = []
        self._pending_route: dict[str, Any] = {}
        self._discovered_corridor_stops: list[CorridorStop] = []
        self._providers_config: dict[str, Any] = {}

    def _get_registry(self) -> TransitProviderRegistry:
        """Retrieve shared registry or instantiate scoped registry."""
        domain_data = self.hass.data.get(DOMAIN, {})
        registry = domain_data.get("registry")
        if not isinstance(registry, TransitProviderRegistry):
            session = async_get_clientsession(self.hass)
            registry = TransitProviderRegistry(session=session)
            registry.discover_providers()
        return registry

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: Configure commute-level metadata and timing thresholds."""
        errors: dict[str, str] = {}

        if user_input is not None:
            commute_name = str(user_input.get("name", "")).strip()
            active_sensor = str(user_input.get("active_sensor", "")).strip()

            if not commute_name:
                errors["name"] = "invalid_name"
            if not active_sensor:
                errors["active_sensor"] = "invalid_sensor"

            if not errors:
                commute_id = slugify(commute_name)
                await self.async_set_unique_id(commute_id)
                self._abort_if_unique_id_configured()

                self._commute_data = dict(user_input)
                return await self.async_step_route()

        user_schema = vol.Schema(
            {
                vol.Required("name"): cv.string,
                vol.Optional("person_name"): cv.string,
                vol.Optional("person_picture"): cv.string,
                vol.Required("active_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig()
                ),
                vol.Optional(
                    "poll_interval", default=DEFAULT_POLL_INTERVAL_SECONDS
                ): cv.positive_int,
                vol.Optional("target_destination_time"): selector.TimeSelector(
                    selector.TimeSelectorConfig()
                ),
                vol.Optional(
                    "prep_seconds", default=DEFAULT_PREP_SECONDS
                ): cv.positive_int,
                vol.Optional(
                    "rollup_strategy", default=DEFAULT_ROLLUP_STRATEGY
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[strat.value for strat in RollupStrategy],
                        translation_key="rollup_strategy",
                    )
                ),
                vol.Optional(
                    "route_late_buffer_seconds",
                    default=DEFAULT_ROUTE_LATE_BUFFER_SECONDS,
                ): cv.positive_int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=user_schema,
            errors=errors,
        )

    async def async_step_route(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: Configure a single transit route and trigger corridor discovery."""
        errors: dict[str, str] = {}
        registry = self._get_registry()
        consumer_ids = sorted(list(registry.consumer_provider_ids))
        if not consumer_ids:
            consumer_ids = [DEFAULT_PROVIDER]

        default_provider = (
            DEFAULT_PROVIDER if DEFAULT_PROVIDER in consumer_ids else consumer_ids[0]
        )
        provider_id = default_provider
        provider_instance: TransitProvider | None = None

        if user_input is not None:
            provider_id = user_input.get("provider", default_provider)
            line = str(user_input.get("line", "")).strip()
            mode_str = user_input.get("mode", TransitMode.BUS.value)
            mode = TransitMode(mode_str)
            boarding_stop = str(user_input.get("boarding_stop", "")).strip()
            alighting_stop = user_input.get("alighting_stop")
            if alighting_stop:
                alighting_stop = str(alighting_stop).strip()

            # Store credentials if entered
            app_id = user_input.get("app_id")
            app_key = user_input.get("app_key")
            provider_kwargs: dict[str, Any] = {}
            if app_id or app_key:
                cred_dict = self._providers_config.setdefault(provider_id, {})
                if app_id:
                    cred_dict["app_id"] = app_id
                    provider_kwargs["app_id"] = app_id
                if app_key:
                    cred_dict["app_key"] = app_key
                    provider_kwargs["app_key"] = app_key

            try:
                provider_instance = registry.get_provider(
                    provider_id=provider_id, **provider_kwargs
                )
            except Exception:
                provider_instance = registry.get_provider(provider_id=provider_id)

            # Validate line
            is_line_valid = await provider_instance.async_validate_line(
                line_id=line, mode=mode
            )
            if not is_line_valid:
                errors["line"] = "invalid_line"

            # Validate boarding stop
            (
                is_stop_valid,
                resolved_naptan,
                resolved_name,
            ) = await provider_instance.async_validate_stop(
                line_id=line,
                stop_id_or_name=boarding_stop,
                mode=mode,
            )
            if not is_stop_valid:
                errors["boarding_stop"] = "invalid_boarding_stop"

            if not errors:
                base_route_id = slugify(user_input.get("name") or line)
                existing_ids = {r[CONF_ROUTE_ID] for r in self._routes}
                route_id = base_route_id
                suffix = 2
                while route_id in existing_ids:
                    route_id = f"{base_route_id}_{suffix}"
                    suffix += 1

                route_dict: dict[str, Any] = {
                    CONF_ROUTE_ID: route_id,
                    CONF_PROVIDER: provider_id,
                    CONF_MODE: mode.value,
                    CONF_LINE: line,
                    CONF_DIRECTION: RouteDirection.FROM_HOME.value,
                    CONF_BOARDING_STOP: resolved_naptan or boarding_stop,
                    CONF_BOARDING_WALK_SECONDS: user_input.get(
                        "boarding_walk_seconds", 300
                    ),
                    CONF_GRACE_SECONDS: user_input.get("grace_seconds", 60),
                }

                if user_input.get("name"):
                    route_dict[CONF_ROUTE_NAME] = user_input["name"]
                if user_input.get("route_color"):
                    route_dict[CONF_ROUTE_COLOR] = user_input["route_color"]
                if alighting_stop:
                    route_dict[CONF_ALIGHTING_STOP] = alighting_stop
                if user_input.get("destination"):
                    route_dict[CONF_DESTINATION] = user_input["destination"]

                # Calculate corridor window and query provider
                prep_sec = self._commute_data.get("prep_seconds", DEFAULT_PREP_SECONDS)
                walk_sec = user_input.get("boarding_walk_seconds", 300)
                t_window = prep_sec + walk_sec + CORRIDOR_UPSTREAM_HORIZON_SECONDS

                discovered = await provider_instance.async_get_corridor_stops(
                    line_id=line,
                    boarding_stop=boarding_stop,
                    mode=mode,
                    target_time_window_seconds=t_window,
                )

                add_another = bool(user_input.get("add_another_route", False))
                route_dict["add_another_route"] = add_another

                if discovered and len(discovered) > 1:
                    self._pending_route = route_dict
                    self._discovered_corridor_stops = discovered
                    return await self.async_step_corridor()

                # If no corridor sequence discovered, proceed directly
                route_dict[CONF_CORRIDOR_STOPS] = [s.id for s in discovered]
                self._routes.append(route_dict)

                if add_another:
                    return await self.async_step_route()
                return self._async_create_commute_entry()

        if provider_instance is None:
            try:
                provider_instance = registry.get_provider(provider_id=provider_id)
            except Exception:
                provider_instance = registry.get_provider(provider_id=default_provider)

        guidance = provider_instance.stop_code_guidance

        route_schema = vol.Schema(
            {
                vol.Required(
                    "provider", default=default_provider
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=consumer_ids,
                    )
                ),
                vol.Optional("app_id"): cv.string,
                vol.Optional("app_key"): cv.string,
                vol.Required(
                    "mode", default=TransitMode.BUS.value
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[m.value for m in TransitMode],
                        translation_key="mode",
                    )
                ),
                vol.Required("line"): cv.string,
                vol.Optional("route_color"): cv.string,
                vol.Optional("name"): cv.string,
                vol.Required("boarding_stop"): cv.string,
                vol.Optional("boarding_walk_seconds", default=300): cv.positive_int,
                vol.Optional("grace_seconds", default=60): cv.positive_int,
                vol.Optional("alighting_stop"): cv.string,
                vol.Optional("destination"): cv.string,
                vol.Optional("add_another_route", default=False): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="route",
            data_schema=route_schema,
            description_placeholders={"stop_guidance": guidance},
            errors=errors,
        )

    async def async_step_corridor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 3: Confirm or adjust auto-discovered upstream corridor stops."""
        if user_input is not None:
            fallback_ids = [s.id for s in self._discovered_corridor_stops]
            chosen_stops = user_input.get(
                "corridor_stops",
                fallback_ids,
            )
            self._pending_route[CONF_CORRIDOR_STOPS] = list(chosen_stops)
            add_another = self._pending_route.pop("add_another_route", False)
            self._routes.append(self._pending_route)
            self._pending_route = {}
            self._discovered_corridor_stops = []

            if add_another:
                return await self.async_step_route()
            return self._async_create_commute_entry()

        options_map: list[selector.SelectOptionDict] = []
        default_ids: list[str] = []
        for stop in self._discovered_corridor_stops:
            label = f"{stop.name} ({stop.id})" + (
                " [Boarding Stop]" if stop.is_target else ""
            )
            options_map.append(
                selector.SelectOptionDict(
                    value=stop.id,
                    label=label,
                )
            )
            default_ids.append(stop.id)

        corridor_schema = vol.Schema(
            {
                vol.Required(
                    "corridor_stops", default=default_ids
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options_map,
                        multiple=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="corridor",
            data_schema=corridor_schema,
        )

    def _async_create_commute_entry(self) -> ConfigFlowResult:
        """Assemble all configured data and create config entry."""
        if not self._routes:
            return self.async_abort(reason="no_routes")

        commute_title = self._commute_data["name"]
        commute_id = self.unique_id or slugify(commute_title)

        entry_data: dict[str, Any] = {
            CONF_COMMUTE_ID: commute_id,
            CONF_COMMUTE_TITLE: commute_title,
            CONF_ACTIVE_SENSOR: self._commute_data["active_sensor"],
            CONF_ROUTES: self._routes,
            CONF_PREP_SECONDS: self._commute_data.get(
                "prep_seconds", DEFAULT_PREP_SECONDS
            ),
            CONF_ROUTE_LATE_BUFFER_SECONDS: self._commute_data.get(
                "route_late_buffer_seconds", DEFAULT_ROUTE_LATE_BUFFER_SECONDS
            ),
            CONF_ROLLUP_STRATEGY: self._commute_data.get(
                "rollup_strategy", DEFAULT_ROLLUP_STRATEGY
            ),
            CONF_POLL_INTERVAL: self._commute_data.get(
                "poll_interval", DEFAULT_POLL_INTERVAL_SECONDS
            ),
        }

        if self._commute_data.get("person_name"):
            entry_data[CONF_PERSON_NAME] = self._commute_data["person_name"]
        if self._commute_data.get("person_picture"):
            entry_data[CONF_PERSON_PICTURE] = self._commute_data["person_picture"]
        if self._commute_data.get("target_destination_time"):
            entry_data[CONF_TARGET_DESTINATION_TIME] = self._commute_data[
                "target_destination_time"
            ]
        if self._providers_config:
            entry_data[CONF_PROVIDERS] = self._providers_config

        # Validate structured domain configuration contract
        CommuteConfig.from_dict(data=entry_data)

        return self.async_create_entry(
            title=commute_title,
            data=entry_data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create options flow handler for commute reconfiguration."""
        return CommuteTrackerOptionsFlow(config_entry=config_entry)


class CommuteTrackerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for tweaking commute timing thresholds."""

    def __init__(self, config_entry: config_entries.ConfigEntry | None = None) -> None:
        """Initialise options flow with config entry reference."""
        self._config_entry_param = config_entry

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return the active config entry."""
        if self._config_entry_param is not None:
            return self._config_entry_param
        return super().config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage commute timing and monitoring options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        entry = self.config_entry
        current_data = {**entry.data, **entry.options}

        options_schema = vol.Schema(
            {
                vol.Optional(
                    "boarding_walk_seconds",
                    default=current_data.get("boarding_walk_seconds", 300),
                ): cv.positive_int,
                vol.Optional(
                    "prep_seconds",
                    default=current_data.get("prep_seconds", DEFAULT_PREP_SECONDS),
                ): cv.positive_int,
                vol.Optional(
                    "grace_seconds",
                    default=current_data.get("grace_seconds", 60),
                ): cv.positive_int,
                vol.Optional(
                    "route_late_buffer_seconds",
                    default=current_data.get(
                        "route_late_buffer_seconds",
                        DEFAULT_ROUTE_LATE_BUFFER_SECONDS,
                    ),
                ): cv.positive_int,
                vol.Optional(
                    "target_destination_time",
                    description={
                        "suggested_value": current_data.get("target_destination_time")
                    },
                ): selector.TimeSelector(selector.TimeSelectorConfig()),
                vol.Optional(
                    "poll_interval",
                    default=current_data.get(
                        "poll_interval", DEFAULT_POLL_INTERVAL_SECONDS
                    ),
                ): cv.positive_int,
                vol.Optional(
                    "active_sensor",
                    default=current_data.get("active_sensor"),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Optional(
                    "rollup_strategy",
                    default=current_data.get(
                        "rollup_strategy", DEFAULT_ROLLUP_STRATEGY
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[strat.value for strat in RollupStrategy],
                        translation_key="rollup_strategy",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
