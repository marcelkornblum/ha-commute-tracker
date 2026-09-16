import "./commute-tracker-card";
import { CommuteTrackerCard } from "./commute-tracker-card";
import {
  MASTER_ENTITY_ID,
  BUS_ENTITY_ID,
  TRAIN_ENTITY_ID,
  SCENARIOS,
  MockHass,
} from "./fixtures";

const mountPoint = document.getElementById("mount-point") as HTMLElement;
const scenarioSelect = document.getElementById("scenario-select") as HTMLSelectElement;
const progressSlider = document.getElementById("progress-slider") as HTMLInputElement;
const progressValue = document.getElementById("progress-value") as HTMLElement;

// Populate scenario selector
Object.entries(SCENARIOS).forEach(([key, scenario]) => {
  const opt = document.createElement("option");
  opt.value = key;
  opt.textContent = scenario.name;
  scenarioSelect.appendChild(opt);
});

// Create and mount card instance
const card = document.createElement("commute-tracker-card") as CommuteTrackerCard;
card.setConfig({
  type: "custom:commute-tracker-card",
  entity: MASTER_ENTITY_ID,
});

mountPoint.appendChild(card);

let currentHass: MockHass = SCENARIOS.relaxed.getHass();

const updateCard = () => {
  const hassClone: MockHass = {
    ...currentHass,
    states: { ...currentHass.states },
  };

  const progress = parseFloat(progressSlider.value);
  if (hassClone.states[BUS_ENTITY_ID]) {
    hassClone.states[BUS_ENTITY_ID] = {
      ...hassClone.states[BUS_ENTITY_ID],
      attributes: {
        ...hassClone.states[BUS_ENTITY_ID].attributes,
        corridor_progress: progress,
      },
    };
  }
  if (hassClone.states[TRAIN_ENTITY_ID]) {
    hassClone.states[TRAIN_ENTITY_ID] = {
      ...hassClone.states[TRAIN_ENTITY_ID],
      attributes: {
        ...hassClone.states[TRAIN_ENTITY_ID].attributes,
        corridor_progress: Math.min(progress / 3, 1),
      },
    };
  }

  card.hass = hassClone;
};

scenarioSelect.addEventListener("change", () => {
  const selectedKey = scenarioSelect.value;
  if (SCENARIOS[selectedKey]) {
    currentHass = SCENARIOS[selectedKey].getHass();
    const busState = currentHass.states[BUS_ENTITY_ID];
    if (busState && busState.attributes.corridor_progress !== undefined) {
      progressSlider.value = String(busState.attributes.corridor_progress);
      progressValue.textContent = String(busState.attributes.corridor_progress);
    }
    updateCard();
  }
});

progressSlider.addEventListener("input", () => {
  progressValue.textContent = progressSlider.value;
  updateCard();
});

// Initial update
updateCard();
