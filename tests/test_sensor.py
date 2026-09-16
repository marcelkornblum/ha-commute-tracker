"""Unit and integration tests for Commute Tracker sensor entities and state engine."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.commute_tracker.const import DOMAIN
from custom_components.commute_tracker.coordinator import CommuteCoordinator
from custom_components.commute_tracker.engine import (
    ChildRouteState,
    CommuteEngine,
    CommuteState,
    MasterRollupState,
)
from custom_components.commute_tracker.models import (
    CommuteConfig,
    LineStatus,
    PillBadge,
    RollupStrategy,
    RouteConfig,
    TransitMode,
    UrgencyStage,
)
from custom_components.commute_tracker.sensor import (
    CommuteChildRouteSensor,
    CommuteMasterRollupSensor,
    derive_child_unique_id,
    derive_commute_unique_id,
)


def test_unique_id_slugification_defaults() -> None:
    """Verify unique_id generation defaults to slugified YAML name."""
    assert derive_commute_unique_id(commute_title="Work Commute") == "work_commute"
    assert (
        derive_commute_unique_id(commute_title="Kolya From Home") == "kolya_from_home"
    )
    assert (
        derive_commute_unique_id(commute_title="Morning Trip 123!")
        == "morning_trip_123"
    )

    child_uid = derive_child_unique_id(
        commute_unique_id="work_commute",
        route_id="bus_73",
    )
    assert child_uid == "work_commute_bus_73"


def test_unique_id_explicit_overrides() -> None:
    """Verify explicit YAML overrides take precedence over slugified names."""
    assert (
        derive_commute_unique_id(
            commute_title="Work Commute",
            explicit_id="custom_master_id",
        )
        == "custom_master_id"
    )
    assert (
        derive_child_unique_id(
            commute_unique_id="work_commute",
            route_id="bus_73",
            explicit_id="custom_child_id",
        )
        == "custom_child_id"
    )


def test_unique_id_staging_mode() -> None:
    """Verify unique_id generation appends _staging suffix when staging_mode is True."""
    assert (
        derive_commute_unique_id(
            commute_title="Work Commute",
            staging_mode=True,
        )
        == "work_commute_staging"
    )
    assert (
        derive_commute_unique_id(
            commute_title="Work Commute",
            explicit_id="custom_master_id",
            staging_mode=True,
        )
        == "custom_master_id_staging"
    )
    assert (
        derive_commute_unique_id(
            commute_title="Work Commute",
            explicit_id="custom_master_id_staging",
            staging_mode=True,
        )
        == "custom_master_id_staging"
    )

    child_uid = derive_child_unique_id(
        commute_unique_id="work_commute",
        route_id="bus_73",
        staging_mode=True,
    )
    assert child_uid == "work_commute_bus_73_staging"

    child_uid_explicit = derive_child_unique_id(
        commute_unique_id="work_commute",
        route_id="bus_73",
        explicit_id="custom_child_id",
        staging_mode=True,
    )
    assert child_uid_explicit == "custom_child_id_staging"

    child_uid_already_staging = derive_child_unique_id(
        commute_unique_id="work_commute_staging",
        route_id="bus_73",
        staging_mode=True,
    )
    assert child_uid_already_staging == "work_commute_bus_73_staging"


def test_child_sensor_icons() -> None:
    """Verify appropriate transit icons are assigned based on transit mode."""
    coord = AsyncMock(spec=CommuteCoordinator)
    coord.commute_config = CommuteConfig(commute_id="c1", routes=[])

    modes_to_icons = {
        TransitMode.BUS: "mdi:bus",
        TransitMode.TRAIN: "mdi:train",
        TransitMode.TUBE: "mdi:subway-variant",
        TransitMode.TRAM: "mdi:tram",
        TransitMode.FERRY: "mdi:ferry",
    }
    for mode, expected_icon in modes_to_icons.items():
        route = RouteConfig(route_id=f"r_{mode.value}", mode=mode, line="1")
        sensor = CommuteChildRouteSensor(coordinator=coord, route_config=route)
        assert sensor.icon == expected_icon


async def test_sensor_setup_and_entity_minimalism(hass: HomeAssistant) -> None:
    """Verify setup registers Master and Child sensors with zero extra state."""

    raw_config = {
        DOMAIN: {
            "commutes": [
                {
                    "name": "Work Commute",
                    "active_sensor": "binary_sensor.work_active",
                    "routes": [
                        {
                            "id": "bus_73",
                            "mode": "bus",
                            "line": "73",
                            "boarding_stop": "490013766F",
                        },
                        {
                            "id": "train_southern",
                            "mode": "train",
                            "line": "southern",
                            "boarding_stop": "910GBALHAM",
                        },
                    ],
                }
            ]
        }
    }

    hass.states.async_set("binary_sensor.work_active", "off")

    with patch(
        "custom_components.commute_tracker.CommuteEngine.async_evaluate_commute",
        new_callable=AsyncMock,
    ):
        setup_success = await async_setup_component(
            hass=hass,
            domain=DOMAIN,
            config=raw_config,
        )
        assert setup_success is True
        await hass.async_block_till_done()

    domain_states = [
        state
        for state in hass.states.async_all()
        if state.entity_id.startswith("sensor.commute_")
    ]
    registered_ids = {s.entity_id for s in domain_states}

    assert "sensor.commute_work_commute" in registered_ids
    assert "sensor.commute_work_commute_bus_73" in registered_ids
    assert "sensor.commute_work_commute_train_southern" in registered_ids

    assert len(registered_ids) == 3
    for entity_id in registered_ids:
        assert "raw" not in entity_id
        assert "timeliness" not in entity_id

    for coordinator in hass.data[DOMAIN]["coordinators"].values():
        coordinator.async_unload()


async def test_master_and_child_attributes_contract(hass: HomeAssistant) -> None:
    """Verify Master and Child sensors expose complete attribute dictionary."""
    route_bus = RouteConfig(
        route_id="bus_73",
        mode=TransitMode.BUS,
        line="73",
        boarding_stop="490013766F",
    )
    commute_cfg = CommuteConfig(
        commute_id="work",
        commute_title="Work",
        person_name="Alex",
        person_picture="https://example.com/alex.jpg",
        active_sensor="binary_sensor.work_active",
        routes=[route_bus],
    )

    engine = CommuteEngine(config=commute_cfg)
    coordinator = CommuteCoordinator(hass=hass, config=commute_cfg, engine=engine)

    pill = PillBadge(
        label="Leave in 4m",
        color="#4CAF50",
        bg="rgba(76, 175, 80, 0.2)",
        border="#4CAF50",
    )
    line_st = LineStatus(
        status_label="Good Service",
        status_color="#00A859",
        status_icon="mdi:check-circle",
        detail=None,
        is_delayed=False,
        is_cancelled=False,
    )
    stops = [{"stop_id": "490013766F", "short_name": "Royal Circus", "is_target": True}]

    mock_master = MasterRollupState(
        active_option="bus_73",
        urgency_stage=UrgencyStage.LEAVE_NOW,
        expected_boarding_time="08:35",
        expected_destination_time="08:55",
        seconds_to_board=360,
        seconds_to_leave=60,
        expected_destination_margin_seconds=300,
        route_label="73",
        will_arrive_on_time=True,
        strategy=RollupStrategy.LATE_WITH_BUFFER,
        leave_by_time="08:31",
        timeliness="on_time",
        destination="Victoria",
        line_status=line_st,
        next_summary="Next at 08:45 (in 16m)",
        pill_badge=pill,
        is_active=True,
    )
    mock_child = ChildRouteState(
        route_id="bus_73",
        mode="bus",
        urgency_stage=UrgencyStage.LEAVE_NOW,
        vehicle_id="LTZ1234",
        expected_boarding_time="08:35",
        expected_alighting_time="08:50",
        expected_destination_time="08:55",
        seconds_to_board=360,
        seconds_to_leave=60,
        leave_by_time="08:31",
        corridor_location="Approaching Royal Circus",
        corridor_progress=0.75,
        corridor_stops=stops,
        next_vehicle_id="LTZ5678",
        seconds_to_next_board=960,
        next_summary="Next at 08:45 (in 16m)",
        will_arrive_on_time=True,
        expected_destination_margin_seconds=300,
        timeliness="on_time",
        line_status=line_st,
        route_label="73",
        destination="Victoria",
        pill_badge=pill,
        is_active=True,
    )

    state = CommuteState(
        commute_id="work",
        master_rollup=mock_master,
        child_routes={"bus_73": mock_child},
    )
    coordinator.data = state
    coordinator._is_active = True

    master_sensor = CommuteMasterRollupSensor(coordinator=coordinator)
    child_sensor = CommuteChildRouteSensor(
        coordinator=coordinator,
        route_config=route_bus,
    )

    assert master_sensor.native_value == "leave_now"
    m_attrs = master_sensor.extra_state_attributes
    assert m_attrs["commute_id"] == "work"
    assert m_attrs["commute_title"] == "Work"
    assert m_attrs["person_name"] == "Alex"
    assert m_attrs["person_picture"] == "https://example.com/alex.jpg"
    assert m_attrs["active_option"] == "bus_73"
    assert m_attrs["is_relevant"] is True
    assert m_attrs["urgency_stage"] == "leave_now"
    assert m_attrs["expected_boarding_time"] == "08:35"
    assert m_attrs["expected_destination_time"] == "08:55"
    assert m_attrs["seconds_to_board"] == 360
    assert m_attrs["seconds_to_leave"] == 60
    assert m_attrs["leave_by_time"] == "08:31"
    assert m_attrs["timeliness"] == "on_time"
    assert m_attrs["expected_destination_margin_seconds"] == 300
    assert m_attrs["will_arrive_on_time"] is True
    assert m_attrs["pill_label"] == "Leave in 4m"
    assert m_attrs["pill_color"] == "#4CAF50"
    assert m_attrs["line_status_label"] == "Good Service"
    assert m_attrs["destination"] == "Victoria"
    assert m_attrs["next_summary"] == "Next at 08:45 (in 16m)"

    assert child_sensor.native_value == "leave_now"
    c_attrs = child_sensor.extra_state_attributes
    assert c_attrs["commute_id"] == "work"
    assert c_attrs["route_id"] == "bus_73"
    assert c_attrs["mode"] == "bus"
    assert c_attrs["direction"] == "from_home"
    assert c_attrs["route_label"] == "73"
    assert c_attrs["destination"] == "Victoria"
    assert c_attrs["route_color"] == "#DC241F"
    assert c_attrs["corridor_location"] == "Approaching Royal Circus"
    assert c_attrs["corridor_progress"] == 0.75
    assert c_attrs["corridor_stops"] == stops
    assert c_attrs["vehicle_id"] == "LTZ1234"
    assert c_attrs["expected_boarding_time"] == "08:35"
    assert c_attrs["expected_alighting_time"] == "08:50"
    assert c_attrs["expected_destination_time"] == "08:55"
    assert c_attrs["seconds_to_board"] == 360
    assert c_attrs["seconds_to_leave"] == 60
    assert c_attrs["expected_destination_margin_seconds"] == 300
    assert c_attrs["will_arrive_on_time"] is True
    assert c_attrs["next_summary"] == "Next at 08:45 (in 16m)"


async def test_sensor_sleep_and_wake_transitions(hass: HomeAssistant) -> None:
    """Verify sensor transitions to 'idle' when inactive and urgency when active."""

    raw_config = {
        DOMAIN: {
            "commutes": [
                {
                    "name": "Work",
                    "active_sensor": "binary_sensor.work_active",
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

    hass.states.async_set("binary_sensor.work_active", "off")
    setup_success = await async_setup_component(
        hass=hass,
        domain=DOMAIN,
        config=raw_config,
    )
    assert setup_success is True
    await hass.async_block_till_done()

    master_state = hass.states.get("sensor.commute_work")
    child_state = hass.states.get("sensor.commute_work_bus_73")

    assert master_state is not None
    assert master_state.state == "idle"
    assert master_state.attributes["is_relevant"] is False

    assert child_state is not None
    assert child_state.state == "idle"
    assert child_state.attributes["is_relevant"] is False

    coordinator = hass.data[DOMAIN]["coordinators"]["work"]
    live_master = MasterRollupState(
        active_option="bus_73",
        urgency_stage=UrgencyStage.RELAXED,
        expected_boarding_time="08:40",
        seconds_to_board=600,
        seconds_to_leave=300,
        route_label="73",
        is_active=True,
    )
    live_child = ChildRouteState(
        route_id="bus_73",
        mode="bus",
        urgency_stage=UrgencyStage.RELAXED,
        is_active=True,
    )
    live_commute_state = CommuteState(
        commute_id="work",
        master_rollup=live_master,
        child_routes={"bus_73": live_child},
    )

    coordinator.engine.async_evaluate_commute = AsyncMock(
        return_value=live_commute_state
    )

    hass.states.async_set("binary_sensor.work_active", "on")
    await hass.async_block_till_done()

    master_state_active = hass.states.get("sensor.commute_work")
    assert master_state_active is not None
    assert master_state_active.state == "relaxed"
    assert master_state_active.attributes["is_relevant"] is True

    coordinator.async_unload()


async def test_sensor_setup_staging_mode(hass: HomeAssistant) -> None:
    """Verify staging_mode: true appends _staging to entity_ids and child_entities."""
    raw_config = {
        DOMAIN: {
            "staging_mode": True,
            "commutes": [
                {
                    "name": "Work Commute",
                    "active_sensor": "binary_sensor.work_active",
                    "routes": [
                        {
                            "id": "bus_73",
                            "mode": "bus",
                            "line": "73",
                            "boarding_stop": "490013766F",
                        },
                    ],
                }
            ],
        }
    }

    hass.states.async_set("binary_sensor.work_active", "off")

    with patch(
        "custom_components.commute_tracker.CommuteEngine.async_evaluate_commute",
        new_callable=AsyncMock,
    ):
        setup_success = await async_setup_component(
            hass=hass,
            domain=DOMAIN,
            config=raw_config,
        )
        assert setup_success is True
        await hass.async_block_till_done()

    domain_states = [
        state
        for state in hass.states.async_all()
        if state.entity_id.startswith("sensor.commute_")
    ]
    registered_ids = {s.entity_id for s in domain_states}

    assert "sensor.commute_work_commute_staging" in registered_ids
    assert "sensor.commute_work_commute_bus_73_staging" in registered_ids

    master_state = hass.states.get("sensor.commute_work_commute_staging")
    assert master_state is not None
    assert master_state.attributes["child_entities"] == [
        "sensor.commute_work_commute_bus_73_staging"
    ]

    for coordinator in hass.data[DOMAIN]["coordinators"].values():
        coordinator.async_unload()
