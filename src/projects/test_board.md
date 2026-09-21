# Test Board

This project designs a modular hardware evaluation and sensor test board featuring a multi-layer rigid carrier PCB and a flexible tail PCB with mutual/self-capacitive proximity electrodes. The board is powered by the **NXP MCX N947** dual-core Arm Cortex-M33 microcontroller (`MCXN947VDF` in VFBGA-184), with high-speed dual-channel Octal/Quad FlexSPI storage (**Winbond W25N01GV** 1Gb SLC NAND), autonomous battery charging & power path management (**TI BQ24074**), precision fuel gauging (**ADI MAX17048**), constant-current logarithmic RGB LED indication (**TI LP5009**), high-speed USB-to-UART telemetry (**FTDI FT232RNQ**), 16-channel capacitive touch sensing (**Infineon CY8CMBR3116**), and digital Class-D audio amplification (**ADI MAX98357A**).

The mechanical enclosure features an upper lid with an optical window for status LED viewing and a rigid lower housing capturing rubber anti-skid feet, with four M3 corner mounting fasteners providing mechanical rigidity.

![Test Board Carrier](carrier_board_schematic.svg)

*Test board carrier top-level schematic and subassembly overview.*

## Build Files

After running `build.py`, you should see these files in your build output organized by subdirectories under the build folder:

- **build/svg/test_board/carrier_board_schematic.svg** - Complete carrier PCB schematic diagram with multi-sheet hierarchy.
- **build/svg/test_board/flex_tail_schematic.svg** - Flexible tail PCB schematic showing capacitive sensor electrodes and connector pinout.
- **build/svg/test_board/test_board_wiring_diagram.svg** - Top-down system wiring diagram illustrating inter-module power and bus connectivity.
- **build/pcb/test_board/carrier_board.kicad_pcb** - 6-layer impedance-matched rigid carrier board layout.
- **build/pcb/test_board/flex_tail.kicad_pcb** - 2-layer polyimide flexible tail PCB layout.
- **build/gerber/test_board/carrier_board/** - RS-274X Gerber manufacturing files, Excellon drill files, and IPC-D-356 netlists.
- **build/gerber/test_board/flex_tail/** - Gerber and NC drill manufacturing files for flexible PCB fabrication.
- **build/stl/test_board/carrier_enclosure.stl** - 3D printable protective enclosure shell for the carrier assembly.
- **build/urdf/test_board/product.urdf** - Full kinematic and simulation URDF model.

## Visualization & Simulation

To view the complete test board mechanical assembly in the 3D CAD viewer:
```bash
python src/view.py test_board/product
```

To visualize the routed carrier PCB with copper zones, silkscreen, and components:
```bash
python src/view.py test_board/carrier_board:pcb
```

To visualize the routed flexible tail with capacitive sensor pads:
```bash
python src/view.py test_board/flex_tail:pcb
```

To view the top-down 2D wiring layout:
```bash
python src/view.py test_board/carrier_board:diagram
```

## System Block Diagram

```mermaid
graph TD
    %% Power In & Charging
    USBC["USB-C Receptacle (J3)"] -->|VBUS: 5V| CHG["TI BQ24074 Charger (U3)"]
    BAT[("1S Li-Ion / LiPo Cell")] <-->|VBAT| CHG
    BAT <-->|Analog Sensing| FUEL["MAX17048 Fuel Gauge (U7)"]
    CHG -->|SYS_3V3 (Switched / Reg)| LDO["TPS7A0533 3.3V LDO"]
    
    %% Power Rails & Gating
    LDO -->|SYS_3V3 Always-On| MCU["NXP MCX N947 (U1, VFBGA-184)"]
    MCU -->|PWR_EN_AUDIO (L4)| Q2["Audio Load Switch (TPS22918)"]
    MCU -->|PWR_EN_SENSORS (L5)| Q3["Sensors Load Switch (TPS22918)"]
    MCU -->|PWR_EN_DEBUG (M4)| Q4["Debug Load Switch (TPS22918)"]
    
    Q2 -->|SW_3V3_AUDIO| AUDIO["MAX98357A Amp (U4) & SPK1"]
    Q3 -->|SW_3V3_SENSORS| TOUCH["CY8CMBR3116 Touch (U2)"]
    Q4 -->|SW_3V3_DEBUG| FTDI["FT232RNQ USB-UART (U9)"]
    
    %% Microcontroller Busses
    MCU <-->|FlexSPI Dual Channel Port A| NAND["Winbond W25N01GV 1Gb NAND (U8)"]
    MCU <-->|FlexSPI Dual Channel Port B| JFLEX["Expansion Flash Header (J_FLEX)"]
    MCU <-->|Core I2C0 Bus: A10/B10| FUEL
    MCU <-->|Core I2C0 Bus: A10/B10| LED["TI LP5009 RGB Driver (U6)"]
    MCU <-->|Touch I2C1 Bus: C5/C6| TOUCH
    MCU <-->|Primary I3C0: A8/C8/B8| JI3C0["Primary I3C Header (J7)"]
    MCU <-->|Secondary I3C1: F4/F6/E4| JI3C1["Secondary I3C Header (J8)"]
    MCU <-->|Expansion I2C2: B1/A1| JI2C2["Expansion I2C Header (J6)"]
    MCU <-->|Expansion SPI0: T6/T7/R8/R9| JSPI0["Expansion SPI Header (J9)"]
    MCU <-->|Expansion UART1: A4/B3| JUART1["Expansion UART Header (J10)"]
    
    %% High-Speed Console & Debug
    USBC <-->|D+/D-| FTDI
    FTDI <-->|UART0 Console: B6/A6/F10/E10| MCU
    JSWD["10-Pin SWD Header (J5)"] <-->|SWD / Reset: A16/A17/B16/F3/C14| MCU
    
    %% Wakeup & Interrupts
    CHG -->|CHG_STAT: G5 (WUU0_IN15)| MCU
    CHG -->|CHG_PGOOD_WAKE: M10 (VBAT_WAKEUP)| MCU
    M2["M.2 Key-M Host (J1)"] -->|M2_WAKE_N: C13 (WUU0_IN1)| MCU
    TOUCH -->|CAP_INT: C4| MCU
```

## Bill of Materials (BOM)

| Designator | Component / Part | Description | Package / Footprint | Bus / Interface | Key Specifications |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`U1`** | **NXP MCX N947 (`MCXN947VDF`)** | Dual-core Arm Cortex-M33 MCU with eIQ Neutron NPU | VFBGA-184 ($11\times 11\text{ mm}$, $0.8\text{ mm}$ pitch) | Host Controller | 150 MHz, 2MB dual-bank Flash, 512KB SRAM, Dual FlexSPI, Dual I3C. Table 93 verified. |
| **`U8`** | **Winbond W25N01GVZEIG** | 1Gb (128MB) SLC Serial NAND Flash Memory | WSON-8 ($8\times 6\text{ mm}$) | FlexSPI Port A (`B17`, `D14`, `E14`..`F16`) | 104 MHz Quad-SPI, Dual-Channel SDR Overdrive mode ($C_L = 15\text{ pF}$, $1\text{ V/ns}$ slew rate). |
| **`U3`** | **TI BQ24074RGTR** | 1.5A Li-Ion Battery Charger with Dynamic Power Path | VQFN-16 ($3\times 3\text{ mm}$) | `/CHG` (`G5`), `/PGOOD` (`M10`) | Autonomous power routing, 4.2V charge voltage, input current limiting (100mA, 500mA, or resistor set). |
| **`U7`** | **ADI / Maxim MAX17048G+T10** | 1-Cell Li+ ModelGauge Fuel Gauge IC | TDFN-8 ($2\times 2\text{ mm}$) | Core `I2C0` (`0x36`) | Ultra-low $3\,\mu\text{A}$ operating current, state of charge (SoC) estimation, alert interrupt. |
| **`U6`** | **TI LP5009RUKR** | 9-Channel Constant-Current RGB LED Driver | WQFN-20 ($3\times 3\text{ mm}$) | Core `I2C0` (`0x14`) | Logarithmic dimming, auto-breathing animation engine, independent RGB color mixing. |
| **`U9`** | **FTDI FT232RNQ-REEL** | High-Speed USB 2.0 to UART Serial Bridge | QFN-32 ($5\times 5\text{ mm}$) | `FC1` UART0 (`B6`, `A6`, `F10`, `E10`) | Up to 3 Mbaud data rate, internal EEPROM, USB bus powered with reset & boot control GPIOs. |
| **`U2`** | **Infineon CY8CMBR3116** | 16-Channel CapSense Capacitive Touch Controller | QFN-24 ($4\times 4\text{ mm}$) | Touch `I2C1` (`0x37`), `CAP_INT` (`C4`)| SmartSense auto-tuning, proximity detection, LED buzzer output, water tolerance. |
| **`U4`** | **ADI / Maxim MAX98357AETE+** | 3.2W Class-D Mono Audio Amplifier | TQFN-16 ($3\times 3\text{ mm}$) | `PDM0` Audio (`B14`, `A14`) | Integrated digital PCM/I2S/PDM input stage, filterless Class-D, 92% efficiency into $4\,\Omega$. |
| **`U5`** | **Piezo Sounder (PKM13EPYH4000)** | Surface-mount piezoelectric audio transducer | Custom Circular ($13\text{ mm}$ dia) | `PIEZO_PWM` (`D15`, `PWM0_X0`) | Resonant frequency 4.0 kHz, SPL $\ge 75\text{ dB}$, audible user feedback. |
| **`Q2`–`Q4`**| **TI TPS22918DBVR** | 5.5V, 2A Ultra-Low On-Resistance Power Switches | SOT-23-6 ($2.9\times 1.6\text{ mm}$) | `PWR_EN_AUDIO` (`L4`), `SENSORS` (`L5`), `DEBUG` (`M4`) | $R_{\text{ON}} = 52\text{ m}\Omega$, controlled rise time, active-high enable with 100k pull-up. |
| **`J3`** | **USB-C 16-Pin Receptacle** | USB Type-C 2.0 Power & Data Receptacle | USB-C Mid-Mount SMD | VBUS, GND, CC1/CC2, D+/D- | Edge-mounted (-X outward) with 5.1k pulldowns on CC pins. |
| **`J5`** | **JST-SH 10-Pin Micro-Header** | SWD Hardware Debug & Flash Programming Header | 1.0mm Pitch Side-Entry SMD | `SWD_CLK`, `DIO`, `SWO`, `nRESET`, `BOOT0`| Compact debug interface for J-Link, MCU-Link, or CMSIS-DAP probes. |
| **`J7`, `J8`**| **JST-SH 5-Pin Micro-Headers** | Primary (`I3C0`) and Secondary (`I3C1`) I3C Headers | 1.0mm Pitch Side-Entry SMD | `I3C0` (`A8`, `C8`, `B8`), `I3C1` (`F4`, `F6`, `E4`) | High-speed MIPI I3C evaluation interface operating up to 12.5 Mbps. |
| **`J6`** | **JST-SH 4-Pin Micro-Header** | Expansion I2C Bus Header | 1.0mm Pitch Side-Entry SMD | `I2C2` (`B1`, `A1`) | External sensor expansion I2C with 3.3V and GND. |
| **`J9`** | **JST-SH 6-Pin Micro-Header** | Expansion SPI Bus Header | 1.0mm Pitch Side-Entry SMD | `SPI0` (`T6`, `T7`, `R8`, `R9`) | 4-wire SPI peripheral bus (SCK, MOSI, MISO, CS#). |
| **`J10`** | **JST-SH 4-Pin Micro-Header** | Expansion UART Bus Header | 1.0mm Pitch Side-Entry SMD | `UART1` (`A4`, `B3`) | Dedicated asynchronous serial link for external radios or modules. |
| **`J14`** | **JST-SH 10-Pin Micro-Header** | General-Purpose GPIO Breakout Header | 1.0mm Pitch Side-Entry SMD | `GPIO0`..`GPIO9` (Port 4 pins) | 10 dedicated digital IO lines supporting timer, PLU, and FlexIO. |

## Technical Integration Notes

1. **MCU Pinmux Verification & Sourcing (`BUG-064`)**:
   * All 184 ball coordinates and functional mappings are derived from **Table 93 ("Pinmux", pages 101–132)** of the NXP MCX N947 datasheet (`MCXNP184M150F70.pdf`).
   * **Ball `F4` Correction**: Ball `F4` is pin `P1_17` and supports `ALT10 - I3C1_SCL`. It is correctly assigned to the secondary I3C evaluation bus clock on `J8`.
   * **Core System I2C (`I2C0`)**: Assigned to `A10` (`P0_17`, ALT2: `FC0_P1`, SCL) and `B10` (`P0_16`, ALT2: `FC0_P0`, SDA), featuring hardware `+I2C` glitch filters and `+I3C` pull-up capability.
   * **Dedicated Touch I2C (`I2C1`)**: Assigned to `C5` (`P1_1`, ALT2: `FC3_P1`, SCL) and `C6` (`P1_0`, ALT2: `FC3_P0`, SDA), completely isolating the high-rate capacitive touch scan traffic from the primary system sensors.
2. **Deep Power Down Wakeup (`BUG-060`)**:
   * The system enters Deep Power Down ($< 2.5\,\mu\text{A}$) by gating internal power domains via the on-chip Smart Power Controller (SPC).
   * **Charger Insertion Wakeup**: BQ24074 `/PGOOD` (pin 10) connects to MCX N947 ball `M10` (`P5_2`, `VBAT_WAKEUP_b` / `WAKEUP0_B`). When USB VBUS is inserted, `/PGOOD` transitions LOW, triggering an immediate hardware wakeup from Deep Power Down into Active Charging state.
   * **Host Wakeup**: M.2 connector pin 50 (`PEWAKE#`) connects to ball `C13` (`P0_7`, `WUU0_IN1` / `WAKEUP1_B`), allowing host PCIe/NVMe systems to wake the evaluation unit via active-low signaling.
3. **Charger State Transitions (`BUG-063`)**:
   * BQ24074 `/CHG` (pin 11) connects via net `CHG_STAT` (with 100k pull-up to `SYS_3V3`) to MCX N947 ball `G5` (`P1_19`, Wake-Up Unit `WUU0_IN15`).
   * The MCU firmware configures asynchronous dual-edge interrupts:
     - **Falling edge** (`/CHG` LOW): Enters `ACTIVE_CHARGING` mode, pulsing the RGB LED in amber via autonomous hardware breathing.
     - **Rising edge** (`/CHG` HIGH): Charge cycle complete; transitions the system into `LOW_POWER_SLEEP` ($< 15\,\mu\text{A}$), displaying solid green for 5 seconds before turning off LEDs.
4. **Power-On Sequencing Compliance (`BUG-061`)**:
   * **Rule 1 (Unified Plane)**: `VDD` (`H6`, `H8`, `G7`), `VDD_P2` (`K8`, `L7`), `VDD_P3` (`G11`, `H10`, `H12`), and `VDD_P4` (`N5`, `P4`) ramp together from the common 3.3V system rail.
   * **Rule 2 (Core Supply Delay)**: `VDD_CORE` (`K10`, `L11`) is powered from the internal LDO/buck regulator and ramps monotonically after `VDD` reaches minimum operating threshold ($1.71\text{V}$).
   * **Rule 3 (Port 4 & Analog Matching)**: `VDD_P4` and `VDD_ANA` are matched to the same potential ($\Delta V < 50\text{ mV}$) via star-routing with ferrite bead isolation.
   * **Rule 4 (Battery Pre-bias)**: `VDD_BAT` is powered continuously from the battery cell, ensuring RTC state and tamper domains are established before/with main system rail ramp.
5. **High-Speed Dual-Channel FlexSPI Design (`BUG-062`)**:
   * **Channel A (Internal NAND)**: Connected to Winbond W25N01GV on Port 3 balls `B17` (SS0), `D14` (SCLK), `E14` (DATA0), `F15` (DATA1), `F17` (DATA2), `F16` (DATA3), and `D17` (DQS loopback).
   * **Channel B (Expansion)**: Routed to `J_FLEX` header on Port 2 balls `H3` (SS0), `J3` (SCLK), `K3` (DATA0), `K1` (DATA1), `K2` (DATA2), `L2` (DATA3), and `H1` (DQS).
   * **Timing Specifications**: Designed for $100\text{ MHz}$ SDR Overdrive mode with calibrated capacitive load $C_L \le 15\text{ pF}$ and maximum slew rate $1.0\text{ V/ns}$. Trace lengths are matched within $\pm 0.5\text{ mm}$ with $50\,\Omega$ single-ended impedance.
6. **Switched Power Rails & Load Switch Gating (`BUG-060`)**:
   * Three dedicated TPS22918 load switches (`Q2`, `Q3`, `Q4`) isolate high-quiescent subsystems during sleep:
     - `PWR_EN_AUDIO` (`L4`): Controls power to MAX98357A amplifier ($I_Q = 2.4\text{ mA}$ active $\to 0.01\,\mu\text{A}$ off).
     - `PWR_EN_SENSORS` (`L5`): Controls power to CY8CMBR3116 touch controller and external sensor headers.
     - `PWR_EN_DEBUG` (`M4`): Controls power to FT232RNQ bridge, eliminating parasitic leakage back-feeding into the MCU when USB is unpowered.
   * All load switch enable pins are equipped with 100k pull-ups to guarantee default-ON state during development and initial boot.

## Battery Life Estimation

Operating on a single **18650 3.7V Li-ion cell (3000 mAh / 11.1 Wh)**, the system implements aggressive power gating across three distinct operating tiers:

### Power Consumption Breakdown

| Subsystem State | Active Components | Current Draw (at 3.7V) | Power Draw | Daily Duty Cycle |
| :--- | :--- | :--- | :--- | :--- |
| **Active Mode** (Processing, NAND R/W, Audio, Telemetry) | MCU active @ 150MHz, NAND R/W active, MAX98357A audio driving speaker, FT232RNQ active, RGB LED on | **~65 mA** | 240 mW | **2.0%** (28.8 mins/day) |
| **Low-Power Sleep** (Touch sensing active, MCU in Deep Sleep) | MCU Deep Sleep (SRAM retained, RTC running), CY8CMBR3116 in Low-Power Scan mode, Q2/Q4 off | **~45 µA** | 0.17 mW | **98.0%** (idle evaluation monitoring) |
| **Deep Power Down** (Storage / Shipping / Off) | MCU Deep Power Down ($2.5\,\mu\text{A}$), BQ24074 in battery standby ($1.5\,\mu\text{A}$), MAX17048 ($3\,\mu\text{A}$), All load switches off | **~7.0 µA** | 0.026 mW | **Storage mode** (exited via USB plug-in or M.2 wake) |

### Calculations
* **Average Daily Operating Current**:
  $$I_{\text{avg}} = (I_{\text{active}} \times 0.02) + (I_{\text{sleep}} \times 0.98) = (65\text{ mA} \times 0.02) + (0.045\text{ mA} \times 0.98) = 1.30\text{ mA} + 0.044\text{ mA} = 1.344\text{ mA}$$
* **Estimated Runtime (Continuous Monitoring)**:
  $$\text{Runtime} = \frac{3000\text{ mAh}}{1.344\text{ mA}} \approx 2232\text{ hours} \approx \mathbf{93\text{ days}}$$
* **Shelf Life in Deep Power Down**:
  $$\text{Shelf Life} = \frac{3000\text{ mAh}}{0.007\text{ mA}} \approx 428571\text{ hours} \approx \mathbf{48\text{ years (limited by self-discharge)}}$$
