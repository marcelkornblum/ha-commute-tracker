"""Schema, duration, validation, and preview helpers for Commute Tracker flows."""

from typing import Any

import voluptuous as vol
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from custom_components.commute_tracker.const import (
    CONF_ACTIVE_SENSOR,
    CONF_ALIGHTING_STOP,
    CONF_AMBER_THRESHOLD_SECONDS,
    CONF_BOARDING_STOP,
    CONF_COMMUTE_TITLE,
    CONF_CORRIDOR_STOPS,
    CONF_DESTINATION,
    CONF_GRACE_FRACTION,
    CONF_GRACE_SECONDS,
    CONF_LINE,
    CONF_MODE,
    CONF_PERSON,
    CONF_POLL_INTERVAL,
    CONF_PREP_SECONDS,
    CONF_PREPARE_THRESHOLD_SECONDS,
    CONF_PROVIDER,
    CONF_ROUTE_LATE_BUFFER_SECONDS,
    CONF_ROUTE_NAME,
    CONF_TARGET_DESTINATION_TIME,
    DEFAULT_AMBER_THRESHOLD_SECONDS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_PREP_SECONDS,
    DEFAULT_PREPARE_THRESHOLD_SECONDS,
    DEFAULT_PROVIDER,
    DEFAULT_ROLLUP_STRATEGY,
    DEFAULT_ROUTE_LATE_BUFFER_SECONDS,
    DEFAULT_STAGING_MODE,
)
from custom_components.commute_tracker.engine import ChildRouteState
from custom_components.commute_tracker.models import (
    CorridorStop,
    RollupStrategy,
    TransitMode,
)

MIN_POLL_INTERVAL_SECONDS = 5

GRACE_FRACTION_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0.0,
        max=0.95,
        step=0.05,
        mode=selector.NumberSelectorMode.BOX,
    )
)

DURATION_SELECTOR = selector.DurationSelector(
    selector.DurationSelectorConfig(enable_day=False)
)

_COMMUTE_DURATION_KEYS: tuple[str, ...] = (
    CONF_PREP_SECONDS,
    CONF_PREPARE_THRESHOLD_SECONDS,
    CONF_AMBER_THRESHOLD_SECONDS,
    CONF_ROUTE_LATE_BUFFER_SECONDS,
    CONF_POLL_INTERVAL,
    CONF_GRACE_SECONDS,
)

_SECTION_KEYS: frozenset[str] = frozenset(
    {
        "overview",
        "destination_timings",
        "rollup_strategy_sec",
        "advanced_settings",
        "service_details",
        "boarding_walk",
        "alighting_walk",
        "stop_display_names",
        "stop_lead_times",
    }
)


def seconds_to_duration(total_seconds: int) -> dict[str, int]:
    """Convert integer seconds to a Home Assistant DurationSelector mapping."""
    clamped = max(0, int(total_seconds))
    hours, rem = divmod(clamped, 3600)
    minutes, seconds = divmod(rem, 60)
    return {"hours": hours, "minutes": minutes, "seconds": seconds}


def duration_to_seconds(value: Any) -> int | None:
    """Convert a DurationSelector mapping or numeric value into integer seconds."""
    if value is None:
        return None
    if isinstance(value, dict):
        hours = int(value.get("hours") or 0)
        minutes = int(value.get("minutes") or 0)
        seconds = int(value.get("seconds") or 0)
        return max(0, hours * 3600 + minutes * 60 + seconds)
    if isinstance(value, (int, float)):
        return max(0, int(value))
    raw = str(value).strip()
    if not raw:
        return None
    return max(0, int(raw))


def flatten_input(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten Home Assistant section-wrapped form inputs into a single mapping."""
    flattened: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict) and key in _SECTION_KEYS:
            flattened.update(value)
        else:
            flattened[key] = value
    return flattened


def normalise_commute_durations(flat: dict[str, Any]) -> dict[str, Any]:
    """Convert DurationSelector fields in flattened commute input to integer seconds."""
    normalised = dict(flat)
    for key in _COMMUTE_DURATION_KEYS:
        if key in normalised:
            parsed = duration_to_seconds(value=normalised[key])
            if parsed is None:
                normalised.pop(key, None)
            else:
                normalised[key] = parsed
    return normalised


def has_input_value(flat: dict[str, Any], key: str) -> bool:
    """Return whether a flattened form dictionary contains a non-empty value."""
    value = flat.get(key)
    if value is None:
        return False
    if isinstance(value, dict):
        return True
    return str(value).strip() != ""


def validate_grace_inputs(flat: dict[str, Any], errors: dict[str, str]) -> None:
    """Validate mutual exclusion between grace_seconds and grace_fraction."""
    if has_input_value(flat=flat, key=CONF_GRACE_SECONDS) and has_input_value(
        flat=flat, key=CONF_GRACE_FRACTION
    ):
        errors["base"] = "mutual_grace"


def validate_commute_inputs(flat: dict[str, Any], errors: dict[str, str]) -> None:
    """Validate commute name, active sensor, poll interval floor, and grace rules."""
    commute_name = str(flat.get("name", "")).strip()
    active_sensor = str(flat.get("active_sensor", "")).strip()
    if not commute_name:
        errors["name"] = "invalid_name"
    if not active_sensor:
        errors["active_sensor"] = "invalid_sensor"
    poll_interval = flat.get(CONF_POLL_INTERVAL)
    if poll_interval is not None and int(poll_interval) < MIN_POLL_INTERVAL_SECONDS:
        errors[CONF_POLL_INTERVAL] = "invalid_poll_interval"
    validate_grace_inputs(flat=flat, errors=errors)


def is_route_service_unchanged(
    existing: dict[str, Any],
    provider_id: str,
    mode: TransitMode,
    line: str,
    boarding_stop: str,
    alighting_stop: str | None,
    has_credentials: bool,
) -> bool:
    """Return whether provider, service, and stop identities are unchanged."""
    if has_credentials:
        return False
    existing_provider = str(existing.get(CONF_PROVIDER, DEFAULT_PROVIDER)).strip()
    existing_mode = str(existing.get(CONF_MODE, "")).strip()
    existing_line = str(existing.get(CONF_LINE, "")).strip()
    existing_boarding = str(existing.get(CONF_BOARDING_STOP, "")).strip()
    existing_alighting = str(existing.get(CONF_ALIGHTING_STOP) or "").strip()
    return (
        existing_provider == provider_id
        and existing_mode == mode.value
        and existing_line == line
        and existing_boarding == boarding_stop
        and existing_alighting == (alighting_stop or "")
    )


def format_route_summary_label(route: dict[str, Any]) -> str:
    """Format a concise label for a route dictionary in menu headers."""
    return str(
        route.get(CONF_ROUTE_NAME)
        or route.get("route_name")
        or f"{str(route.get('mode', '')).title()} {route.get('line', '')}".strip()
    )


def select_exact_or_single_stop(
    query: str,
    candidates: list[CorridorStop],
) -> tuple[str | None, list[CorridorStop]]:
    """Resolve an exact stop ID or unique match, else return ambiguous candidates."""
    if not candidates:
        return None, []
    query_upper = query.strip().upper()
    exact = next(
        (stop for stop in candidates if stop.id.strip().upper() == query_upper),
        None,
    )
    if exact is not None:
        return exact.id, []
    if len(candidates) == 1:
        return candidates[0].id, []
    return None, candidates


def build_commute_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Construct Commute Settings schema with structured sections and selectors."""
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
                    "suggested_value": d.get("destination") or d.get(CONF_DESTINATION)
                },
            )
        ] = cv.string
    else:
        dest_timings_dict[vol.Optional("destination")] = cv.string

    if d.get(CONF_TARGET_DESTINATION_TIME):
        dest_timings_dict[
            vol.Optional(
                "target_destination_time",
                description={"suggested_value": d.get(CONF_TARGET_DESTINATION_TIME)},
            )
        ] = selector.TimeSelector(selector.TimeSelectorConfig())
    else:
        dest_timings_dict[vol.Optional("target_destination_time")] = (
            selector.TimeSelector(selector.TimeSelectorConfig())
        )

    prep_default = duration_to_seconds(
        value=d.get("prep_seconds", DEFAULT_PREP_SECONDS)
    )
    prepare_default = duration_to_seconds(
        value=d.get(CONF_PREPARE_THRESHOLD_SECONDS, DEFAULT_PREPARE_THRESHOLD_SECONDS)
    )
    amber_default = duration_to_seconds(
        value=d.get(CONF_AMBER_THRESHOLD_SECONDS, DEFAULT_AMBER_THRESHOLD_SECONDS)
    )
    dest_timings_dict[
        vol.Optional(
            "prep_seconds",
            default=seconds_to_duration(
                total_seconds=prep_default
                if prep_default is not None
                else DEFAULT_PREP_SECONDS
            ),
        )
    ] = DURATION_SELECTOR
    dest_timings_dict[
        vol.Optional(
            CONF_PREPARE_THRESHOLD_SECONDS,
            default=seconds_to_duration(
                total_seconds=prepare_default
                if prepare_default is not None
                else DEFAULT_PREPARE_THRESHOLD_SECONDS
            ),
        )
    ] = DURATION_SELECTOR
    dest_timings_dict[
        vol.Optional(
            CONF_AMBER_THRESHOLD_SECONDS,
            default=seconds_to_duration(
                total_seconds=amber_default
                if amber_default is not None
                else DEFAULT_AMBER_THRESHOLD_SECONDS
            ),
        )
    ] = DURATION_SELECTOR

    late_buffer_default = duration_to_seconds(
        value=d.get("route_late_buffer_seconds", DEFAULT_ROUTE_LATE_BUFFER_SECONDS)
    )
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
            default=seconds_to_duration(
                total_seconds=late_buffer_default
                if late_buffer_default is not None
                else DEFAULT_ROUTE_LATE_BUFFER_SECONDS
            ),
        ): DURATION_SELECTOR,
    }

    poll_default = duration_to_seconds(
        value=d.get("poll_interval", DEFAULT_POLL_INTERVAL_SECONDS)
    )
    advanced_dict: dict[Any, Any] = {
        vol.Optional(
            "poll_interval",
            default=seconds_to_duration(
                total_seconds=poll_default
                if poll_default is not None
                else DEFAULT_POLL_INTERVAL_SECONDS
            ),
        ): DURATION_SELECTOR,
        vol.Optional(
            "staging_mode",
            default=d.get("staging_mode", DEFAULT_STAGING_MODE),
        ): cv.boolean,
    }
    commute_grace = duration_to_seconds(value=d.get(CONF_GRACE_SECONDS))
    if commute_grace is not None:
        advanced_dict[
            vol.Optional(
                CONF_GRACE_SECONDS,
                description={
                    "suggested_value": seconds_to_duration(total_seconds=commute_grace)
                },
            )
        ] = DURATION_SELECTOR
    else:
        advanced_dict[vol.Optional(CONF_GRACE_SECONDS)] = DURATION_SELECTOR

    if d.get(CONF_GRACE_FRACTION) is not None:
        advanced_dict[
            vol.Optional(
                CONF_GRACE_FRACTION,
                description={"suggested_value": d.get(CONF_GRACE_FRACTION)},
            )
        ] = GRACE_FRACTION_SELECTOR
    else:
        advanced_dict[vol.Optional(CONF_GRACE_FRACTION)] = GRACE_FRACTION_SELECTOR

    return vol.Schema(
        {
            vol.Required("overview"): section(vol.Schema(overview_dict)),
            vol.Optional("destination_timings"): section(vol.Schema(dest_timings_dict)),
            vol.Optional("rollup_strategy_sec"): section(vol.Schema(strategy_dict)),
            vol.Optional("advanced_settings"): section(
                vol.Schema(advanced_dict),
                {"collapsed": True},
            ),
        }
    )


def format_route_preview_summary(
    route_dict: dict[str, Any],
    child: ChildRouteState | None = None,
    error: Exception | None = None,
) -> str:
    """Format a markdown preview summary for the opt-in test_route step."""
    corridor_count = len(route_dict.get(CONF_CORRIDOR_STOPS, []))
    summary_lines = [
        f"- **Service**: {route_dict.get(CONF_MODE, '')} "
        f"`{route_dict.get(CONF_LINE, '')}`",
        f"- **Boarding Stop**: `{route_dict.get(CONF_BOARDING_STOP, '')}`",
        f"- **Corridor Stops**: {corridor_count}",
    ]
    if error is not None:
        summary_lines.append(f"- **Preview Error**: {error}")
        return "\n".join(summary_lines)
    if child is None:
        summary_lines.append("- **Result**: Standby (no telemetry returned)")
        return "\n".join(summary_lines)

    status_label = (
        child.line_status.status_label if child.line_status is not None else "Unknown"
    )
    summary_lines.append(f"- **Line Status**: {status_label}")
    if child.expected_boarding_time:
        summary_lines.extend(
            [
                f"- **Next Departure**: {child.expected_boarding_time} "
                f"to {child.destination or 'Unknown'}",
                f"- **Leave By**: {child.leave_by_time or 'N/A'} "
                f"({child.urgency_stage.value})",
                f"- **Alighting ETA**: {child.expected_alighting_time or 'N/A'}",
                f"- **Corridor**: {child.corridor_location or 'N/A'} "
                f"(progress {child.corridor_progress})",
            ]
        )
    else:
        summary_lines.append(
            "- **Next Departure**: Standby (no live departures scheduled)"
        )
    return "\n".join(summary_lines)
