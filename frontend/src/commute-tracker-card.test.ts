import { describe, it, expect, beforeEach, vi } from "vitest";
import "./commute-tracker-card";
import { CommuteTrackerCard } from "./commute-tracker-card";
import {
  MASTER_ENTITY_ID,
  BUS_ENTITY_ID,
  TRAIN_ENTITY_ID,
  createFixtureSet,
  SCENARIOS,
} from "./fixtures";

describe("CommuteTrackerCard", () => {
  let card: CommuteTrackerCard;

  beforeEach(() => {
    card = document.createElement("commute-tracker-card") as CommuteTrackerCard;
    document.body.appendChild(card);
  });

  const setupCard = async (
    urgency: "standby" | "relaxed" | "prepare" | "leave_now" = "relaxed",
    overrides?: any
  ) => {
    card.setConfig({
      type: "custom:commute-tracker-card",
      entity: MASTER_ENTITY_ID,
    });
    card.hass = createFixtureSet(urgency, overrides);
    await card.updateComplete;
    return card.shadowRoot!;
  };

  it("throws error when config is missing entity", () => {
    expect(() => card.setConfig({ type: "custom:commute-tracker-card" } as any)).toThrow(
      "Please define an entity in your card configuration."
    );
  });

  it("registers card metadata in window.customCards", () => {
    const customCards = (window as any).customCards;
    expect(customCards).toBeDefined();
    const cardEntry = customCards.find((c: any) => c.type === "commute-tracker-card");
    expect(cardEntry).toEqual({
      type: "commute-tracker-card",
      name: "Commute Tracker Card",
      description:
        "A compact, reactive commute card showing real-time corridor progress, line status, and departure timings.",
      preview: true,
      documentationURL: "https://github.com/marcelkornblum/ha-commute-tracker",
    });
  });

  it("returns a card size of 4", () => {
    expect(card.getCardSize()).toBe(4);
  });

  it("displays warning card when entity is not found in hass.states", async () => {
    card.setConfig({
      type: "custom:commute-tracker-card",
      entity: "sensor.non_existent",
    });
    card.hass = { states: {} };
    await card.updateComplete;

    const root = card.shadowRoot!;
    expect(root.textContent).toContain("Entity not found: sensor.non_existent");
  });

  it("renders unified header with avatar, title, and status pill", async () => {
    const root = await setupCard("relaxed");

    const titleEl = root.querySelector(".header-title");
    expect(titleEl?.textContent).toBe("Nelson's Column to Brick Lane");

    const avatar = root.querySelector(".person-avatar") as HTMLImageElement;
    expect(avatar).not.toBeNull();
    expect(avatar.src).toContain("unsplash.com");

    const pill = root.querySelector(".header-pill") as HTMLElement;
    expect(pill.textContent?.trim()).toBe("Leave in 12m");
    expect(pill.style.color.toUpperCase()).toBe("#4CAF50");
  });

  it("updates header pill styling across urgency stages", async () => {
    // Prepare stage
    let root = await setupCard("prepare");
    let pill = root.querySelector(".header-pill") as HTMLElement;
    expect(pill.textContent?.trim()).toBe("Leave in 6m");
    expect(pill.style.color.toUpperCase()).toBe("#FF9800");

    // Leave now stage
    root = await setupCard("leave_now");
    pill = root.querySelector(".header-pill") as HTMLElement;
    expect(pill.textContent?.trim()).toBe("🚨 LEAVE NOW");
    expect(pill.style.color.toUpperCase()).toBe("#FF5252");

    // Standby stage
    root = await setupCard("standby");
    pill = root.querySelector(".header-pill") as HTMLElement;
    expect(pill.textContent?.trim()).toBe("Standby");
    expect(pill.style.color.toUpperCase()).toBe("#8E8E93");
  });

  it("promotes active recommended route to top position", async () => {
    // By default, Bus 26 is active_option
    let root = await setupCard("relaxed");
    let modules = root.querySelectorAll(".transit-module");
    expect(modules.length).toBe(2);

    let firstBadge = modules[0].querySelector(".route-badge");
    let secondBadge = modules[1].querySelector(".route-badge");
    expect(firstBadge?.textContent?.trim()).toBe("26");
    expect(secondBadge?.textContent?.trim()).toBe("Southeastern");

    // Switch active_option to Southeastern train
    root = await setupCard("relaxed", {
      master: { active_option: "train_southeastern" },
    });
    modules = root.querySelectorAll(".transit-module");
    firstBadge = modules[0].querySelector(".route-badge");
    secondBadge = modules[1].querySelector(".route-badge");
    expect(firstBadge?.textContent?.trim()).toBe("Southeastern");
    expect(secondBadge?.textContent?.trim()).toBe("26");
  });

  it("hides transit modules when commute is in standby (not relevant)", async () => {
    const root = await setupCard("standby");
    const modules = root.querySelectorAll(".transit-module");
    expect(modules.length).toBe(0);
  });

  it("renders corridor schematic SVG with stop circles and vehicle marker", async () => {
    const root = await setupCard("relaxed");
    const busModule = root.querySelectorAll(".transit-module")[0];

    const svgEl = busModule.querySelector("svg.schematic-svg");
    expect(svgEl).not.toBeNull();

    // Check stop circles
    const circles = svgEl?.querySelectorAll("circle");
    expect(circles && circles.length).toBeGreaterThan(4);

    // Target stop text should be present
    const texts = Array.from(svgEl?.querySelectorAll("text") || []).map((t) =>
      t.textContent?.trim()
    );
    expect(texts).toContain("Trafalgar Sq");
    expect(texts).toContain("Victoria");

    // Vehicle marker group
    const vehicleMarkerGroup = svgEl?.querySelector("g[transform]");
    expect(vehicleMarkerGroup).not.toBeNull();
    expect(vehicleMarkerGroup?.getAttribute("transform")).toContain("translate(");
  });

  it("renders live timings and highlights late arrival with warning styles", async () => {
    // Normal on-time arrival
    let root = await setupCard("relaxed");
    let busModule = root.querySelectorAll(".transit-module")[0];
    let leavePill = busModule.querySelector(".leave-pill");
    expect(leavePill?.textContent).toContain("08:18");

    let transitPill = busModule.querySelector(".transit-pill");
    expect(transitPill?.textContent).toContain("08:24");
    expect(transitPill?.textContent).toContain("08:56");

    let destPill = busModule.querySelector(".destination-pill") as HTMLElement;
    expect(destPill?.textContent).toContain("09:06");
    expect(destPill.style.color.toUpperCase()).toBe("#FFFFFF");

    // Late arrival scenario
    root = await setupCard("relaxed", {
      bus: {
        target_slack_minutes: -4,
        will_arrive_on_time: false,
        will_arrive_in_time: false,
      },
    });
    busModule = root.querySelectorAll(".transit-module")[0];
    destPill = busModule.querySelector(".destination-pill") as HTMLElement;
    expect(destPill.style.color.toUpperCase()).toBe("#FF8A80");
    expect(destPill.style.borderColor.toUpperCase()).toBe("#FF5252");
  });

  it("opens details view on module click and returns to overview on close click", async () => {
    let root = await setupCard("relaxed");
    const busModule = root.querySelectorAll(".transit-module")[0] as HTMLElement;

    busModule.click();
    await card.updateComplete;
    root = card.shadowRoot!;

    // Details view is active
    expect(root.querySelector(".details-view")).not.toBeNull();
    expect(root.querySelector(".line-status-box")).not.toBeNull();
    expect(root.querySelector(".advanced-accordion")).not.toBeNull();

    // Close button exists and back button does not
    const closeBtn = root.querySelector(".close-btn") as HTMLButtonElement;
    expect(closeBtn).not.toBeNull();
    expect(root.querySelector(".back-btn")).toBeNull();

    // Clicking close returns to overview
    closeBtn.click();
    await card.updateComplete;
    root = card.shadowRoot!;

    expect(root.querySelector(".details-view")).toBeNull();
    expect(root.querySelectorAll(".transit-module").length).toBe(2);
  });

  it("renders corridor schematics safely without NaN when corridor_progress is null", async () => {
    const root = await setupCard("relaxed", {
      bus: { corridor_progress: null },
      train: { corridor_progress: null },
    });

    const svgs = root.querySelectorAll("svg.schematic-svg");
    expect(svgs.length).toBe(2);

    const htmlContent = root.innerHTML;
    expect(htmlContent).not.toContain("NaN");
    expect(htmlContent).not.toContain("translate(NaN");
  });

  it("handles unmapped or orphaned child entities gracefully", async () => {
    // Case 1: One existing child entity and one orphaned entity
    const hassWithOrphan = createFixtureSet("relaxed", {
      master: { child_entities: [BUS_ENTITY_ID, "sensor.commute_orphan_ghost"] },
    });
    card.setConfig({
      type: "custom:commute-tracker-card",
      entity: MASTER_ENTITY_ID,
    });
    card.hass = hassWithOrphan;
    await card.updateComplete;
    let root = card.shadowRoot!;

    const modules = root.querySelectorAll(".transit-module");
    expect(modules.length).toBe(1);
    expect(root.textContent).toContain("26");

    // Case 2: All mapped child entities are missing from hass.states
    card.setConfig({
      type: "custom:commute-tracker-card",
      entity: MASTER_ENTITY_ID,
    });
    card.hass = {
      states: {
        [MASTER_ENTITY_ID]: {
          entity_id: MASTER_ENTITY_ID,
          state: "active",
          attributes: {
            child_entities: ["sensor.orphan_1", "sensor.orphan_2"],
            friendly_name: "Morning Commute",
          },
        },
      },
    };
    await card.updateComplete;
    root = card.shadowRoot!;
    expect(root.textContent).toContain(`⚠️ Child route entities not found for: ${MASTER_ENTITY_ID}`);
  });

  it("renders successfully when configured directly with a child route sensor", async () => {
    card.setConfig({
      type: "custom:commute-tracker-card",
      entity: BUS_ENTITY_ID,
    });
    card.hass = createFixtureSet("relaxed");
    await card.updateComplete;

    const root = card.shadowRoot!;
    expect(root.querySelector(".warning-card")).toBeNull();
    const modules = root.querySelectorAll(".transit-module");
    expect(modules.length).toBe(1);
    expect(modules[0].querySelector(".route-badge")?.textContent?.trim()).toBe("26");
  });

  it("provides valid stub configuration via getStubConfig", () => {
    // Fallback when hass is undefined or has no states
    expect(CommuteTrackerCard.getStubConfig()).toEqual({
      entity: "sensor.commute_tracker",
    });
    expect(CommuteTrackerCard.getStubConfig({ states: {} })).toEqual({
      entity: "sensor.commute_tracker",
    });

    // Detects sensor with child_entities
    const mockHass = {
      states: {
        "switch.commute_switch": {
          entity_id: "switch.commute_switch",
          state: "on",
          attributes: { child_entities: ["sensor.route_a"] },
        },
        "sensor.work_commute": {
          entity_id: "sensor.work_commute",
          state: "active",
          attributes: { child_entities: ["sensor.route_bus"] },
        },
      },
    };
    expect(CommuteTrackerCard.getStubConfig(mockHass)).toEqual({
      entity: "sensor.work_commute",
    });
  });

  describe("DOM Snapshots", () => {
    const cleanHtml = (html: string) =>
      html.replace(/<!--\?lit\$[0-9]+\$-->/g, "<!--?lit-->");

    it("matches relaxed scenario snapshot", async () => {
      card.setConfig({
        type: "custom:commute-tracker-card",
        entity: MASTER_ENTITY_ID,
      });
      card.hass = SCENARIOS.relaxed.getHass();
      await card.updateComplete;
      expect(cleanHtml(card.shadowRoot?.innerHTML || "")).toMatchSnapshot();
    });

    it("matches prepare window snapshot", async () => {
      card.setConfig({
        type: "custom:commute-tracker-card",
        entity: MASTER_ENTITY_ID,
      });
      card.hass = SCENARIOS.prepare.getHass();
      await card.updateComplete;
      expect(cleanHtml(card.shadowRoot?.innerHTML || "")).toMatchSnapshot();
    });

    it("matches leave now urgent snapshot", async () => {
      card.setConfig({
        type: "custom:commute-tracker-card",
        entity: MASTER_ENTITY_ID,
      });
      card.hass = SCENARIOS.leaveNow.getHass();
      await card.updateComplete;
      expect(cleanHtml(card.shadowRoot?.innerHTML || "")).toMatchSnapshot();
    });

    it("matches disruption scenario snapshot", async () => {
      card.setConfig({
        type: "custom:commute-tracker-card",
        entity: MASTER_ENTITY_ID,
      });
      card.hass = SCENARIOS.disruption.getHass();
      await card.updateComplete;
      expect(cleanHtml(card.shadowRoot?.innerHTML || "")).toMatchSnapshot();
    });

    it("matches late arrival warning snapshot", async () => {
      card.setConfig({
        type: "custom:commute-tracker-card",
        entity: MASTER_ENTITY_ID,
      });
      card.hass = SCENARIOS.lateArrival.getHass();
      await card.updateComplete;
      expect(cleanHtml(card.shadowRoot?.innerHTML || "")).toMatchSnapshot();
    });

    it("matches standby dormant snapshot", async () => {
      card.setConfig({
        type: "custom:commute-tracker-card",
        entity: MASTER_ENTITY_ID,
      });
      card.hass = SCENARIOS.standby.getHass();
      await card.updateComplete;
      expect(cleanHtml(card.shadowRoot?.innerHTML || "")).toMatchSnapshot();
    });
  });
});
