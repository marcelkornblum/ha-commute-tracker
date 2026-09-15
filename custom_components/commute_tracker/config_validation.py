"""Configuration schema validation for Commute Tracker integration."""

from typing import Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from custom_components.commute_tracker.const import (
    CONF_ACTIVE_SENSOR,
    CONF_ALIGHTING_WALK_SECONDS,
    CONF_API_KEY,
    CONF_APP_ID,
    CONF_APP_KEY,
    CONF_BOARDING_STOP,
    CONF_COMMUTE_ID,
    CONF_COMMUTE_TITLE,
    CONF_COMMUTES,
    CONF_CORRIDOR_STOPS,
    CONF_DEFAULT_GRACE_FRACTION,
    CONF_DEFAULT_GRACE_SECONDS,
    CONF_DESTINATION_STOP,
    CONF_DIRECTION,
    CONF_GRACE_FRACTION,
    CONF_GRACE_SECONDS,
    CONF_IN_VEHICLE_DURATION_SECONDS,
    CONF_LINE,
    CONF_MODE,
    CONF_PERSON_NAME,
    CONF_PERSON_PICTURE,
    CONF_POLL_INTERVAL,
    CONF_PREP_SECONDS,
    CONF_PROVIDER,
    CONF_PROVIDERS,
    CONF_ROLLUP_STRATEGY,
    CONF_ROUTE_ID,
    CONF_ROUTE_LATE_BUFFER_SECONDS,
    CONF_ROUTES,
    CONF_TARGET_ARRIVAL,
    CONF_TARGET_ARRIVAL_TIME,
    CONF_TARGET_STOP,
    CONF_WALK_SECONDS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_PROVIDER,
    DEFAULT_ROLLUP_STRATEGY,
    DEFAULT_ROUTE_LATE_BUFFER_SECONDS,
    DOMAIN,
)
from custom_components.commute_tracker.models import RollupStrategy, TransitMode


def _normalise_route(route: dict[str, Any]) -> dict[str, Any]:
    """Normalise route parameters, deriving route ID and stop aliases."""
    data = dict(route)
    if CONF_ROUTE_ID not in data or not data[CONF_ROUTE_ID]:
        line_val = str(data.get(CONF_LINE, "route"))
        data[CONF_ROUTE_ID] = slugify(line_val)

    if CONF_BOARDING_STOP not in data and CONF_TARGET_STOP in data:
        data[CONF_BOARDING_STOP] = data[CONF_TARGET_STOP]

    if CONF_CORRIDOR_STOPS not in data:
        data[CONF_CORRIDOR_STOPS] = []

    return data


def _normalise_commute(commute: dict[str, Any]) -> dict[str, Any]:
    """Normalise commute parameters, applying defaults and resolving aliases."""
    data = dict(commute)
    if CONF_COMMUTE_ID not in data or not data[CONF_COMMUTE_ID]:
        title = data.get(CONF_COMMUTE_TITLE, "commute")
        data[CONF_COMMUTE_ID] = slugify(str(title))

    if CONF_TARGET_ARRIVAL_TIME not in data and CONF_TARGET_ARRIVAL in data:
        data[CONF_TARGET_ARRIVAL_TIME] = data[CONF_TARGET_ARRIVAL]

    if CONF_DEFAULT_GRACE_SECONDS not in data and CONF_GRACE_SECONDS in data:
        data[CONF_DEFAULT_GRACE_SECONDS] = data[CONF_GRACE_SECONDS]

    if CONF_DEFAULT_GRACE_FRACTION not in data and CONF_GRACE_FRACTION in data:
        data[CONF_DEFAULT_GRACE_FRACTION] = data[CONF_GRACE_FRACTION]

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

ROUTE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_ROUTE_ID): cv.string,
            vol.Required(CONF_MODE): vol.In([mode.value for mode in TransitMode]),
            vol.Required(CONF_LINE): cv.string,
            vol.Optional(CONF_PROVIDER, default=DEFAULT_PROVIDER): cv.string,
            vol.Optional(CONF_WALK_SECONDS): cv.positive_int,
            vol.Optional(CONF_PREP_SECONDS): cv.positive_int,
            vol.Optional(CONF_GRACE_SECONDS): cv.positive_int,
            vol.Optional(CONF_GRACE_FRACTION): cv.small_float,
            vol.Optional(CONF_BOARDING_STOP): cv.string,
            vol.Optional(CONF_TARGET_STOP): cv.string,
            vol.Optional(CONF_DESTINATION_STOP): cv.string,
            vol.Optional(CONF_DIRECTION): cv.string,
            vol.Optional(CONF_IN_VEHICLE_DURATION_SECONDS): cv.positive_int,
            vol.Optional(CONF_ALIGHTING_WALK_SECONDS): cv.positive_int,
            vol.Optional(CONF_TARGET_ARRIVAL_TIME): cv.string,
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
            vol.Required(CONF_COMMUTE_TITLE): cv.string,
            vol.Required(CONF_ACTIVE_SENSOR): cv.entity_id,
            vol.Optional(CONF_TARGET_ARRIVAL_TIME): cv.string,
            vol.Optional(CONF_TARGET_ARRIVAL): cv.string,
            vol.Optional(CONF_PERSON_NAME): cv.string,
            vol.Optional(CONF_PERSON_PICTURE): cv.string,
            vol.Optional(CONF_DEFAULT_GRACE_SECONDS): cv.positive_int,
            vol.Optional(CONF_GRACE_SECONDS): cv.positive_int,
            vol.Optional(CONF_DEFAULT_GRACE_FRACTION): cv.small_float,
            vol.Optional(CONF_GRACE_FRACTION): cv.small_float,
            vol.Optional(CONF_ROLLUP_STRATEGY, default=DEFAULT_ROLLUP_STRATEGY): vol.In(
                [strat.value for strat in RollupStrategy]
            ),
            vol.Optional(
                CONF_ROUTE_LATE_BUFFER_SECONDS,
                default=DEFAULT_ROUTE_LATE_BUFFER_SECONDS,
            ): cv.positive_int,
            vol.Optional(
                CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL_SECONDS
            ): cv.positive_int,
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

COMMUTE_TRACKER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PROVIDERS, default=dict): PROVIDERS_SCHEMA,
        vol.Required(CONF_COMMUTES): COMMUTES_SCHEMA,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): COMMUTE_TRACKER_SCHEMA,
    },
    extra=vol.ALLOW_EXTRA,
)
