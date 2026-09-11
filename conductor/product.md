# ha-commute-tracker
A standalone, spec-driven Home Assistant custom integration built with Red/Green Test-Driven Development (TDD). It provides multi-modal transit tracking, corridor schematics, and urgency staging. 

## Vision
The product vision is to make it simple for people to get ready for and catch their transit mode for their commute without worry, even when there are multiple options. Under the hood, it decouples raw API transit models from the Home Assistant entity state machine using a Universal Provider Plugin architecture, ensuring minimal polling overhead and strict entity minimalism.
