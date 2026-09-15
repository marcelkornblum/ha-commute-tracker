"""Unit tests for the template provider boilerplate."""

import pytest

from custom_components.commute_tracker.models import (
    RouteConfig,
    TransitMode,
)
from custom_components.commute_tracker.providers.template_provider import (
    TemplateTransitProvider,
)


def test_template_provider_instantiation_and_metadata() -> None:
    """Verify TemplateTransitProvider subclasses TransitProvider correctly."""
    provider = TemplateTransitProvider()
    assert provider.provider_id == "template"
    assert TransitMode.BUS in provider.supported_modes
    assert TransitMode.TRAIN in provider.supported_modes


@pytest.mark.asyncio
async def test_template_provider_async_methods() -> None:
    """Verify TemplateTransitProvider default implementations return valid models."""
    provider = TemplateTransitProvider()
    status = await provider.async_get_line_status("sample_line", TransitMode.BUS)
    assert status.status_label != ""
    assert status.status_colour.startswith("#")

    route = RouteConfig(
        route_id="sample_bus",
        mode=TransitMode.BUS,
        line="sample_line",
        provider="template",
        boarding_walk_seconds=180,
        prep_seconds=60,
        grace_seconds=120,
        boarding_stop="stop_a",
        alighting_stop="stop_b",
    )
    telemetry = await provider.async_get_telemetry(route)
    assert telemetry.route_id == "sample_bus"
    assert telemetry.line_id == "sample_line"
    assert telemetry.mode == TransitMode.BUS
