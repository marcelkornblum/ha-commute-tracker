"""Unit tests for CommuteCoordinator sleep/wake lifecycle and polling."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.commute_tracker.coordinator import (
    CommuteCoordinator,
    create_idle_commute_state,
)
from custom_components.commute_tracker.engine import (
    CommuteEngine,
    CommuteState,
    MasterRollupState,
)
from custom_components.commute_tracker.models import (
    CommuteConfig,
    RouteConfig,
    TransitMode,
    UrgencyStage,
)


@pytest.fixture
def sample_commute_config() -> CommuteConfig:
    """Return a valid test CommuteConfig."""
    route = RouteConfig(
        route_id="bus_73",
        mode=TransitMode.BUS,
        line="73",
        boarding_stop="490013766F",
        walk_seconds=240,
        prep_seconds=120,
    )
    return CommuteConfig(
        commute_id="work",
        commute_title="Work Commute",
        active_sensor="binary_sensor.work_commute_active",
        target_arrival_time="09:00",
        poll_interval=30,
        routes=[route],
    )


async def test_coordinator_initial_sleep_state(
    hass: HomeAssistant,
    sample_commute_config: CommuteConfig,
) -> None:
    """Verify coordinator starts sleeping when active_sensor is not 'on'."""
    engine = CommuteEngine(config=sample_commute_config)
    engine.async_evaluate_commute = AsyncMock()  # type: ignore[method-assign]

    coordinator = CommuteCoordinator(
        hass=hass,
        config=sample_commute_config,
        engine=engine,
    )
    await coordinator.async_setup()

    assert not coordinator.is_active
    assert coordinator.update_interval is None
    assert coordinator.data is not None
    assert coordinator.data.master_rollup.urgency_stage == UrgencyStage.STANDBY
    assert not coordinator.data.master_rollup.is_active
    engine.async_evaluate_commute.assert_not_called()

    coordinator.async_unload()


async def test_coordinator_wake_and_sleep_transitions(
    hass: HomeAssistant,
    sample_commute_config: CommuteConfig,
) -> None:
    """Verify coordinator wakes on active sensor 'on' and sleeps on 'off'."""
    engine = CommuteEngine(config=sample_commute_config)
    mock_active_state = CommuteState(
        commute_id="work",
        master_rollup=MasterRollupState(
            active_option="bus_73",
            urgency_stage=UrgencyStage.LEAVE_NOW,
            expected_time="08:45",
            seconds_to_arrival=360,
            leave_in_seconds=0,
            route_label="73",
            is_active=True,
        ),
        child_routes={},
    )
    engine.async_evaluate_commute = AsyncMock(return_value=mock_active_state)  # type: ignore[method-assign]

    coordinator = CommuteCoordinator(
        hass=hass,
        config=sample_commute_config,
        engine=engine,
    )
    await coordinator.async_setup()

    assert not coordinator.is_active
    assert coordinator.update_interval is None

    hass.states.async_set("binary_sensor.work_commute_active", "on")
    await hass.async_block_till_done()

    assert coordinator.is_active
    assert coordinator.update_interval == timedelta(seconds=30)
    assert coordinator.data.master_rollup.urgency_stage == UrgencyStage.LEAVE_NOW
    assert coordinator.data.master_rollup.is_active
    engine.async_evaluate_commute.assert_called_once()

    hass.states.async_set("binary_sensor.work_commute_active", "off")
    await hass.async_block_till_done()

    assert not coordinator.is_active
    assert coordinator.update_interval is None
    assert coordinator.data.master_rollup.urgency_stage == UrgencyStage.STANDBY
    assert not coordinator.data.master_rollup.is_active

    coordinator.async_unload()


async def test_coordinator_initial_active_sensor(
    hass: HomeAssistant,
    sample_commute_config: CommuteConfig,
) -> None:
    """Verify coordinator starts active if active_sensor is already 'on' at setup."""
    hass.states.async_set("binary_sensor.work_commute_active", "on")
    await hass.async_block_till_done()

    engine = CommuteEngine(config=sample_commute_config)
    mock_state = CommuteState(
        commute_id="work",
        master_rollup=MasterRollupState(
            active_option="bus_73",
            urgency_stage=UrgencyStage.PREPARE,
            expected_time="08:50",
            seconds_to_arrival=600,
            leave_in_seconds=240,
            route_label="73",
            is_active=True,
        ),
        child_routes={},
    )
    engine.async_evaluate_commute = AsyncMock(return_value=mock_state)  # type: ignore[method-assign]

    coordinator = CommuteCoordinator(
        hass=hass,
        config=sample_commute_config,
        engine=engine,
    )
    await coordinator.async_setup()

    assert coordinator.is_active
    assert coordinator.update_interval == timedelta(seconds=30)
    assert coordinator.data.master_rollup.urgency_stage == UrgencyStage.PREPARE
    engine.async_evaluate_commute.assert_called_once()

    coordinator.async_unload()


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    sample_commute_config: CommuteConfig,
) -> None:
    """Verify coordinator raises UpdateFailed on API or engine errors."""
    hass.states.async_set("binary_sensor.work_commute_active", "on")
    await hass.async_block_till_done()

    engine = CommuteEngine(config=sample_commute_config)
    engine.async_evaluate_commute = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("Transit network connection timeout")
    )

    coordinator = CommuteCoordinator(
        hass=hass,
        config=sample_commute_config,
        engine=engine,
    )
    await coordinator.async_setup()
    assert not coordinator.last_update_success

    with pytest.raises(UpdateFailed, match="Transit network connection timeout"):
        await coordinator._async_update_data()

    coordinator.async_unload()


def test_create_idle_commute_state(sample_commute_config: CommuteConfig) -> None:
    """Verify create_idle_commute_state constructs standby structure."""
    idle = create_idle_commute_state(sample_commute_config)
    assert idle.commute_id == "work"
    assert idle.master_rollup.urgency_stage == UrgencyStage.STANDBY
    assert idle.master_rollup.active_option == "none"
    assert not idle.master_rollup.is_active
    assert "bus_73" in idle.child_routes
    assert not idle.child_routes["bus_73"].is_active
