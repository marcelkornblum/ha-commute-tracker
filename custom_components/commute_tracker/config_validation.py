"""Configuration schema validation for Commute Tracker integration."""

from typing import Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from custom_components.commute_tracker.const import (
    CONF_ACTIVE_SENSOR,
    CONF_ALIGHTING_STOP,
    CONF_ALIGHTING_WALK_SECONDS,
    CONF_API_KEY,
    CONF_APP_ID,
    CONF_APP_KEY,
    CONF_BOARDING_STOP,
    CONF_BOARDING_WALK_SECONDS,
    CONF_COMMUTE_ID,
    CONF_COMMUTE_TITLE,
    CONF_COMMUTES,
    CONF_CORRIDOR_STOPS,
    CONF_DESTINATION,
    CONF_DIRECTION,
    CONF_GRACE_FRACTION,
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
    CONF_STAGING_MODE,
    CONF_TARGET_DESTINATION_TIME,
    CONF_TRANSIT_DURATION_SECONDS,
    CONF_UNIQUE_ID,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_PROVIDER,
    DEFAULT_ROLLUP_STRATEGY,
    DEFAULT_ROUTE_LATE_BUFFER_SECONDS,
    DEFAULT_STAGING_MODE,
    DOMAIN,
)
from custom_components.commute_tracker.models import (
    RollupStrategy,
    RouteDirection,
    TransitMode,
)


def _normalise_route(route: dict[str, Any]) -> dict[str, Any]:
    """Normalise route parameters, deriving route ID."""
    data = dict(route)
    if CONF_UNIQUE_ID in data and (
        CONF_ROUTE_ID not in data or not data[CONF_ROUTE_ID]
    ):
        data[CONF_ROUTE_ID] = data[CONF_UNIQUE_ID]

    if CONF_ROUTE_ID not in data or not data[CONF_ROUTE_ID]:
        line_val = str(data.get(CONF_LINE, "route"))
        data[CONF_ROUTE_ID] = slugify(line_val)

    if CONF_CORRIDOR_STOPS not in data:
        data[CONF_CORRIDOR_STOPS] = []

    return data


def _normalise_commute(commute: dict[str, Any]) -> dict[str, Any]:
    """Normalise commute parameters, deriving commute ID."""
    data = dict(commute)
    if CONF_UNIQUE_ID in data and (
        CONF_COMMUTE_ID not in data or not data[CONF_COMMUTE_ID]
    ):
        data[CONF_COMMUTE_ID] = data[CONF_UNIQUE_ID]

    if CONF_COMMUTE_ID not in data or not data[CONF_COMMUTE_ID]:
        title = data.get(CONF_COMMUTE_TITLE, "commute")
        data[CONF_COMMUTE_ID] = slugify(str(title))

    return data


TFL_PROVIDER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_APP_ID): cv.string,
        vol.Optional(CONF_APP_KEY): cv.string,
    }
)

PROVIDER_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_APP_ID): cv.string,
        vol.Optional(CONF_APP_KEY): cv.string,
        vol.Optional(CONF_API_KEY): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

PROVIDERS_SCHEMA = vol.Schema(
    {
        vol.Optional("tfl"): TFL_PROVIDER_SCHEMA,
        cv.slug: PROVIDER_ENTRY_SCHEMA,
    }
)

_ERR_MUTUAL_GRACE = "Cannot specify both grace_seconds and grace_fraction"

ROUTE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_ROUTE_ID): cv.string,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_ROUTE_NAME): cv.string,
            vol.Optional(CONF_ROUTE_COLOR): cv.string,
            vol.Required(CONF_MODE): vol.In([mode.value for mode in TransitMode]),
            vol.Required(CONF_LINE): cv.string,
            vol.Optional(CONF_PROVIDER, default=DEFAULT_PROVIDER): cv.string,
            vol.Optional(
                CONF_DIRECTION, default=RouteDirection.FROM_HOME.value
            ): vol.In([d.value for d in RouteDirection]),
            vol.Optional(CONF_BOARDING_STOP): cv.string,
            vol.Optional(CONF_ALIGHTING_STOP): cv.string,
            vol.Optional(CONF_DESTINATION): cv.string,
            vol.Optional(CONF_BOARDING_WALK_SECONDS): cv.positive_int,
            vol.Optional(CONF_PREP_SECONDS): cv.positive_int,
            vol.Exclusive(
                CONF_GRACE_SECONDS,
                "grace_group",
                msg=_ERR_MUTUAL_GRACE,
            ): cv.positive_int,
            vol.Exclusive(
                CONF_GRACE_FRACTION,
                "grace_group",
                msg=_ERR_MUTUAL_GRACE,
            ): cv.small_float,
            vol.Optional(CONF_TRANSIT_DURATION_SECONDS): cv.positive_int,
            vol.Optional(CONF_ALIGHTING_WALK_SECONDS): cv.positive_int,
            vol.Optional(CONF_CORRIDOR_STOPS, default=list): vol.All(
                cv.ensure_list, [cv.string]
            ),
        }
    ),
    _normalise_route,
)

COMMUTE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_COMMUTE_ID): cv.string,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Required(CONF_COMMUTE_TITLE): cv.string,
            vol.Required(CONF_ACTIVE_SENSOR): cv.entity_id,
            vol.Optional(CONF_TARGET_DESTINATION_TIME): cv.string,
            vol.Optional(CONF_PERSON_NAME): cv.string,
            vol.Optional(CONF_PERSON_PICTURE): cv.string,
            vol.Exclusive(
                CONF_GRACE_SECONDS,
                "grace_group",
                msg=_ERR_MUTUAL_GRACE,
            ): cv.positive_int,
            vol.Exclusive(
                CONF_GRACE_FRACTION,
                "grace_group",
                msg=_ERR_MUTUAL_GRACE,
            ): cv.small_float,
            vol.Optional(CONF_ROLLUP_STRATEGY): vol.In(
                [strat.value for strat in RollupStrategy]
            ),
            vol.Optional(CONF_ROUTE_LATE_BUFFER_SECONDS): cv.positive_int,
            vol.Optional(CONF_POLL_INTERVAL): cv.positive_int,
            vol.Optional(CONF_PREP_SECONDS): cv.positive_int,
            vol.Optional(CONF_BOARDING_WALK_SECONDS): cv.positive_int,
            vol.Optional(CONF_STAGING_MODE): cv.boolean,
            vol.Required(CONF_ROUTES): vol.All(
                cv.ensure_list,
                [ROUTE_SCHEMA],
                vol.Length(min=1, msg="must contain at least one route"),
            ),
        }
    ),
    _normalise_commute,
)

COMMUTES_SCHEMA = vol.All(
    cv.ensure_list,
    [COMMUTE_SCHEMA],
    vol.Length(min=1, msg="must contain at least one commute"),
)


def _normalise_commute_tracker(config: dict[str, Any]) -> dict[str, Any]:
    """Cascade root configuration defaults down to child commutes and routes."""
    data = dict(config)
    root_poll = data.get(CONF_POLL_INTERVAL)
    root_strat = data.get(CONF_ROLLUP_STRATEGY)
    root_buffer = data.get(CONF_ROUTE_LATE_BUFFER_SECONDS)
    root_grace_sec = data.get(CONF_GRACE_SECONDS)
    root_grace_frac = data.get(CONF_GRACE_FRACTION)
    root_prep = data.get(CONF_PREP_SECONDS)
    root_walk = data.get(CONF_BOARDING_WALK_SECONDS)
    root_staging = data.get(CONF_STAGING_MODE, DEFAULT_STAGING_MODE)

    normalised_commutes: list[dict[str, Any]] = []
    for commute_raw in data.get(CONF_COMMUTES, []):
        commute = dict(commute_raw)

        if CONF_STAGING_MODE not in commute:
            commute[CONF_STAGING_MODE] = root_staging

        if CONF_POLL_INTERVAL not in commute:
            commute[CONF_POLL_INTERVAL] = (
                root_poll if root_poll is not None else DEFAULT_POLL_INTERVAL_SECONDS
            )

        if CONF_ROLLUP_STRATEGY not in commute:
            commute[CONF_ROLLUP_STRATEGY] = (
                root_strat if root_strat is not None else DEFAULT_ROLLUP_STRATEGY
            )

        if CONF_ROUTE_LATE_BUFFER_SECONDS not in commute:
            commute[CONF_ROUTE_LATE_BUFFER_SECONDS] = (
                root_buffer
                if root_buffer is not None
                else DEFAULT_ROUTE_LATE_BUFFER_SECONDS
            )

        if CONF_GRACE_SECONDS not in commute and CONF_GRACE_FRACTION not in commute:
            if root_grace_sec is not None:
                commute[CONF_GRACE_SECONDS] = root_grace_sec
            elif root_grace_frac is not None:
                commute[CONF_GRACE_FRACTION] = root_grace_frac

        if CONF_PREP_SECONDS not in commute and root_prep is not None:
            commute[CONF_PREP_SECONDS] = root_prep

        if CONF_BOARDING_WALK_SECONDS not in commute and root_walk is not None:
            commute[CONF_BOARDING_WALK_SECONDS] = root_walk

        normalised_routes: list[dict[str, Any]] = []
        for route_raw in commute.get(CONF_ROUTES, []):
            route = dict(route_raw)
            if CONF_PREP_SECONDS not in route and CONF_PREP_SECONDS in commute:
                route[CONF_PREP_SECONDS] = commute[CONF_PREP_SECONDS]
            if (
                CONF_BOARDING_WALK_SECONDS not in route
                and CONF_BOARDING_WALK_SECONDS in commute
            ):
                route[CONF_BOARDING_WALK_SECONDS] = commute[CONF_BOARDING_WALK_SECONDS]
            normalised_routes.append(route)

        commute[CONF_ROUTES] = normalised_routes
        normalised_commutes.append(commute)

    data[CONF_COMMUTES] = normalised_commutes
    return data


COMMUTE_TRACKER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_PROVIDERS, default=dict): PROVIDERS_SCHEMA,
            vol.Exclusive(
                CONF_GRACE_SECONDS,
                "grace_group",
                msg=_ERR_MUTUAL_GRACE,
            ): cv.positive_int,
            vol.Exclusive(
                CONF_GRACE_FRACTION,
                "grace_group",
                msg=_ERR_MUTUAL_GRACE,
            ): cv.small_float,
            vol.Optional(CONF_POLL_INTERVAL): cv.positive_int,
            vol.Optional(CONF_ROLLUP_STRATEGY): vol.In(
                [strat.value for strat in RollupStrategy]
            ),
            vol.Optional(CONF_ROUTE_LATE_BUFFER_SECONDS): cv.positive_int,
            vol.Optional(CONF_PREP_SECONDS): cv.positive_int,
            vol.Optional(CONF_BOARDING_WALK_SECONDS): cv.positive_int,
            vol.Optional(CONF_STAGING_MODE, default=DEFAULT_STAGING_MODE): cv.boolean,
            vol.Required(CONF_COMMUTES): COMMUTES_SCHEMA,
        }
    ),
    _normalise_commute_tracker,
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): COMMUTE_TRACKER_SCHEMA,
    },
    extra=vol.ALLOW_EXTRA,
)
