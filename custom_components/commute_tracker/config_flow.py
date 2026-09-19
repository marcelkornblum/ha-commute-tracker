"""Home Assistant Config Flow and Options Flow for Commute Tracker."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from custom_components.commute_tracker.const import (
    CONF_ACTIVE_SENSOR,
    CONF_ALIGHTING_STOP,
    CONF_ALIGHTING_WALK_SECONDS,
    CONF_BOARDING_STOP,
    CONF_BOARDING_WALK_SECONDS,
    CONF_COMMUTE_ID,
    CONF_COMMUTE_TITLE,
    CONF_CORRIDOR_STOP_NAMES,
    CONF_CORRIDOR_STOPS,
    CONF_DESTINATION,
    CONF_DIRECTION,
    CONF_GRACE_SECONDS,
    CONF_LINE,
    CONF_MODE,
    CONF_PERSON,
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
    CONF_STAGING_MODE,
    CONF_TARGET_DESTINATION_TIME,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_PREP_SECONDS,
    DEFAULT_PROVIDER,
    DEFAULT_ROLLUP_STRATEGY,
    DEFAULT_ROUTE_LATE_BUFFER_SECONDS,
    DEFAULT_STAGING_MODE,
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


def _flatten_input(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively flatten section-wrapped user inputs."""
    flattened: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict) and key in {
            "overview",
            "destination_timings",
            "rollup_strategy_sec",
            "advanced_settings",
            "service_details",
            "boarding_walk",
            "alighting_walk",
            "stop_display_names",
        }:
            flattened.update(value)
        else:
            flattened[key] = value
    return flattened


class CommuteFlowHandlerMixin(config_entries.ConfigEntryBaseFlow):
    """Shared flow handler logic for ConfigFlow and OptionsFlow."""

    _commute_data: dict[str, Any]
    _routes: list[dict[str, Any]]
    _editing_route_index: int | None
    _pending_route: dict[str, Any]
    _discovered_corridor_stops: list[CorridorStop]
    _chosen_corridor_stops: list[str]
    _providers_config: dict[str, Any]

    def _get_registry(self) -> TransitProviderRegistry:
        """Retrieve shared registry or instantiate scoped registry."""
        domain_data = self.hass.data.get(DOMAIN, {})
        registry = domain_data.get("registry")
        if not isinstance(registry, TransitProviderRegistry):
            session = async_get_clientsession(self.hass)
            registry = TransitProviderRegistry(session=session)
            registry.discover_providers()
        return registry

    def _build_commute_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        """Construct Screen 1 (Commute Settings) schema with structured sections."""
        d = defaults or {}
        overview_dict: dict[Any, Any] = {}
        if d.get(CONF_PERSON):
            overview_dict[
                vol.Optional(
                    "person",
                    description={"suggested_value": d.get(CONF_PERSON)},
                )
            ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="person"))
        else:
            overview_dict[vol.Optional("person")] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="person")
            )

        if d.get("name") or d.get(CONF_COMMUTE_TITLE):
            overview_dict[
                vol.Required(
                    "name",
                    description={
                        "suggested_value": d.get("name") or d.get(CONF_COMMUTE_TITLE)
                    },
                )
            ] = cv.string
        else:
            overview_dict[vol.Required("name")] = cv.string

        if d.get(CONF_ACTIVE_SENSOR):
            overview_dict[
                vol.Required(
                    "active_sensor",
                    description={"suggested_value": d.get(CONF_ACTIVE_SENSOR)},
                )
            ] = selector.EntitySelector(selector.EntitySelectorConfig())
        else:
            overview_dict[vol.Required("active_sensor")] = selector.EntitySelector(
                selector.EntitySelectorConfig()
            )

        dest_timings_dict: dict[Any, Any] = {}
        if d.get("destination") or d.get(CONF_DESTINATION):
            dest_timings_dict[
                vol.Optional(
                    "destination",
                    description={
                        "suggested_value": d.get("destination")
                        or d.get(CONF_DESTINATION)
                    },
                )
            ] = cv.string
        else:
            dest_timings_dict[vol.Optional("destination")] = cv.string

        if d.get(CONF_TARGET_DESTINATION_TIME):
            dest_timings_dict[
                vol.Optional(
                    "target_destination_time",
                    description={
                        "suggested_value": d.get(CONF_TARGET_DESTINATION_TIME)
                    },
                )
            ] = selector.TimeSelector(selector.TimeSelectorConfig())
        else:
            dest_timings_dict[vol.Optional("target_destination_time")] = (
                selector.TimeSelector(selector.TimeSelectorConfig())
            )

        dest_timings_dict[
            vol.Optional(
                "prep_seconds",
                default=d.get("prep_seconds", DEFAULT_PREP_SECONDS),
            )
        ] = cv.positive_int

        strategy_dict: dict[Any, Any] = {
            vol.Optional(
                "rollup_strategy",
                default=d.get("rollup_strategy", DEFAULT_ROLLUP_STRATEGY),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[strat.value for strat in RollupStrategy],
                    translation_key="rollup_strategy",
                )
            ),
            vol.Optional(
                "route_late_buffer_seconds",
                default=d.get(
                    "route_late_buffer_seconds", DEFAULT_ROUTE_LATE_BUFFER_SECONDS
                ),
            ): cv.positive_int,
        }

        advanced_dict: dict[Any, Any] = {
            vol.Optional(
                "poll_interval",
                default=d.get("poll_interval", DEFAULT_POLL_INTERVAL_SECONDS),
            ): cv.positive_int,
            vol.Optional(
                "staging_mode",
                default=d.get("staging_mode", DEFAULT_STAGING_MODE),
            ): cv.boolean,
        }

        return vol.Schema(
            {
                vol.Required("overview"): section(
                    vol.Schema(overview_dict),
                ),
                vol.Optional("destination_timings"): section(
                    vol.Schema(dest_timings_dict),
                ),
                vol.Optional("rollup_strategy_sec"): section(
                    vol.Schema(strategy_dict),
                ),
                vol.Optional("advanced_settings"): section(
                    vol.Schema(advanced_dict),
                    {"collapsed": True},
                ),
            }
        )

    async def async_step_routes(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Screen 2: Manage routes (add, edit, delete, or finish)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            action = str(user_input.get("route_action", "")).strip()
            if action == "add_route":
                self._editing_route_index = None
                self._pending_route = {}
                return await self.async_step_route()

            if action.startswith("edit_route_"):
                idx_str = action.removeprefix("edit_route_")
                if idx_str.isdigit():
                    idx = int(idx_str)
                    if 0 <= idx < len(self._routes):
                        self._editing_route_index = idx
                        self._pending_route = dict(self._routes[idx])
                        return await self.async_step_route()

            if action.startswith("delete_route_"):
                idx_str = action.removeprefix("delete_route_")
                if idx_str.isdigit():
                    idx = int(idx_str)
                    if 0 <= idx < len(self._routes):
                        self._routes.pop(idx)
                        return await self.async_step_routes()

            if action == "finish":
                if not self._routes:
                    errors["base"] = "no_routes"
                else:
                    return self._async_finish_flow()

        options_map: list[selector.SelectOptionDict] = [
            selector.SelectOptionDict(
                value="add_route",
                label="➕ Add New Route",
            )
        ]
        for idx, r in enumerate(self._routes):
            r_name = (
                r.get("name") or f"{str(r.get('mode', '')).title()} {r.get('line', '')}"
            )
            b_stop = r.get("boarding_stop", "")
            options_map.append(
                selector.SelectOptionDict(
                    value=f"edit_route_{idx}",
                    label=f"✏️ Edit Route: {r_name} ({b_stop})",
                )
            )
            options_map.append(
                selector.SelectOptionDict(
                    value=f"delete_route_{idx}",
                    label=f"🗑️ Delete Route: {r_name}",
                )
            )

        if self._routes:
            options_map.append(
                selector.SelectOptionDict(
                    value="finish",
                    label="✅ Finish & Save Commute",
                )
            )

        default_action = "add_route" if not self._routes else "finish"
        routes_schema = vol.Schema(
            {
                vol.Required(
                    "route_action", default=default_action
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options_map,
                    )
                ),
            }
        )

        routes_summary = (
            "\n".join(
                f"- **{r.get('name') or r.get('line')}** "
                f"({r.get('mode')}) at `{r.get('boarding_stop')}`"
                for r in self._routes
            )
            if self._routes
            else "No routes configured yet."
        )

        return self.async_show_form(
            step_id="routes",
            data_schema=routes_schema,
            description_placeholders={"routes_summary": routes_summary},
            errors=errors,
        )

    async def async_step_route(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Screen 3: Configure route details and walk timings."""
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
            flat = _flatten_input(user_input)
            provider_id = flat.get("provider", default_provider)
            line = str(flat.get("line", "")).strip()
            mode_str = flat.get("mode", TransitMode.BUS.value)
            mode = TransitMode(mode_str)
            boarding_stop = str(flat.get("boarding_stop", "")).strip()
            alighting_stop = flat.get("alighting_stop")
            if alighting_stop:
                alighting_stop = str(alighting_stop).strip()

            app_id = flat.get("app_id")
            app_key = flat.get("app_key")
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

            is_line_valid = await provider_instance.async_validate_line(
                line_id=line, mode=mode
            )
            if not is_line_valid:
                errors["line"] = "invalid_line"

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
                base_route_id = slugify(flat.get("name") or line)
                existing_ids = {
                    r[CONF_ROUTE_ID]
                    for idx, r in enumerate(self._routes)
                    if idx != self._editing_route_index
                }
                route_id = base_route_id
                suffix = 2
                while route_id in existing_ids:
                    route_id = f"{base_route_id}_{suffix}"
                    suffix += 1

                route_dict: dict[str, Any] = {
                    CONF_ROUTE_ID: (self._pending_route.get(CONF_ROUTE_ID) or route_id),
                    CONF_PROVIDER: provider_id,
                    CONF_MODE: mode.value,
                    CONF_LINE: line,
                    CONF_DIRECTION: RouteDirection.FROM_HOME.value,
                    CONF_BOARDING_STOP: resolved_naptan or boarding_stop,
                    CONF_BOARDING_WALK_SECONDS: flat.get("boarding_walk_seconds", 300),
                    CONF_GRACE_SECONDS: flat.get("grace_seconds", 60),
                }

                if flat.get("name"):
                    route_dict[CONF_ROUTE_NAME] = flat["name"]
                if flat.get("route_color"):
                    route_dict[CONF_ROUTE_COLOR] = flat["route_color"]
                if alighting_stop:
                    route_dict[CONF_ALIGHTING_STOP] = alighting_stop
                if flat.get("alighting_walk_seconds") is not None:
                    route_dict[CONF_ALIGHTING_WALK_SECONDS] = flat[
                        "alighting_walk_seconds"
                    ]

                # Query provider for full corridor branch without early truncation
                discovered = await provider_instance.async_get_corridor_stops(
                    line_id=line,
                    boarding_stop=boarding_stop,
                    mode=mode,
                    target_time_window_seconds=None,
                )

                self._pending_route = route_dict
                self._discovered_corridor_stops = discovered

                if discovered:
                    return await self.async_step_corridor()

                # If no corridor sequence discovered, proceed to routes overview
                self._pending_route[CONF_CORRIDOR_STOPS] = []
                self._pending_route[CONF_CORRIDOR_STOP_NAMES] = {}
                if self._editing_route_index is not None:
                    self._routes[self._editing_route_index] = self._pending_route
                else:
                    self._routes.append(self._pending_route)
                self._pending_route = {}
                self._editing_route_index = None
                return await self.async_step_routes()

        d = self._pending_route or {}
        if provider_instance is None:
            try:
                provider_instance = registry.get_provider(
                    provider_id=d.get("provider", default_provider)
                )
            except Exception:
                provider_instance = registry.get_provider(provider_id=default_provider)

        guidance = provider_instance.stop_code_guidance

        service_dict: dict[Any, Any] = {
            vol.Required(
                "provider", default=d.get("provider", default_provider)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=consumer_ids,
                )
            ),
            vol.Required(
                "mode", default=d.get("mode", TransitMode.BUS.value)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[m.value for m in TransitMode],
                    translation_key="mode",
                )
            ),
        }
        if d.get("line"):
            service_dict[
                vol.Required(
                    "line",
                    description={"suggested_value": d.get("line")},
                )
            ] = cv.string
        else:
            service_dict[vol.Required("line")] = cv.string

        if d.get("name"):
            service_dict[
                vol.Optional(
                    "name",
                    description={"suggested_value": d.get("name")},
                )
            ] = cv.string
        else:
            service_dict[vol.Optional("name")] = cv.string

        if d.get("route_color"):
            service_dict[
                vol.Optional(
                    "route_color",
                    description={"suggested_value": d.get("route_color")},
                )
            ] = cv.string
        else:
            service_dict[vol.Optional("route_color")] = cv.string

        service_dict[vol.Optional("app_id")] = cv.string
        service_dict[vol.Optional("app_key")] = cv.string

        boarding_dict: dict[Any, Any] = {}
        if d.get("boarding_stop"):
            boarding_dict[
                vol.Required(
                    "boarding_stop",
                    description={"suggested_value": d.get("boarding_stop")},
                )
            ] = cv.string
        else:
            boarding_dict[vol.Required("boarding_stop")] = cv.string

        boarding_dict[
            vol.Optional(
                "boarding_walk_seconds",
                default=d.get("boarding_walk_seconds", 300),
            )
        ] = cv.positive_int
        boarding_dict[
            vol.Optional(
                "grace_seconds",
                default=d.get("grace_seconds", 60),
            )
        ] = cv.positive_int

        alighting_dict: dict[Any, Any] = {}
        if d.get("alighting_stop"):
            alighting_dict[
                vol.Optional(
                    "alighting_stop",
                    description={"suggested_value": d.get("alighting_stop")},
                )
            ] = cv.string
        else:
            alighting_dict[vol.Optional("alighting_stop")] = cv.string

        alighting_dict[
            vol.Optional(
                "alighting_walk_seconds",
                default=d.get("alighting_walk_seconds", 0),
            )
        ] = cv.positive_int

        route_schema = vol.Schema(
            {
                vol.Required("service_details"): section(
                    vol.Schema(service_dict),
                ),
                vol.Required("boarding_walk"): section(
                    vol.Schema(boarding_dict),
                ),
                vol.Optional("alighting_walk"): section(
                    vol.Schema(alighting_dict),
                ),
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
        """Screen 4: Select stops along the corridor and add extra stops."""
        if user_input is not None:
            fallback_ids = [s.id for s in self._discovered_corridor_stops]
            chosen = list(user_input.get("corridor_stops", fallback_ids))
            extra = str(user_input.get("extra_stops", "")).strip()
            if extra:
                for sid in extra.split(","):
                    clean_sid = sid.strip()
                    if clean_sid and clean_sid not in chosen:
                        chosen.append(clean_sid)

            self._chosen_corridor_stops = chosen
            return await self.async_step_corridor_names()

        options_map: list[selector.SelectOptionDict] = []
        default_ids: list[str] = []
        existing_stops = self._pending_route.get(CONF_CORRIDOR_STOPS)

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
            if existing_stops is not None:
                if stop.id in existing_stops:
                    default_ids.append(stop.id)
            else:
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
                vol.Optional("extra_stops", default=""): cv.string,
            }
        )

        return self.async_show_form(
            step_id="corridor",
            data_schema=corridor_schema,
        )

    async def async_step_corridor_names(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Screen 4b: Configure short display names for each selected corridor stop."""
        chosen_ids = getattr(self, "_chosen_corridor_stops", [])
        discovered_lookup = {s.id: s.name for s in self._discovered_corridor_stops}
        existing_names = self._pending_route.get(CONF_CORRIDOR_STOP_NAMES, {})

        if user_input is not None:
            flat = _flatten_input(user_input)
            custom_names: dict[str, str] = {}
            for sid in chosen_ids:
                field_key = f"name_{slugify(sid)}"
                val = str(
                    flat.get(field_key)
                    or user_input.get(field_key)
                    or discovered_lookup.get(sid, sid)
                ).strip()
                custom_names[sid] = val

            self._pending_route[CONF_CORRIDOR_STOPS] = list(chosen_ids)
            self._pending_route[CONF_CORRIDOR_STOP_NAMES] = custom_names

            if self._editing_route_index is not None:
                self._routes[self._editing_route_index] = self._pending_route
            else:
                self._routes.append(self._pending_route)

            self._pending_route = {}
            self._editing_route_index = None
            self._discovered_corridor_stops = []
            self._chosen_corridor_stops = []

            return await self.async_step_routes()

        names_fields: dict[Any, Any] = {}
        for sid in chosen_ids:
            field_key = f"name_{slugify(sid)}"
            default_label = existing_names.get(sid) or discovered_lookup.get(sid, sid)
            names_fields[vol.Optional(field_key, default=default_label)] = cv.string

        names_schema = vol.Schema(
            {vol.Required("stop_display_names"): section(vol.Schema(names_fields))}
        )

        return self.async_show_form(
            step_id="corridor_names",
            data_schema=names_schema,
        )

    def _build_entry_data(self) -> dict[str, Any]:
        """Assemble all configured commute and route data."""
        commute_title = self._commute_data.get("name", "Commute")
        commute_id = (
            getattr(self, "unique_id", None)
            or self._commute_data.get("id")
            or slugify(commute_title)
        )

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
            CONF_STAGING_MODE: self._commute_data.get(
                "staging_mode", DEFAULT_STAGING_MODE
            ),
        }

        if self._commute_data.get("person"):
            entry_data[CONF_PERSON] = self._commute_data["person"]
        if self._commute_data.get("destination"):
            entry_data[CONF_DESTINATION] = self._commute_data["destination"]
        if self._commute_data.get("target_destination_time"):
            entry_data[CONF_TARGET_DESTINATION_TIME] = self._commute_data[
                "target_destination_time"
            ]
        if self._providers_config:
            entry_data[CONF_PROVIDERS] = self._providers_config

        return entry_data

    def _async_finish_flow(self) -> ConfigFlowResult:
        """Abstract method implemented by ConfigFlow and OptionsFlow."""
        raise NotImplementedError


class CommuteTrackerConfigFlow(
    CommuteFlowHandlerMixin, config_entries.ConfigFlow, domain=DOMAIN
):
    """Handle config flow for adding a new commute."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise flow state."""
        self._commute_data: dict[str, Any] = {}
        self._routes: list[dict[str, Any]] = []
        self._editing_route_index: int | None = None
        self._pending_route: dict[str, Any] = {}
        self._discovered_corridor_stops: list[CorridorStop] = []
        self._chosen_corridor_stops: list[str] = []
        self._providers_config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Screen 1: Configure commute settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            flat = _flatten_input(user_input)
            commute_name = str(flat.get("name", "")).strip()
            active_sensor = str(flat.get("active_sensor", "")).strip()

            if not commute_name:
                errors["name"] = "invalid_name"
            if not active_sensor:
                errors["active_sensor"] = "invalid_sensor"

            if not errors:
                commute_id = slugify(commute_name)
                await self.async_set_unique_id(commute_id)
                self._abort_if_unique_id_configured()

                self._commute_data = dict(flat)
                # First route prompt in create flow
                if not self._routes:
                    return await self.async_step_route()
                return await self.async_step_routes()

        schema = self._build_commute_schema(defaults=self._commute_data)
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    def _async_finish_flow(self) -> ConfigFlowResult:
        """Assemble all configured data and create config entry."""
        if not self._routes:
            return self.async_abort(reason="no_routes")

        entry_data = self._build_entry_data()
        commute_title = entry_data[CONF_COMMUTE_TITLE]

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


class CommuteTrackerOptionsFlow(CommuteFlowHandlerMixin, config_entries.OptionsFlow):
    """Handle options flow for editing an existing commute."""

    def __init__(self, config_entry: config_entries.ConfigEntry | None = None) -> None:
        """Initialise options flow with existing config entry data."""
        self._config_entry_param = config_entry
        self._editing_route_index: int | None = None
        self._pending_route: dict[str, Any] = {}
        self._discovered_corridor_stops: list[CorridorStop] = []
        self._chosen_corridor_stops: list[str] = []
        self._providers_config: dict[str, Any] = {}

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return the active config entry."""
        if self._config_entry_param is not None:
            return self._config_entry_param
        return super().config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Screen 1: Edit commute settings."""
        errors: dict[str, str] = {}
        entry = self.config_entry
        current = {**entry.data, **entry.options}

        if not hasattr(self, "_commute_data") or not self._commute_data:
            self._commute_data = dict(current)
            self._routes = [dict(r) for r in current.get(CONF_ROUTES, [])]
            self._providers_config = dict(current.get(CONF_PROVIDERS, {}))

        if user_input is not None:
            flat = _flatten_input(user_input)
            commute_name = str(flat.get("name", "")).strip()
            active_sensor = str(flat.get("active_sensor", "")).strip()

            if not commute_name:
                errors["name"] = "invalid_name"
            if not active_sensor:
                errors["active_sensor"] = "invalid_sensor"

            if not errors:
                self._commute_data.update(flat)
                return await self.async_step_routes()

        schema = self._build_commute_schema(defaults=self._commute_data)
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )

    def _async_finish_flow(self) -> ConfigFlowResult:
        """Save updated commute settings and routes, updating entry and reloading."""
        if not self._routes:
            return self.async_abort(reason="no_routes")

        entry_data = self._build_entry_data()
        CommuteConfig.from_dict(data=entry_data)

        # Update entry data directly
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            title=entry_data[CONF_COMMUTE_TITLE],
            data=entry_data,
            options={},
        )

        return self.async_create_entry(title="", data={})
