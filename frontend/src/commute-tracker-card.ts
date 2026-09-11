import { LitElement, html, css } from "lit";
import { customElement, property } from "lit/decorators.js";

@customElement("commute-tracker-card")
export class CommuteTrackerCard extends LitElement {
  @property({ attribute: false }) public hass?: unknown;
  @property({ type: Object }) public config?: Record<string, unknown>;

  static styles = css`
    :host {
      display: block;
      padding: 16px;
    }
  `;

  render() {
    return html`
      <ha-card header="Commute Tracker">
        <div class="card-content">
          <p>Commute Tracker Card</p>
        </div>
      </ha-card>
    `;
  }

  setConfig(config: Record<string, unknown>) {
    this.config = config;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "commute-tracker-card": CommuteTrackerCard;
  }
}
