/**
 * Mock Home Assistant state fixtures based strictly on specs/commute_contract.md.
 */

export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: Record<string, any>;
  last_changed?: string;
  last_updated?: string;
}

export interface MockHass {
  states: Record<string, HassEntity>;
  callService?: (domain: string, service: string, serviceData?: any) => Promise<void>;
}

export const MASTER_ENTITY_ID = "sensor.commute_nelson_to_brick_lane";
export const BUS_ENTITY_ID = "sensor.commute_nelson_to_brick_lane_bus_26";
export const TRAIN_ENTITY_ID = "sensor.commute_nelson_to_brick_lane_train_southeastern";
export const TUBE_ENTITY_ID = "sensor.commute_nelson_to_brick_lane_tube_central";

const CANONICAL_BUS_STOPS = [
  { short_name: "Victoria", is_target: false },
  { short_name: "Westminster", is_target: false },
  { short_name: "Horse Guards", is_target: false },
  { short_name: "Trafalgar Sq", is_target: true },
];

const CANONICAL_TRAIN_STOPS = [
  { short_name: "Charing Cross", is_target: true },
];

export const createFixtureSet = (
  urgencyStage: "standby" | "relaxed" | "prepare" | "leave_now" = "relaxed",
  overrides?: {
    master?: Partial<HassEntity["attributes"]>;
    bus?: Partial<HassEntity["attributes"]>;
    train?: Partial<HassEntity["attributes"]>;
  }
): MockHass => {
  const isStandby = urgencyStage === "standby";

  let masterPill = {
    label: "Leave in 12m",
    color: "#4CAF50",
    bg: "rgba(76, 175, 80, 0.15)",
    border: "#4CAF50",
  };

  if (urgencyStage === "prepare") {
    masterPill = {
      label: "Leave in 6m",
      color: "#FF9800",
      bg: "rgba(255, 152, 0, 0.15)",
      border: "#FF9800",
    };
  } else if (urgencyStage === "leave_now") {
    masterPill = {
      label: "🚨 LEAVE NOW",
      color: "#FF5252",
      bg: "rgba(255, 82, 82, 0.2)",
      border: "#FF5252",
    };
  } else if (isStandby) {
    masterPill = {
      label: "Standby",
      color: "#8E8E93",
      bg: "rgba(142, 142, 147, 0.2)",
      border: "#8E8E93",
    };
  }

  const busEntity: HassEntity = {
    entity_id: BUS_ENTITY_ID,
    state: urgencyStage,
    attributes: {
      commute_id: "nelson_to_brick_lane",
      route_id: "bus_26",
      mode: "bus",
      vehicle_type: "bus",
      line: "26",
      route_label: "26",
      route_color: "#DC241F",
      corridor_color: "#DC241F",
      destination: "Shoreditch",
      route_destination: "Shoreditch",
      is_relevant: !isStandby,
      urgency_stage: urgencyStage,
      leave_by_time: isStandby ? "--:--" : "08:18",
      expected_boarding_time: isStandby ? "--:--" : "08:24",
      expected_time: isStandby ? "--:--" : "08:24",
      expected_alighting_time: isStandby ? "--:--" : "08:56",
      estimated_transit_arrival: isStandby ? "--:--" : "08:56",
      expected_destination_time: isStandby ? "--:--" : "09:06",
      estimated_destination_arrival: isStandby ? "--:--" : "09:06",
      destination_icon: "🏫",
      seconds_to_leave: isStandby ? null : 720,
      seconds_to_board: isStandby ? null : 1080,
      expected_destination_margin_seconds: 240,
      target_slack_minutes: 4,
      will_arrive_on_time: true,
      will_arrive_in_time: true,
      timeliness: "on_time",
      vehicle_id: "LX11BFA",
      corridor_location: "Between Horse Guards & Trafalgar Sq",
      corridor_progress: 2.3,
      corridor_stops: CANONICAL_BUS_STOPS,
      line_status: "Good Service",
      line_status_label: "Good Service",
      line_status_color: "#4CAF50",
      line_status_icon: "✓",
      line_status_detail: "Good service operating across Route 26. Buses running to regular scheduled headways with no transit corridor delays.",
      pill_label: masterPill.label,
      pill_color: masterPill.color,
      pill_bg: masterPill.bg,
      pill_border: masterPill.border,
      detail_navigation_path: "/lovelace/commute-details",
      ...overrides?.bus,
    },
  };

  const trainEntity: HassEntity = {
    entity_id: TRAIN_ENTITY_ID,
    state: urgencyStage,
    attributes: {
      commute_id: "nelson_to_brick_lane",
      route_id: "train_southeastern",
      mode: "train",
      vehicle_type: "train",
      line: "southeastern",
      route_label: "Southeastern",
      route_color: "#0019A8",
      corridor_color: "#0019A8",
      destination: "London Bridge",
      route_destination: "London Bridge",
      is_relevant: !isStandby,
      urgency_stage: urgencyStage,
      leave_by_time: isStandby ? "--:--" : "08:20",
      expected_boarding_time: isStandby ? "--:--" : "08:26",
      expected_time: isStandby ? "--:--" : "08:26",
      expected_alighting_time: isStandby ? "--:--" : "08:34",
      estimated_transit_arrival: isStandby ? "--:--" : "08:34",
      expected_destination_time: isStandby ? "--:--" : "08:49",
      estimated_destination_arrival: isStandby ? "--:--" : "08:49",
      destination_icon: "🏫",
      seconds_to_leave: isStandby ? null : 840,
      seconds_to_board: isStandby ? null : 1200,
      expected_destination_margin_seconds: 660,
      target_slack_minutes: 11,
      will_arrive_on_time: true,
      will_arrive_in_time: true,
      timeliness: "on_time",
      vehicle_id: "375801",
      corridor_location: "Platform 2 Charing Cross",
      corridor_progress: 0.8,
      corridor_stops: CANONICAL_TRAIN_STOPS,
      line_status: "Good Service",
      line_status_label: "Good Service",
      line_status_color: "#4CAF50",
      line_status_icon: "✓",
      line_status_detail: "Normal timetable in operation between London Charing Cross and London Bridge. All platforms operating normally.",
      pill_label: "Leave in 14m",
      pill_color: "#4CAF50",
      pill_bg: "rgba(76, 175, 80, 0.15)",
      pill_border: "#4CAF50",
      detail_navigation_path: "/lovelace/commute-details",
      ...overrides?.train,
    },
  };

  const masterEntity: HassEntity = {
    entity_id: MASTER_ENTITY_ID,
    state: urgencyStage,
    attributes: {
      commute_id: "nelson_to_brick_lane",
      commute_title: "Nelson's Column to Brick Lane",
      person_name: "Marcel",
      person_picture: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=128&h=128&q=80",
      active_option: "bus_26",
      options: ["bus_26", "train_southeastern"],
      child_entities: [BUS_ENTITY_ID, TRAIN_ENTITY_ID],
      is_relevant: !isStandby,
      urgency_stage: urgencyStage,
      pill_label: masterPill.label,
      pill_color: masterPill.color,
      pill_bg: masterPill.bg,
      pill_border: masterPill.border,
      route_label: "26",
      route_color: "#DC241F",
      destination: "Shoreditch",
      line_status_label: "Good Service",
      line_status_color: "#4CAF50",
      line_status_icon: "✓",
      expected_boarding_time: isStandby ? "--:--" : "08:24",
      expected_destination_time: isStandby ? "--:--" : "09:06",
      leave_by_time: isStandby ? "--:--" : "08:18",
      seconds_to_board: isStandby ? null : 1080,
      seconds_to_leave: isStandby ? null : 720,
      expected_destination_margin_seconds: 240,
      will_arrive_on_time: true,
      timeliness: "on_time",
      strategy: "late_with_buffer",
      ...overrides?.master,
    },
  };

  return {
    states: {
      [MASTER_ENTITY_ID]: masterEntity,
      [BUS_ENTITY_ID]: busEntity,
      [TRAIN_ENTITY_ID]: trainEntity,
    },
  };
};

export const SCENARIOS: Record<string, { name: string; getHass: () => MockHass }> = {
  relaxed: {
    name: "Relaxed (Bus 26 Top, Train Alternative)",
    getHass: () => createFixtureSet("relaxed"),
  },
  trainActive: {
    name: "Relaxed (Train Top, Bus Alternative)",
    getHass: () =>
      createFixtureSet("relaxed", {
        master: {
          active_option: "train_southeastern",
          route_label: "Southeastern",
          route_color: "#0019A8",
          destination: "London Bridge",
        },
      }),
  },
  prepare: {
    name: "Prepare Window (6m to Leave)",
    getHass: () => createFixtureSet("prepare"),
  },
  leaveNow: {
    name: "Urgent Departure (🚨 LEAVE NOW)",
    getHass: () => createFixtureSet("leave_now"),
  },
  disruption: {
    name: "Disruption / Minor Delays",
    getHass: () =>
      createFixtureSet("relaxed", {
        bus: {
          line_status: "Minor Delays",
          line_status_label: "Minor Delays",
          line_status_color: "#FF9800",
          line_status_icon: "⚠",
          line_status_detail: "Delays of up to 10 minutes through Trafalgar Square due to emergency gas works and lane closures.",
        },
        train: {
          line_status: "Part Suspended",
          line_status_label: "Part Suspended",
          line_status_color: "#F44336",
          line_status_icon: "✕",
          line_status_detail: "No Southeastern service between Charing Cross and London Bridge following an earlier points failure at Waterloo East. London Underground accepting tickets via Jubilee/Northern lines.",
        },
      }),
  },
  lateArrival: {
    name: "Late Arrival (Negative Margin Warning)",
    getHass: () =>
      createFixtureSet("relaxed", {
        bus: {
          target_slack_minutes: -4,
          expected_destination_margin_seconds: -240,
          will_arrive_on_time: false,
          will_arrive_in_time: false,
          timeliness: "late",
        },
      }),
  },
  standby: {
    name: "Standby / Inactive Window",
    getHass: () => createFixtureSet("standby"),
  },
};
