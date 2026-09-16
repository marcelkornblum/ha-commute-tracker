# Lovelace Custom Card Guide (`commute-tracker-card`)

The `commute-tracker-card` is a custom Home Assistant Lovelace dashboard card designed specifically for the Commute Tracker integration. Built with LitElement and TypeScript, it displays multi-modal transit corridors side-by-side with live vehicle positioning, real-time urgency stages, and an in-card details overlay.

---

## Key Features

- **Unified Master Header**: Displays the commuter avatar, commute title, and colour-coded urgency badge (`Standby`, `Leave in Xm`, `🚨 LEAVE NOW`).
- **Arbitration Sorting**: Automatically prioritises and places the recommended route (`active_option`) at the top of the stack.
- **Corridor Schematic**: Live SVG schematic tracking vehicle progression across corridor stops, highlighting the boarding station and vehicle location with smooth animations.
- **Terminus Station Support**: Handles terminus origins (e.g. railway terminus stations) using a brand-coloured gradient that fades to complete transparency on the approach side.
- **In-Card Details Overlay**: Clicking any transit module opens the route's line status details and advanced technical diagnostics directly inside the card—eliminating the need for separate dashboard subviews or complex router configurations.
- **Zero Layout Reflow**: Matches the main card's height dynamically to prevent page jumping when expanding or collapsing the details view.

---

## Installation

### Automatic Integration Loading (Recommended)

When `ha-commute-tracker` is installed via HACS or as a custom component, Home Assistant automatically serves the compiled card script from:

```text
/commute_tracker/commute-tracker-card.js
```

The integration registers this script with Home Assistant's frontend automatically via `add_extra_js_url`. Upon restarting Home Assistant after installing the integration, the card is immediately available in your dashboard.

### Manual Lovelace Resource Registration

If your Home Assistant configuration uses YAML dashboard mode or does not automatically load integration frontend assets, you can add the resource manually:

1. In Home Assistant, navigate to **Settings** -> **Dashboards** -> **Three Dots (Top Right)** -> **Resources**.
2. Click **Add Resource**.
3. Set **URL** to:
   ```text
   /commute_tracker/commute-tracker-card.js
   ```
4. Set **Resource type** to:
   ```text
   JavaScript Module
   ```
5. Click **Create** and refresh your browser.

If you manage your dashboard via `ui-lovelace.yaml`:

```yaml
lovelace:
  mode: yaml
  resources:
    - url: /commute_tracker/commute-tracker-card.js
      type: module
```

---

## Card Configuration

### Minimal Configuration

The card only requires the `entity_id` of the Master Rollup sensor. The card automatically discovers child route entities from the `child_entities` attribute:

```yaml
type: custom:commute-tracker-card
entity: sensor.commute_nelson_to_brick_lane
```

### Full Configuration Example

```yaml
type: custom:commute-tracker-card
entity: sensor.commute_nelson_to_brick_lane
title: "Work Commute"
routes:
  - sensor.commute_nelson_to_brick_lane_bus_26
  - sensor.commute_nelson_to_brick_lane_train_southeastern
```

### Configuration Options

| Option | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `type` | `string` | **Yes** | `custom:commute-tracker-card` | Card identifier. |
| `entity` | `string` | **Yes** | *None* | Entity ID of the Commute Tracker Master Rollup sensor (e.g. `sensor.commute_<commute_id>`). |
| `title` | `string` | No | Sensor `commute_title` / `friendly_name` | Custom title displayed in the card header. |
| `routes` | `list[string]` | No | Master sensor `child_entities` attribute | Optional explicit list of child route sensor entity IDs to display and sort. |

---

## Interactive Behaviour & Data Consumption

### 1. Main View (Overview)
- **Header**: Shows commuter portrait and leave-by urgency stage.
- **Route Cards**: Each active route displays its route badge (e.g. `26`, `Southeastern`), destination, and line health (`✓ Good Service`, `⚠️ Minor Delays`).
- **Schematic Track**: Renders transit corridor stops (`is_target: true` boarding node with highlight halo) and the real-time vehicle marker.
- **Live Timings Grid**:
  - **Left**: Doorstep departure pill (`👟 07:42`).
  - **Centre**: Transit leg boarding & arrival (`07:50 🚌 08:15`).
  - **Right**: Destination arrival pill (`🏫 08:28`). If the journey is projected to arrive past the target buffer, this pill dynamically shifts to a red alert border and text.

### 2. Details Overlay
- Clicking any transit module opens the route's in-card details overlay.
- **Primary Section**: Shows live line status, transit provider feed name (e.g. TfL, National Rail), and any operational disruption notices.
- **Advanced Details Accordion**: Expandable view revealing:
  - Route Information: Direction, boarding location, doorstep countdown, target margin/slack, timeliness classification.
  - Technical & Debugging Parameters: Vehicle ID, corridor progress float, target destination time, arbitration strategy, and raw seconds counters.
- **Close Button**: Clicking `✕` smoothly returns to the main card overview without triggering page reloads.

---

## Standalone Preview Harness

To test and visually verify card rendering without running Home Assistant:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173/` in your browser. The preview harness includes:
- An interactive **Scenario Selector** (`Relaxed`, `Prepare`, `Leave Now`, `Disruption`, `Late Arrival`, `Standby`).
- A live **Corridor Progress Slider** to test vehicle marker tracking and transition smoothing in real time.

---

## Automated Testing

The frontend card includes unit tests, component tests, and DOM snapshot regression tests using Vitest and `happy-dom`:

```bash
cd frontend
npm test
```

To update DOM snapshots after intentional styling adjustments:

```bash
npm run test -- -u
```
