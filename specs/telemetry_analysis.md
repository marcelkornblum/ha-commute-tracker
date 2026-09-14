# Detailed Telemetry & Reachability Analysis: Multi-Modal Live Capture

Empirical analysis of the multi-modal snapshots captured across the canonical Nelson's Column to Brick Lane commute corridor.

---

## 1. Executive Summary & Key Milestones

- **Dataset Duration**: 90 snapshots at 30.0s intervals spanning ~45 minutes.
- **Bus 26 (Trafalgar Square Stop F `490013766F`)**: 8 distinct vehicles tracked.
- **Southeastern Rail (Charing Cross `910GCHRX`)**: 15 distinct departures tracked.
- **Central Line Tube (Tottenham Court Road `940GZZLUTCR`)**: 28 distinct services tracked.

---

## 2. Bus 26 Fleet Tracking & Lifecycles

| Vehicle ID | First Seen | Initial TTS | Min TTS | Last Seen | Final TTS |
|:-----------|:-----------|:------------|:--------|:----------|:----------|
| `SN16OJA` | Snap 1 | 326s | 75s | Snap 9 | 75s |
| `SN66WRP` | Snap 1 | 917s | 148s | Snap 20 | 148s |
| `SN66WRJ` | Snap 1 | 1487s | 1100s | Snap 72 | 1206s |
| `SN66WRO` | Snap 6 | 1797s | 78s | Snap 64 | 78s |
| `SN66WSE` | Snap 14 | 1784s | 75s | Snap 64 | 75s |
| `SN16OJF` | Snap 30 | 1539s | 18s | Snap 68 | 18s |
| `LJ24ZRN` | Snap 58 | 1753s | 319s | Snap 90 | 319s |
| `SN16OJH` | Snap 71 | 1754s | 1034s | Snap 90 | 1034s |

---

## 3. Southeastern Rail Departures

| Scheduled Departure | First Observed Snap | Destination / Line |
|:--------------------|:--------------------|:-------------------|
| `2026-09-14T14:01:00` | Snap 1 | Southeastern to London Bridge |
| `2026-09-14T14:04:00` | Snap 6 | Southeastern to London Bridge |
| `2026-09-14T14:06:00` | Snap 11 | Southeastern to London Bridge |
| `2026-09-14T14:08:00` | Snap 14 | Southeastern to London Bridge |
| `2026-09-14T14:20:00` | Snap 18 | Southeastern to London Bridge |
| `2026-09-14T14:21:00` | Snap 37 | Southeastern to London Bridge |
| `2026-09-14T14:29:00` | Snap 38 | Southeastern to London Bridge |
| `2026-09-14T14:34:00` | Snap 51 | Southeastern to London Bridge |
| `2026-09-14T14:38:00` | Snap 59 | Southeastern to London Bridge |
| `2026-09-14T14:37:00` | Snap 60 | Southeastern to London Bridge |
| `2026-09-14T14:41:00` | Snap 65 | Southeastern to London Bridge |
| `2026-09-14T14:45:00` | Snap 70 | Southeastern to London Bridge |
| `2026-09-14T14:50:00` | Snap 76 | Southeastern to London Bridge |
| `2026-09-14T14:51:00` | Snap 84 | Southeastern to London Bridge |
| `2026-09-14T14:55:00` | Snap 85 | Southeastern to London Bridge |

---

## 4. Central Line Underground Progression

| Train Set ID | Destination | Initial Location | Initial TTS | Final Location | Last Seen |
|:-------------|:------------|:-----------------|:------------|:---------------|:----------|
| `061` | Hainault Underground Station | Left Lancaster Gate | 333s | At Oxford Circus | Snap 9 |
| `012` | Epping Underground Station | At Notting Hill Gate | 573s | At Platform | Snap 15 |
| `067` | Hainault Underground Station | Left Shepherd's Bush | 693s | At Platform | Snap 20 |
| `052` | Hainault Underground Station | Between White City and Shepherd's Bush | 753s | Between Oxford Circus and Tottenham Court Road | Snap 21 |
| `013` | Epping Underground Station | At White City | 933s | Between Oxford Circus and Tottenham Court Road | Snap 25 |
| `014` | Epping Underground Station | Between North Acton and East Acton | 1233s | Left Oxford Circus | Snap 31 |
| `070` | Hainault Underground Station | Between North Acton Junction and North Acton | 1293s | Between Oxford Circus and Tottenham Court Road | Snap 33 |
| `015` | Epping Underground Station | Approaching Perivale | 1653s | At Oxford Circus | Snap 45 |
| `022` | Loughton Underground Station | Between North Acton and East Acton | 1255s | At Platform | Snap 38 |
| `016` | Epping Underground Station | At Greenford | 1719s | At Tottenham Court Road | Snap 62 |
| `053` | Hainault Underground Station | Between Ealing Broadway and West Acton | 1556s | At Oxford Circus | Snap 56 |
| `062` | Hainault Underground Station | Between White City and Shepherd's Bush | 832s | Approaching Oxford Circus | Snap 41 |
| `020` | Loughton Underground Station | Approaching Greenford | 1792s | Left Oxford Circus | Snap 66 |
| `040` | Epping Underground Station | At East Acton | 1196s | At Platform | Snap 56 |
| `071` | Hainault Underground Station | Left Ealing Broadway | 1556s | Approaching Tottenham Court Road | Snap 64 |

---

## 5. Master Rollup Arbitration Timeline (Every 5th Snapshot)

| Snap | Elapsed | Bus Active | Train Departure | Tube Active | Master Route | Master Stage |
|:-----|:--------|:-----------|:----------------|:------------|:-------------|:-------------|
| 01 |   0.0s | `SN16OJA` (326s / leave_now) | `2026-09-14T14:01:00` (363s / prepare) | `012` (573s / leave_now) | `bus_26` | `leave_now` |
| 06 | 185.7s | `SN16OJA` (296s / leave_now) | `2026-09-14T14:04:00` (357s / leave_now) | `052` (595s / leave_now) | `train_southeastern` | `leave_now` |
| 11 | 374.4s | `SN66WRP` (354s / leave_now) | `2026-09-14T14:06:00` (289s / leave_now) | `013` (575s / leave_now) | `bus_26` | `leave_now` |
| 16 | 559.8s | `SN66WRP` (243s / leave_now) | `2026-09-14T14:08:00` (223s / leave_now) | `014` (596s / leave_now) | `bus_26` | `leave_now` |
| 21 | 746.8s | `SN66WRO` (1234s / relaxed) | `2026-09-14T14:20:00` (756s / prepare) | `022` (592s / leave_now) | `tube_central` | `leave_now` |
| 26 | 930.9s | `SN66WRO` (1078s / relaxed) | `2026-09-14T14:20:00` (572s / prepare) | `062` (643s / leave_now) | `tube_central` | `leave_now` |
| 31 | 1121.2s | `SN66WSE` (1149s / relaxed) | `2026-09-14T14:20:00` (382s / prepare) | `015` (584s / leave_now) | `tube_central` | `leave_now` |
| 36 | 1315.4s | `SN66WSE` (957s / relaxed) | `2026-09-14T14:20:00` (188s / leave_now) | `040` (658s / leave_now) | `tube_central` | `leave_now` |
| 41 | 1500.6s | `SN66WSE` (766s / prepare) | `2026-09-14T14:29:00` (543s / prepare) | `053` (629s / leave_now) | `tube_central` | `leave_now` |
| 46 | 1689.8s | `SN66WSE` (618s / prepare) | `2026-09-14T14:29:00` (353s / leave_now) | `016` (585s / leave_now) | `train_southeastern` | `leave_now` |
| 51 | 1879.3s | `SN66WSE` (526s / prepare) | `2026-09-14T14:34:00` (464s / prepare) | `020` (643s / leave_now) | `tube_central` | `leave_now` |
| 56 | 2065.6s | `SN66WRO` (203s / leave_now) | `2026-09-14T14:34:00` (278s / leave_now) | `063` (648s / leave_now) | `tube_central` | `leave_now` |
| 61 | 2278.3s | `SN16OJF` (272s / leave_now) | `2026-09-14T14:37:00` (245s / leave_now) | `054` (694s / leave_now) | `tube_central` | `leave_now` |
| 66 | 2464.2s | `SN66WRJ` (1108s / relaxed) | `2026-09-14T14:41:00` (299s / leave_now) | `041` (653s / leave_now) | `train_southeastern` | `leave_now` |
| 71 | 2668.2s | `SN66WRJ` (1206s / relaxed) | `2026-09-14T14:45:00` (335s / leave_now) | `041` (554s / leave_now) | `train_southeastern` | `leave_now` |
| 76 | 2853.2s | `LJ24ZRN` (1049s / relaxed) | `2026-09-14T14:50:00` (450s / prepare) | `021` (621s / leave_now) | `tube_central` | `leave_now` |
| 81 | 3039.9s | `LJ24ZRN` (905s / relaxed) | `2026-09-14T14:50:00` (263s / leave_now) | `072` (546s / leave_now) | `train_southeastern` | `leave_now` |
| 86 | 3225.9s | `LJ24ZRN` (481s / prepare) | `2026-09-14T14:55:00` (377s / prepare) | `030` (560s / leave_now) | `tube_central` | `leave_now` |
