"""DataUpdateCoordinator managing transit telemetry and sleep/wake polling."""

import logging
from datetime import timedelta

from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from custom_components.commute_tracker.engine import (
    ChildRouteState,
    CommuteEngine,
    CommuteState,
    MasterRollupState,
)
from custom_components.commute_tracker.models import (
    CommuteConfig,
    UrgencyStage,
)

_LOGGER = logging.getLogger(__name__)


def create_idle_commute_state(config: CommuteConfig) -> CommuteState:
    """Construct default idle CommuteState when commute monitoring is inactive."""
    master = MasterRollupState(
        active_option="none",
        urgency_stage=UrgencyStage.STANDBY,
        expected_time="",
        seconds_to_arrival=0,
        leave_in_seconds=0,
        route_label="",
        is_active=False,
    )
    child_routes: dict[str, ChildRouteState] = {}
    for route in config.routes:
        child_routes[route.route_id] = ChildRouteState(
            route_id=route.route_id,
            mode=route.mode.value,
            urgency_stage=UrgencyStage.STANDBY,
            is_active=False,
        )
    return CommuteState(
        commute_id=config.commute_id,
        master_rollup=master,
        child_routes=child_routes,
    )


class CommuteCoordinator(DataUpdateCoordinator[CommuteState]):
    """Data update coordinator for commute tracking with sensor-driven polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: CommuteConfig,
        engine: CommuteEngine | None = None,
    ) -> None:
        """Initialise coordinator with commute configuration and engine.

        :param hass: Home Assistant instance.
        :param config: CommuteConfig specifying routes and polling behaviour.
        :param engine: Optional pre-configured CommuteEngine instance.
        """
        self.commute_config = config
        self.engine = engine or CommuteEngine(config=config)
        self.active_sensor: str | None = config.active_sensor
        self.poll_interval: int = config.poll_interval
        self._unsub_active_listener: CALLBACK_TYPE | None = None
        self._is_active: bool = False

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"Commute {config.commute_id}",
            update_interval=None,
        )
        self.data = create_idle_commute_state(config=self.commute_config)

    @property
    def is_active(self) -> bool:
        """Return whether the coordinator is actively polling transit APIs."""
        return self._is_active

    async def async_setup(self) -> None:
        """Register active sensor state listener and set initial sleep/wake state."""
        if not self.active_sensor:
            self._is_active = True
            self.update_interval = timedelta(seconds=self.poll_interval)
            await self.async_refresh()
            return

        self._unsub_active_listener = async_track_state_change_event(
            self.hass,
            [self.active_sensor],
            self._async_handle_active_sensor_change,
        )

        current_state = self.hass.states.get(self.active_sensor)
        if current_state is not None and current_state.state == "on":
            self._is_active = True
            self.update_interval = timedelta(seconds=self.poll_interval)
            await self.async_refresh()
        else:
            self._is_active = False
            self.update_interval = None

    async def _async_handle_active_sensor_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state transitions for the external active_sensor."""
        new_state = event.data.get("new_state")
        is_now_active = new_state is not None and new_state.state == "on"

        if is_now_active:
            self._is_active = True
            self.update_interval = timedelta(seconds=self.poll_interval)
            await self.async_request_refresh()
            return

        self._is_active = False
        self.update_interval = None
        idle_state = create_idle_commute_state(config=self.commute_config)
        self.async_set_updated_data(data=idle_state)

    async def _async_update_data(self) -> CommuteState:
        """Fetch live telemetry and evaluate commute state."""
        if not self._is_active:
            return create_idle_commute_state(config=self.commute_config)

        try:
            return await self.engine.async_evaluate_commute()
        except Exception as err:
            raise UpdateFailed(f"Transit update failed: {err}") from err

    def async_unload(self) -> None:
        """Unsubscribe from external state change listeners."""
        if self._unsub_active_listener is not None:
            self._unsub_active_listener()
            self._unsub_active_listener = None
