# Commute Tracker (`ha-commute-tracker`)

[![CI](https://github.com/marcelkornblum/ha-commute-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/marcelkornblum/ha-commute-tracker/actions/workflows/ci.yml)
[![HACS Default](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration and companion dashboard card that removes the anxiety from your daily travel. Commute Tracker monitors your alternative direct transit options in real time, factors in your walking time to the stop, and gives you a single, glanceable leave-by countdown so you always walk out the door at the perfect moment.

<p align="center">
  <img src="https://raw.githubusercontent.com/marcelkornblum/ha-commute-tracker/main/docs/assets/card-preview.png" alt="Commute Tracker Lovelace Card" width="480">
</p>

---

## Why Commute Tracker?

Most transit apps only tell you when a vehicle arrives at a stop, leaving you to calculate when to leave home, whether you will make it on time, or whether another bus or train has overtaken it.

Commute Tracker does the math for you:
- **Doorstep Countdown**: Factors in walking time so you know when to walk out your front door, not just when the vehicle departs.
- **Smart Route Arbitration**: Monitors multiple parallel options (e.g. Bus 26 vs Southeastern Train) and automatically promotes the quickest, most reliable choice to the top.
- **Visual Corridor Schematic**: A live schematic track that illustrates the vehicle's actual progress towards your boarding stop.
- **Actionable Urgency States**: Provides clear stages (`Standby`, `Leave in Xm`, `🚨 LEAVE NOW`) that are easy to view on wall tablets or feed into Home Assistant automations (e.g. flashing hallway lights amber when it's time to put your shoes on).
- **Zero Idle Polling**: Automatically sleeps outside of commute hours or once you have arrived, minimising API usage and preserving system resources.

---

## Installation

### Via HACS (Recommended)

1. Open **HACS** in Home Assistant and go to **Integrations**.
2. Click the three dots in the top-right corner and select **Custom repositories**.
3. Add repository URL:
   ```text
   https://github.com/marcelkornblum/ha-commute-tracker
   ```
4. Set **Category** to `Integration`.
5. Click **Add**, find **Commute Tracker**, and select **Download**.
6. Restart Home Assistant.

### Manual Installation

1. Download `commute_tracker.zip` from the [Latest Release](https://github.com/marcelkornblum/ha-commute-tracker/releases).
2. Extract the contents into your Home Assistant directory under:
   ```text
   config/custom_components/commute_tracker/
   ```
3. Restart Home Assistant.

The companion custom card (`commute-tracker-card`) is bundled with the integration and automatically registers itself with Home Assistant's Lovelace Resources table so it can be found in the dashboard edit view.

---

## Quick Start Configuration

Add your commute to your `configuration.yaml`:

```yaml
commute_tracker:
  providers:
    tfl:
      app_id: !secret tfl_app_id
      app_key: !secret tfl_app_key

  commutes:
    - name: "Nelson's Column to Brick Lane"
      active_sensor: binary_sensor.morning_commute_window
      target_time: "09:00"
      routes:
        - mode: bus
          line: "26"
          boarding_stop: "490013766F"
          destination_stop: "490004123E"
          boarding_walk_seconds: 360

        - mode: train
          line: "southeastern"
          boarding_stop: "910GCHRX"
          destination_stop: "910GLNDNBDG"
          boarding_walk_seconds: 480
```

Restart Home Assistant or reload your YAML configuration. Commute Tracker will create:
- A **Master Rollup Sensor** (`sensor.commute_nelsons_column_to_brick_lane`) representing the overall commute leave-by urgency and top recommended option.
- Individual **Child Route Sensors** for each configured route option.

---

## Dashboard Card

Commute Tracker includes a dedicated custom Lovelace card (`commute-tracker-card`) designed specifically for wall tablets, mobile dashboards, and desktop views.

### Adding via Visual UI
1. Edit your dashboard and click **Add Card**.
2. Search for **Commute Tracker Card** in the card picker.
3. Select your Master Commute sensor.

### Adding via YAML

```yaml
type: custom:commute-tracker-card
entity: sensor.commute_nelsons_column_to_brick_lane
```

Clicking any transit module on the card opens an in-card details overlay with line disruption notices and diagnostic telemetry without navigating away from your dashboard.

---

## Documentation

- **[Lovelace Custom Card Guide](docs/lovelace-card.md)**: Full card styling options, custom avatars, and configuration options.
- **[Configuration Reference & Schema](docs/configuration.md)**: Exhaustive reference for all root, commute, and route options, cascading overrides, and time buffers.
- **[Architecture & Developer Documentation](docs/README.md)**: Internal Python domain models, decision engine control flow, transit provider plugins, and testing instructions.

---

## Licence

Distributed under the [MIT Licence](LICENSE).
