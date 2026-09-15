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
