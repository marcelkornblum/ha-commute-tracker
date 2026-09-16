"""Unit tests for configuration schema validation."""

from typing import Any

import pytest
import voluptuous as vol

from custom_components.commute_tracker.config_validation import (
    COMMUTE_TRACKER_SCHEMA,
    CONFIG_SCHEMA,
)
from custom_components.commute_tracker.const import DOMAIN


def test_valid_minimal_configuration() -> None:
    """Validate minimal valid configuration with sensible defaults."""
    raw_config = {
        DOMAIN: {
            "commutes": [
                {
                    "name": "Work",
                    "active_sensor": "binary_sensor.work_commute_active",
                    "routes": [
                        {
                            "id": "bus_73",
                            "mode": "bus",
                            "line": "73",
                            "boarding_stop": "490013766F",
                        }
                    ],
                }
            ]
        }
    }
    validated = CONFIG_SCHEMA(raw_config)
    commute_data = validated[DOMAIN]["commutes"][0]
    assert commute_data["id"] == "work"
    assert commute_data["name"] == "Work"
    assert commute_data["active_sensor"] == "binary_sensor.work_commute_active"
    assert commute_data["poll_interval"] == 30
    assert commute_data["rollup_strategy"] == "late_with_buffer"
    assert commute_data["route_late_buffer_seconds"] == 300

    route_data = commute_data["routes"][0]
    assert route_data["id"] == "bus_73"
    assert route_data["mode"] == "bus"
    assert route_data["line"] == "73"
    assert route_data["provider"] == "tfl"
    assert route_data["boarding_stop"] == "490013766F"
    assert route_data["corridor_stops"] == []


def test_valid_full_configuration_with_providers() -> None:
    """Validate full configuration with provider credentials and route options."""
    raw_config = {
        "providers": {
            "tfl": {
                "app_id": "dummy_app_id",
                "app_key": "dummy_app_key",
            },
            "darwin": {
                "api_key": "dummy_darwin_key",
            },
        },
        "commutes": [
            {
                "id": "morning_commute",
                "name": "Morning Commute",
                "active_sensor": "binary_sensor.morning_active",
                "target_destination_time": "08:45",
                "person_name": "Marcel",
                "person_picture": "/local/marcel.png",
                "grace_seconds": 120,
                "rollup_strategy": "latest",
                "route_late_buffer_seconds": 180,
                "poll_interval": 15,
                "routes": [
                    {
                        "id": "train_southern",
                        "mode": "train",
                        "line": "southern",
                        "provider": "tfl",
                        "boarding_walk_seconds": 300,
                        "prep_seconds": 180,
                        "grace_fraction": 0.15,
                        "boarding_stop": "910GWNORWOD",
                        "alighting_stop": "910GLNDNBDC",
                        "direction": "from_home",
                        "transit_duration_seconds": 720,
                        "alighting_walk_seconds": 600,
                        "corridor_stops": ["910GWNORWOD", "910GTWH", "910GLNDNBDC"],
                    }
                ],
            }
        ],
    }
    validated = COMMUTE_TRACKER_SCHEMA(raw_config)
    assert validated["providers"]["tfl"]["app_id"] == "dummy_app_id"
    assert validated["providers"]["tfl"]["app_key"] == "dummy_app_key"
    assert validated["providers"]["darwin"]["api_key"] == "dummy_darwin_key"

    commute = validated["commutes"][0]
    assert commute["id"] == "morning_commute"
    assert commute["poll_interval"] == 15
    assert commute["rollup_strategy"] == "latest"

    route = commute["routes"][0]
    assert route["boarding_walk_seconds"] == 300
    assert len(route["corridor_stops"]) == 3


def test_deprecated_aliases_rejected() -> None:
    """Validate that deprecated aliases are rejected and not permitted."""
    raw_config = {
        "commutes": [
            {
                "name": "Evening Commute",
                "active_sensor": "binary_sensor.evening_active",
                "target_arrival": "17:30",
                "routes": [
                    {
                        "mode": "tube",
                        "line": "northern",
                        "target_stop": "940GZZLUBXN",
                    }
                ],
            }
        ]
    }
    with pytest.raises(vol.Invalid):
        COMMUTE_TRACKER_SCHEMA(raw_config)


def test_grace_mutual_exclusivity() -> None:
    """Verify that specifying both grace_seconds and grace_fraction fails validation."""
    config_both = {
        "commutes": [
            {
                "name": "Work",
                "active_sensor": "binary_sensor.work",
                "grace_seconds": 60,
                "grace_fraction": 0.2,
                "routes": [{"mode": "bus", "line": "26"}],
            }
        ]
    }
    with pytest.raises(vol.Invalid):
        COMMUTE_TRACKER_SCHEMA(config_both)


@pytest.mark.parametrize(
    "invalid_config, expected_error",
    [
        ({}, "required key not provided"),
        ({"commutes": []}, "must contain at least one commute"),
        (
            {"commutes": [{"name": "Work", "routes": [{"mode": "bus", "line": "26"}]}]},
            "active_sensor",
        ),
        (
            {
                "commutes": [
                    {
                        "name": "Work",
                        "active_sensor": "invalid_not_an_entity_id",
                        "routes": [{"mode": "bus", "line": "26"}],
                    }
                ]
            },
            "Entity ID",
        ),
        (
            {
                "commutes": [
                    {
                        "name": "Work",
                        "active_sensor": "binary_sensor.work",
                        "routes": [],
                    }
                ]
            },
            "must contain at least one route",
        ),
        (
            {
                "commutes": [
                    {
                        "name": "Work",
                        "active_sensor": "binary_sensor.work",
                        "routes": [{"mode": "teleport", "line": "space"}],
                    }
                ]
            },
            r"value must be one of",
        ),
        (
            {
                "commutes": [
                    {
                        "name": "Work",
                        "active_sensor": "binary_sensor.work",
                        "routes": [{"mode": "bus"}],
                    }
                ]
            },
            "line",
        ),
        (
            {
                "commutes": [
                    {
                        "name": "Work",
                        "active_sensor": "binary_sensor.work",
                        "poll_interval": -10,
                        "routes": [{"mode": "bus", "line": "26"}],
                    }
                ]
            },
            r"value must be at least",
        ),
        (
            {
                "commutes": [
                    {
                        "name": "Work",
                        "active_sensor": "binary_sensor.work",
                        "routes": [
                            {
                                "mode": "bus",
                                "line": "26",
                                "grace_fraction": 1.5,
                            }
                        ],
                    }
                ]
            },
            r"value must be at most 1",
        ),
        (
            {
                "rollup_strategy": "invalid_strat",
                "commutes": [
                    {
                        "name": "Work",
                        "active_sensor": "binary_sensor.work",
                        "routes": [{"mode": "bus", "line": "26"}],
                    }
                ],
            },
            r"value must be one of",
        ),
        (
            {
                "grace_seconds": 120,
                "grace_fraction": 0.25,
                "commutes": [
                    {
                        "name": "Work",
                        "active_sensor": "binary_sensor.work",
                        "routes": [{"mode": "bus", "line": "26"}],
                    }
                ],
            },
            r"Cannot specify both grace_seconds and grace_fraction",
        ),
    ],
)
def test_invalid_configurations(
    invalid_config: dict[str, Any],
    expected_error: str,
) -> None:
    """Validate that invalid configurations raise voluptuous validation errors."""
    with pytest.raises(vol.Invalid, match=expected_error):
        COMMUTE_TRACKER_SCHEMA(invalid_config)


def test_root_level_options_cascade_to_commutes_and_routes() -> None:
    """Validate that root-level defaults cascade down to child commutes and routes."""
    raw_config = {
        "rollup_strategy": "soonest",
        "route_late_buffer_seconds": 180,
        "prep_seconds": 200,
        "boarding_walk_seconds": 350,
        "poll_interval": 45,
        "grace_seconds": 90,
        "commutes": [
            {
                "name": "Work",
                "active_sensor": "binary_sensor.work_active",
                "routes": [
                    {
                        "mode": "bus",
                        "line": "73",
                        "boarding_stop": "490013766F",
                    }
                ],
            }
        ],
    }
    validated = COMMUTE_TRACKER_SCHEMA(raw_config)
    commute = validated["commutes"][0]
    assert commute["rollup_strategy"] == "soonest"
    assert commute["route_late_buffer_seconds"] == 180
    assert commute["prep_seconds"] == 200
    assert commute["boarding_walk_seconds"] == 350
    assert commute["poll_interval"] == 45
    assert commute["grace_seconds"] == 90

    route = commute["routes"][0]
    assert route["prep_seconds"] == 200
    assert route["boarding_walk_seconds"] == 350


def test_commute_and_route_overrides_root_level_options() -> None:
    """Validate that commute/route options take precedence over root defaults."""
    raw_config = {
        "rollup_strategy": "soonest",
        "route_late_buffer_seconds": 180,
        "prep_seconds": 200,
        "boarding_walk_seconds": 350,
        "poll_interval": 45,
        "grace_seconds": 90,
        "commutes": [
            {
                "name": "Work",
                "active_sensor": "binary_sensor.work_active",
                "rollup_strategy": "latest",
                "route_late_buffer_seconds": 240,
                "prep_seconds": 150,
                "grace_fraction": 0.2,
                "poll_interval": 20,
                "routes": [
                    {
                        "mode": "bus",
                        "line": "73",
                        "boarding_stop": "490013766F",
                        "boarding_walk_seconds": 180,
                        "prep_seconds": 60,
                        "grace_seconds": 45,
                    }
                ],
            }
        ],
    }
    validated = COMMUTE_TRACKER_SCHEMA(raw_config)
    commute = validated["commutes"][0]
    assert commute["rollup_strategy"] == "latest"
    assert commute["route_late_buffer_seconds"] == 240
    assert commute["prep_seconds"] == 150
    assert commute["boarding_walk_seconds"] == 350
    assert commute["poll_interval"] == 20
    assert commute["grace_fraction"] == 0.2
    assert "grace_seconds" not in commute

    route = commute["routes"][0]
    assert route["prep_seconds"] == 60
    assert route["boarding_walk_seconds"] == 180
    assert route["grace_seconds"] == 45


def test_staging_mode_configuration_cascades() -> None:
    """Validate that root staging_mode cascades to commutes when not overridden."""
    raw_config = {
        "staging_mode": True,
        "commutes": [
            {
                "name": "Work",
                "active_sensor": "binary_sensor.work_active",
                "routes": [
                    {
                        "mode": "bus",
                        "line": "73",
                    }
                ],
            }
        ],
    }
    validated = COMMUTE_TRACKER_SCHEMA(raw_config)
    commute = validated["commutes"][0]
    assert commute["staging_mode"] is True


def test_staging_mode_commute_override() -> None:
    """Validate that commute staging_mode overrides root staging_mode."""
    raw_config = {
        "staging_mode": False,
        "commutes": [
            {
                "name": "Work",
                "active_sensor": "binary_sensor.work_active",
                "staging_mode": True,
                "routes": [
                    {
                        "mode": "bus",
                        "line": "73",
                    }
                ],
            }
        ],
    }
    validated = COMMUTE_TRACKER_SCHEMA(raw_config)
    commute = validated["commutes"][0]
    assert commute["staging_mode"] is True
