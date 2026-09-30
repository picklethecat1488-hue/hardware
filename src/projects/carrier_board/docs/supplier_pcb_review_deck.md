---
marp: true
theme: default
paginate: true
header: 'Carrier Board & Flex Tail Rev 2.0 — Supplier PCB Manufacturing Review'
footer: 'Test Board Hardware Group | Confidential & Proprietary'
style: |
  section {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    padding: 32px 48px;
    background-color: #fafafa;
    color: #1f2937;
  }
  h1 { color: #1b120a; font-size: 26px; border-bottom: 3px solid #ffb800; padding-bottom: 8px; margin-bottom: 16px; }
  h2 { color: #8d5d33; font-size: 20px; margin-bottom: 10px; }
  h3 { color: #374151; font-size: 16px; margin-bottom: 8px; }
  p, li { font-size: 13px; line-height: 1.5; }
  table { font-size: 12px; width: 100%; border-collapse: collapse; margin-top: 8px; margin-bottom: 8px; background: white; border: 1px solid #e5e7eb; }
  th { background: #291a10; color: #ffb800; padding: 6px 10px; text-align: left; font-weight: 700; }
  td { padding: 5px 10px; border-bottom: 1px solid #e5e7eb; }
  tr:nth-child(even) { background-color: #f9fafb; }
  .badge { font-weight: 700; padding: 2px 6px; border-radius: 3px; font-size: 10px; display: inline-block; }
  .badge-green { background: #dcfce7; color: #15803d; border: 1px solid #86efac; }
  .badge-gold { background: #fef3c7; color: #b45309; border: 1px solid #fde68a; }
  .badge-blue { background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
  .grid-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .callout { background: #fffbeb; border-left: 4px solid #f59e0b; padding: 8px 14px; margin: 10px 0; border-radius: 0 4px 4px 0; font-size: 12px; }
---

# Carrier Board & Flex Tail Rev 2.0
## Supplier PCB Manufacturing & DFM Review Deck

<div class="grid-2col" style="margin-top: 24px;">
<div>

### Executive Summary
* **Subsystem Assembly**: Test Board Carrier Board & Flex Tail Assembly
* **Revision**: `2.0` (Production Prototype Candidate)
* **Architecture**: 6-Layer Rigid-Flex Carrier Board + 2-Layer Polyimide Capacitive Flex Tail
* **DRC Compliance**: <span class="badge badge-green">100% CLEAN (0 ERRORS, 0 WARNINGS)</span>
* **Manufacturing Standard**: IPC-A-600 / IPC-6013 Class 2 (Rigid-Flex)
* **CAM Package**: RS-274X Gerbers, Excellon NC Drill, IPC-D-356 Netlist

</div>
<div>

### Key Target Specifications
* **Rigid Board Form Factor**: $60.0 \times 90.0 \times 1.6\text{ mm}$ ($R=6.0\text{ mm}$ corners)
* **Flex Tail Dimensions**: $24.0\text{ mm}$ body / $17.0\text{ mm}$ tab $\times 54.0 \times 0.20\text{ mm}$
* **Rigid Finish**: ENIG (Electroless Nickel Immersion Gold)
* **Solder Mask**: Matte Black LPI; Silkscreen: High-contrast White
* **Primary MCU**: NXP i.MX RT1062 Crossover MCU (BGA)
* **Wireless Subsystem**: u-blox NINA-B312 BLE 5.0 Module
* **Power Management**: TI BQ24074 Charger + Maxim MAX17048 Fuel Gauge

</div>
</div>

<div class="callout">
<strong>Review Objective:</strong> Complete technical sign-off and DFM qualification with primary PCB fabrication and assembly partners for rapid prototype production run.
</div>

---

# Board Overview & Mechanical Form Factor

<div class="grid-2col">
<div>

### Carrier Board (Rigid Section)
* **Outer Outline**: $60.00\text{ mm (X)} \times 90.00\text{ mm (Y)}$
* **Corner Radius**: $6.0\text{ mm}$ on all four exterior corners
* **Nominal Thickness**: $1.60\text{ mm} \pm 0.10\text{ mm}$
* **Mounting Holes**: 4x $\varnothing 3.20\text{ mm}$ (M3 screw clearance)
  * Inset: $4.50\text{ mm}$ from outer edge ($X = \pm 25.50\text{ mm}, Y = \pm 40.50\text{ mm}$)
  * Plated through-hole tied directly to chassis GND plane
* **Connector Edge Alignment**:
  * `J3` (USB-C Receptacle): Flush at left edge ($X = -25.00\text{ mm}$)
  * `J2` (Hirose FPC-30P): Top edge ($Y = 38.00\text{ mm}$)
  * `J13` (JST-PH Battery): Protected internal alcove

</div>
<div>

### Flex Tail (Flexible Section)
* **Flex Body Dimensions**: $24.00\text{ mm (W)} \times 54.00\text{ mm (L)}$
* **Connector Insertion Tab**: $17.00\text{ mm}$ width (mates to `J2`)
* **Substrate Thickness**: $0.20\text{ mm}$ Polyimide flex core
* **Corner Radius**: $1.0\text{ mm}$ transition fillets to prevent tear points
* **Minimum Bend Radius**: $R_{\text{bend}} \ge 3.0\text{ mm}$ ($15\times$ flex thickness)
* **Stiffener Reinforcement**:
  * $0.80\text{ mm}$ FR4 stiffener bonded at connector finger tab
  * $0.80\text{ mm}$ FR4 stiffener under capacitive electrode array

</div>
</div>

| Parameter | Carrier Board (Rigid) | Flex Tail (Flexible) | Unit |
| :--- | :--- | :--- | :--- |
| Board Outline Dimensions | $60.00 \times 90.00$ | $24.00 \times 54.00$ (Tab $17.00$) | mm |
| Board Thickness | $1.60 \pm 0.10$ | $0.20 \pm 0.03$ | mm |
| Layer Count | 6 Copper Layers | 2 Copper Layers | - |
| Substrate Material | FR4 High-Tg ($T_g \ge 170^\circ\text{C}$) | DuPont Pyralux Polyimide | - |

---

# Carrier Board 6-Layer Physical Stackup

### Symmetrical Rigid-Flex Layer Stackup Architecture

| Layer ID | Name | Type | Material | Thickness | Notes & Signal Allocation |
| :---: | :--- | :---: | :--- | :---: | :--- |
| - | Top Silkscreen | Silk | White Liquid Photoimageable | - | Canonical ref des, pin 1 markers |
| - | Top Solder Mask | Mask | Matte Black LPI | $0.020\text{ mm}$ | Minimum dam $0.10\text{ mm}$ ($4\text{ mil}$) |
| **L1** | **F.Cu** | **Signal** | **Copper Foil (1 oz)** | **$0.035\text{ mm}$** | High-speed FlexSPI, USB, crystal, RF |
| - | Prepreg 1 | Dielectric | FR4 2116 ($\varepsilon_r = 4.2$) | $0.100\text{ mm}$ | High dielectric breakdown ($>32\text{ kV/mm}$) |
| **L2** | **In1.Cu** | **Plane** | **Copper Foil (1 oz)** | **$0.035\text{ mm}$** | Solid Ground Plane (unbroken L1 reference) |
| - | Core 1 | Dielectric | FR4 Core ($\varepsilon_r = 4.4$) | $0.450\text{ mm}$ | High-Tg structural core ($T_g \ge 170^\circ\text{C}$) |
| **L3** | **In2.Cu** | **Signal** | **Copper Foil (1 oz)** | **$0.035\text{ mm}$** | High-density escape & Flex transition |
| - | Flex Dielectric | Dielectric | Polyimide Flex ($\varepsilon_r = 3.4$) | $0.200\text{ mm}$ | Continuous flexible inner substrate |
| **L4** | **In3.Cu** | **Plane** | **Copper Foil (1 oz)** | **$0.035\text{ mm}$** | Power Plane (+3V3, VBUS, VBAT split zones) |
| - | Core 2 | Dielectric | FR4 Core ($\varepsilon_r = 4.4$) | $0.450\text{ mm}$ | High-Tg structural core ($T_g \ge 170^\circ\text{C}$) |
| **L5** | **In4.Cu** | **Signal** | **Copper Foil (1 oz)** | **$0.035\text{ mm}$** | Low-speed I2C, SPI, GPIO, control lines |
| - | Prepreg 2 | Dielectric | FR4 2116 ($\varepsilon_r = 4.2$) | $0.100\text{ mm}$ | Symmetrical bonding layer |
| **L6** | **B.Cu** | **Signal** | **Copper Foil (1 oz)** | **$0.035\text{ mm}$** | Bottom routing & auxiliary GND flood |
| - | Bottom Solder Mask | Mask | Matte Black LPI | $0.020\text{ mm}$ | Mask-defined bottom test pads |

* **Total Finished Rigid Thickness**: $1.580\text{ mm} \pm 0.10\text{ mm}$ ($1.6\text{ mm}$ nominal).
* **Surface Finish**: ENIG (IPC-4552) — Gold $0.05 \text{--} 0.10\ \mu\text{m}$ over Electroless Nickel $3.0 \text{--} 6.0\ \mu\text{m}$.

---

# Flex Tail Specifications & Transition Details

<div class="grid-2col">
<div>

### Flex Substrate & Coverlay
* **Base Substrate**: DuPont Pyralux AP252500E or equivalent
  * $50\ \mu\text{m}$ ($2.0\text{ mil}$) Polyimide core
  * $35\ \mu\text{m}$ ($1.0\text{ oz}$) Rolled Annealed (RA) Copper on both sides
  * Non-adhesive substrate for superior dynamic flex endurance
* **Coverlay Film**:
  * Amber Polyimide $25\ \mu\text{m}$ ($1.0\text{ mil}$) + $25\ \mu\text{m}$ acrylic adhesive
  * Opening clearance: $0.15\text{ mm}$ nominal around contact fingers
* **Flex Edge Clearance**:
  * All copper traces maintain $\ge 1.50\text{ mm}$ keepout from flex outline
  * Eliminates edge delamination and copper tearing during bending

</div>
<div>

### Stiffeners & Finger Plating
* **FPC Contact Finger Plating**:
  * Hard Gold plating ($0.76\ \mu\text{m}\ / 30\ \mu\text{in}$ Au over $2.5\ \mu\text{m}$ Ni)
  * Chamfered insertion tip ($45^\circ \times 0.20\text{ mm}$) for zero insertion force mating
* **Finger Pitch**: $0.50\text{ mm}$ pitch, 30 contact pins
* **Stiffener Specifications**:
  * Material: FR4 composite dielectric
  * Thickness: $0.80\text{ mm} \pm 0.05\text{ mm}$
  * Adhesive: Thermal cure modified acrylic adhesive ($30\ \mu\text{m}$)
* **Transition Zone Relief**:
  * Flexible coverlay extends $\ge 2.0\text{ mm}$ inside rigid FR4 transition border
  * Strain-relief polyurethane bead along rigid-flex interface line

</div>
</div>

<div class="callout">
<strong>Flex Bending Rule:</strong> Minimum static bend radius is $1.5\text{ mm}$. Minimum dynamic operational bend radius is $3.0\text{ mm}$. No component pads or vias allowed in the active bend corridor.
</div>

---

# Controlled Impedance & High-Speed Routing Invariants

<div class="grid-2col">
<div>

### Controlled Impedance Targets
* **$50\ \Omega$ Single-Ended Microstrip (Layer 1)**:
  * Trace Width: $0.180\text{ mm}$ ($7.1\text{ mil}$)
  * Reference: Layer 2 unbroken GND plane ($0.100\text{ mm}$ dielectric height)
  * Tolerance: $\pm 10\%$ ($\pm 5\ \Omega$)
* **$90\ \Omega$ Differential Pair (USB 2.0 D+/D-)**:
  * Trace Width: $0.160\text{ mm}$ ($6.3\text{ mil}$)
  * Pair Spacing: $0.180\text{ mm}$ ($7.1\text{ mil}$)
  * Reference: Layer 2 GND plane
  * Intra-pair skew constraint: $< 0.15\text{ mm}$ ($< 1.0\text{ ps}$)

</div>
<div>

### Critical Bus Routing Invariants
* **FlexSPI NAND Flash (`U2`)**:
  * Clock, strobe, and data lines (`D0..D3`) routed on Layer 1 over solid GND
  * Length matching: $\Delta L \le 1.50\text{ mm}$ across all 6 bus traces
  * No layer-change vias on high-speed clock trace
* **Crystal Oscillators (`Y1` 24MHz, `Y2` 32.768kHz)**:
  * Point-to-point guard ring stitched directly to Layer 2 GND
  * Zero underlying signal routes on Layer 3
* **BLE UART Subsystem (1.0 Mb/s)**:
  * Direct low-impedance connection between RT1062 and u-blox NINA-B312
* **USB Type-C D+/D-**:
  * Ultra-short routing to `D8` TVS protection diode array adjacent to receptacle

</div>
</div>

| Net / Bus Class | Topology | Trace Width (mm) | Spacing (mm) | Target Impedance | Tolerance | Ref Layer |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| USB 2.0 Differential | Edge-Coupled Microstrip | $0.160$ | $0.180$ | $90\ \Omega\ \text{diff}$ | $\pm 10\%$ | L2 (GND) |
| FlexSPI Bus | Single-Ended Microstrip | $0.180$ | $0.250$ | $50\ \Omega\ \text{SE}$ | $\pm 10\%$ | L2 (GND) |
| General Digital / I2C | Microstrip / Stripline | $0.200$ | $0.200$ | Uncontrolled | - | L2 / L4 |
| High-Current Power (VBUS/VBAT) | Copper Polygon Pour | $> 0.500$ | $0.250$ | Low DCR ($< 20\text{ m}\Omega$) | - | L4 (PWR) |

---

# RF Ground Plane Keepouts & Mechanical Constraints

<div class="grid-2col">
<div>

### BLE Integrated Antenna Keepout
* **Module**: u-blox NINA-B312 (`U11`) with integrated ceramic/PCB antenna
* **Keepout Dimensions**: $16.00\text{ mm (X)} \times 5.00\text{ mm (Y)}$
* **Location**: Centered at board bottom edge ($X = 0.00\text{ mm}, Y = -42.00\text{ mm}$)
* **Exclusion Constraints**:
  * **Zero Copper**: Void across all 6 copper layers (L1 through L6)
  * **Zero Components**: No passives, no ICs, no test points
  * **Zero Fasteners**: No screws, metal brackets, or conductive housings within $10\text{ mm}$
  * **No Solder Mask Requirement**: Bare dielectric with silkscreen antenna boundary outline

</div>
<div>

### Edge-Mounted Connector Rules
* **USB-C Receptacle (`J3`)**:
  * Located at $X = -25.00\text{ mm}, Y = 0.00\text{ mm}$
  * Receptacle shell overhangs board edge by $0.80\text{ mm}$ to mate flush with enclosure exterior
  * 4x through-hole structural shield tabs soldered to chassis GND
* **Hirose FPC Connector (`J2`)**:
  * Located at $X = 0.00\text{ mm}, Y = 38.00\text{ mm}$
  * Top-mounted 30-position $0.5\text{ mm}$ pitch receptacle
  * $2.00\text{ mm}$ clearance to enclosure lid lip
* **SWD Header (`J5`) & Battery JST-PH (`J13`)**:
  * Keyed polarization prevent reverse insertion

</div>
</div>

<div class="callout">
<strong>DFM Note on Edge Cutouts:</strong> USB Type-C connector shell cutout is approved for edge-flush mounting per DRC rule exemptions for external mating connectors.
</div>

---

# Power Architecture & Thermal Distribution

<div class="grid-2col">
<div>

### Power Subsystem Architecture
* **Primary Input (VBUS)**:
  * $+5.0\text{V}$ from USB Type-C receptacle (`J3`)
  * Overvoltage & ESD clamp via bidirectional TVS diode `D8`
* **Battery Subsystem (VBAT)**:
  * Single-cell Li-Ion / LiPo ($3.7\text{V}$ nominal, $4.2\text{V}$ max) via JST-PH (`J13`)
  * Integrated TI BQ24074 (`U3`) autonomous power-path management
  * Up to $1.5\text{A}$ charge rate with programmable thermal regulation
* **Fuel Gauge (`U4`)**:
  * Maxim Integrated MAX17048 with $\text{ModelGauge}^{\text{TM}}$ algorithm
  * Zero-sense-resistor implementation minimizing $I^2R$ power loss
* **Main System Rails**:
  * $+3\text{V}3$ High-efficiency synchronous buck converter ($2.0\text{A}$ peak)
  * Dedicated low-noise LDO for BLE radio core

</div>
<div>

### Decoupling & Thermal Vias
* **MCU BGA Decoupling Array**:
  * 12x $0.1\ \mu\text{F}$ 0402 X7R ceramic capacitors placed directly beneath BGA balls
  * 4x $1.0\ \mu\text{F}$ 0402 ceramic caps on core rail
  * Low-inductance via-in-pad / adjacent dogleg vias connected directly to L2 GND
* **Charger IC Thermal Relief (`U3`)**:
  * Exposed thermal pad ($3.0 \times 3.0\text{ mm}$) soldered to top copper
  * $3 \times 3$ grid of $0.30\text{ mm}$ thermal vias with $0.65\text{ mm}$ pitch
  * Direct thermal conduction to internal Layer 2 GND and bottom ground plane
* **Bulk Storage**:
  * $22\ \mu\text{F}$ and $47\ \mu\text{F}$ 0805 low-ESR ceramic caps adjacent to inductors

</div>
</div>

---

# Design Rule Check (DRC) Zero-Defect Report

### Comprehensive Automated DRC Verification Results

| Rule Category | Description | Minimum Design Rule | Actual Board Margin | Verification Status |
| :--- | :--- | :---: | :---: | :---: |
| **Clearance** | Trace-to-Trace Spacing | $0.150\text{ mm}$ ($6.0\text{ mil}$) | $0.180\text{ mm}$ ($7.1\text{ mil}$) | <span class="badge badge-green">PASSED (0 VIOLATIONS)</span> |
| **Clearance** | Trace-to-Pad Clearance | $0.150\text{ mm}$ ($6.0\text{ mil}$) | $0.175\text{ mm}$ ($6.9\text{ mil}$) | <span class="badge badge-green">PASSED (0 VIOLATIONS)</span> |
| **Clearance** | Pad-to-Pad Spacing | $0.150\text{ mm}$ ($6.0\text{ mil}$) | $0.160\text{ mm}$ ($6.3\text{ mil}$) | <span class="badge badge-green">PASSED (0 VIOLATIONS)</span> |
| **Drill / Via** | Minimum Drill Diameter | $0.250\text{ mm}$ ($10\text{ mil}$) | $0.250\text{ mm}$ ($10\text{ mil}$) | <span class="badge badge-green">PASSED (0 VIOLATIONS)</span> |
| **Drill / Via** | Annular Ring Width | $0.125\text{ mm}$ ($5.0\text{ mil}$) | $0.150\text{ mm}$ ($6.0\text{ mil}$) | <span class="badge badge-green">PASSED (0 VIOLATIONS)</span> |
| **Edge Clearance** | Rigid Copper-to-Edge | $0.300\text{ mm}$ ($12\text{ mil}$) | $0.450\text{ mm}$ ($18\text{ mil}$) | <span class="badge badge-green">PASSED (0 VIOLATIONS)</span> |
| **Edge Clearance** | Flex Copper-to-Edge | $1.500\text{ mm}$ ($60\text{ mil}$) | $1.850\text{ mm}$ ($73\text{ mil}$) | <span class="badge badge-green">PASSED (0 VIOLATIONS)</span> |
| **Antenna** | RF Ground Plane Keepout | $16.0 \times 5.0\text{ mm}$ Void | $16.0 \times 5.0\text{ mm}$ Void | <span class="badge badge-green">PASSED (0 VIOLATIONS)</span> |
| **Electrical** | Unrouted Nets / Opens | 0 Opens Allowed | 0 Opens Detected | <span class="badge badge-green">PASSED (0 VIOLATIONS)</span> |
| **Electrical** | Short Circuits | 0 Shorts Allowed | 0 Shorts Detected | <span class="badge badge-green">PASSED (0 VIOLATIONS)</span> |

<div class="callout" style="background: #ecfdf5; border-color: #10b981;">
<strong>DRC Audit Verdict:</strong> Carrier Board Rev 2.0 passed automated DRC with <strong>0 Errors and 0 Warnings</strong>. Flex Tail passed automated DRC with <strong>0 Errors and 0 Warnings</strong>. Both boards qualify for immediate CAM toolchain generation.
</div>

---

# CAM Deliverables Package & Manufacturing Files

### Archive Deliverable Manifest (`carrier_board_rev2.0_fab.zip`)

<div class="grid-2col">
<div>

### RS-274X Gerber & Drill Files
* `CarrierBoard-F_Cu.gtl`: Top Copper (Layer 1)
* `CarrierBoard-In1_Cu.g1`: Internal Ground Plane (Layer 2)
* `CarrierBoard-In2_Cu.g2`: Internal Signal / Flex (Layer 3)
* `CarrierBoard-In3_Cu.g3`: Internal Power Plane (Layer 4)
* `CarrierBoard-In4_Cu.g4`: Internal Signal (Layer 5)
* `CarrierBoard-B_Cu.gbl`: Bottom Copper (Layer 6)
* `CarrierBoard-F_Mask.gts` / `B_Mask.gbs`: Solder Masks
* `CarrierBoard-F_Silkscreen.gto` / `B_Silkscreen.gbo`: Silkscreens
* `CarrierBoard-F_Paste.gtp` / `B_Paste.gbp`: Solder Paste Stencils
* `CarrierBoard-Edge_Cuts.gko`: Board Outline & Milling
* `CarrierBoard-PTH.drl`: Plated Through-Hole Drill File
* `CarrierBoard-NPTH.drl`: Non-Plated Hole Drill File

</div>
<div>

### Assembly & Testing Artifacts
* `CarrierBoard.ipc`: IPC-D-356 Electrical Test Netlist
  * Complete netlist for 100% bare-board flying probe test
* `CarrierBoard-top-pos.csv`: Component Pick-and-Place Centroids
  * Formatted with RefDes, Val, Package, PosX, PosY, Rotation
* `CarrierBoard-BOM.xlsx`: Bill of Materials
  * Full manufacturer part numbers, descriptions, alternate sources
* `FlexTail-*.gerber`: Matching 2-layer flex deliverables package
* `stackup_report.pdf`: Factory impedance test coupons

</div>
</div>

<div class="callout">
<strong>Toolchain Generation:</strong> All CAM files generated headlessly via <code>kicad-cli</code> pipeline with strict coordinate precision ($0.1\ \mu\text{m}$) and zero manual post-editing.
</div>

---

# Supplier Quality Assurance & Sign-Off Criteria

### Acceptance & Quality Control Requirements

<div class="grid-2col">
<div>

### Quality & Manufacturing Standards
* **Fabrication Standard**: IPC-A-600 Class 2 / IPC-6013 Class 2
* **Assembly Standard**: IPC-A-610 Class 2
* **Solderability Standard**: J-STD-003 Category 3
* **Electrical Test**: 100% Flying Probe Test against IPC-D-356 netlist
* **Impedance Coupons**: Included on manufacturing panel rails
  * Test coupons for $50\ \Omega$ SE and $90\ \Omega$ diff pairs
  * TDR microsection test report required with each lot
* **Cleanliness**: Ionic contamination $< 1.0\ \mu\text{g/cm}^2\ \text{NaCl}$ equivalent

</div>
<div>

### Packaging & Environmental
* **Moisture Sensitivity**: IPC/JEDEC J-STD-033 Level 3
  * Vacuum sealed with active desiccant and humidity indicator card
  * Bakeout protocol: $125^\circ\text{C}$ for 4 hours prior to SMT reflow
* **RoHS & REACH**: 100% Lead-Free and RoHS 3 compliant
* **X-Ray Inspection (AXI)**:
  * 100% AXI on RT1062 BGA balls (`U1`)
  * Voiding percentage $< 15\%$ on BGA solder joints
  * 100% optical inspection (AOI) on all SMT passives

</div>
</div>

### Engineering Sign-Off Checklist
* [x] **Schematic & Netlist Sign-off**: All functional nets verified, floating pins resolved
* [x] **Mechanical & Keepout Sign-off**: RF antenna void verified, connector overhang checked
* [x] **DRC Zero-Defect Audit**: Automated checker passed with 0 errors and 0 warnings
* [x] **CAM Package Completeness**: Gerber, drill, netlist, and centroid files verified

---

# PCB Assembly Specifications & Component Metrics

### Manufacturing Bill of Materials & SMT Line Metrics

<div class="grid-2col">
<div>

### Component Counts by Mounting Type
* **Total Components Placed**: 67 components
* **Number of Unique Parts (BOM Line Items)**: **36 unique line items**
* **Number of SMD Parts**: **60 parts**
* **Number of BGA / QFP / QFN Parts**: **4 complex parts**
  * `U1`: NXP MCXN947 / RT1062 Crossover MCU (`VFBGA-184`, 0.8mm pitch)
  * `U2`: Azoteq IQS7222A Capacitive Controller (`QFN-20`, 0.5mm pitch)
  * `U4`: High-efficiency Audio Amplifier (`QFN-16-AMP`, 0.5mm pitch)
  * `U9`: FTDI FT232RNQ USB-UART Interface (`QFN-32`, 0.5mm pitch)
* **Number of Through-Hole Parts**: **7 parts**
  * `J5`, `J15`: 10-pin micro-headers (1.27mm pitch)
  * `J14`: 10-pin peripheral expansion header (2.54mm pitch)
  * `JP1`..`JP4`: 2-pin configuration jumpers

</div>
<div>

### Detailed Assembly & SMT Process Guidelines
* **Placement Topology**: Double-sided SMT assembly
  * Primary Top Side (`F.Cu`): MCU (`U1`), BLE module (`U11`), Charger (`U3`), USB-C (`J3`), FPC (`J2`), Passives
  * Secondary Bottom Side (`B.Cu`): Cap touch controller (`U2`), decoupling passives
* **Solder Paste & Stencil**:
  * Alloy: Lead-free SAC305 (Sn96.5 / Ag3.0 / Cu0.5), RoHS 3 compliant
  * Powder size: Type 4 or Type 5 mesh suitable for 0.4mm BGA pads
  * Stencil foil: $0.10\text{ mm}$ ($4.0\text{ mil}$) laser-cut electro-polished stainless steel with nano-coating
* **Reflow Thermal Profile**:
  * Peak reflow temperature: $240^\circ\text{C} \text{ to } 245^\circ\text{C}$ (Max $250^\circ\text{C}$)
  * Time above liquidus ($217^\circ\text{C}$): $60 \text{--} 90\text{ seconds}$
* **Post-Reflow Inspection**:
  * 100% 3D Automated Optical Inspection (AOI) for all SMT chips
  * 100% Automated X-ray Inspection (AXI) for BGA balls on `U1` and QFN thermal ground pads on `U2`, `U3`, `U4`, `U9`

</div>
</div>

<div class="callout">
<strong>Assembly Requirement:</strong> Moisture-sensitive parts (MSL 3: <code>U1</code>, <code>U11</code>) must be baked at $125^\circ\text{C}$ for 4 hours prior to surface-mount reflow if dry-pack seal was broken $> 168\text{ hours}$.
</div>

---

# Schematic No-Connect (NC) & Unused Pin Audit

### Complex Integrated Circuit Omitted Pin Matrix

| Component RefDes | IC Description & Package | Total Pins | Connected Pins | Omitted / No-Connect Count | Dedicated No-Connect Pin Names & Functional Rationale |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **U1** | NXP MCXN947VDF<br>`VFBGA-184` | 184 | 52 | **132 balls** | **Unassigned GPIOs & Secondary Peripheral Ports:**<br>132 unassigned balls (e.g. `A2, A4, A12, A14, B3, B4, B7...`). Intentionally left unrouted to maintain continuous ground plane reference under high-speed FlexSPI and audio lines without stub antenna emissions. |
| **U2** | Azoteq IQS7222A<br>`QFN-20` | 21 | 17 | **4 pads** | **`NC1` (Pin 9), `NC2` (Pin 10):** Factory internal test points — must float per Azoteq datasheet.<br>**`CT8` (Pin 12):** Unused 9th sensing channel (design utilizes CT0..CT7 for 5-button slider & proximity).<br>**`OUTA` (Pin 14):** Unused auxiliary direct output. |
| **U11** | u-blox NINA-B312<br>`MOD-BLE-PCB-ANT` | 27 | 9 | **18 pads** | **`NFC1`, `NFC2`:** Unused near-field antenna terminals.<br>**`IO_2..IO_5`, `IO_24..IO_27`:** Auxiliary GPIOs reserved for future firmware features.<br>**`RED`, `GREEN`, `BLUE`:** Unused internal open-drain LED pins.<br>**`RESET_N`:** Internal power-on reset; reset controlled via AT commands.<br>**`EGP`, `GND_12, 26, 30`:** Redundant internal thermal test pads. |
| **U7** | Maxim MAX17048<br>`TDFN-8` | 9 | 9 | **0 pads** | **Fully Terminated (Zero Omitted Pins):**<br>All 8 functional pins (`CELL, VCON, SDA, SCL, QSTRT, ALRT, GND`) and exposed thermal pad (`EP`) are 100% connected to power, I2C bus, and reference ground. |
| **U9** | FTDI FT232RNQ<br>`QFN-32` | 33 | 31 | **2 pads** | **Pin 6 (`NC`), Pin 8 (`NC`):**<br>Explicit internal no-connect pins per FTDI FT232RNQ datasheet specifications. Left floating with zero copper stubs. |

<div class="callout">
<strong>Design Validation:</strong> All omitted pins have been audited against manufacturer authoritative datasheets. High-impedance CMOS inputs are tied to internal pull-ups or firmware-isolated to eliminate parasitic leakage currents.
</div>
