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
                "target_arrival_time": "08:45",
                "person_name": "Marcel",
                "person_picture": "/local/marcel.png",
                "default_grace_seconds": 120,
                "default_grace_fraction": 0.2,
                "rollup_strategy": "latest",
                "route_late_buffer_seconds": 180,
                "poll_interval": 15,
                "routes": [
                    {
                        "id": "train_southern",
                        "mode": "train",
                        "line": "southern",
                        "provider": "tfl",
                        "walk_seconds": 300,
                        "prep_seconds": 180,
                        "grace_seconds": 90,
                        "grace_fraction": 0.15,
                        "boarding_stop": "910GWNORWOD",
                        "destination_stop": "910GLNDNBDC",
                        "direction": "inbound",
                        "in_vehicle_duration_seconds": 720,
                        "alighting_walk_seconds": 600,
                        "target_arrival_time": "08:45",
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
    assert route["walk_seconds"] == 300
    assert len(route["corridor_stops"]) == 3


def test_aliases_and_normalisation() -> None:
    """Validate alias normalisation for target_arrival and thresholds."""
    raw_config = {
        "commutes": [
            {
                "name": "Evening Commute",
                "active_sensor": "binary_sensor.evening_active",
                "target_arrival": "17:30",
                "grace_seconds": 150,
                "grace_fraction": 0.3,
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
    validated = COMMUTE_TRACKER_SCHEMA(raw_config)
    commute = validated["commutes"][0]
    assert commute["id"] == "evening_commute"
    assert commute["target_arrival_time"] == "17:30"
    assert commute["default_grace_seconds"] == 150
    assert commute["default_grace_fraction"] == 0.3

    route = commute["routes"][0]
    assert route["id"] == "northern"
    assert route["boarding_stop"] == "940GZZLUBXN"


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
    ],
)
def test_invalid_configurations(
    invalid_config: dict[str, Any],
    expected_error: str,
) -> None:
    """Validate that invalid configurations raise voluptuous validation errors."""
    with pytest.raises(vol.Invalid, match=expected_error):
        COMMUTE_TRACKER_SCHEMA(invalid_config)
