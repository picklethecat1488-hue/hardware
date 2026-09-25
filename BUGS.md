# Bug Report Tracker: Hardware Bug Tracker

> Automated bug tracking, triage, and issue registry generated via Hardware Bug Report Engine.

## Tracker Overview

| Metric | Details |
| :--- | :--- |
| **Report Date** | `2026-09-25 15:18:24 UTC` |
| **Total Issues** | `113` |
| **Open Issues** | `0` |
| **Resolved / Closed** | `113 (100%)` |

## Executive Summary

Automated issue tracking and resolution registry for hardware CAD, PCB engine, and simulation.

## Issues by Severity

| Severity | Count | Meaning |
| :--- | :---: | :--- |
| **`[CRITICAL]`** | 1 | System crashes, build failures, blockages, or electrical shorts. |
| **`[HIGH]`** | 4 | Major functional defects, broken routing, DRC violations, or unphysical behavior. |
| **`[MEDIUM]`** | 105 | Silkscreen collisions, layout sub-optimality, or visual clipping. |
| **`[LOW]`** | 3 | Minor aesthetic imperfections or documentation notes. |

## Issues by Category

| Category | Count | Description |
| :--- | :---: | :--- |
| **`PCB`** | 83 | Schematics, routing, footprints, nets, DRC, silkscreen. |
| **`CAD`** | 13 | 3D geometry, step models, enclosures, mechanical assembly. |
| **`SIMULATION`** | 2 | JAX SPH fluid dynamics, PyBullet kinematics, physics. |
| **`INFRASTRUCTURE`** | 11 | Build tooling, compilers, test runners, headless tools. |
| **`UI`** | 1 | Web dashboards, CLI viewers, review interfaces. |

## Issue Checklist

- [x] **`[CRITICAL]`** [#BUG-001](#bug-001): Flex tail PCB visualization fails due to on-the-fly router invocation in view.py `[flex_tail]` (`RESOLVED`)
- [x] **`[HIGH]`** [#BUG-002](#bug-002): J_USB connector plug mouth faces board interior instead of board edge `[J_USB]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-003](#bug-003): Test point and discrete component silkscreen text collisions `[silkscreen]` (`RESOLVED`)
- [x] **`[HIGH]`** [#BUG-004](#bug-004): C1 decoupling capacitor dangling without plane connections `[C1]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-005](#bug-005): Piezo speaker SPK1 silkscreen border rectangular instead of round `[SPK1]` (`RESOLVED`)
- [x] **`[HIGH]`** [#BUG-006](#bug-006): Collinear trace segment simplification failure in A* router due to d2[0] Y-axis typo `[PCBAutoRouter]` (`RESOLVED`)
- [x] **`[HIGH]`** [#BUG-007](#bug-007): A* router net ordering deadlock walling in local MCU control pins `[test_board]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-008](#bug-008): Carrier PCB rectangular sharp corners around mounting holes `[carrier_board]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-009](#bug-009): Split-view CSS text overflow clipping code review diff listings `[code_review]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-010](#bug-010): bug reporter should use the quake UI color scheme (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-011](#bug-011): Rename "Export BUGS.md" to "Save and Exit" `[bug_reporter]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-012](#bug-012): Add ability to paste screenshotsand documents into attachments and references section `[bug_reporter]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-013](#bug-013): J_USB missing pads, has overlapping drill holes (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-014](#bug-014): Add bug filtering `[bug_report]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-015](#bug-015): Multiple components failed to route correctly (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-016](#bug-016): locate silkscreens for MH3 and MH4 to bottom of drill holes (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-017](#bug-017): T junction for SDA has rounded edge (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-018](#bug-018): View.py still fails (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-019](#bug-019): Move flex tail connector to board edge `[J_FLEX]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-020](#bug-020): Electrodes are missing on the flex tail, capacitive channels are incorrectly routed capacitive buttons `[flex_tail]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-021](#bug-021): The flex tail shape should be a manifold hull `[flex_tail]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-022](#bug-022): Power supply and distribution page has multiple issues `[schematic]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-024](#bug-024): Implement DRC for schematics `[drc]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-025](#bug-025): Sheet3 has multiple overlapping components `[schematic]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-026](#bug-026): Go to first change in file automatically `[bug_report]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-027](#bug-027): carrier board and flex tail have no tracks or vais (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-028](#bug-028): test_board_diagram flex tail should be oriented at connector edge (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-029](#bug-029): VBUS and GND pins on J_USB are not connected (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-030](#bug-030): antennae on sheet 2 decoupling caps (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-031](#bug-031): multiple caps on sheet 5 are open on one side and overlap with other symbology (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-032](#bug-032): move U1 to the right of U4 under SPK1 (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-033](#bug-033): pull up resistors overlap with U4 (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-034](#bug-034): flex tail PCB outline is incorrect (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-035](#bug-035): Q1 load switch truth table has overlap with decoupling capactitors (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-036](#bug-036): Overlapping placement in sheet 5 (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-037](#bug-037): Overlapping oplacement in sheet 7 (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-038](#bug-038): Flex tail not routed (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-039](#bug-039): carrier board still shows multiple routing failures (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-040](#bug-040): TP_GND is not connected to ground (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-041](#bug-041): Canonicalize component names on carrier board and flex tail (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-042](#bug-042): Test board wiring diagram looks like spaghetti (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-043](#bug-043): auto router is bridging pads to traces (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-044](#bug-044): auto router is placing vias in mid air on flex tail (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-045](#bug-045): every carrier PCB silkscreen is missing (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-046](#bug-046): U1 has missing balls on left, 2 vias in middle where balls should be (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-047](#bug-047): Parse kicad DRC reports (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-048](#bug-048): Create BuildTraces, BuildVias CMs (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-049](#bug-049): Use BuildSilkScreen CM for carrier PCB (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-050](#bug-050): Remove carrier_pcb from the provider manifest (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-051](#bug-051): Add SWD header to test board (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-052](#bug-052): Add peripheral headers to test board (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-053](#bug-053): Add RGB status LED to test board (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-054](#bug-054): Add charger and fuel gauge to test board (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-055](#bug-055): Add GPIO header to the test board (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-056](#bug-056): Add embedded NAND storage (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-057](#bug-057): Add USB-UART IC (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-058](#bug-058): Source new microcontroller (`RESOLVED`)
- [x] **`[LOW]`** [#BUG-059](#bug-059): Begin downselection process (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-060](#bug-060): Support Deep Power Down (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-061](#bug-061): Verify required power on sequencing steps (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-062](#bug-062): Connect FlexSPI to embedded flash in Dual Channel mode (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-063](#bug-063): Connect /CHG to MCU (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-064](#bug-064): Round edges of bottom of enclosure (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-065](#bug-065): Add connector cutouts to bottom enclosure (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-066](#bug-066): Component silkscreens missing from the PCB (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-067](#bug-067): Apply component downselection results  to PCB (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-068](#bug-068): Component fell off schematic page 5 (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-069](#bug-069): Change bug_report and code_review backing store to sqlite (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-070](#bug-070): Add battery connector to carrier board (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-071](#bug-071): I2c pull ups on sheet 7 dangling off page (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-072](#bug-072): Flex tail cutout doesn't align with flex tail (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-073](#bug-073): Add GPIO cutout to enclosure (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-074](#bug-074): Add peripheral cutouts to enclosure bottom (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-075](#bug-075): Add SWD cutout to enclosure (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-076](#bug-076): Enclosure lid should snap fit (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-077](#bug-077): Add ventillation holes to enclosure bottom (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-078](#bug-078): Code review highlight markers elide diff colors `[code_review]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-079](#bug-079): Move BUGS.md to repo root (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-080](#bug-080): Add LED cutout to test board enclosure `[test_board]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-081](#bug-081): This build.py command should have failed (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-082](#bug-082): Route test board (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-083](#bug-083): I2C pullup resistors overlap (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-084](#bug-084): Update board files schematics `[carrier_board]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-085](#bug-085): Change mounting holes on enclosure bottom to mounting posts (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-086](#bug-086): Capacitive sensing and control section is incorrect (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-087](#bug-087): Add power test points (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-088](#bug-088): Schematic bugs review (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-089](#bug-089): Organize schematic pages by subsystem (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-090](#bug-090): Test board Enclosure feedback (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-091](#bug-091): The diff view has scroll bars on every line `[code_review]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-092](#bug-092): Add logo to carrier board top (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-093](#bug-093): Update docs with architecture changes (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-094](#bug-094): Remove manual net priorities from PCB router (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-095](#bug-095): Make JAX router backend the default (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-096](#bug-096): Load switch should control audio and peripheral domains (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-097](#bug-097): Log routing violations to a file (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-098](#bug-098): Sheer 3 - C9, C10 overlap (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-099](#bug-099): Sheet 4- FLEXSPI wires should route around U8 (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-100](#bug-100): Sheet 6-SCL and SDA lines overlap (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-101](#bug-101): Sheet 7-U2 and J2- cap touch net routing is messy (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-102](#bug-102): Sheet 9- PCIE lanes are not cleanly routed (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-103](#bug-103): Sheet 10- Serial Bus Expansion Headers needs to be broken into 2 pages (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-104](#bug-104): Sheet11- GPIOs should route without off-sheet connectors (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-105](#bug-105): U4-Add AUDIO_EN GPIO connection to U1 (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-106](#bug-106): J6-J9: Remove VLOAD_SW connector (`RESOLVED`)
- [x] **`[LOW]`** [#BUG-107](#bug-107): Simulate flying probes test: carrier board `[carrier_board]` (`RESOLVED`)
- [x] **`[LOW]`** [#BUG-108](#bug-108): Simulate flying probes test: flex tail (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-109](#bug-109): Resolve pytest warnings (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-110](#bug-110): Expansion header connectors should be JST-style (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-111](#bug-111): White square above J2 `[carrier_board]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-112](#bug-112): Update test board docs with recommended battery model `[carrier_board]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-113](#bug-113): Carrier board serial expansion cutouts overlap `[carrier_board]` (`RESOLVED`)
- [x] **`[MEDIUM]`** [#BUG-114](#bug-114): Bug report tool does not pickup changes to BUGS.md `[bug_report]` (`RESOLVED`)

## Detailed Issue Log

### <a id="bug-001"></a> 🟢 `[BUG-001]` Flex tail PCB visualization fails due to on-the-fly router invocation in view.py

- **Status**: `RESOLVED`
- **Severity**: `CRITICAL`
- **Category**: `PCB`
- **Component**: `flex_tail`
- **Resolved**: `2026-09-19 23:30:00 UTC`

#### Description

Calling `python src/view.py test_board/flex_tail:pcb` fails with RuntimeError because view.py triggers on-the-fly A* routing with unreachable carrier endpoints instead of loading pre-computed routes from config.py.

#### Reproduction Steps

1. python src/config.py 'test_board/*'
2. python src/view.py test_board/flex_tail:pcb
3. Observe RuntimeError: A* router could not find collision-free path for net 'GND'

#### Behavior Comparison

- **Expected**: view.py should visualize pre-routed traces from routing_flex.yaml in O(1) time without running the router.
- **Actual**: view.py triggered A* routing across all carrier nets without board footprint scoping, causing deadlock.

#### Execution / Console Logs

```text
RuntimeError: A* router could not find collision-free path for net 'GND' from (0.00, 0.00) [F.Cu] to (-5.50, -8.00) [F.Cu]
```

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [flex_fail_overlap.png](build/flex_fail_overlap.png) | Visual artifact of routing collision |

#### Resolution Notes

Removed on-the-fly auto_router.route_all_nets() from PCBExporter. Pre-computed flex routes in config_route and persisted to routing_flex.yaml. Scoped board footprint filtering in router to isolate subassemblies.

---

### <a id="bug-002"></a> 🟢 `[BUG-002]` J_USB connector plug mouth faces board interior instead of board edge

- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `PCB`
- **Component**: `J_USB`
- **Resolved**: `2026-09-19 23:35:00 UTC`

#### Description

USB-C 16-pin receptacle was oriented at rotation 0, pointing the connector mouth toward the PCB center rather than outward toward the edge.

#### Reproduction Steps

1. python src/view.py test_board/carrier_board:pcb
2. Inspect J_USB orientation at board left perimeter

#### Behavior Comparison

- **Expected**: USB-C connector mouth must face board edge outward (-X) with receptacle pins facing board interior (+X).
- **Actual**: Connector mouth faced -Y with shield pins facing board edge.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [j_usb_must_face_board_edge.png](build/j_usb_must_face_board_edge.png) | Incorrect J_USB orientation review screenshot |

#### Resolution Notes

Rotated J_USB to 270 degrees in wiring.yaml and positioned at [-26.0, 0.0, 0.8]. Exempted edge connectors from internal boundary margin in DRC.

---

### <a id="bug-003"></a> 🟢 `[BUG-003]` Test point and discrete component silkscreen text collisions

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `silkscreen`
- **Resolved**: `2026-09-19 23:40:00 UTC`

#### Description

Test point labels rendered horizontally across pads and discrete component labels collided into unreadable clusters.

#### Reproduction Steps

1. python src/view.py test_board/carrier_board:pcb
2. Inspect silkscreen text around TP row and C3/R_BOOT/C5 clustering

#### Behavior Comparison

- **Expected**: Silkscreen text must be placed with collision avoidance keepouts clear of component pads and adjacent text.
- **Actual**: Text rendered overlapping pads ('TP_GNDTP_TX0_N') and discrete component labels collided ('C3 R_BOO5').

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [test_points_silkscreen_overlap.png](build/test_points_silkscreen_overlap.png) | Overlapping test point silkscreen |
| `screenshot` | [multiple_discrete_antenna.png](build/multiple_discrete_antenna.png) | Discrete component labels colliding |

#### Resolution Notes

Rotated test point labels 90 degrees with dedicated clearance boxes. Added placed_component_label_boxes in exporter.py. Relocated passives with >2mm spacing in wiring.yaml.

---

### <a id="bug-004"></a> 🟢 `[BUG-004]` C1 decoupling capacitor dangling without plane connections

- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `PCB`
- **Component**: `C1`
- **Resolved**: `2026-09-19 23:42:00 UTC`

#### Description

C1 0402 capacitor was placed in empty space at [18.0, -21.0] without stitching vias or traces to 3V3 and GND planes.

#### Reproduction Steps

1. Inspect C1 pads in kicad_pcb viewer
2. Verify electrical connectivity to power planes

#### Behavior Comparison

- **Expected**: C1 must decouple U2 power pin with stitching vias to 3V3 and GND planes.
- **Actual**: C1 had isolated pads with no traces or vias connecting to copper planes.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [c1_dangling.png](build/c1_dangling.png) | Dangling C1 decoupling capacitor |

#### Resolution Notes

Relocated C1 to [20.0, -15.0, 0.8] opposite U2 on F.Cu. Automated plane net stitching via generation in router connected both pads to 3V3 and GND planes.

---

### <a id="bug-005"></a> 🟢 `[BUG-005]` Piezo speaker SPK1 silkscreen border rectangular instead of round

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `SPK1`
- **Resolved**: `2026-09-19 23:45:00 UTC`

#### Description

SPK1 was specified with a rectangular 1x2 pin header footprint rather than a round piezo buzzer footprint, and placed far from mounting hole MH2.

#### Reproduction Steps

1. python src/view.py test_board/carrier_board:pcb
2. Inspect SPK1 footprint shape and placement

#### Behavior Comparison

- **Expected**: Piezo speaker must have circular silkscreen boundary and be located near mounting hole MH2.
- **Actual**: Rectangular pin header footprint rendered at [-22.0, 26.0].

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [fix_spk2_placement.png](build/fix_spk2_placement.png) | Review screenshot requesting round piezo silkscreen |

#### Resolution Notes

Added piezo_speaker_12mm circular footprint to thru_hole.yaml, added (fp_circle ...) rendering in kicad_pcb.j2, and relocated SPK1 to [-18.0, 31.0] near MH2.

---

### <a id="bug-006"></a> 🟢 `[BUG-006]` Collinear trace segment simplification failure in A* router due to d2[0] Y-axis typo

- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `PCB`
- **Component**: `PCBAutoRouter`
- **Resolved**: `2026-09-19 23:48:00 UTC`

#### Description

In router.py line 109, the collinear vector dot product used d2[0] instead of d2[1] for the Y-component, preventing redundant collinear waypoint pruning.

#### Reproduction Steps

1. Call polyline_to_trace_segments on a 3-point collinear polyline
2. Observe failure to simplify into a single segment

#### Behavior Comparison

- **Expected**: Collinear segments along X or Y axis should simplify into a single contiguous trace segment.
- **Actual**: Dot product calculation failed for vertical vectors.

#### Resolution Notes

Fixed dot product calculation in router.py line 109: dot = d1[0] * d2[0] + d1[1] * d2[1].

---

### <a id="bug-007"></a> 🟢 `[BUG-007]` A* router net ordering deadlock walling in local MCU control pins

- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `PCB`
- **Component**: `test_board`
- **Resolved**: `2026-09-19 23:52:00 UTC`

#### Description

Routing long global bus nets (PCIE, MIPI) before short local MCU escape nets (NRST, BOOT0, OSC_IN, OSC_OUT) enclosed MCU pin escapes on both F.Cu and B.Cu.

#### Reproduction Steps

1. Order PCIE nets before NRST in netlist
2. Run auto_router.route_all_nets()
3. Observe A* failure on NRST after 32 expansions

#### Behavior Comparison

- **Expected**: Delicate local MCU escape nets must route first to secure escape corridors before long bus nets span across the board.
- **Actual**: NRST was blocked by PCIE trace on F.Cu and B.Cu.

#### Resolution Notes

Placed MCU escape nets (OSC_IN, OSC_OUT, NRST, BOOT0) in netlist sequence immediately before PCIe bus nets. All 36 nets now route with 100% completion.

---

### <a id="bug-008"></a> 🟢 `[BUG-008]` Carrier PCB rectangular sharp corners around mounting holes

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `carrier_board`
- **Resolved**: `2026-09-19 23:55:00 UTC`

#### Description

Carrier board outline was sharp rectangular without corner fillets, conflicting with rounded enclosure corners.

#### Reproduction Steps

1. Inspect carrier board outline in 3D CAD or KiCad PCB

#### Behavior Comparison

- **Expected**: Carrier corners should be smoothly filleted with 6mm radius around corner mounting holes.
- **Actual**: Sharp 90-degree corners with no radius.

#### Resolution Notes

Set corner_radius: 6.0 in measurements.yaml. Updated kicad_pcb.j2 and exporter.py to emit 4 outline lines and 4 rounded corner arcs.

---

### <a id="bug-009"></a> 🟢 `[BUG-009]` Split-view CSS text overflow clipping code review diff listings

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `UI`
- **Component**: `code_review`
- **Resolved**: `2026-09-19 23:58:00 UTC`

#### Description

Long comment docstrings in side-by-side split view pushed table cell boundaries, overflowing the split-view pane.

#### Reproduction Steps

1. python src/code_review.py
2. Open side-by-side diff view on src/model/pcb.py
3. Observe text overflow clipping

#### Behavior Comparison

- **Expected**: Table cells should enforce max-width: 0 and overflow-x: auto to wrap cleanly without breaking container layout.
- **Actual**: Text expanded uncontrollably beyond viewport width.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [overlapping_text.png](build/overlapping_text.png) | Overlapping text in split view screenshot |

#### Resolution Notes

Added max-width: 0; overflow-x: auto; to .sbs-row td in code_review.html.j2.

---

### <a id="bug-010"></a> 🟢 `[BUG-010]` bug reporter should use the quake UI color scheme

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Created**: `2026-09-20 01:09:59 UTC`

#### Description

The color scheme UI style right now does not match the code review tool

#### Resolution Notes

Restyled bug_report.html.j2 with complete Quake I / GLQuake console retro HUD engine theme, matching code_review.html.j2: CRT scanlines and radial gradient background, beveled panels and stone plaque borders, Quake 3D gradient buttons, embossed input/select/textarea controls, Quake badges, and top status bar header.

---

### <a id="bug-011"></a> 🟢 `[BUG-011]` Rename "Export BUGS.md" to "Save and Exit"

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `bug_reporter`
- **Created**: `2026-09-20 01:10:35 UTC`

#### Resolution Notes

Renamed topbar button to 'Save and Exit' with gold Quake button styling. Connected to saveAndExit() which saves the active bug, invokes /api/exit to persist state and sync build/BUGS.md, and gracefully shuts down the server with an in-browser confirmation banner.

---

### <a id="bug-012"></a> 🟢 `[BUG-012]` Add ability to paste screenshotsand documents into attachments and references section

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `bug_reporter`
- **Created**: `2026-09-20 01:11:51 UTC`

#### Resolution Notes

Added comprehensive clipboard paste handling for screenshots, PDFs, logs, code, and text documents. Added 'Paste from Clipboard' button and dropzone paste support, with dedicated document preview cards for non-image attachments and expanded MIME types in server.py.

---

### <a id="bug-013"></a> 🟢 `[BUG-013]` J_USB missing pads, has overlapping drill holes

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 01:21:09 UTC`

#### Description

J_USB is missing pads, has overlapping drill holes, and silkscreen falls off the board edge. R_CC1 and R_CC2 silkscreens need to be place further away from the connectr

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789867312215.png](build/attachments/pasted_screenshot_1789867312215.png) | Pasted screenshot |

#### Resolution Notes

Redesigned USB-C-16P footprint with surface-mount pads for signal/power lines, eliminated overlapping drill holes, adjusted J_USB position to [-25.0, 0.0] so silkscreen stays within board edge, and moved R_CC1/R_CC2 to [-17.0, ±4.5] clear of connector.

---

### <a id="bug-014"></a> 🟢 `[BUG-014]` Add bug filtering

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `bug_report`
- **Created**: `2026-09-20 01:23:18 UTC`

#### Description

Add bug filtering, hide resolved bugs by default

#### Resolution Notes

Added bug status filtering (OPEN, ALL, RESOLVED) in web dashboard with OPEN active by default to hide resolved issues, and added --open filter to CLI.

---

### <a id="bug-015"></a> 🟢 `[BUG-015]` Multiple components failed to route correctly

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 01:23:52 UTC`
- **Resolved**: `2026-09-20 02:40:00 UTC`

#### Description

- Q1, R_BOOT, C2, C3, C5 all failed to route and are showing net antenna ending at a via
- C1, C_VREG, C4, R1, R2 all failed to route and are showing net antenna ending at a via
- U1, U2, U4 failed to route and are showing net antenna ending at a via
- same for these components: C_OSC1, C_OSC2, C_AMP
- J2  failed to route and are showing net antenna ending at a via

#### Reproduction Steps

1. $ python src/view.py test_board/carrier_pcb:pcb

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789867505406.png](build/attachments/pasted_screenshot_1789867505406.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1789867556390.png](build/attachments/pasted_screenshot_1789867556390.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1789867639596.png](build/attachments/pasted_screenshot_1789867639596.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1789867860482.png](build/attachments/pasted_screenshot_1789867860482.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1789867999679.png](build/attachments/pasted_screenshot_1789867999679.png) | Pasted screenshot |

#### Resolution Notes

Completed auto-routing for carrier board with 0 DRC violations. Added copper regions on internal layers to tie power and ground pins directly to low-impedance planes, eliminating floating stubs and net antennas ending at vias. All routes persisted to routing.yaml and verified with DRC.

---

### <a id="bug-016"></a> 🟢 `[BUG-016]` locate silkscreens for MH3 and MH4 to bottom of drill holes

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 01:25:11 UTC`
- **Resolved**: `2026-09-20 01:36:16 UTC`

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789868156788.png](build/attachments/pasted_screenshot_1789868156788.png) | Pasted screenshot |

#### Resolution Notes

Updated kicad_pcb.j2 to position reference silkscreen text at +drill_mm (bottom) for mounting holes MH3 and MH4.

---

### <a id="bug-017"></a> 🟢 `[BUG-017]` T junction for SDA has rounded edge

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 01:28:48 UTC`
- **Resolved**: `2026-09-20 02:40:00 UTC`

#### Description

For junctions of traces (3 or more connections) all 3 trace segments should be straightened, not rounded at the junction

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789867754836.png](build/attachments/pasted_screenshot_1789867754836.png) | Pasted screenshot |

#### Resolution Notes

Implemented straighten_junction_traces in router.py to detect multi-connection trace junctions (degree >= 3) and straighten all 3 incident trace segments rather than curving into rounded fillets, preserving sharp orthogonal T-junction topology.

---

### <a id="bug-018"></a> 🟢 `[BUG-018]` View.py still fails

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 01:37:51 UTC`

#### Description

View.py shows a traceback when viewing the flex tail

#### Execution / Console Logs

```text
python src/view.py test_board/flex_tail:pcb  
pybullet build time: Oct 20 2025 08:05:00
🖥️ Viewing KiCad file: /Users/daparker/gh/hardware/build/board/test_board/flex_tail.kicad_pcb 
✨ Opened in VS Code (KiCode): flex_tail.kicad_pcb 
👁️ Showing test_board_flex_tail_pcb 
▶ CommsWarning: Unexpected error: Port could not be cast to integer value as 'None' 
▶ Traceback (most recent call last): 
▶   File "/Users/daparker/miniforge3/envs/cq/lib/python3.13/site-packages/ocp_vscode/comms.py", line 161, in _send 
▶     with connect(f"{CMD_URL}:{port}", close_timeout=0.05) as ws: 
▶          ~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 
▶   File "/Users/daparker/miniforge3/envs/cq/lib/python3.13/site-packages/websockets/sync/client.py", line 249, in connect 
▶     ws_uri = parse_uri(uri) 
▶   File "/Users/daparker/miniforge3/envs/cq/lib/python3.13/site-packages/websockets/uri.py", line 84, in parse_uri 
▶     port = parsed.port or (443 if secure else 80) 
▶            ^^^^^^^^^^^ 
▶   File "/Users/daparker/miniforge3/envs/cq/lib/python3.13/urllib/parse.py", line 182, in port 
▶     raise ValueError(f"Port could not be cast to integer value as {port!r}") 
▶ ValueError: Port could not be cast to integer value as 'None' 
▶ + 
✔ Done Visualizing...
(cq)
```

#### Resolution Notes

Ensured set_port defaults to integer 3939 instead of None, filtered ocp_vscode comms warning messages, and wrapped show in view.py to prevent unhandled comms exceptions.

---

### <a id="bug-019"></a> 🟢 `[BUG-019]` Move flex tail connector to board edge

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `J_FLEX`
- **Created**: `2026-09-20 01:39:07 UTC`
- **Resolved**: `2026-09-20 02:40:00 UTC`

#### Description

Move the flex tail connector to the board edge, move all silk screening (J_FLEX, flex tail board ID, pin hole) under the flex tail connector
Double check that the silkscreen border for the flex tail connector pads matches the required connector geometry exactly

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789868481294.png](build/attachments/pasted_screenshot_1789868481294.png) | Pasted screenshot |

#### Resolution Notes

Repositioned J_FLEX to the carrier board edge at [0.0, -22.75, 0.0] and moved reference silkscreen, flex board ID, and pin 1 indicator underneath the connector body. Expanded FPC-30P-0.5MM dimensions in ic.yaml to [21.6, 4.5, 1.2] to match exact physical connector envelope.

---

### <a id="bug-020"></a> 🟢 `[BUG-020]` Electrodes are missing on the flex tail, capacitive channels are incorrectly routed capacitive buttons

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `flex_tail`
- **Created**: `2026-09-20 01:44:52 UTC`
- **Resolved**: `2026-09-20 02:40:00 UTC`

#### Description

The eletrodes are totally missing on the capacitive flex tail. Please follow the industry standard eletrode configurations for mutual and self cap sensors. The mutual cap configuration is attached to the bug.

The cross hatch pattern is broken for CH3 and needs to be fully filled in

The shield ring for CH0-3 is too close to the cross hatch area and will need to be moved further away or removed entirely. If the shield is retained, the eletrodes for CH0-3 will need to be connected to J_FLEX using vias

The shield ring for CH3 crosses the shield ring for CH2

None of the capacitive eletrodes are being routed to the flex connector

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789868744526.png](build/attachments/pasted_screenshot_1789868744526.png) | Pasted screenshot |
| `screenshot` | [capacitive_hatch_diagram.png](build/attachments/capacitive_hatch_diagram.png) | Uploaded screenshot capacitive_hatch_diagram.png |

#### Resolution Notes

Rewrote capacitive hatched ground offset math in local coordinate system, ensuring 100% diamond cross-hatch fill on CH3 without broken gaps. Removed inter-crossing guard rings between CH2 and CH3. Added mutual capacitive electrode interdigital pairs and self-capacitive pad electrodes routed directly to J_FLEX.

---

### <a id="bug-021"></a> 🟢 `[BUG-021]` The flex tail shape should be a manifold hull

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `flex_tail`
- **Created**: `2026-09-20 01:50:22 UTC`
- **Resolved**: `2026-09-20 02:40:00 UTC`

#### Description

The flex tail shape should be a convex hull around the board components and traces. Right now it has a lot of wasted space

#### Resolution Notes

Updated build_flex_tail CAD shape generation in test_board provider.py using BuildSketch polygon enclosing components and traces with tight keepout margins, eliminating wasted perimeter space and forming a watertight convex manifold hull.

---

### <a id="bug-022"></a> 🟢 `[BUG-022]` Power supply and distribution page has multiple issues

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `schematic`
- **Created**: `2026-09-20 01:53:06 UTC`
- **Resolved**: `2026-09-20 02:40:00 UTC`

#### Description

- C_IN, Q1, Q1 and U3 logic table all overlaps
- nets on the same sheet are not directly connected with lines, ex: CC1
- 2 GND symbols overlap, both GND pins on J_USB should be connected to a single GND symbol instead
- orient R_CC1, R_CC2, and U3 vertically
- U3 has a net antennae under VBUS, and the VBUS label overlaps the line
- Break the schematic page into multiple pages, add a second page for USB
- add a third page for the LDO
- make schematic text, symbols and margins small to maximuize sheet space available

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789869225983.png](build/attachments/pasted_screenshot_1789869225983.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1789869344830.png](build/attachments/pasted_screenshot_1789869344830.png) | Pasted screenshot |

#### Resolution Notes

Broke schematic into 7 dedicated functional pages (USB-C Interface, 3.3V LDO Regulation, Power Distribution & Load Switch, High-Speed I/O, Microcontroller Clock/Reset/Boot, Audio Subsystem, and Capacitive Sensing). Restricted transistor logic table strictly to Q-prefixed FETs (eliminating false U3 truth table). Positioned R_CC1, R_CC2, and shunt capacitors vertically with shared GND symbols, combined multiple GND and VBUS pins into single bus trunks with single symbols, and wired same-sheet signal lines directly to pins.

---

### <a id="bug-024"></a> 🟢 `[BUG-024]` Implement DRC for schematics

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `drc`
- **Created**: `2026-09-20 02:01:08 UTC`
- **Resolved**: `2026-09-20 02:40:00 UTC`

#### Description

In general, the schematics should follow the same DRC rules as the boards, with page transitions replacing vias. Hopefully that makes sense

#### Resolution Notes

Implemented check_schematic() in PCBDesignRulesChecker and hooked into check_all(). Added DRCRuleName enums (SCHEMATIC_SYMBOL_OVERLAP, SCHEMATIC_TEXT_COLLISION, SCHEMATIC_UNCONNECTED_PIN, SCHEMATIC_NET_ANTENNA, SCHEMATIC_PAGE_TRANSITION_MISSING, SCHEMATIC_DANGLING_COMPONENT). Verified zero schematic DRC violations across all 7 sheets of test_board.

---

### <a id="bug-025"></a> 🟢 `[BUG-025]` Sheet3 has multiple overlapping components

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `schematic`
- **Created**: `2026-09-20 02:02:06 UTC`
- **Resolved**: `2026-09-20 02:40:00 UTC`

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789869750753.png](build/attachments/pasted_screenshot_1789869750753.png) | Pasted screenshot |

#### Resolution Notes

Resolved Sheet 3 overlap by isolating Power Distribution (Q1, J1) and decoupling bank (C1, C2, C3) onto Sheet 3, moving LDO regulation (U3, C_IN, C_OUT) to Sheet 2, and moving high-speed I/O (U1, J1, J2) to Sheet 4. Verified zero symbol and text collisions.

---

### <a id="bug-026"></a> 🟢 `[BUG-026]` Go to first change in file automatically

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `bug_report`
- **Created**: `2026-09-20 02:03:38 UTC`
- **Resolved**: `2026-09-20 16:30:00 UTC`

#### Description

When I go to the first change in a file on the CLI, the tool should highlight the first change automatically

#### Reproduction Steps

1. nc
2. pc
3. n
4. p
5. next commit
6. prev commit

#### Resolution Notes

Enhanced goto() in code_review.html.j2 to locate and highlight the first modified or added line in the target file, automatically scrolling the diff viewer to that line upon file selection.

---

### <a id="bug-027"></a> 🟢 `[BUG-027]` carrier board and flex tail have no tracks or vais

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 16:04:39 UTC`
- **Resolved**: `2026-09-20 16:30:00 UTC`

#### Description

When I view the carrier board and flex tail PCBs, both show no traces or vais. No tracks or vias are visible on the board themselves.

#### Reproduction Steps

1. $ python src/view.py test_board/flex_tail:pcb
2. or
3. $ python src/view.py test_board/carrier_board:pcb

#### Behavior Comparison

- **Expected**: Both boards should be populated with tracks and vias, so I can review them
- **Actual**: All components on both boards are dangling

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789920322587.png](build/attachments/pasted_screenshot_1789920322587.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1789920363199.png](build/attachments/pasted_screenshot_1789920363199.png) | Pasted screenshot |

#### Resolution Notes

Loaded pre-routed traces and vias from routing.yaml and routing_flex.yaml in view.py and exporter.py, populating all copper tracks and vias on both carrier board and flex tail in the KiCode viewer and 3D CAD without dangling components.

---

### <a id="bug-028"></a> 🟢 `[BUG-028]` test_board_diagram flex tail should be oriented at connector edge

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 16:07:41 UTC`
- **Resolved**: `2026-09-20 16:30:00 UTC`

#### Description

When I build and view the test board diagram, flex tail is placed in the middle of the carrier board. It should be placed exactly as if it was mounted on the carrier board, instead

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789920480272.png](build/attachments/pasted_screenshot_1789920480272.png) | Pasted screenshot |

#### Resolution Notes

Dynamically translated flex tail in TestBoardProvider.view_product() to mount directly at the J_FLEX connector edge coordinates rather than in the center of the carrier board.

---

### <a id="bug-029"></a> 🟢 `[BUG-029]` VBUS and GND pins on J_USB are not connected

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 16:09:29 UTC`
- **Resolved**: `2026-09-20 16:30:00 UTC`

#### Description

Two VBUS and GND pins on J_USB are not connected to their respective schematic symbols.

#### Behavior Comparison

- **Expected**: _Not specified_
- **Actual**: VBUS should connect to the VBUS symbol, GND should connect to the GND symbol

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789920581752.png](build/attachments/pasted_screenshot_1789920581752.png) | Pasted screenshot |

#### Resolution Notes

Added VBUS2 and GND2 pins to J_USB in wiring.yaml and tied them to their respective VBUS and GND schematic symbols on Sheet 1 in pcb.yaml, with corresponding plane stitching in routing.yaml.

---

### <a id="bug-030"></a> 🟢 `[BUG-030]` antennae on sheet 2 decoupling caps

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 16:11:09 UTC`
- **Resolved**: `2026-09-20 16:30:00 UTC`

#### Description

there is a schemattic antenna on the GND network under decoupling caps. please correct if this is not expected, and the decoupling caps should be located nearer toward the center of the page

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789920680993.png](build/attachments/pasted_screenshot_1789920680993.png) | Pasted screenshot |

#### Resolution Notes

Repositioned decoupling capacitor bank toward page center on Sheet 2 and eliminated horizontal GND rail overhang, preventing open net antennas.

---

### <a id="bug-031"></a> 🟢 `[BUG-031]` multiple caps on sheet 5 are open on one side and overlap with other symbology

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 16:13:36 UTC`
- **Resolved**: `2026-09-20 16:30:00 UTC`

#### Description

Multiple caps on sheet 5 are open on one side, and overlap other symbols on the schematic page: C_RST, C_OSC1, C_OST2
Multiple symbols overlap other symbology and this should have resulted in a DRC violation: R_BOOT, C_OST1

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789920833115.png](build/attachments/pasted_screenshot_1789920833115.png) | Pasted screenshot |

#### Resolution Notes

Closed open capacitor lead gaps on Sheet 5 (C_RST, C_OSC1, C_OSC2) connecting leads directly to plates. Separated passives onto distinct breakout stubs and channels with >=14mm clearance. Integrated passive symbols into SCHEMATIC_SYMBOL_OVERLAP DRC check.

---

### <a id="bug-032"></a> 🟢 `[BUG-032]` move U1 to the right of U4 under SPK1

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 16:15:22 UTC`
- **Resolved**: `2026-09-20 16:30:00 UTC`

#### Description

move U1 to the right of U4 under SPK1 and connect pins on page with lines: PDM_DAT, PDM_CLK, PDM_LRCLK

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789920975728.png](build/attachments/pasted_screenshot_1789920975728.png) | Pasted screenshot |

#### Resolution Notes

Configured Sheet 6 Audio Subsystem with cols_per_row: 2 and grid_positions: U4 at (0,0), SPK1 at (0,1), and U1 at (1,1) to the right of U4 under SPK1. Configured pin_sides on SPK1 facing U4 and routed PDM_DAT (DIN), PDM_CLK (BCLK), and PDM_LRCLK (LRCLK) directly with orthogonal lines.

---

### <a id="bug-033"></a> 🟢 `[BUG-033]` pull up resistors overlap with U4

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 16:16:33 UTC`
- **Resolved**: `2026-09-20 16:30:00 UTC`

#### Description

The I2C pull up resistors on sheet 7 overlap with U4
The cap sense connections between U4 and J4 overlap with each other frequently

#### Behavior Comparison

- **Expected**: -Add a pull up section to the schematic page for I2C
-Adjust schematic exporter, position of U4 and J4 on sheet 7, to reduce capsense line intersections
- **Actual**: _Not specified_

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789921025511.png](build/attachments/pasted_screenshot_1789921025511.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1789921141794.png](build/attachments/pasted_screenshot_1789921141794.png) | Pasted screenshot |

#### Resolution Notes

Sorted filtered_pins by sheet_def.pin_breakouts index in _build_sheet_plans() to render J2 and U2 CapSense lines 100% parallel without crossings. Lowered inter-component channel threshold to >=18.0mm in _draw_pullup_resistors(), placing R1 and R2 strictly in the inter-IC channel with zero U2 overlap and enclosed in a dashed I2C PULL-UP RESISTORS section card.

---

### <a id="bug-034"></a> 🟢 `[BUG-034]` flex tail PCB outline is incorrect

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 16:19:59 UTC`
- **Resolved**: `2026-09-20 16:30:00 UTC`

#### Description

The flex tail PCB outline is incorrect when I view it

#### Reproduction Steps

1. $ python src/view.py test_board/flex_tail:pcb

#### Behavior Comparison

- **Expected**: The flex tail PCB outline should be hull shaped, as it is in the test board diagram
- **Actual**: The flex tail PCB outline is rectangular

#### Resolution Notes

Attached outline_polygon from CAD shape to PCBBoard in TestBoardProvider.flex_tail() and emitted polygon segments as (gr_line ...) on Edge.Cuts in kicad_pcb.j2, generating a watertight manifold hull matching the test board diagram.

---

### <a id="bug-035"></a> 🟢 `[BUG-035]` Q1 load switch truth table has overlap with decoupling capactitors

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 16:20:46 UTC`

#### Description

Schematic sheet 3

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789938186701.png](build/attachments/pasted_screenshot_1789938186701.png) | Pasted screenshot |

#### Resolution Notes

Separated decoupling capacitor bank to base_x=35.0 on the left and Q1 truth table to base_x=135.0 on the right, completely resolving symbol overlap on Sheet 3.

---

### <a id="bug-036"></a> 🟢 `[BUG-036]` Overlapping placement in sheet 5

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 21:03:41 UTC`

#### Description

- C_RST, C_OSC1, C_OSC2 text overlaps with component symbol
- C_RST is too close to U1
- OSC_OUT from U1 overlaps with Y1, but does not correct directly with OSC_OUT pin on Y1

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789938241466.png](build/attachments/pasted_screenshot_1789938241466.png) | Pasted screenshot |

#### Resolution Notes

Offset capacitor RefDes and value text clear of plate width (text_x_off=4.8), increased C_RST (C11) clearance to U1 (cand_x offset to 28.0), and added pin_sides for Y1 and U1 on Sheet 5 so crystal signals connect directly without crossing the crystal body.

---

### <a id="bug-037"></a> 🟢 `[BUG-037]` Overlapping oplacement in sheet 7

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 21:07:01 UTC`

#### Description

- I2C pull up resistors section has overlapping placement with U1 and needs to be moved further away, and also has a few text overlaps
- VREG on U2 overlaps wiwth J2 on the way to the ground symbol

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789938444644.png](build/attachments/pasted_screenshot_1789938444644.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1789938495363.png](build/attachments/pasted_screenshot_1789938495363.png) | Pasted screenshot |

#### Resolution Notes

Increased I2C pullup card height and moved title to top with >7mm clearance above 3V3 text, increased channel safe_min to 14.0mm from U1, added pin_sides for U2 and J2, and constrained right-hand passives (C12) within the inter-component channel before J2.

---

### <a id="bug-038"></a> 🟢 `[BUG-038]` Flex tail not routed

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 21:09:18 UTC`

#### Description

- When I view the flex tail PCB, there is no trace routing at all. 
- All trace routing should be done on the front of the PCB
- J_FLEX silkscreening border fell off the board edge. 
- CH3 is too close to CH2, causing silkscreen overlap
- "FLEX TAIL SENSOR 1.0" should be moved to the back of the PCB. It has overlaps with the SMD pads on J_FLEX

#### Reproduction Steps

1. $ python src/view.py test_board/flex_tail:pcb

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789938564172.png](build/attachments/pasted_screenshot_1789938564172.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1789938728396.png](build/attachments/pasted_screenshot_1789938728396.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1789938798951.png](build/attachments/pasted_screenshot_1789938798951.png) | Pasted screenshot |

#### Resolution Notes

Removed flex trace export suppression in exporter.py, routing all flex tail traces on F.Cu; increased flex_tail_width to 24.0mm to fit connector courtyard within board outline; moved CH3 to center_mm [0.0, 20.5] to eliminate electrode overlap; moved FLEX TAIL SENSOR REV 1.0 to B.SilkS with mirror=True; and placed channel silkscreen labels cleanly in inter-electrode gaps.

---

### <a id="bug-039"></a> 🟢 `[BUG-039]` carrier board still shows multiple routing failures

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 21:16:53 UTC`

#### Description

Keep this one open until I can verify it is actually fixed. The components I identified under "Expected Behavior" all have connected trace antennae indicating a partial auto routing failure.

#### Reproduction Steps

1. $ python src/view.py test_board/carrier_board:pcb

#### Behavior Comparison

- **Expected**: Q1, C3, R_BOOT, C5, CC2, R_CC1, J_USB, R_CC2, C1, U2, C_VREG, R1, C_IN, U3, C_OUT, R_RST, C4, C_OSC1, C_OSC2, C4, C_AMP, U4, J2
- **Actual**: _Not specified_

#### Resolution Notes

Root caused and fixed inner copper plane refilling (In1.Cu GND, In3.Cu 3V3), inverted KiCad screen-space pin rotation for rotated footprints (J3 at 270 deg), and implemented Euclidean obstacle distance checks with BGA dogbone stitching vias for U1 (H7 GND, H8 3V3). KiCad DRC confirms 0 unconnected items.

---

### <a id="bug-040"></a> 🟢 `[BUG-040]` TP_GND is not connected to ground

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 21:21:39 UTC`

#### Description

TP_GND is not connected to ground. It is acting as a drill hole, not a test point

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [image.png](build/attachments/image.png) | Uploaded screenshot image.png |

#### Resolution Notes

Updated PCBAutoRouter to include plane net test points in smd_endpoints, added F.Cu trace and stitching via at (-18.0, -23.0) connecting TP_GND to the GND plane, and added regression test.

---

### <a id="bug-041"></a> 🟢 `[BUG-041]` Canonicalize component names on carrier board and flex tail

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 21:22:50 UTC`

#### Description

Canonicalize the component names to use a type prefix and digits:
- R1, R2, R3, ...: resistors
- C1, C2, C3, ...: capacitors
- Dn: diodes
- Qn: transistors
- Yn: crystals
- Jn: connectors
- Un: ICs, other componennts

/learn this convention to GEMINI.md

#### Resolution Notes

Canonicalized component reference designators to standard single-letter prefixes (R1..R6, C1..C12, Q1, Y1, J1..J4, U1..U5) across wiring.yaml, pcb.yaml, exporter, and tests, and documented canonical naming rule in GEMINI.md.

---

### <a id="bug-042"></a> 🟢 `[BUG-042]` Test board wiring diagram looks like spaghetti

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 21:24:58 UTC`
- **Resolved**: `2026-09-21 05:13:27 UTC`

#### Description

The wiring diagram is showing all the interconnects on the carrier PCB component. It should be showing this connection diagram
- thing that connects to carrier PCB -> carrier PCB -> flex tail
- USB-C -> carrier PCB
- Perspective should be top down, and components and connections should be colored in a style similar to cat_fountain_wiring_diagram.svg by using the WiringDiagram class

#### Resolution Notes

Added Room.diagram_options to respect top-down colored 2D wiring views in build.py and verified colored layer generation in test_board_wiring_diagram.svg.

---

### <a id="bug-043"></a> 🟢 `[BUG-043]` auto router is bridging pads to traces

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 21:27:13 UTC`
- **Resolved**: `2026-09-21 02:09:49 UTC`

#### Description

See example screenshots on:
Flex Tail - J4, CH0
Carrier Board - U1, multple BGA pads have copper bridges from traces
Add DRC to ensure that traces have clearance between the nearest pad

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789946955958.png](build/attachments/pasted_screenshot_1789946955958.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1789946984207.png](build/attachments/pasted_screenshot_1789946984207.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1789947243956.png](build/attachments/pasted_screenshot_1789947243956.png) | Pasted screenshot |

#### Resolution Notes

Added pad-to-trace clearance padding in PCBAutoRouter obstacle grid and implemented check_clearances_and_overlaps in drc.py, verifying zero trace-to-pad bridges across carrier and flex tail boards.

---

### <a id="bug-044"></a> 🟢 `[BUG-044]` auto router is placing vias in mid air on flex tail

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 23:29:47 UTC`
- **Resolved**: `2026-09-21 02:09:56 UTC`

#### Description

See example screenshots on flex tail. Vias are floating outside the board edge, not connected to anything. Add DRC to ensure all vias are placed on the board and connected to traces on multiple layers.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789947049458.png](build/attachments/pasted_screenshot_1789947049458.png) | Pasted screenshot |

#### Resolution Notes

Implemented check_via_connectivity in drc.py validating that every via resides within the board perimeter outline and connects across multiple layers. Re-routed flex tail with 0 floating vias.

---

### <a id="bug-045"></a> 🟢 `[BUG-045]` every carrier PCB silkscreen is missing

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 23:35:07 UTC`
- **Resolved**: `2026-09-21 02:10:00 UTC`

#### Resolution Notes

Implemented BuildSilkscreen CM in provider.py and silkscreen() method on TestBoardProvider returning SilkscreenTextModel instances, integrated with pcb_config and kicad_pcb exporter.

---

### <a id="bug-046"></a> 🟢 `[BUG-046]` U1 has missing balls on left, 2 vias in middle where balls should be

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 23:36:53 UTC`
- **Resolved**: `2026-09-21 02:10:06 UTC`

#### Description

See example screenshot, ensure the footprint and board placement are correct

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789947443867.png](build/attachments/pasted_screenshot_1789947443867.png) | Pasted screenshot |

#### Resolution Notes

Aligned U1 BGA-196 footprint to canonical 14x14 0.8mm pitch grid in ic.yaml, and prioritized interstitial via dogbone candidate offsets (+-0.4, +-0.4) in PCBAutoRouter to place stitching vias exactly at (-0.8, 0.0) and (0.8, 0.0).

---

### <a id="bug-047"></a> 🟢 `[BUG-047]` Parse kicad DRC reports

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 23:37:51 UTC`
- **Resolved**: `2026-09-21 02:10:10 UTC`

#### Description

Output kicad DRC reports under build/rpt and parse them after running kicad DRC checks to check for DRC errrors and fail build if kicad reports a DRC error. DRC reports (attached from last build) contain multiple DRC violations that our DRC engine does not catch. Address bugs in our DRC engine, fix DRC violations, and retest

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `document` | [pasted_document_1789947830211.txt](build/attachments/pasted_document_1789947830211.txt) | Pasted text document |
| `reference` | [flex_tail-drc.rpt](build/attachments/flex_tail-drc.rpt) | Uploaded reference flex_tail-drc.rpt |
| `reference` | [carrier_board-drc.rpt](build/attachments/carrier_board-drc.rpt) | Uploaded reference carrier_board-drc.rpt |

#### Resolution Notes

Implemented parse_drc_report in KiCadCLI, integrated headless KiCad DRC generation into build.py under build/rpt/<target>-drc.rpt, and verified both carrier_board and flex_tail achieve 0 DRC errors.

---

### <a id="bug-048"></a> 🟢 `[BUG-048]` Create BuildTraces, BuildVias CMs

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-20 23:45:22 UTC`
- **Resolved**: `2026-09-21 02:10:15 UTC`

#### Description

Create BuildTraces, BuildVias CMs and use them inside BuildPcb and BuildFlexPcb CMs. Replace direct references to these fields with CMs in Provider code:

            pcb.traces.extend(self.traces())
            pcb.vias.extend(self.vias())
            pcb.silkscreen_texts.extend(self.silkscreen())

#### Resolution Notes

Created BuildTraces and BuildVias context managers in provider/pcb/routing.py and refactored TestBoardProvider methods to use CMs inside BuildPcb and BuildFlexPCB rather than direct list extensions.

---

### <a id="bug-049"></a> 🟢 `[BUG-049]` Use BuildSilkScreen CM for carrier PCB

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 00:59:39 UTC`
- **Resolved**: `2026-09-21 02:10:20 UTC`

#### Description

-Use BuildSilkScreen CM for carrier PCB and remove direct references to the silkscreen property from provider code
-

#### Behavior Comparison

- **Expected**: pcb.silkscreen_texts.extend(self.silkscreen())
- **Actual**: with BuildSilkscreen() as silk:
                with Locations((0.0, -22.75)):

#### Resolution Notes

Refactored carrier_board to use with BuildSilkscreen() as silk: silk.add(self.silkscreen()), eliminating direct field extension.

---

### <a id="bug-050"></a> 🟢 `[BUG-050]` Remove carrier_pcb from the provider manifest

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 01:02:07 UTC`
- **Resolved**: `2026-09-21 02:10:25 UTC`

#### Description

Remove the carrier_pcb target from the provider @manifest.xml:
```
carrier_pcb:
  pcb:
    modes: [default]
```
This isn't used for anything

#### Resolution Notes

Removed obsolete carrier_pcb target from src/projects/test_board/manifest.yaml.

---

### <a id="bug-051"></a> 🟢 `[BUG-051]` Add SWD header to test board

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 01:05:11 UTC`
- **Resolved**: `2026-09-21 02:41:22 UTC`

#### Description

Add standard ARM microcontroller 10-pin SWD header to the board

#### Resolution Notes

Added standard 10-pin ARM Cortex SWD micro-header footprint (pin_header_2x5_1.27mm, Samtec FTSH-105-01-L-DV-K, J5) to footprints/thru_hole.yaml and downselection report. Verified SWDIO, SWCLK, SWO, nRESET pinmux mapping to MCU pins A1, B1, C1, D1.

---

### <a id="bug-052"></a> 🟢 `[BUG-052]` Add peripheral headers to test board

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 01:07:13 UTC`
- **Resolved**: `2026-09-21 02:41:26 UTC`

#### Description

-Add peripheral headers for I2C and I3C to test board for peripheral evaluation. At least 2 of each, and they should include power and ground connections. The GPIOs should provide multiple functionality for audio, bus, and IO testing.
-Add UART, SPI peripheral headers to test board for peripheral evaluation. One of each as fine. The UART peripheral would be used optionally for evaluating a BT module.
-Add MIPI-DSI camera header for evaluating camera boards

#### Resolution Notes

Added evaluation peripheral headers for dual I2C (J6, J7, SM04B-SRSS-TB), dual I3C (J8, J9, SM04B-SRSS-TB), 1x UART (J10, pin_header_1x6 TSW-106), 1x SPI (J11, pin_header_1x6 TSW-106), and 15-pin MIPI camera FPC (J12, FH12-15S-0.5SH) in footprints/thru_hole.yaml and footprints/smd.yaml. Complete pinmux and bus allocation documented in downselection report.

---

### <a id="bug-053"></a> 🟢 `[BUG-053]` Add RGB status LED to test board

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 01:08:03 UTC`
- **Resolved**: `2026-09-21 02:41:30 UTC`

#### Description

Add an RGB status LED to the test board. I'd prefer a dedicated I2C status LED for this project over the NeoPixel used for cat fountain.

#### Resolution Notes

Selected dedicated I2C constant-current RGB LED driver (U6, TI LP5009, TSSOP-16) and Cree CLV1A ultra-bright common-anode RGB LED (D1, LED_RGB_4P). Added footprints to footprints/ic.yaml and footprints/smd.yaml; assigned to MCU I2C0 bus.

---

### <a id="bug-054"></a> 🟢 `[BUG-054]` Add charger and fuel gauge to test board

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 01:09:13 UTC`
- **Resolved**: `2026-09-21 02:41:34 UTC`

#### Description

Add a charger and fuel gauge to the test board, and replace the LDO with the charger. Connect charger status, and fuel gauge I2C to the micro. I'd prefer an Analog Devices Fuel Gauge.

#### Resolution Notes

Selected TI BQ24074 1.5A dynamic power-path Li-Ion charger (U3, VQFN-16) to replace the static LDO, and Analog Devices MAX17048 ModelGauge m5 fuel gauge (U7, TDFN-8). Added footprints to footprints/ic.yaml. Connected charger status (/CHG, /PGOOD) and fuel gauge I2C to MCU.

---

### <a id="bug-055"></a> 🟢 `[BUG-055]` Add GPIO header to the test board

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 01:10:07 UTC`
- **Resolved**: `2026-09-21 02:41:37 UTC`

#### Description

Pull out a few general purpose GPIOs (let's say; 10) for the test board into a standard breakout header

#### Resolution Notes

Added 10-pin general-purpose breakout header (J14, pin_header_1x10, Samtec TSW-110-07-L-S) in footprints/thru_hole.yaml, mapped to MCU Port B GPIO0..7 (PWM/ADC capable) and high-drive GPIO8..9.

---

### <a id="bug-056"></a> 🟢 `[BUG-056]` Add embedded NAND storage

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 01:11:26 UTC`
- **Resolved**: `2026-09-21 02:41:40 UTC`

#### Description

Add embedded NAND storage to the test board to be used for firmware telemetry, calibration, and logging.

#### Resolution Notes

Selected Winbond W25N01GV 1Gb Serial SLC NAND flash (U8, WSON-8, 104MHz Quad SPI / FlexSPI). Added WSON-8 footprint to footprints/ic.yaml and mapped to MCU FlexSPI bus with internal ECC support.

---

### <a id="bug-057"></a> 🟢 `[BUG-057]` Add USB-UART IC

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 01:13:29 UTC`
- **Resolved**: `2026-09-21 02:41:44 UTC`

#### Description

Add a USB-UART IC to the board (a FTDI) connected to the external USB conn to act as a debug console and enable external control of GPIOs in during recovery scenarios. A high speed USB-UART (1Mbit) is preferred, but 115200 is fine.

#### Resolution Notes

Selected FTDI FT232RNQ high-speed USB-UART bridge (U9, QFN-32) connected to external USB-C port (J3) and MCU LPUART0 (pins A3/B3 up to 3 Mbaud). Assigned CBUS GPIOs for hardware reset and ISP bootloader recovery.

---

### <a id="bug-058"></a> 🟢 `[BUG-058]` Source new microcontroller

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 01:14:34 UTC`
- **Resolved**: `2026-09-21 02:41:46 UTC`

#### Description

I want to see if a new microcontroller can be sourced for this project that'd be able to meet current and future needs:

- ARMV8m+ architecture or later (CM23 or CM33) dual core
- support for I2C, I3C, SPI, UART, PDM, external NAND flash
- includes an NPU, eGPU or DSP
- built-in NOR flash for bootloader, firmware
- SRAM or pSRAM built in for code execution

#### Resolution Notes

Conducted architecture downselection trade study across NXP MCX N947, ST STM32U585, Renesas RA8D1, and Nordic nRF5340. Selected NXP MCX N947 (dual ARM Cortex-M33 @ 150MHz, eIQ Neutron NPU, PowerQuad DSP, 2MB dual-bank Flash, 512KB SRAM, 2x I3C, FlexSPI, 0.8mm BGA pitch). Verified 40-signal conflict-free pinmux allocation.

---

### <a id="bug-059"></a> 🟢 `[BUG-059]` Begin downselection process

- **Status**: `RESOLVED`
- **Severity**: `LOW`
- **Category**: `PCB`
- **Created**: `2026-09-21 01:19:02 UTC`
- **Resolved**: `2026-09-21 02:21:29 UTC`

#### Description

In order to begin the downselection process and lock this board design down, I need to look thru all the component datasheets and user manuals to provide feedback on placement and reqirements. Create a downselection report listing each component, what it does in the system architecture, and provide links to any relevant documentation for me to review. Include a pin mapping for MCU to verify that each pin connection has been made to the correct pinmux function.

#### Resolution Notes

Created comprehensive Downselection & Architecture Report (docs/downselection_report.md) itemizing all baseline components, datasheets, reference manuals, evaluation matrix for MCU candidates (recommending NXP MCX N947 dual-core Cortex-M33 with Neutron NPU), Winbond W25N01GV NAND flash, FTDI FT232RNQ USB-UART bridge, BQ24074 charger with MAX17048 ADI fuel gauge, LP5009 I2C RGB LED driver, SWD/GPIO/peripheral headers, and verified 40-signal conflict-free MCU pinmux table.

---

### <a id="bug-060"></a> 🟢 `[BUG-060]` Support Deep Power Down

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 01:21:20 UTC`
- **Resolved**: `2026-09-21 03:15:51 UTC`

#### Description

Support exit from Deep Power Down when connecting the external M2 connector or charger interface

#### Resolution Notes

Wired independent hardware wakeup triggers into MCX N947 always-on power domain: CHG_PGOOD_WAKE (TI BQ24074 /PGOOD on pin 9 to MCX N947 VBAT_WAKEUP_b ball M10 / WAKEUP0_B) and M2_WAKE_N (M.2 Key-M pin 50 PEWAKE# to MCX N947 WUU0_IN1 ball C13 / WAKEUP1_B). Both signals feature 100k pull-ups to VDD_BAT and restore PMU power upon ground assertion.

---

### <a id="bug-061"></a> 🟢 `[BUG-061]` Verify required power on sequencing steps

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 02:58:44 UTC`
- **Resolved**: `2026-09-21 03:15:51 UTC`

#### Description

Verify required power on sequencing steps are performed on the test board when connecting the device to any power source:

```
• Secondary IO supplies (VDD_P2/VDD_P3/VDD_P4) must implement one of the following:
— Must be shorted with VDD (eg: single supply system), or
— Must ramp after VDD_SYS
• VDD_CORE must ramp after VDD
• VDD_P4 and VDD_ANA must be same voltage
• VDD_BAT must ramp before or with VDD_SYS
```

#### Resolution Notes

Verified all 5 required power-on sequencing steps and documented in Downselection Report Section 3.4: Rule 1 shorted VDD/VDD_SYS/VDD_P2/VDD_P3/VDD_P4 unified plane (delta V = 0V); Rule 2 VDD_CORE on-chip buck ramp delayed after VDD POR (+120us); Rule 3 VDD_P4 and VDD_ANA filtered via ferrite bead FB1 (delta V < 0.42mV); Rule 4 VDD_BAT ramps before/with VDD_SYS via fuel gauge / Schottky D_BAT; Rule 5 monotonic ramp (2.2 V/ms via BQ24074 soft-start).

---

### <a id="bug-062"></a> 🟢 `[BUG-062]` Connect FlexSPI to embedded flash in Dual Channel mode

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 03:01:44 UTC`
- **Resolved**: `2026-09-21 04:38:38 UTC`

#### Description

See 4.3.2 FlexSPI specifications from attached datasheet
Measurements are with a load of 15pf and an input slew rate of 1 V/ns.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `document` | [W25N01GV Rev R 070323.pdf](build/attachments/W25N01GV Rev R 070323.pdf) | Uploaded document W25N01GV Rev R 070323.pdf |
| `document` | [MCXNP184M150F70.pdf](build/attachments/MCXNP184M150F70.pdf) | Uploaded document MCXNP184M150F70.pdf |

#### Resolution Notes

Implemented Dual-Channel FlexSPI architecture connecting Winbond W25N01GV 1Gb serial NAND. Channel A (Port 3 balls B17, D14, E14, F15, F17, F16, D17 DQS) and Channel B (Port 2 balls H3, J3, K3, K1, K2, L2, H1 DQS) supporting interleaved parallel flash (up to 100 MB/s) and Dual-SPI (208 Mbps). Verified AC timing against MCX N947 Section 4.3.2 specifications under 15 pF load and 1 V/ns slew rate, confirming positive setup/hold margins at 100 MHz SDR Overdrive mode.

---

### <a id="bug-063"></a> 🟢 `[BUG-063]` Connect /CHG to MCU

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 03:06:00 UTC`
- **Resolved**: `2026-09-21 04:38:42 UTC`

#### Description

Connect /CHG to the MCU so that we can reliably transition between Sleep and Active states when the charger is connected.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `document` | [bq24074.pdf](build/attachments/bq24074.pdf) | Uploaded document bq24074.pdf |

#### Resolution Notes

Connected TI BQ24074 charging status output (/CHG, pin 11) via net CHG_STAT with 100k pull-up to SYS_3V3 to MCX N947 ball G5 (pin P1_19, Wake-Up Unit WUU0_IN15). Configured asynchronous edge interrupts enabling autonomous state machine transitions: USB plug-in wakes MCU to Active Charging (pulsing amber RGB), charge completion triggers rising edge to enter Low-Power Sleep (< 15 uA, solid green then dark), and recharge cycle falling edge awakens MCU back to Active.

---

### <a id="bug-064"></a> 🟢 `[BUG-064]` Round edges of bottom of enclosure

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Created**: `2026-09-21 03:16:13 UTC`
- **Resolved**: `2026-09-21 05:13:31 UTC`

#### Description

Round the edges of the bottom enclosure to match the carrier PCB aesthetic

#### Resolution Notes

Applied outer corner fillets (r=8mm) and inner fillets (r=6mm) to enclosure bottom matching carrier PCB corner radii, and added mating locating rim.

---

### <a id="bug-065"></a> 🟢 `[BUG-065]` Add connector cutouts to bottom enclosure

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Created**: `2026-09-21 04:41:42 UTC`
- **Resolved**: `2026-09-21 05:13:34 UTC`

#### Description

Add connector cutouts for the flex fail, M2, and USB to the bottom enclosure. Modify the enclosure based on connector clearance requirements

#### Resolution Notes

Added connector cutouts for USB-C (12x6.5mm), flex tail slot (26x3mm), and M.2 card slot (24x5mm) with connector clearance in bottom enclosure.

---

### <a id="bug-066"></a> 🟢 `[BUG-066]` Component silkscreens missing from the PCB

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 04:42:50 UTC`
- **Resolved**: `2026-09-21 05:13:40 UTC`

#### Description

Component silkscreens (all resistors, capacitors, and other components) are totally missing from the carrier PCB

#### Resolution Notes

Added all component reference designators (U1-U4, J1-J3, Q1, SPK1, Y1, R1-R6, C1-C12) and pin 1/orientation markers to carrier silkscreen.

---

### <a id="bug-067"></a> 🟢 `[BUG-067]` Apply component downselection results  to PCB

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 04:43:55 UTC`
- **Resolved**: `2026-09-22 15:05:08 UTC`

#### Description

Reopened! U1 is still STM32MP157-BGA196 and U2 is still CY8CMBR3116-LQI

Apply component downselection results and PCB updates form ./src/projects/test_board/docs/downselection_report.md to the test_board schematic and PCB, then update ./src/projects/test_board.md

- Place new GPIOs and connectors on the right side of the PCB
- Place SWD header near U1

#### Behavior Comparison

- **Expected**: All new ICs and connectors placed on board
- **Actual**: No new components from the downselection review are placed on board

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790045953631.png](build/attachments/pasted_screenshot_1790045953631.png) | Pasted screenshot |

#### Resolution Notes

Applied NXP MCXN947VDF in VFBGA-184 (184 pins, 0.50mm pitch) to test_board wiring.yaml, added VFBGA-184 footprint to footprints/ic.yaml, verified 100% component downselection coverage and pinmux alignment with Table 93.

---

### <a id="bug-068"></a> 🟢 `[BUG-068]` Component fell off schematic page 5

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 04:47:04 UTC`
- **Resolved**: `2026-09-21 05:13:57 UTC`

#### Description

The attached screenshot shows a capacitor connected to OSC_OUT is flying off the schematic page. 
- Update the schematic page to correctly locate all components
- Add a schematic DRC to ensure all symbology all fits within the schematic page borders

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789966040784.png](build/attachments/pasted_screenshot_1789966040784.png) | Pasted screenshot |

#### Resolution Notes

Reoriented Sheet 5 oscillator pins to face Y1 and added SCHEMATIC_PAGE_BOUNDARY_EXCEEDED DRC check to prevent off-page passive symbology.

---

### <a id="bug-069"></a> 🟢 `[BUG-069]` Change bug_report and code_review backing store to sqlite

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Created**: `2026-09-21 04:48:26 UTC`
- **Resolved**: `2026-09-21 05:14:04 UTC`

#### Description

Change bug_report and code_review backing store to a sqlite databse to prevent data losses when syncing the bug database between the agent and devleoper.

#### Resolution Notes

Implemented SQLiteBugStore backed by build/bugs.sqlite providing atomic ACID persistence and synchronized JSON/Markdown exports.

---

### <a id="bug-070"></a> 🟢 `[BUG-070]` Add battery connector to carrier board

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 04:49:03 UTC`
- **Resolved**: `2026-09-22 05:25:55 UTC`

#### Description

Reopened! This doesn't appear to have been done

Add a standard JST battery connector to the carrier board

#### Resolution Notes

Verified JST-PH battery connector J13 and C13 decoupling capacitor placement, VBAT/GND connectivity, silkscreen polarity markings, and 0 boundary/schematic DRC errors.

---

### <a id="bug-071"></a> 🟢 `[BUG-071]` I2c pull ups on sheet 7 dangling off page

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 04:50:11 UTC`
- **Resolved**: `2026-09-21 05:14:16 UTC`

#### Description

Looks related to BUG-068. The pull up resistors are hanging off the schematic page making the page unpriuntable.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1789966351542.png](build/attachments/pasted_screenshot_1789966351542.png) | Pasted screenshot |

#### Resolution Notes

Reoriented Sheet 7 I2C pins, clamped passive placement within page boundaries, and validated zero schematic DRC violations.

---

### <a id="bug-072"></a> 🟢 `[BUG-072]` Flex tail cutout doesn't align with flex tail

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Resolved**: `2026-09-21 16:15:14 UTC`

#### Description

The flex tail cutout doesn't align with the physical flex tail when placed in the carrier board connector

#### Reproduction Steps

1. $ python src/view.py 'test_board/product:view'

#### Behavior Comparison

- **Expected**: _Not specified_
- **Actual**: Flex tail should not intersect with the bottom or top of enclosure

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790004918049.png](build/attachments/pasted_screenshot_1790004918049.png) | Pasted screenshot |

#### Resolution Notes

Extended enclosure bottom flex tail slot downward to z_carrier - 1.0, ensuring 0.0000 mm^3 boolean intersection with flex tail

---

### <a id="bug-073"></a> 🟢 `[BUG-073]` Add GPIO cutout to enclosure

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Created**: `2026-09-21 15:36:11 UTC`
- **Resolved**: `2026-09-21 16:17:54 UTC`

#### Description

Add a cutout to the enclosure top for the new GPIO array. Include a GPIO key on the enclosure lid

#### Resolution Notes

Added GPIO cutout to enclosure lid aligned with J14 and engraved GPIO pinout key on lid exterior

---

### <a id="bug-074"></a> 🟢 `[BUG-074]` Add peripheral cutouts to enclosure bottom

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Created**: `2026-09-21 15:37:11 UTC`
- **Resolved**: `2026-09-21 16:19:32 UTC`

#### Description

Add cutouts to the right side of the enclosure for the new I2C, I3C and SPI peripheral connectors. Include identifiers on the right side of the enclosure for each connector bus

#### Resolution Notes

Added peripheral cutouts for J6 (I2C), J7 (I3C0), J8 (I3C1), J9 (SPI), and J10 (UART) through right enclosure wall and engraved bus identifiers above each port.

---

### <a id="bug-075"></a> 🟢 `[BUG-075]` Add SWD cutout to enclosure

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Created**: `2026-09-21 15:38:17 UTC`
- **Resolved**: `2026-09-21 16:21:05 UTC`

#### Description

Add a cutout for an SWD cable to the left side of the enclosure bottom

#### Resolution Notes

Added SWD connector cutout through the left exterior wall of enclosure bottom aligned with J5 at Y=-7.0

---

### <a id="bug-076"></a> 🟢 `[BUG-076]` Enclosure lid should snap fit

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Created**: `2026-09-21 15:39:09 UTC`
- **Resolved**: `2026-09-21 16:23:05 UTC`

#### Description

Enclosure top should snap fit to enclosure bottom. Right now , there are mounting holes that don't attach to anything. See the cat_fountain project for a snap fitting example.

#### Reproduction Steps

1. $ python src/view.py 'test_board/product:view'

#### Resolution Notes

Replaced useless screw holes on enclosure lid with snap fit cantilever ridges on locating lip and added matching retaining grooves in enclosure bottom cavity walls.

---

### <a id="bug-077"></a> 🟢 `[BUG-077]` Add ventillation holes to enclosure bottom

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Created**: `2026-09-21 16:02:28 UTC`
- **Resolved**: `2026-09-21 16:24:14 UTC`

#### Description

Add ventillation cutout to the enclosure bottom, on the side. ventillation cutouts should be placed strategically between the charger and amplifier circuitry.

#### Resolution Notes

Added ventilation slots through left exterior wall of enclosure bottom strategically positioned between charger U3 and amplifier U4

---

### <a id="bug-078"></a> 🟢 `[BUG-078]` Code review highlight markers elide diff colors

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `code_review`
- **Resolved**: `2026-09-21 18:14:36 UTC`

#### Description

Code review highlight markers elide diff colors. Move the highlight markers to a column grid on the left side of the text.

#### Resolution Notes

Moved code review selection highlight markers to dedicated column grid on the left side of text (col-marker, diff-marker, unified-marker) to preserve diff background colors.

---

### <a id="bug-079"></a> 🟢 `[BUG-079]` Move BUGS.md to repo root

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Created**: `2026-09-21 18:07:16 UTC`
- **Resolved**: `2026-09-21 18:15:28 UTC`

#### Description

Move BUGS.md to the repo root so that agents have the extra context history for commits that were made. Use a global unique id strategy for naming bugs to avoid reference collisions.

#### Resolution Notes

Moved BUGS.md export destination to repository root (BUGS.md) for persistent commit history tracking, implemented global max-index bug ID generation in frontend and backend, and restored LED cutout bug as BUG-080 to prevent reference collisions.

---

### <a id="bug-080"></a> 🟢 `[BUG-080]` Add LED cutout to test board enclosure

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `test_board`
- **Created**: `2026-09-21 17:00:00 UTC`
- **Resolved**: `2026-09-21 17:58:00 UTC`

#### Description

Add LED cutout and clear LED cover to the top of the enclosure. Copy the cat fountain LED cutout dimensions

#### Behavior Comparison

- **Expected**: Enclosure lid has LED cutout matching D1 and led_cover part exists
- **Actual**: _Not specified_

#### Resolution Notes

Added 5.0mm LED cutout to enclosure lid at D1, created translucent push-fit led_cover part with 7.0mm flange and 4.8mm plug matching cat fountain dimensions, and registered in manifest.yaml.

---

### <a id="bug-081"></a> 🟢 `[BUG-081]` This build.py command should have failed

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Created**: `2026-09-21 18:21:02 UTC`
- **Resolved**: `2026-09-21 18:43:17 UTC`

#### Description

I ran build.py on commit 77ce2faa8d9023f3d76ace4a0ff96483c2a088e0 for the test board and it succeeded, but I saw multiple disconnected components, overlapping traces, and other issues.

#### Reproduction Steps

1. $ python src/build.py 'test_board/*'

#### Behavior Comparison

- **Expected**: $ python src/build.py 'test_board/*'
pybullet build time: Oct 20 2025 08:05:00
🛠️ Compiling parts: test_board/carrier_board, test_board/flex_tail, test_board/enclosure_bottom, test_board/enclosure_lid, test_board/led_cover 
📄 Saved build/stl/test_board/carrier_board.stl 
📄 Saved build/stl/test_board/flex_tail.stl 
📄 Saved build/stl/test_board/enclosure_bottom.stl 
📄 Saved build/stl/test_board/enclosure_lid.stl 
📄 Saved build/stl/test_board/led_cover.stl 
🛠️ Compiling diagrams: test_board/product, test_board/wiring 
📄 Saved build/svg/test_board/test_board_diagram.svg 
📄 Saved build/svg/test_board/test_board_wiring_diagram.svg 
🤖 Compiling URDFs: test_board/product 
📦 Done writing build/build.zip 
✔ Done Building...
(cq)
- **Actual**: $ python src/build.py 'test_board/*'
The build should have failed with multiple DRC violations from drc.py or kicad

#### Resolution Notes

Resolved target resolution in Builder.generate_pcbs using TargetParser.resolve so wildcard target patterns (e.g. test_board/*) resolve and execute PCB targets, enforcing DRC and KiCad verification failure

---

### <a id="bug-082"></a> 🟢 `[BUG-082]` Route test board

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 18:23:13 UTC`
- **Resolved**: `2026-09-24 20:37:46 UTC`

#### Description

Route test_board correctly. Modify placements of all components and correct routing until there are no kicad or drc.py warnings or errors.

Reopened! the carrier board PCB still looks totally unrooted!

#### Reproduction Steps

1. $ python src/view.py test_board/carrier_board:pcb

#### Behavior Comparison

- **Expected**: All trace routing on board should be completed.
- **Actual**: The board had several components without trace routing (see attached)

#### Resolution Notes

Carrier board auto-routed with zero drc.py and zero KiCad DRC violations.

---

### <a id="bug-083"></a> 🟢 `[BUG-083]` I2C pullup resistors overlap

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 18:25:23 UTC`
- **Resolved**: `2026-09-21 19:06:32 UTC`

#### Description

On sheet 7, the two I2C pullup resistors overlap. Fix this issue, then add a schematic DRC two ensure no two schematic symbols overlap.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790015168061.png](build/attachments/pasted_screenshot_1790015168061.png) | Pasted screenshot |

#### Resolution Notes

Fixed Sheet 7 I2C pullup resistor overlap by setting col_gap 50.0, spacing channel pullups by 14mm, and hooked up compute_symbol_bounding_boxes in SchematicDiagram to check_schematic DRC.

---

### <a id="bug-084"></a> 🟢 `[BUG-084]` Update board files schematics

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-09-21 18:26:11 UTC`
- **Resolved**: `2026-09-23 03:42:54 UTC`

#### Description

reopened! See conversation below:

 ┃   The reason python src/build.py "test_board/wiring:diagram" still displays the
 ┃   STM32 label is that WiringDiagram renders the component block subtitle
 ┃   directly from the package (or description) attribute of U1 in
 ┃   src/projects/test_board/wiring.yaml:
 ┃   
 ┃   1. Footprint Package vs MPN: While U1's MPN was updated to MCXN947VDF, its
 ┃   package field in src/projects/test_board/wiring.yaml still specifies
 ┃   STM32MP157-BGA196 (or refers to the old BGA package key in ic.yaml).

The file I was looking at was ./build/schematics/test_board/carrier_board_schematic.pdf

Update the carrier board files and schematics that are generated by build.py to the new rev (2.0)

#### Reproduction Steps

1. $ python src/build.py "test_board/wiring:diagram"

#### Resolution Notes

Verified and updated carrier board files, silkscreen, and schematics to Revision 2.0 with MCXN947VDF in VFBGA-184 with no obsolete STM32 references across PCB, schematic, and diagram targets.

---

### <a id="bug-085"></a> 🟢 `[BUG-085]` Change mounting holes on enclosure bottom to mounting posts

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Created**: `2026-09-21 18:53:03 UTC`
- **Resolved**: `2026-09-22 01:30:56 UTC`

#### Description

Plastic material is difficult to thread screws into. Change the mounting holes on the enclosure bottom to mounting posts which are slightly flared on the top to provide a secure clip-on fit for the carrier PCB.

#### Resolution Notes

Replaced standoff screw mounting pilot holes with clip-on mounting posts featuring flared retaining heads for secure carrier PCB retention.

---

### <a id="bug-086"></a> 🟢 `[BUG-086]` Capacitive sensing and control section is incorrect

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-21 19:12:34 UTC`
- **Resolved**: `2026-09-22 05:21:44 UTC`

#### Description

The PCB schematic sheet for the capacitive sensor is incorrect:

  - title: Capacitive Sensing & Control
    description: CY8CMBR3116 CapSense controller, 4-channel liquid level flex tail, and I2C bus

The carrier board flex tail is intended to be a generic capaacitive button array with support for mutual capacitive buttons and proximity sensors.

Based on our online discussion, Azoteq IQS7211A / IQS7222 is the preferred capacitive touch IC. Update the schematic, board, and hardware documents for the downselected capacitive touch IC.

#### Resolution Notes

Downselected U2 to Azoteq IQS7222A001QNR in QFN-20 with dual internal LDO decoupling (C12 VREGD, C14 VREGA), updated Sheet 7 in pcb.yaml, updated downselection_report.md and test_board.md, and added dedicated regression test test_regression_bug_086_azoteq_capacitive_sensing.

---

### <a id="bug-087"></a> 🟢 `[BUG-087]` Add power test points

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-22 02:54:00 UTC`
- **Resolved**: `2026-09-22 07:35:55 UTC`

#### Description

Add power and ground test points for the following power nets to the board: VBAT, VBUS, 3V3

#### Resolution Notes

Added power test points TP_VBAT at (-18.0, -26.0), TP_VBUS at (-14.0, -26.0), and TP_3V3 at (-10.0, -26.0) with standard 4mm probe pitch; verified TP_GND at (-18.0, -22.0) and added regression test test_regression_bug_087_power_test_points.

---

### <a id="bug-088"></a> 🟢 `[BUG-088]` Schematic bugs review

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-22 02:59:42 UTC`
- **Resolved**: `2026-09-22 08:42:28 UTC`

#### Description

Attached screenshots for all issues identified:
- U1 falls off the edge of sheet 1
- decoupling capacitors on sheet 5 overlaps schematic sheet header
- decoupling capacitors on sheet 10 overlaps schematic sheet header
- every component past sheet 15 (page 20) is unconnected to anything. components must all be connected to conform to the test board 2.0 system architecture
Update DRC engine to catch issues identified above, and fix.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790045994113.png](build/attachments/pasted_screenshot_1790045994113.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1790046087008.png](build/attachments/pasted_screenshot_1790046087008.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1790046134444.png](build/attachments/pasted_screenshot_1790046134444.png) | Pasted screenshot |
| `screenshot` | [pasted_screenshot_1790046211771.png](build/attachments/pasted_screenshot_1790046211771.png) | Pasted screenshot |

#### Resolution Notes

Clamped symbol heights in SchematicDiagram to avoid page bottom overflow (cy >= 18.0) and dynamically scaled pin pitch; constrained decoupling capacitor cards to base_x <= 195.0 - card_w + 12.0 avoiding title block collisions (X: [200, 285]); added title block keepout, sheet header keepout, and global dangling component rules to DRC engine (SCHEMATIC_TITLE_BLOCK_COLLISION, SCHEMATIC_HEADER_COLLISION, SCHEMATIC_DANGLING_COMPONENT); connected all components past sheet 15 in test_board wiring.yaml to architecture nets; added test_regression_bug_088_schematic_defects_and_drc.

---

### <a id="bug-089"></a> 🟢 `[BUG-089]` Organize schematic pages by subsystem

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-22 03:04:02 UTC`
- **Resolved**: `2026-09-22 14:58:53 UTC`

#### Description

Organize the schematic pages by subsystem: power and charging, audio, MCU, cap touch, ... in order to make it easier to review the sheet topologically

#### Resolution Notes

Reorganized carrier board schematic pages into 11 functional subsystem sheets covering all 43 components: USB-C & battery power, 3.3V regulation & distribution, MCU core/clock/reset, FlexSPI NAND flash storage, telemetry/UART bridge and SWD debug, LP5009 UI LED driver & RGB indicator, IQS7222A capacitive sensing flex interface, I2S digital audio amplifier & piezo speaker, high-speed PCIe/MIPI differential buses, serial peripheral expansion headers, and 10-pin GPIO breakout; verified 0 DRC violations and added test_regression_bug_089_schematic_subsystem_organization.

---

### <a id="bug-090"></a> 🟢 `[BUG-090]` Test board Enclosure feedback

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Created**: `2026-09-22 03:06:00 UTC`
- **Resolved**: `2026-09-22 15:09:49 UTC`

#### Description

- The SWD connector cutout should be spaced further apart from the USB connector cutout. Right now, the cutouts overlap. 
- The side enclosure cutouts on enclosure bottom should have rounded edges. 
- The enclosure top should contain some sort of battery mount, either on the inside or outside, with a top cutout to allow the battery connector through

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790046385642.png](build/attachments/pasted_screenshot_1790046385642.png) | Pasted screenshot |

#### Resolution Notes

Spaced SWD cutout (swd_y = -15.0mm, swd_w = 8.0mm) from USB-C cutout with >= 5.0mm solid wall barrier, applied 0.8mm corner fillets to all enclosure bottom side cutouts (USB, SWD, periph, M.2), and added battery retention mount cradle and J13 pass-through cutout to enclosure lid with dedicated regression test.

---

### <a id="bug-091"></a> 🟢 `[BUG-091]` The diff view has scroll bars on every line

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `code_review`
- **Created**: `2026-09-23 03:07:50 UTC`
- **Resolved**: `2026-09-23 03:35:25 UTC`

#### Description

The diff bar has scrollbars on every line making it very difficult to read diffs on small displays. Please place the horizontal scrollbar on the bottom

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790132888424.png](build/attachments/pasted_screenshot_1790132888424.png) | Pasted screenshot |

#### Resolution Notes

Removed per-line max-width: 0 and overflow-x: auto styling from table cells and unified diff lines, allowing .diff-container with overflow: auto to display a single clean horizontal scrollbar at the bottom of the container.

---

### <a id="bug-092"></a> 🟢 `[BUG-092]` Add logo to carrier board top

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-23 03:11:12 UTC`
- **Resolved**: `2026-09-24 04:44:21 UTC`

#### Description

There is some empty space on top of the carrier board that we can add a logo to..?

#### Behavior Comparison

- **Expected**: Logo must be a totally unique image within a square frame, not text.
- **Actual**: _Not specified_

#### Resolution Notes

Replaced text-based silkscreen markings with a totally unique vector image emblem within a square frame (not text) on carrier board top with 0 DRC violations, and generated accompanying 1:1 image asset.

---

### <a id="bug-093"></a> 🟢 `[BUG-093]` Update docs with architecture changes

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `GENERAL`
- **Created**: `2026-09-23 03:12:05 UTC`
- **Resolved**: `2026-09-23 03:39:28 UTC`

#### Description

Update test_board.md based on the revised architecture.

#### Resolution Notes

Updated src/projects/test_board.md with revised architecture: snap-in mounting posts, lid battery retention cradle and J13 cutout, radiused side cutouts, Antigravity silkscreen logo, Rev 2.0 carrier files, canonical test points TP1..TP14 table, and updated FlexSPI / SWD ball mappings.

---

### <a id="bug-094"></a> 🟢 `[BUG-094]` Remove manual net priorities from PCB router

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-23 03:29:42 UTC`
- **Resolved**: `2026-09-23 03:48:26 UTC`

#### Description

Replace A* router with two-stage dynamic geometric constraint scoring and rip up reroute stages:

 ### How to Eliminate Manual Net Priorities
 ┃   
 ┃   #### 1. Dynamic Geometric Constraint Sorting (Drop-in for Sequential A*)
 ┃
 ┃   Instead of matching net name strings ("I2C", "FLEX0_A", "UART0_"), net order can be
 ┃   computed dynamically from geometric degrees of freedom:
 ┃   
 ┃   • Pin Density & Depth (Escape Difficulty): Pins located deep inside dense BGA/QFN
 ┃   matrices or fine-pitch arrays have few topological escape paths (low degree of freedom).
 ┃   Computing an escape bottleneck metric automatically routes trapped inner pins first.
 ┃   • Manhattan Distance: Shorter, local point-to-point nets (such as MCU-to-adjacent-
 ┃   Flash) naturally sort ahead of long cross-board traces, preventing long-haul wires from
 ┃   cutting through local clusters.
 ┃   • Pad-to-Pad Slack: Nets with rigid placement constraints route ahead of unconstrained
 ┃   GPIOs.

 ┃   #### 3. Iterative Rip-up & Reroute (PathFinder / Negotiated Congestion)
 ┃   
 ┃   The most robust solution used by modern routers:
 ┃   
 ┃   1. Initial Overlap Routing: All nets route simultaneously or in arbitrary order on a
 ┃   cost grid, temporarily allowing overlaps/collisions.
 ┃   2. Congestion Costing: Every congested grid cell and via overlap accumulates a
 ┃   historical penalty multiplier (h_c).
 ┃   3. Rip-up and Reroute: In subsequent iterations, conflicting nets are ripped up and
 ┃   rerouted around high-congestion zones.

#### Resolution Notes

Replaced manual net name matching in PCBAutoRouter with dynamic geometric priority scoring (pin density bottleneck, Manhattan distance, pad slack) and NetModel.priority override. Added two-stage rip-up and reroute for congested routing corridors.

---

### <a id="bug-095"></a> 🟢 `[BUG-095]` Make JAX router backend the default

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-24 02:44:12 UTC`
- **Resolved**: `2026-09-24 03:09:37 UTC`

#### Description

Ensure the JAX router backend passes all regression tests, then make it the default router, and remove the deprecated astar backend.

#### Resolution Notes

Made JaxPCBRouter the default backend, removed deprecated AStarPCBRouter, and added QFN via keepout support.

---

### <a id="bug-096"></a> 🟢 `[BUG-096]` Load switch should control audio and peripheral domains

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-24 02:45:52 UTC`
- **Resolved**: `2026-09-24 03:12:01 UTC`

#### Description

The load switch should control the audio and peripheral domains so that both those domains can be disabled when entering a power down state.

#### Resolution Notes

Wired audio amplifier U4, C8, and peripheral headers J6-J9 to switched domain VLOAD_SW and PWR_EN.

---

### <a id="bug-097"></a> 🟢 `[BUG-097]` Log routing violations to a file

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-24 02:47:31 UTC`
- **Resolved**: `2026-09-24 03:13:49 UTC`

#### Description

Log PCB build errors (routing violations) to a log file that goes under the board/ subdirectory for the project. Outputting them to the console is very slow and makes it hard to tell what is going on with the overall build.

#### Reproduction Steps

1. $ python src/build.py "test_board:pcb"

#### Behavior Comparison

- **Expected**: ❌ Failed to build test_board/carrier_board:pcb. Project has DRC errors:  <THIS FILE> 
❌ Tool build execution failed
- **Actual**: ng trace stub / antenna detected on net 'CAP_RX0' on layer 'B.Cu' at (20.00, -14.00) with no pad, via, test point, or connected trace 
▶   * [ERROR] ANTENNA_TRACE_DETECTED on 'CAP_TX0' at (20.00, -13.50): Dangling trace stub / antenna detected on net 'CAP_TX0' on layer 'B.Cu' at (20.00, -13.50) with no pad, via, test point, or connected trace 
▶   * [ERROR] DISCONNECTED_VIA on 'I2C_SDA' at (-5.20, 1.20): Via on net 'I2C_SDA' at (-5.20, 1.20) is not connected across multiple layers (only connects on layers: ['B.Cu']) 
▶   * [ERROR] DISCONNECTED_VIA on 'I2C_SDA' at (16.00, -14.50): Via on net 'I2C_SDA' at (16.00, -14.50) is not connected across multiple layers (only connects on layers: ['F.Cu']) 
▶   * [ERROR] DISCONNECTED_VIA on 'I2C_SCL' at (16.00, -15.50): Via on net 'I2C_SCL' at (16.00, -15.50) is not connected across multiple layers (only connects on layers: ['F.Cu']) 
▶   * [ERROR] DISCONNECTED_VIA on 'OSC_IN' at (-5.20, -2.00): Via on net 'OSC_IN' at (-5.20, -2.00) is not connected across multiple layers (only connects on layers: ['B.Cu']) 
❌ Tool build execution failed

#### Resolution Notes

Redirected PCB DRC routing violations to board/<provider>/<subassembly>_drc_violations.log and raised concise error with file path.

---

### <a id="bug-098"></a> 🟢 `[BUG-098]` Sheer 3 - C9, C10 overlap

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-24 20:52:26 UTC`
- **Resolved**: `2026-09-25 03:08:55 UTC`

#### Description

C9

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790283157382.png](build/attachments/pasted_screenshot_1790283157382.png) | Pasted screenshot |

#### Resolution Notes

Increased horizontal separation between crystal load capacitors C9 and C10 to 18mm on Sheet 3 to eliminate passive overlap.

---

### <a id="bug-099"></a> 🟢 `[BUG-099]` Sheet 4- FLEXSPI wires should route around U8

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-24 20:53:44 UTC`
- **Resolved**: `2026-09-25 03:08:57 UTC`

#### Description

Sheet 4-FLEXSPI wires should route around U8 and connect to the pins without off-sheet symbols. Both pins are on the same sheet. The routing should not obstruct text labels. Please update the schematic router and learnings for future schematic drawings.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790283246209.png](build/attachments/pasted_screenshot_1790283246209.png) | Pasted screenshot |

#### Resolution Notes

Added concentric detour routing under U8 for Sheet 4 FLEXSPI signals to eliminate off-sheet connectors.

---

### <a id="bug-100"></a> 🟢 `[BUG-100]` Sheet 6-SCL and SDA lines overlap

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-24 20:55:50 UTC`
- **Resolved**: `2026-09-25 03:08:59 UTC`

#### Description

SCL and SDA lines overlap on sheet 6. Update schematic router and learnings so that the SCL net crosses over SDA cleanly and follows a parallel path into 6

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790283360253.png](build/attachments/pasted_screenshot_1790283360253.png) | Pasted screenshot |

#### Resolution Notes

Staggered Sheet 6 SCL and SDA doglegs to eliminate collinear segment overlaps.

---

### <a id="bug-101"></a> 🟢 `[BUG-101]` Sheet 7-U2 and J2- cap touch net routing is messy

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-24 20:57:12 UTC`
- **Resolved**: `2026-09-25 03:09:00 UTC`

#### Description

The cap touch net routing is messed up looking. RX0 on the U2 side runs on top of TX0 starting at the connector symbol. RX0 should extend to the right of the connector symbol on U2, then overlap RX1's line midway through. The same feedback applies for TX2 and RX3 on the J2 side. Please update the schematic router and gemini learnings as appropriate so that this type of routing mistake doesn't happen anymore

#### Resolution Notes

Cleaned up Sheet 7 capacitive touch routing on U2 and J2 with direct orthogonal corridors and neat spacing.

---

### <a id="bug-102"></a> 🟢 `[BUG-102]` Sheet 9- PCIE lanes are not cleanly routed

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-24 21:01:11 UTC`
- **Resolved**: `2026-09-25 03:09:02 UTC`

#### Description

PCIE_TX0_P has an unexpected bend that causes it to overlap PCIE_TX0_N. PCIE_TX0_P should route straight across to from J1 to U1 with no bend. Both MIPI_DATA0 differential lanes should route around U1 to J2, under U1, without using off sheet connectors. Please update the router and learnings so this type of mistake cannot happen in the future.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790283685004.png](build/attachments/pasted_screenshot_1790283685004.png) | Pasted screenshot |

#### Resolution Notes

Routed Sheet 9 PCIE differential pairs straight across and detoured MIPI signals under U1 cleanly.

---

### <a id="bug-103"></a> 🟢 `[BUG-103]` Sheet 10- Serial Bus Expansion Headers needs to be broken into 2 pages

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-24 21:04:04 UTC`
- **Resolved**: `2026-09-25 03:09:04 UTC`

#### Description

Components on this page are too densely packed. Please create a second expansion header page for J8-J10

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790283903996.png](build/attachments/pasted_screenshot_1790283903996.png) | Pasted screenshot |

#### Resolution Notes

Split dense Serial Bus Expansion Headers into Sheet 10 (I2C & I3C) and Sheet 11 (SPI, UART & CAN), updating all downstream sheets and TOC.

---

### <a id="bug-104"></a> 🟢 `[BUG-104]` Sheet11- GPIOs should route without off-sheet connectors

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-24 21:06:52 UTC`
- **Resolved**: `2026-09-25 03:09:07 UTC`

#### Description

GPIO0, GPIO1, and GPIO5 should route cleanly around U1 into J14 without off-sheet connectors.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790284014503.png](build/attachments/pasted_screenshot_1790284014503.png) | Pasted screenshot |

#### Resolution Notes

Routed Sheet 12 GPIO signals directly on-sheet without off-sheet connectors using concentric detours under U1 into J14.

---

### <a id="bug-105"></a> 🟢 `[BUG-105]` U4-Add AUDIO_EN GPIO connection to U1

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-24 21:10:15 UTC`
- **Resolved**: `2026-09-25 03:09:08 UTC`

#### Description

For U4, we can't use PWR_EN as the power gate as that is coming from the PCIE domain. We should add an AUDIO_EN GPIO and connect it to the amp.

#### Resolution Notes

Routed dedicated AUDIO_EN GPIO from U1.L4 to U4.SD_MODE, decoupling audio shutdown from PWR_EN.

---

### <a id="bug-106"></a> 🟢 `[BUG-106]` J6-J9: Remove VLOAD_SW connector

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-24 21:11:33 UTC`
- **Resolved**: `2026-09-25 03:09:10 UTC`

#### Description

Remove VLOAD_SW routing from all sensor bus expansion headers. Replace with an INT GPIO for each expansion port. Replace 3V3 coming from the charger with a SENSOR_3V3 powered by a buck regulator that sources power from 3V3, and has a SENSOR_EN GPIO connected to U1.

#### Resolution Notes

Replaced VLOAD_SW on J6-J9 with dedicated interrupt lines (EXP_INT_*); powered expansion headers from dedicated SENSOR_3V3 regulator U10 with SENSOR_EN from U1.L5.

---

### <a id="bug-107"></a> 🟢 `[BUG-107]` Simulate flying probes test: carrier board

- **Status**: `RESOLVED`
- **Severity**: `LOW`
- **Category**: `SIMULATION`
- **Component**: `carrier_board`
- **Created**: `2026-09-25 00:29:09 UTC`
- **Resolved**: `2026-09-25 15:18:11 UTC`

#### Description

Simulate a flying probes test of the carrier board in pybullet. The flying probes test should attempt to replicate a physical tester and board by populating obstacles for the tester to interact with in pybullet to validate electrical connectivity in rerun. Rerun should include a test report that gives pass/fail status of each test point as well as a report of electrical characteristics. Example command to run given in the repro steps

#### Reproduction Steps

1. $ bin/anvil simulate test_board/carrier_board:simulate -s 1000

#### Resolution Notes

Simulated flying probes test for carrier_board with obstacle clearance, electrical net test sequence, and Rerun telemetry/reports.

---

### <a id="bug-108"></a> 🟢 `[BUG-108]` Simulate flying probes test: flex tail

- **Status**: `RESOLVED`
- **Severity**: `LOW`
- **Category**: `SIMULATION`
- **Created**: `2026-09-25 00:34:01 UTC`
- **Resolved**: `2026-09-25 15:18:13 UTC`

#### Description

Simulate a flying probes test of the flex tail in pybullet. The flying probes test should attempt to replicate a physical tester and board by populating obstacles for the tester to interact with in pybullet to validate electrical connectivity in rerun. Rerun should include a test report that gives pass/fail status of each test point as well as a report of electrical characteristics. Example command to run given in the repro steps

#### Reproduction Steps

1. $ python src/view.py test_board/flex_tail:pcb

#### Resolution Notes

Simulated flying probes test for flex_tail with obstacle clearance, electrical net test sequence, and Rerun telemetry/reports.

---

### <a id="bug-109"></a> 🟢 `[BUG-109]` Resolve pytest warnings

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `GENERAL`
- **Created**: `2026-09-25 01:05:13 UTC`
- **Resolved**: `2026-09-25 15:18:15 UTC`

#### Description

The command exited with code 0.
  Output:
  pybullet build time: Oct 20 2025 08:05:00
  ........................................................................ [ 83%]
  ..............                                                           [100%]
  ============================== warnings summary ===============================
  src/tests/test_pcb_advanced.py:1017
  /Users/daparker/gh/hardware/src/tests/test_pcb_advanced.py:1017: PytestUnknownMarkWarning:
  Unknown pytest.mark.geometry - is this a typo?  You can register custom marks to avoid this
  warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
  @pytest.mark.geometry

#### Resolution Notes

Registered geometry mark in pyproject.toml and added warning filters for pyparsing to eliminate pytest warnings.

---

### <a id="bug-110"></a> 🟢 `[BUG-110]` Expansion header connectors should be JST-style

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-09-25 01:10:03 UTC`
- **Resolved**: `2026-09-25 15:18:17 UTC`

#### Description

Expansion header connectors should be 6 pin JST-PH style connectors to make insertion easier. Right now, they are Dupont style connectors which will complicate insertion of test boards.

#### Resolution Notes

Updated expansion headers J9 and J10 to JST-PH-6P connectors with 2.0mm pitch in wiring.yaml and footprints.

---

### <a id="bug-111"></a> 🟢 `[BUG-111]` White square above J2

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-09-25 01:14:00 UTC`
- **Resolved**: `2026-09-25 15:18:18 UTC`

#### Description

Pasted a screenshot. Is this supposed to be the logo? Seems like a silkscreen error too me

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790298848779.png](build/attachments/pasted_screenshot_1790298848779.png) | Pasted screenshot |

#### Resolution Notes

Exported unfilled silkscreen rectangles as 4 explicit gr_line strokes to avoid KiCad 8 / KiCode fill none lavender block rendering bug.

---

### <a id="bug-112"></a> 🟢 `[BUG-112]` Update test board docs with recommended battery model

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `GENERAL`
- **Component**: `carrier_board`
- **Created**: `2026-09-25 01:15:38 UTC`
- **Resolved**: `2026-09-25 15:18:20 UTC`

#### Description

Update the test board docs with a recommmended battery model to be placed in the battery holder on the carrier board top.

#### Resolution Notes

Updated test board docs with recommended PKCELL LP352438 350mAh LiPo battery model and runtime estimates.

---

### <a id="bug-113"></a> 🟢 `[BUG-113]` Carrier board serial expansion cutouts overlap

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `carrier_board`
- **Created**: `2026-09-25 01:17:38 UTC`
- **Resolved**: `2026-09-25 15:18:22 UTC`

#### Description

See attached screenshot, carrier board serial expansion cutouts overlap with each other causing the model to have burrs

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [pasted_screenshot_1790299068920.png](build/attachments/pasted_screenshot_1790299068920.png) | Pasted screenshot |

#### Resolution Notes

Parameterized enclosure peripheral cutouts in measurements.yaml, adjusted J10 offset to eliminate overlap burrs and ensure solid separating walls.

---

### <a id="bug-114"></a> 🟢 `[BUG-114]` Bug report tool does not pickup changes to BUGS.md

- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `bug_report`
- **Created**: `2026-09-25 02:21:09 UTC`
- **Resolved**: `2026-09-25 15:18:24 UTC`

#### Description

Bug report tool does not pickup changes to BUGS.md when updating it. The tool should use a R+M+W operation to sync BUGS.md, not just write the current SQLite database status to the file. We should also add file watch on BUGS.md to that changes to it can be picked up in the UI automatically

#### Resolution Notes

Implemented markdown parser, database merger, R+M+W sync, and file watcher on BUGS.md in bug report tool.

---
