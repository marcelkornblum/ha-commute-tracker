"""Unit tests for Home Assistant translation files."""

import json
from pathlib import Path


def test_translations_validity() -> None:
    """Validate that strings.json and translations/en.json exist and match."""
    component_dir = (
        Path(__file__).parent.parent / "custom_components" / "commute_tracker"
    )
    strings_file = component_dir / "strings.json"
    en_file = component_dir / "translations" / "en.json"

    assert strings_file.is_file(), "strings.json must exist"
    assert en_file.is_file(), "translations/en.json must exist"

    strings_content = json.loads(strings_file.read_text(encoding="utf-8"))
    en_content = json.loads(en_file.read_text(encoding="utf-8"))

    assert strings_content == en_content, "strings.json and en.json must match"
    assert strings_content.get("title") == "Commute Tracker"
    assert "entity" in strings_content
    assert "sensor" in strings_content["entity"]
    assert "master_rollup" in strings_content["entity"]["sensor"]
    assert "child_route" in strings_content["entity"]["sensor"]

    config_errors = strings_content.get("config", {}).get("error", {})
    assert "mutual_grace" in config_errors
    assert "no_routes" in config_errors
    assert "no_commutes" in config_errors
    assert "cannot_connect" in config_errors
    assert "invalid_auth" in config_errors
    assert "invalid_name" in config_errors
    assert "invalid_sensor" in config_errors
    assert "invalid_line" in config_errors
    assert "invalid_boarding_stop" in config_errors

    config_aborts = strings_content.get("config", {}).get("abort", {})
    assert "already_configured" in config_aborts
    assert "no_routes" in config_aborts

    selectors = strings_content.get("selector", {})
    assert "rollup_strategy" in selectors
    assert "direction" in selectors
    assert "mode" in selectors
