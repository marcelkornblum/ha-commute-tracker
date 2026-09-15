# Transit Provider Architecture & Plugin Guide

This document explains the Universal Transit Provider Plugin Architecture in `ha-commute-tracker`. It details the domain models, provider contracts, caching layer, registry validation, and provides a step-by-step tutorial on implementing a new transit authority provider.

---

## 1. Provider Architecture Overview

The integration uses a decoupled plugin pattern to ingest transit data from any authority or protocol (e.g. Transport for London Unified API, National Rail Darwin, Deutsche Bahn, Paris RATP, or GTFS-RT).

The core calculation engine ([`CommuteEngine`](../custom_components/commute_tracker/engine.py)) knows nothing about vendor APIs, HTTP endpoints, or specific JSON structures. It interacts solely with normalised domain models.

```mermaid
classDiagram
    class TransitMode {
        <<enumeration>>
        BUS
        TRAIN
        TUBE
        TRAM
        FERRY
    }

    class TransitProvider {
        <<abstract>>
        +provider_id: ClassVar[str]
        +supported_modes: ClassVar[set[TransitMode]]
        +async_get_line_status(line_id: str, mode: TransitMode)* LineStatus
        +async_get_telemetry(route: RouteConfig, snapshot: dict?)* RouteTelemetry
        +extract_telemetry_from_snapshot(route: RouteConfig, snapshot: dict)* RouteTelemetry
    }

    class DebouncedCache {
        +_ttl_seconds: float
        +async_get_or_set(key, fetch_callable)
        +invalidate(key)
        +clear()
    }

    class TransitProviderRegistry {
        +validate_provider(provider_cls)
        +is_valid_provider(provider_cls) bool
        +register(provider_cls)
        +get_provider(provider_id) TransitProvider
        +discover_providers()
    }

    class TfLTransitProvider {
        +provider_id = "tfl"
        +supported_modes = {BUS, TRAIN, TUBE, TRAM}
    }

    class TemplateTransitProvider {
        +provider_id = "template"
        +supported_modes = {BUS, TRAIN, TUBE, TRAM, FERRY}
    }

    TransitProvider <|-- TfLTransitProvider
    TransitProvider <|-- TemplateTransitProvider
    TransitProviderRegistry o-- TransitProvider
    TransitProvider o-- DebouncedCache
```

---

## 2. Normalised Domain Models

All providers map raw vendor responses into strongly-typed dataclasses defined in [`models.py`](../custom_components/commute_tracker/models.py):

### `TransitMode` (Enum)
Supported modes: `TransitMode.BUS`, `TransitMode.TRAIN`, `TransitMode.TUBE`, `TransitMode.TRAM`, `TransitMode.FERRY`.

### `LineStatus` (Dataclass)
Represents the operational health of a transit line:
- `status_label`: e.g. `"Good Service"`, `"Minor Delays"`, `"Suspended"`.
- `status_colour`: Hex colour code for UI indicators (e.g. `"#00A859"`).
- `status_icon`: Material Design icon string (e.g. `"mdi:check-circle"`).
- `reason`: Optional natural language description of disruptions.
- `is_delayed`: Boolean flag indicating delay.
- `is_cancelled`: Boolean flag indicating suspension or cancellation.

### `DeparturePrediction` (Dataclass)
Represents an individual vehicle arrival prediction:
- `vehicle_id`: Unique vehicle identifier (e.g. bus registration or train trip ID).
- `destination`: Terminal destination string (e.g. `"Hackney Central"`).
- `expected_time`: ISO-8601 arrival timestamp.
- `seconds_to_arrival`: Integer countdown until the vehicle arrives at the stop.
- `platform_or_bay`: Optional platform identifier.
- `is_realtime`: `True` for live telemetry, `False` for timetable schedules.
- `location`: Current vendor position description if available.

### `RouteTelemetry` (Dataclass)
Collated operational telemetry for a configured route:
- `route_id`: Route identifier string.
- `line_id`: Line or route number (e.g. `"26"`, `"central"`).
- `mode`: `TransitMode` enum.
- `departures`: Sorted list of `DeparturePrediction` objects targeting the boarding stop.
- `corridor_departures`: Map of `stop_id -> list[DeparturePrediction]` along the corridor.
- `stop_names`: Map of `stop_id -> display_name` for corridor stations.
- `active_vehicle_id`: Identified lead vehicle identifier.
- `line_status`: The active `LineStatus` model for the line.

---

## 3. Provider Contract & Registry Validation

The [`TransitProviderRegistry`](../custom_components/commute_tracker/providers/base.py) is responsible for registering, instantiating, and discovering providers.

### Strict Contract Validation (`validate_provider`)
To prevent broken or incomplete plugins from registering and crashing Home Assistant at runtime, the registry provides class-level contract evaluation:

```python
from custom_components.commute_tracker.providers.base import (
    TransitProviderRegistry,
    ProviderValidationError,
)

# Validates class compliance; raises ProviderValidationError on failure
TransitProviderRegistry.validate_provider(MyProvider)

# Returns boolean status without raising
is_valid = TransitProviderRegistry.is_valid_provider(MyProvider)
```

The validator verifies:
1. **Concrete Subclass**: Must inherit from [`TransitProvider`](../custom_components/commute_tracker/providers/base.py) and must not be abstract.
2. **Identifier**: Must declare a non-empty string `provider_id`.
3. **Supported Modes**: Must declare a non-empty `supported_modes` set consisting entirely of [`TransitMode`](../custom_components/commute_tracker/models.py) enum instances.
4. **Required Methods**: Must implement all required callable methods:
   - `async_get_line_status(line_id: str, mode: TransitMode) -> LineStatus`
   - `async_get_telemetry(route: RouteConfig, snapshot: dict | None) -> RouteTelemetry`
   - `extract_telemetry_from_snapshot(route: RouteConfig, snapshot: dict) -> RouteTelemetry`

### Dynamic Discovery
When `TransitProviderRegistry.discover_providers()` is called, it scans the `custom_components/commute_tracker/providers/` directory, imports every module, validates all discovered `TransitProvider` subclasses, and registers those that pass validation.

---

## 4. How to Create a New Transit Provider

Follow this guide to implement support for a new transit authority (e.g. `mta`, `bvg`, `national_rail`).

### Step 1: Create the Provider File
Create a new Python file in `custom_components/commute_tracker/providers/`, for example `mta.py`.

### Step 2: Implement the Class
Inherit from `TransitProvider` and implement the required methods:

```python
"""New York MTA transit provider implementation."""

from typing import Any, ClassVar
from custom_components.commute_tracker.models import (
    DeparturePrediction,
    LineStatus,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
)
from custom_components.commute_tracker.providers.base import TransitProvider

MTA_API_URL = "https://api.mta.info"


class MtaTransitProvider(TransitProvider):
    """Transit provider for New York MTA subway and bus feeds."""

    provider_id: ClassVar[str] = "mta"
    supported_modes: ClassVar[set[TransitMode]] = {
        TransitMode.BUS,
        TransitMode.TUBE,
    }

    async def async_get_line_status(
        self, line_id: str, mode: TransitMode
    ) -> LineStatus:
        """Fetch operational line status with debounced caching."""
        cache_key = f"mta_status_{line_id}"

        async def _fetch() -> LineStatus:
            if not self._session:
                return LineStatus(status_label="Unknown")

            url = f"{MTA_API_URL}/status/{line_id}"
            async with self._session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                return LineStatus(
                    status_label=data.get("status", "Good Service"),
                    status_colour="#00A859" if data.get("status") == "Good Service" else "#FFAE42",
                    status_icon="mdi:check-circle",
                )

        return await self._cache.async_get_or_set(key=cache_key, fetch_callable=_fetch)

    def extract_telemetry_from_snapshot(
        self, route: RouteConfig, snapshot: dict[str, Any]
    ) -> RouteTelemetry:
        """Extract normalised telemetry from offline snapshot dictionary."""
        # Parse static JSON fixture matching MTA format for testing
        raw_departures = snapshot.get("mta", {}).get(route.line, [])
        departures: list[DeparturePrediction] = []

        for item in raw_departures:
            if item.get("stop_id") == route.boarding_stop:
                departures.append(
                    DeparturePrediction(
                        vehicle_id=item.get("trip_id"),
                        destination=item.get("destination", ""),
                        expected_time=item.get("expected_arrival"),
                        seconds_to_arrival=int(item.get("countdown_seconds", 0)),
                        is_realtime=True,
                    )
                )

        departures.sort(key=lambda d: d.seconds_to_arrival)

        return RouteTelemetry(
            route_id=route.route_id,
            line_id=route.line,
            mode=route.mode,
            departures=departures,
            active_vehicle_id=departures[0].vehicle_id if departures else None,
            line_status=LineStatus(status_label="Good Service"),
        )

    async def async_get_telemetry(
        self, route: RouteConfig, snapshot: dict[str, Any] | None = None
    ) -> RouteTelemetry:
        """Fetch live telemetry from API or offline snapshot."""
        if snapshot is not None:
            return self.extract_telemetry_from_snapshot(route=route, snapshot=snapshot)

        # In production, query the live API via self._session
        line_status = await self.async_get_line_status(
            line_id=route.line, mode=route.mode
        )
        # Fetch and parse departures...
        return RouteTelemetry(
            route_id=route.route_id,
            line_id=route.line,
            mode=route.mode,
            departures=[],
            line_status=line_status,
        )
```

### Step 3: Write Unit Tests
Add test cases in `tests/test_mta_provider.py`:
1. Verify contract validity with `TransitProviderRegistry.validate_provider(MtaTransitProvider)`.
2. Test parsing of line statuses and arrival predictions against sample API payloads.
3. Test offline snapshot extraction.

### Step 4: Verification
Run the standard test runners:
```bash
./.venv/bin/pytest tests/test_mta_provider.py
./.venv/bin/ruff check custom_components/commute_tracker/providers/
./.venv/bin/mypy custom_components tests
```

Once placed in the `providers/` directory, `TransitProviderRegistry.discover_providers()` will automatically discover and load the provider without requiring edits to `engine.py` or the registry itself.
