import { LitElement, html, css, svg, PropertyValues } from "lit";
import { customElement, property, state } from "lit/decorators.js";

export interface CommuteCardConfig {
  type: string;
  entity: string;
  title?: string;
  routes?: string[];
}

export interface CorridorStop {
  short_name?: string;
  name?: string;
  stop_id?: string;
  is_target: boolean;
}

export interface HassEntityState {
  entity_id: string;
  state: string;
  attributes: Record<string, any>;
}

export interface HomeAssistantLike {
  states: Record<string, HassEntityState>;
}

const TRAIN_SVG_PATH =
  "M12 2c-4 0-8 .5-8 4v9.5C4 17.43 5.57 19 7.5 19L6 20.5v.5h12v-.5L16.5 19c1.93 0 3.5-1.57 3.5-3.5V6c0-3.5-4-4-8-4zm0 2c3.5 0 6 .5 6 2.5V8H6V6.5C6 4.5 8.5 4 12 4zm-5 12c-.83 0-1.5-.67-1.5-1.5S6.17 13 7 13s1.5.67 1.5 1.5S7.83 16 7 16zm10 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm1-5H6v-2h12v2z";

const BUS_SVG_PATH =
  "M4 16c0 .88.39 1.67 1 2.22V20c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h8v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1.78c.61-.55 1-1.34 1-2.22V6c0-3.5-3.58-4-8-4s-8 .5-8 4v10zm3.5 1c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm9 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm1.5-6H6V6h12v5z";

@customElement("commute-tracker-card")
export class CommuteTrackerCard extends LitElement {
  @property({ attribute: false }) public hass?: HomeAssistantLike;
  @state() private _config?: CommuteCardConfig;
  @state() private _selectedRouteId?: string;
  @state() private _mainHeight = 360;

  public setConfig(config: CommuteCardConfig): void {
    if (!config || !config.entity) {
      throw new Error("Please define an entity in your card configuration.");
    }
    this._config = config;
  }

  public getCardSize(): number {
    return 4;
  }

  static styles = css`
    :host {
      display: block;
      width: 100%;
      box-sizing: border-box;
      font-family: var(
        --ha-card-font-family,
        'Inter',
        -apple-system,
        BlinkMacSystemFont,
        'Segoe UI',
        Roboto,
        'Noto Color Emoji',
        'Apple Color Emoji',
        'Segoe UI Emoji',
        sans-serif
      );
    }

    ha-card,
    .card-container {
      display: block;
      background: #2b2d3a;
      border-radius: 16px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      padding: 16px;
      box-sizing: border-box;
      width: 100%;
      cursor: default;
      color: #ffffff;
      transition: all 0.25s ease;
    }

    .card-layout {
      display: flex;
      flex-direction: column;
      gap: 12px;
      text-align: left;
      width: 100%;
      box-sizing: border-box;
      min-width: 0;
    }

    /* Row 1: Unified Header */
    .header-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      box-sizing: border-box;
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .person-avatar {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      object-fit: cover;
      border: 2px solid rgba(255, 255, 255, 0.15);
      flex-shrink: 0;
    }

    .header-title {
      font-size: 16px;
      font-weight: 600;
      color: #ffffff;
      line-height: 1.2;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .header-right {
      text-align: right;
      flex-shrink: 0;
    }

    .header-pill {
      font-weight: 700;
      font-size: 13px;
      padding: 5px 12px;
      border-radius: 20px;
      display: inline-block;
      white-space: nowrap;
      border-width: 1px;
      border-style: solid;
      box-sizing: border-box;
    }

    /* Child Route Modules */
    .transit-module {
      text-decoration: none;
      color: inherit;
      display: flex;
      flex-direction: column;
      width: 100%;
      box-sizing: border-box;
      background: rgba(0, 0, 0, 0.25);
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      overflow: hidden;
      cursor: pointer;
      transition: background 0.2s ease, border-color 0.2s ease, transform 0.15s ease;
    }

    .transit-module:hover {
      background: rgba(255, 255, 255, 0.04);
      border-color: rgba(255, 255, 255, 0.12);
      transform: translateY(-1px);
    }

    /* Row 2: Transport Mode & Line Health */
    .module-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px 6px 12px;
      width: 100%;
      box-sizing: border-box;
    }

    .mode-label-group {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .route-badge {
      color: #ffffff;
      font-weight: 800;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 12px;
      letter-spacing: 0.5px;
    }

    .destination-label {
      font-size: 13px;
      font-weight: 500;
      color: #ffffff;
    }

    .line-health {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 600;
    }

    /* Row 3: Corridor Schematic */
    .schematic-wrapper {
      padding: 6px 10px 4px 10px;
      width: 100%;
      box-sizing: border-box;
    }

    .schematic-svg {
      display: block;
      width: 100%;
      max-width: 100%;
      overflow: visible;
    }

    /* Row 4: Live Location & Timings */
    .timings-wrapper {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 4px 12px 11px 12px;
      width: 100%;
      box-sizing: border-box;
    }

    .location-row {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: #c4c6ca;
    }

    .location-text {
      font-weight: 500;
    }

    .metrics-grid {
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      align-items: center;
      width: 100%;
      box-sizing: border-box;
      padding-top: 2px;
    }

    .metric-left {
      justify-self: start;
      display: flex;
      align-items: center;
    }

    .metric-centre {
      justify-self: center;
      display: flex;
      align-items: center;
    }

    .metric-right {
      justify-self: end;
      display: flex;
      align-items: center;
    }

    .leave-pill {
      font-weight: 700;
      font-size: 11.5px;
      padding: 2px 8px;
      border-radius: 6px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      flex-shrink: 0;
      border-width: 1px;
      border-style: solid;
      box-sizing: border-box;
    }

    .transit-pill {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.08);
      font-size: 11.5px;
      padding: 2px 8px;
      border-radius: 6px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
      color: #ffffff;
      box-sizing: border-box;
    }

    .transit-time {
      font-weight: 600;
    }

    .destination-pill {
      font-size: 11.5px;
      padding: 2px 8px;
      border-radius: 6px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      flex-shrink: 0;
      border-width: 1px;
      border-style: solid;
      box-sizing: border-box;
    }

    .destination-time {
      font-weight: 600;
    }

    .emoji-icon {
      font-family: 'Noto Color Emoji', 'Apple Color Emoji', 'Segoe UI Emoji', sans-serif;
      font-size: 13px;
      line-height: 1;
      display: inline-block;
      transform: translateY(-2px);
    }

    /* DETAILS VIEW (OPENS ON TOP OF MAIN CARD) */
    .details-view {
      display: flex;
      flex-direction: column;
      gap: 12px;
      width: 100%;
      box-sizing: border-box;
      min-height: 360px;
      animation: fadeIn 0.2s ease-in-out;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .details-nav-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      padding-bottom: 10px;
    }



    .details-route-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .close-btn {
      background: rgba(255, 255, 255, 0.08);
      border: none;
      color: #ffffff;
      width: 26px;
      height: 26px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      transition: background 0.15s ease;
    }

    .close-btn:hover {
      background: rgba(255, 255, 255, 0.16);
    }

    .line-status-box {
      background: rgba(0, 0, 0, 0.25);
      border-radius: 12px;
      padding: 14px 16px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-left-width: 5px;
      box-sizing: border-box;
    }

    .line-status-feed-badge {
      font-size: 10.5px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #a0a5b5;
      margin-bottom: 6px;
    }

    .line-status-headline {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 15px;
      font-weight: 700;
      margin-bottom: 6px;
    }

    .line-status-desc {
      font-size: 13px;
      line-height: 1.5;
      color: #e0e2ec;
      margin: 0;
    }

    details.advanced-accordion {
      background: rgba(0, 0, 0, 0.15);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 10px;
      overflow: hidden;
      margin-top: 4px;
    }

    details.advanced-accordion summary {
      padding: 10px 14px;
      cursor: pointer;
      font-size: 12.5px;
      font-weight: 600;
      color: #a0a5b5;
      display: flex;
      justify-content: space-between;
      align-items: center;
      user-select: none;
      list-style: none;
      transition: background 0.15s ease, color 0.15s ease;
    }

    details.advanced-accordion summary::-webkit-details-marker {
      display: none;
    }

    details.advanced-accordion summary:hover {
      background: rgba(255, 255, 255, 0.03);
      color: #ffffff;
    }

    .accordion-body {
      padding: 12px 14px;
      border-top: 1px solid rgba(255, 255, 255, 0.06);
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .accordion-section-header {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #64b5f6;
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .details-table {
      width: 100%;
      font-size: 12px;
      border-collapse: collapse;
    }

    .details-table td {
      padding: 5px 2px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      vertical-align: top;
    }

    .details-table td:first-child {
      color: #a0a5b5;
      width: 44%;
      font-weight: 500;
    }

    .warning-card {
      padding: 16px;
      color: #ffb74d;
      background: rgba(255, 183, 77, 0.1);
      border-radius: 12px;
      border: 1px solid rgba(255, 183, 77, 0.3);
      font-size: 13px;
    }
  `;

  protected render() {
    if (!this._config || !this.hass) {
      return html`
        <div class="card-container warning-card">
          Entity configuration missing or Home Assistant not connected.
        </div>
      `;
    }

    const masterEntity = this.hass.states[this._config.entity];
    if (!masterEntity) {
      return html`
        <div class="card-container warning-card">
          Entity not found: <code>${this._config.entity}</code>
        </div>
      `;
    }

    // IF A ROUTE IS SELECTED: RENDER DETAILS VIEW OVER/ON TOP OF MAIN CARD
    if (this._selectedRouteId) {
      return this._renderDetailsView(masterEntity, this._selectedRouteId);
    }

    const attr = masterEntity.attributes || {};
    const pic = attr.person_picture || "";
    const title = this._config.title || attr.commute_title || attr.friendly_name || "Commute";
    const pillText = attr.pill_label || (masterEntity.state === "standby" ? "Standby" : "Active");
    const pillCol = attr.pill_color || "#8E8E93";
    const pillBg = attr.pill_bg || "rgba(142, 142, 147, 0.2)";
    const pillBorder = attr.pill_border || "#8E8E93";
    const activeOpt = attr.active_option || "";

    const childEntities: string[] = this._config?.routes || attr.child_entities || [];
    const isRelevant =
      attr.is_relevant === true ||
      attr.is_relevant === "true" ||
      (attr.is_relevant === undefined &&
        masterEntity.state !== "standby" &&
        masterEntity.state !== "idle" &&
        masterEntity.state !== "unavailable" &&
        masterEntity.state !== "unknown");

    // Order child modules: Recommended route on top, others underneath
    const orderedChildEntities = [...childEntities].sort((a, b) => {
      const aState = this.hass?.states[a];
      const bState = this.hass?.states[b];
      const aRouteId = aState?.attributes?.route_id || a;
      const bRouteId = bState?.attributes?.route_id || b;
      if (aRouteId === activeOpt || a === activeOpt) return -1;
      if (bRouteId === activeOpt || b === activeOpt) return 1;
      return 0;
    });

    return html`
      <div class="card-container" role="region" aria-label="${title}">
        <div class="card-layout">
          <!-- Row 1: Unified Header -->
          <div class="header-row">
            <div class="header-left">
              ${pic
                ? html`<img
                    src="${pic}"
                    alt="${title}"
                    class="person-avatar"
                  />`
                : ""}
              <div class="header-title">${title}</div>
            </div>
            <div class="header-right">
              <span
                class="header-pill"
                style="background: ${pillBg}; border-color: ${pillBorder}; color: ${pillCol};"
              >
                ${pillText}
              </span>
            </div>
          </div>

          <!-- Transit Modules (Only displayed when commute is relevant) -->
          ${isRelevant
            ? orderedChildEntities.map((entId, idx) =>
                this._renderTransitModule(entId, idx === 0)
              )
            : ""}
        </div>
      </div>
    `;
  }

  protected updated(changedProperties: PropertyValues): void {
    super.updated(changedProperties);
    if (!this._selectedRouteId) {
      const layout = this.shadowRoot?.querySelector(".card-layout") as HTMLElement;
      if (layout && layout.offsetHeight > 0 && layout.offsetHeight !== this._mainHeight) {
        this._mainHeight = layout.offsetHeight;
      }
    }
  }

  private _openDetails(e: Event, entId: string): void {
    e.preventDefault();
    e.stopPropagation();
    const layout = this.shadowRoot?.querySelector(".card-layout") as HTMLElement;
    if (layout && layout.offsetHeight > 0) {
      this._mainHeight = layout.offsetHeight;
    }
    this._selectedRouteId = entId;
  }

  private _renderStatusIcon(iconStr: string) {
    if (!iconStr) return html``;
    if (iconStr.startsWith("mdi:")) {
      if (typeof customElements !== "undefined" && customElements.get("ha-icon")) {
        return html`<ha-icon .icon=${iconStr} style="--mdc-icon-size: 14px; width: 14px; height: 14px; display: inline-flex; align-items: center; justify-content: center; vertical-align: -1px;"></ha-icon>`;
      }
      if (iconStr.includes("check") || iconStr === "✓") return "✓";
      if (iconStr.includes("alert") || iconStr.includes("warning") || iconStr === "⚠️") return "⚠️";
      if (iconStr.includes("close") || iconStr.includes("cancel") || iconStr === "✕") return "✕";
      if (iconStr.includes("help") || iconStr === "?") return "?";
    }
    return iconStr;
  }

  private _closeDetails(): void {
    this._selectedRouteId = undefined;
  }

  private _renderDetailsView(masterEntity: HassEntityState, entId: string) {
    const childState = this.hass?.states[entId];
    if (!childState) {
      this._selectedRouteId = undefined;
      return html``;
    }

    const a = childState.attributes || {};
    const route = a.route_label || a.line || "Transit";
    const dest = a.route_destination || a.destination || "";
    const trackCol = a.corridor_color || a.route_color || "#8E8E93";
    const lineSt = a.line_status || a.line_status_label || "Good Service";
    const lineCol = a.line_status_color || "#4CAF50";
    const lineIcon = a.line_status_icon || "✓";
    const lineDetail =
      a.line_status_detail ||
      "No operational disruptions or delays reported. Regular service operating across the corridor.";
    const provider = a.provider ? a.provider.toUpperCase() : "TfL";
    const loc = a.corridor_location || "Awaiting Service";
    const leaveBy = a.leave_by_time || "--:--";
    const exp = a.expected_time || a.expected_boarding_time || "--:--";
    const transitArr =
      a.expected_alighting_time || a.estimated_transit_arrival || "--:--";
    const destArr =
      a.expected_destination_time || a.estimated_destination_arrival || "--:--";
    const slack = a.target_slack_minutes;
    const marginText =
      slack !== undefined
        ? slack >= 0
          ? `+${slack}m buffer (On Time)`
          : `${slack}m late`
        : "N/A";
    const leaveCountdown =
      a.seconds_to_leave !== null && a.seconds_to_leave !== undefined
        ? `in ${Math.round(a.seconds_to_leave / 60)}m`
        : "--";

    return html`
      <div class="card-container" role="region" aria-label="${route} Details">
        <div class="details-view" style="min-height: ${this._mainHeight}px;">
          <!-- Header with Route Title and Close Button -->
          <div class="details-nav-header">
            <div class="details-route-title">
              <span class="route-badge" style="background: ${trackCol};">${route}</span>
              <span class="destination-label">${dest}</span>
            </div>
            <button
              class="close-btn"
              @click=${() => this._closeDetails()}
              aria-label="Close details"
            >
              ✕
            </button>
          </div>

          <!-- PRIMARY SECTION: Line Status Details -->
          <div class="line-status-box" style="border-left-color: ${lineCol};">
            <div class="line-status-feed-badge">Transit Provider Feed · ${provider}</div>
            <div class="line-status-headline" style="color: ${lineCol};">
              <span>${this._renderStatusIcon(lineIcon)}</span>
              <span>${lineSt}</span>
            </div>
            <p class="line-status-desc">${lineDetail}</p>
          </div>

          <!-- ADVANCED DETAILS ACCORDION -->
          <details class="advanced-accordion">
            <summary>
              <span><span class="emoji-icon">⚙️</span> Advanced Details (Route & Technical Info)</span>
              <span style="font-size: 11px; opacity: 0.7;">▼</span>
            </summary>
            <div class="accordion-body">
              <!-- Group 1: Route Information -->
              <div>
                <div class="accordion-section-header">
                  <span class="emoji-icon">🗺️</span>
                  <span>Route Information</span>
                </div>
                <table class="details-table">
                  <tbody>
                    <tr>
                      <td>Route / Direction</td>
                      <td>${route} to ${dest} (${a.direction || "from_home"})</td>
                    </tr>
                    <tr>
                      <td>Boarding Location</td>
                      <td>${loc}</td>
                    </tr>
                    <tr>
                      <td>Doorstep Departure</td>
                      <td><strong>${leaveBy}</strong> (${leaveCountdown})</td>
                    </tr>
                    <tr>
                      <td>Boarding Departure</td>
                      <td>${exp}</td>
                    </tr>
                    <tr>
                      <td>Transit Arrival</td>
                      <td>${transitArr}</td>
                    </tr>
                    <tr>
                      <td>Destination Arrival</td>
                      <td>${destArr}</td>
                    </tr>
                    <tr>
                      <td>Target Margin / Slack</td>
                      <td>${marginText}</td>
                    </tr>
                    <tr>
                      <td>Timeliness State</td>
                      <td><code>${a.timeliness || "on_time"}</code></td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- Group 2: Debugging & Technical Info -->
              <div>
                <div class="accordion-section-header">
                  <span class="emoji-icon">🔧</span>
                  <span>Debugging & Technical Info</span>
                </div>
                <table class="details-table">
                  <tbody>
                    <tr>
                      <td>Master Entity</td>
                      <td><code>${masterEntity.entity_id}</code></td>
                    </tr>
                    <tr>
                      <td>Child Route Entity</td>
                      <td><code>${entId}</code></td>
                    </tr>
                    <tr>
                      <td>Tracked Vehicle ID</td>
                      <td><code>${a.vehicle_id || "Scheduled / None"}</code></td>
                    </tr>
                    <tr>
                      <td>Corridor Progress Index</td>
                      <td><code>${a.corridor_progress !== undefined ? a.corridor_progress : "N/A"}</code></td>
                    </tr>
                    <tr>
                      <td>Target Destination Time</td>
                      <td><code>09:00</code></td>
                    </tr>
                    <tr>
                      <td>Arbitration Strategy</td>
                      <td><code>${masterEntity.attributes?.strategy || "late_with_buffer"}</code></td>
                    </tr>
                    <tr>
                      <td>Raw Seconds to Board</td>
                      <td><code>${a.seconds_to_board !== null && a.seconds_to_board !== undefined ? a.seconds_to_board + "s" : "null"}</code></td>
                    </tr>
                    <tr>
                      <td>Raw Seconds to Leave</td>
                      <td><code>${a.seconds_to_leave !== null && a.seconds_to_leave !== undefined ? a.seconds_to_leave + "s" : "null"}</code></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </details>
        </div>
      </div>
    `;
  }

  private _renderTransitModule(entId: string, isTop: boolean) {
    const optState = this.hass?.states[entId];
    if (!optState) return html``;

    const a = optState.attributes || {};
    const route = a.route_label || a.line || "";
    const dest = a.route_destination || a.destination || "";
    const trackCol = a.corridor_color || a.route_color || "#8E8E93";
    const lineSt = a.line_status || a.line_status_label || "Good Service";
    const lineCol = a.line_status_color || "#4CAF50";
    const lineIcon = a.line_status_icon || "✓";
    const loc = a.corridor_location || "Awaiting Service";
    const stops: CorridorStop[] = a.corridor_stops || [];
    const progress = parseFloat(
      a.corridor_progress !== undefined ? String(a.corridor_progress) : "-1"
    );

    const rawLeave = a.leave_by_time;
    const leaveBy = rawLeave && rawLeave !== "none" ? rawLeave : "--:--";
    const rawExp = a.expected_time || a.expected_boarding_time;
    const exp = rawExp && rawExp !== "none" ? rawExp : "--:--";
    const rawTransit =
      a.estimated_transit_arrival ||
      a.estimated_balham_arrival ||
      a.expected_alighting_time;
    const transitArr =
      rawTransit && rawTransit !== "none" ? rawTransit : "--:--";
    const rawDest =
      a.estimated_destination_arrival || a.expected_destination_time;
    const destArr = rawDest && rawDest !== "none" ? rawDest : "--:--";
    const destIcon = a.destination_icon || "🏫";

    const rawSlack =
      a.target_slack_minutes !== undefined
        ? a.target_slack_minutes
        : a.expected_destination_margin_seconds !== undefined
        ? Math.round(a.expected_destination_margin_seconds / 60)
        : undefined;

    const willArriveInTime =
      a.will_arrive_in_time === true ||
      a.will_arrive_in_time === "true" ||
      a.will_arrive_on_time === true ||
      a.will_arrive_on_time === "true" ||
      (rawSlack !== undefined &&
        rawSlack !== null &&
        rawSlack !== "none" &&
        parseFloat(String(rawSlack)) >= 0);

    const hasSlack =
      rawSlack !== undefined && rawSlack !== null && rawSlack !== "none";
    const isLate = hasSlack && !willArriveInTime;

    const destPillBorder = isLate
      ? "#FF5252"
      : "rgba(255, 255, 255, 0.08)";
    const destPillBg = isLate
      ? "rgba(255, 82, 82, 0.15)"
      : "rgba(255, 255, 255, 0.05)";
    const destTextColor = isLate ? "#FF8A80" : "#FFFFFF";

    const optPillCol = a.pill_color || "#8E8E93";
    const optPillBg = a.pill_bg || "rgba(142, 142, 147, 0.2)";
    const optPillBorder = a.pill_border || "#8E8E93";

    const isTrain =
      a.vehicle_type === "train" || a.mode === "train" || a.mode === "tube";

    return html`
      <div
        class="transit-module"
        @click=${(e: Event) => this._openDetails(e, entId)}
        role="button"
        tabindex="0"
        aria-label="View details for ${route} to ${dest}"
      >
        <!-- Row 2: Transport Mode & Line Health -->
        <div class="module-header">
          <div class="mode-label-group">
            <span class="route-badge" style="background: ${trackCol};">
              ${route}
            </span>
            <span class="destination-label">${dest}</span>
          </div>
          <div class="line-health" style="color: ${lineCol};">
            <span>${this._renderStatusIcon(lineIcon)}</span>
            <span>${lineSt}</span>
          </div>
        </div>

        <!-- Row 3: Corridor Schematic -->
        ${stops.length >= 1
          ? html`
              <div class="schematic-wrapper">
                ${this._renderSchematicSvg(entId, stops, progress, trackCol, isTrain)}
              </div>
            `
          : ""}

        <!-- Row 4: Live Corridor Location & Timings -->
        <div class="timings-wrapper">
          <div class="location-row">
            <span class="emoji-icon" style="color: #64B5F6;">📍</span>
            <span class="location-text">${loc}</span>
          </div>

          ${exp !== "--:--" || leaveBy !== "--:--"
            ? html`
                <div class="metrics-grid">
                  <!-- Left: Doorstep Leave-by Pill -->
                  <div class="metric-left">
                    <span
                      class="leave-pill"
                      style="background: ${optPillBg}; border-color: ${optPillBorder}; color: ${optPillCol};"
                    >
                      <span class="emoji-icon">👟</span>
                      <span>${leaveBy}</span>
                    </span>
                  </div>

                  <!-- Centre: Transit Times (Departure + Icon + Transit Arrival) -->
                  <div class="metric-centre">
                    <span class="transit-pill">
                      <span class="transit-time">${exp}</span>
                      <span class="emoji-icon">${isTrain ? "🚆" : "🚌"}</span>
                      <span class="transit-time">${transitArr}</span>
                    </span>
                  </div>

                  <!-- Right: Final Destination Arrival -->
                  <div class="metric-right">
                    ${destArr !== "--:--"
                      ? html`
                          <span
                            class="destination-pill"
                            style="background: ${destPillBg}; border-color: ${destPillBorder}; color: ${destTextColor};"
                          >
                            <span class="emoji-icon">${destIcon}</span>
                            <span class="destination-time">${destArr}</span>
                          </span>
                        `
                      : ""}
                  </div>
                </div>
              `
            : ""}
        </div>
      </div>
    `;
  }

  private _renderSchematicSvg(
    entId: string,
    stops: CorridorStop[],
    progress: number,
    trackCol: string,
    isTrain: boolean
  ) {
    const minX = 40;
    const maxX = 420;
    const isTerminus = stops.length === 1;
    const vehicleSvgPath = isTrain ? TRAIN_SVG_PATH : BUS_SVG_PATH;
    const gradId = `terminus-grad-${entId.replace(/[^a-zA-Z0-9]/g, "-")}`;

    if (isTerminus) {
      const targetStop = stops[0];
      const showMarker = progress >= -0.5;
      const normProgress = Math.min(Math.max(progress, 0), 1);
      const bx = minX + normProgress * (maxX - minX);

      return svg`
        <svg viewBox="0 0 460 60" class="schematic-svg">
          <defs>
            <linearGradient
              id="${gradId}"
              gradientUnits="userSpaceOnUse"
              x1="${minX}"
              y1="22"
              x2="${maxX}"
              y2="22"
            >
              <stop offset="0%" stop-color="${trackCol}" stop-opacity="0" />
              <stop offset="100%" stop-color="${trackCol}" stop-opacity="1" />
            </linearGradient>
          </defs>

          <!-- Virtual Approach Line (Brand Colour with 0 Alpha on Left Fading to Solid on Right) -->
          <line
            x1="${minX}"
            y1="22"
            x2="${maxX}"
            y2="22"
            stroke="url(#${gradId})"
            stroke-width="6"
            stroke-linecap="round"
          />

          <!-- Highlighted Boarding Stop (at the Right) -->
          <circle cx="${maxX}" cy="22" r="9" fill="#2B2D3A" stroke="${trackCol}" stroke-width="3.5" />
          <circle cx="${maxX}" cy="22" r="4" fill="#FFFFFF" />
          <text
            x="${maxX}"
            y="46"
            text-anchor="middle"
            fill="#FFFFFF"
            font-size="10.5"
            font-family="system-ui"
            font-weight="700"
          >
            ${targetStop.short_name || targetStop.name || targetStop.stop_id || ""}
          </text>

          <!-- Vehicle Marker (Clean White Circle, No Outer Halo) -->
          ${
            showMarker
              ? svg`
                  <g
                    transform="translate(${bx}, 22)"
                    style="filter: drop-shadow(0px 2px 4px rgba(0, 0, 0, 0.7)); transition: transform 0.6s ease;"
                  >
                    <circle
                      cx="0"
                      cy="0"
                      r="11"
                      fill="${trackCol}"
                      stroke="#FFFFFF"
                      stroke-width="2.5"
                    />
                    <g transform="translate(-6, -6) scale(0.5)">
                      <path d="${vehicleSvgPath}" fill="#FFFFFF" />
                    </g>
                  </g>
                `
              : ""
          }
        </svg>
      `;
    }

    // Standard Multi-Stop Corridor (e.g. Bus)
    const maxP = stops.length - 1;
    const showMarker = progress >= -0.5 && stops.length > 1;
    let bx = minX;
    if (showMarker) {
      const clampedP = Math.max(0, progress);
      bx =
        clampedP > maxP
          ? maxX + 20
          : minX + clampedP * ((maxX - minX) / maxP);
    }

    return svg`
      <svg viewBox="0 0 460 60" class="schematic-svg">
        <!-- Background Track -->
        <line
          x1="${minX}"
          y1="22"
          x2="${maxX}"
          y2="22"
          stroke="rgba(255, 255, 255, 0.12)"
          stroke-width="8"
          stroke-linecap="round"
        />
        <!-- Colored Route Track -->
        <line
          x1="${minX}"
          y1="22"
          x2="${maxX}"
          y2="22"
          stroke="${trackCol}"
          stroke-width="6"
          stroke-linecap="round"
        />

        <!-- Stops Nodes -->
        ${stops.map((stop, idx) => {
          const sx = minX + idx * ((maxX - minX) / maxP);
          const label = stop.short_name || stop.name || stop.stop_id || "";
          if (stop.is_target) {
            return svg`
              <circle cx="${sx}" cy="22" r="9" fill="#2B2D3A" stroke="${trackCol}" stroke-width="3.5" />
              <circle cx="${sx}" cy="22" r="4" fill="#FFFFFF" />
              <text x="${sx}" y="46" text-anchor="middle" fill="#FFFFFF" font-size="10.5" font-family="system-ui" font-weight="700">
                ${label}
              </text>
            `;
          }
          return svg`
            <circle cx="${sx}" cy="22" r="6" fill="#2B2D3A" stroke="#FFFFFF" stroke-width="3" />
            <text x="${sx}" y="46" text-anchor="middle" fill="#A0A5B5" font-size="9.5" font-family="system-ui" font-weight="500">
              ${label}
            </text>
          `;
        })}

        <!-- Vehicle Marker (Clean White Circle, No Outer Halo) -->
        ${
          showMarker
            ? svg`
                <g
                  transform="translate(${bx}, 22)"
                  style="filter: drop-shadow(0px 2px 4px rgba(0, 0, 0, 0.7)); transition: transform 0.6s ease;"
                >
                  <circle
                    cx="0"
                    cy="0"
                    r="11"
                    fill="${trackCol}"
                    stroke="#FFFFFF"
                    stroke-width="2.5"
                  />
                  <g transform="translate(-6, -6) scale(0.5)">
                    <path d="${vehicleSvgPath}" fill="#FFFFFF" />
                  </g>
                </g>
              `
            : ""
        }
      </svg>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "commute-tracker-card": CommuteTrackerCard;
  }
}

interface CustomCardEntry {
  type: string;
  name: string;
  description: string;
  preview?: boolean;
  documentationURL?: string;
}

interface WindowWithCustomCards extends Window {
  customCards?: CustomCardEntry[];
}

const windowWithCustomCards = (
  typeof window !== "undefined" ? window : globalThis
) as unknown as WindowWithCustomCards;

if (windowWithCustomCards) {
  windowWithCustomCards.customCards = windowWithCustomCards.customCards || [];
  if (
    !windowWithCustomCards.customCards.some(
      (card) => card.type === "commute-tracker-card"
    )
  ) {
    windowWithCustomCards.customCards.push({
      type: "commute-tracker-card",
      name: "Commute Tracker Card",
      description:
        "A compact, reactive commute card showing real-time corridor progress, line status, and departure timings.",
      preview: true,
      documentationURL: "https://github.com/marcelkornblum/ha-commute-tracker",
    });
  }
}
