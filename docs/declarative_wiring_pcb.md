# Declarative Wiring & PCB Engine

Guidelines for schematic capture, routing engines, DRC checks, headless KiCad toolchains, and firmware co-design.

## 1. Declarative Pipeline & Toolchain
* **Pipeline Architecture**: The PCB engine follows a strict declarative pipeline:
  `pcb_materials.yaml imports -> manifest.yaml -> .kicad_pcb / .kicad_sch targets -> kicad_cli -> board and schematic files`.
* **Headless CAM Generation**: Manufacturing board files (RS-274X Gerbers, Excellon NC drills, Gerber job files) must be generated strictly via headless `kicad-cli` (`KiCadCLI`), not custom DIY string formatting.
* **Pre-Computed Route Persistence**: PCB viewing workflows (`view.py`) and standard artifact generation MUST consume pre-computed, persisted routing artifacts (`routing.yaml`, `routing_flex.yaml`) rather than invoking the A* auto-router on the fly. Auto-routing is an explicit orchestration action performed via `python src/config.py '<target>'`.

## 2. Component Scoping & Canonical Reference Designators
* **Subassembly Footprint Scoping**: Multi-board and rigid-flex assemblies must scope footprints, passives, and connectors explicitly to target subassemblies (via `shape_ref: carrier_board` or `shape_ref: flex_tail`). Never duplicate components across subassemblies or rely on hardcoded component names for footprint queries.
* **Canonical Reference Designators**: All components across PCB designs, schematics, netlists, manifests, and BOMs MUST adhere to standard canonical reference designators using single-letter type prefixes followed by sequential digits:
  - `Rn`: Resistors (`R1`, `R2`, `R3`, ...)
  - `Cn`: Capacitors (`C1`, `C2`, `C3`, ...)
  - `Dn`: Diodes (`D1`, `D2`, ...)
  - `Qn`: Transistors and FETs (`Q1`, `Q2`, ...)
  - `Yn`: Crystals and resonators (`Y1`, `Y2`, ...)
  - `Jn`: Connectors, receptacles, and headers (`J1`, `J2`, `J3`, `J4`, ...)
  - `Un`: Integrated circuits (ICs) and transducers (`U1`, `U2`, `U3`, `U4`, `U5`, ...)
  - `TPn`: Test points (`TP1`, `TP2`, `TP3`, `TP4`, ...)
  Never use ad-hoc descriptive names (such as `J_USB`, `J_FLEX`, `SPK1`, `C_IN`, `C_AMP`, `R_CC1`, `R_BOOT`, `TP_GND`, `TP_SDA`) in production footprints, netlists, or schematic sheet models.

## 3. PCB Routing & DRC Invariants
* **Planar Flex Routing**: Flexible PCB tails and ribbons must maintain planar single-layer routing without trace crossovers, ensure non-overlapping capacitive electrode traces with generous keepouts ($\ge 1.5$ mm clearance to flex outline edges), and provide silkscreen channel callouts directly on the substrate.
* **Auto-Router Grid & Clearance Parity**: The PCB A* auto-router and DRC clearance definitions must maintain mathematical parity: trace widths and obstacle expansion margins must ensure adjacent grid corridors do not violate trace-to-trace spacing constraints ($s \ge (w_1 + w_2)/2 + \text{clearance}$). Stitching vias to internal power/ground planes and escape corridors must be generated dynamically from netlist graph topology.
* **Net Escape Prioritization**: In high-density or mixed-signal PCB layouts, local pin-dense escape nets (MCU crystal oscillators, reset lines, boot controls) MUST be scheduled and routed before wide global multi-drop buses (PCIe, MIPI).
* **Edge-Mounted Connector DRC Exemption**: Receptacle connectors intended to mate with external plugs (USB-C, card-edge, FPC sockets) must be permitted to sit flush with or slightly overhang board edges. DRC board boundary containment rules must exempt edge-facing connectors whose bounding center falls within the board outline.
* **Subassembly Netlist Scoping & Antenna Termination**: Multi-subassembly projects sharing a top-level wiring declaration must scope connectivity DRC checks strictly to nets having two or more terminals on the specific subassembly. Antenna/stub detection algorithms must recognize non-pad copper structures (such as capacitive touch electrodes) as valid termination nodes to avoid false positive antenna violations.

## 4. Schematic Router Invariants & Detour Rules
* **No Collinear Overlaps**: Parallel signal wires and dogleg corridor segments must never share collinear coordinates. Staggered doglegs must be sorted directionally (step-down vs step-up) so that vertical transitions occur at distinct coordinates with clean jumper bridge crossings.
* **Corridor Boundary Clearance**: Vertical dogleg corridors must be strictly constrained to the channel interior ($x_v \in [x_{\text{left}} + 10.0, x_{\text{right}} - 10.0]$) to ensure wire stubs extending from component symbols have sufficient clearance and never run on top of connector/IC symbols or pin labels.
* **Channel Passive Spacing**: Shunt and pull-up/pull-down passives residing in the same inter-component channel must be grouped together across overlapping channel spans and spaced with a generous pitch ($\ge 20.0$ mm pitch, minimum separation $\ge 16.0$ mm) to prevent text collisions.
* **Concentric Detour Routing**: On-sheet wire detours around IC footprints must be sorted concentrically by pin coordinates to guarantee nested routing with zero wire crossings and no off-sheet connectors.

## 5. Component Selection & Bare-Metal Firmware Co-Design
* **Target Firmware Environment**: Downstream target execution environment is bare-metal Rust (`no_std`, Embassy asynchronous executor, `embedded-hal` driver abstractions, `defmt` logging, stack-based zero-allocation concurrency).
* **Authoritative Datasheet Grounding**: ALWAYS obtain connector, IC, and peripheral information directly from the official manufacturer documentation archived in `docs/datasheets/`. Never trust third-party summaries or synthetic pin assignments.
* **Programmable Component Qualification**: Active components integrated into designs must meet:
  - Open-source driver code (permissive Rust crate or clean C library).
  - Public, non-confidential datasheet.
  - Comprehensive register maps documenting addresses, bit fields, reset defaults, and initialization sequences.
  - Zero binary blobs or closed-source NDA firmware.
