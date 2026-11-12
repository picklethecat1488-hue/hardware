# Code Review Report: Code Review: hardware

> Automated code review log and findings generated via Quake Code Review Engine.

## Review Overview

| Metric | Details |
| :--- | :--- |
| **Review Date** | `2026-11-08 11:45:41 UTC` |
| **Revisions** | `working` |
| **Overall Verdict** | **`CHANGES_REQUESTED`** |
| **Review Progress** | `0/3 files reviewed (0%)` |
| **Total Comments** | `26 findings` |

## Findings by Severity

| Severity | Count | Meaning |
| :--- | :---: | :--- |
| **[MUST FIX]** | 26 | Must be resolved before merge; bugs, defects, or safety regressions. |
| **[PROPOSAL]** | 0 | Architecture ideas, design proposals, or optional enhancements. |
| **[NIT]** | 0 | Minor formatting, naming, or cosmetic cleanups. |

## File-by-File Review Findings

### [`model/wiring.py`](file:///Users/<username>/gh/hardware/model/wiring.py) — ⏳ `PENDING`

#### **[MUST FIX]** [model/wiring.py:L417-L427](file:///Users/<username>/gh/hardware/model/wiring.py#L417-L427)
<!-- comment-uuid: 29f34525-045c-4672-861d-cb18bb3ef1d3 -->
<!-- comment-commit: working -->

```python
def load_shared_footprints(search_dir: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Load standard footprint definitions from provider.footprints declarative primitives."""
    global _SHARED_FOOTPRINTS_CACHE
    if _SHARED_FOOTPRINTS_CACHE is not None:
        return _SHARED_FOOTPRINTS_CACHE

    from provider.footprints import get_shared_footprints

    _SHARED_FOOTPRINTS_CACHE = get_shared_footprints()
    return _SHARED_FOOTPRINTS_CACHE
```

> **Reviewer (Reviewer)**: can we remove this?

### [`projects/carrier_board/cad.py`](file:///Users/<username>/gh/hardware/projects/carrier_board/cad.py) — ⏳ `PENDING`

#### **[MUST FIX]** [projects/carrier_board/cad.py:L659-L685](file:///Users/<username>/gh/hardware/projects/carrier_board/cad.py#L659-L685)
<!-- comment-uuid: 37285658-901e-48e5-a647-98c029ff4af3 -->
<!-- comment-commit: working -->

```python
@property
    def btle_status_signaling(self) -> dict[str, dict[str, str]]:
        """Return BTLE connection status signaling configuration for RGB LED (D1) and piezo buzzer (U5).

        Status Modes:
            - pairing: LED D1 pulses blue, buzzer U5 emits rising chirp (1kHz -> 2kHz).
              Triggered by capacitive touch input gesture on flex tail or proximity sensor.
            - connected: LED D1 solid cyan, buzzer U5 emits single confirmation tone (2.5kHz).
            - disconnected: LED D1 breathing white, buzzer U5 emits descending tone (2kHz -> 1kHz).
        """
        return {
            "pairing": {
                "led_color": "blue_pulse",
                "buzzer_tone": "chirp_rising_1khz_2khz",
                "trigger": "capacitive_touch_gesture_or_proximity",
            },
            "connected": {
                "led_color": "solid_cyan",
                "buzzer_tone": "confirmation_beep_2.5khz",
                "trigger": "ble_peer_connected",
            },
            "disconnected": {
                "led_color": "breathing_white",
                "buzzer_tone": "descending_tone_2khz_1khz",
                "trigger": "ble_peer_disconnected",
            },
        }
```

> **Reviewer (Reviewer)**: let’s remove this property, there’s no use case for it

### [`projects/carrier_board/carrier_board.py`](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py) — ⏳ `PENDING`

#### **[MUST FIX]** [projects/carrier_board/carrier_board.py:L1326-L1328](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py#L1326-L1328)
<!-- comment-uuid: 98484bb2-40b2-40af-827e-c79ea6f36f68 -->
<!-- comment-commit: working -->

```python
with BuildPcb(name="carrier_board", board_type=BoardType.RIGID) as pcb_ctx:
        with BuildComponents(
```

> **Reviewer (Reviewer)**: This seems bad to me, we’re creating a separate BuildPcb CM just for definign the board wiring. We should remove this second definition!!

#### **[MUST FIX]** [projects/carrier_board/carrier_board.py:L2327-L2349](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py#L2327-L2349)
<!-- comment-uuid: 8b65070e-3c35-4017-9cbd-9b4523445f27 -->
<!-- comment-commit: working -->

```python
all_components = carrier_comps.components + status_comps.components + rf_comps.components
    symbol_table.update(carrier_comps.symbol_table_entries)
    symbol_table.update(status_comps.symbol_table_entries)
    symbol_table.update(rf_comps.symbol_table_entries)

    merged_nets = list(pwr_nets.nets)
    existing_net_names = {n.name for n in merged_nets}
    for sn in sig_nets.nets:
        if sn.name in existing_net_names:
            target = next(n for n in merged_nets if n.name == sn.name)
            for p in sn.pins:
                if p not in target.pins:
                    target.pins.append(p)
        else:
            merged_nets.append(sn)
            existing_net_names.add(sn.name)

    wiring = Wiring.from_models(
        footprints=all_components,
        nets=merged_nets,
        parent_part=parent_part,
        symbol_table=symbol_table,
    )
```

> **Reviewer (Reviewer)**: We def shouldn’t require the user to manipulate the symbol table in their project code. This should all be handled transparently in the provider module when building the wiring object

#### **[MUST FIX]** [projects/carrier_board/carrier_board.py:L2463](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py#L2463)
<!-- comment-uuid: a2a98f2b-1d56-435f-8e23-1219d2e00381 -->
<!-- comment-commit: working -->

```python
symbol_table=sys_comps.symbol_table_entries,
```

> **Reviewer (Reviewer)**: can we remove this parameter from Wiring.from_models while retaining the symbol table functionality

#### **[MUST FIX]** [projects/carrier_board/carrier_board.py:L562-L628](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py#L562-L628)
<!-- comment-uuid: c1616d76-62e9-428e-8f94-640cfef21a69 -->
<!-- comment-commit: working -->

```python
def schematic_config(self) -> SchematicConfig:
        """Return cached SchematicConfig containing all 21 carrier board drawing sheets."""
        return build_carrier_board_schematic_config()

    def sheets(self) -> SchematicConfig:
        """Return schematic drawing sheets configuration."""
        return self.schematic_config

    @cached_property
    def assembly_test_config(self) -> AssemblyTestModel:
        """Return cached assembly test model and instructions."""
        return build_carrier_board_assembly_test()

    def tests(self) -> AssemblyTestModel:
        """Return assembly test model/instructions."""
        return self.assembly_test_config

    @cached_property
    def net_class_config(self) -> List[NetClassModel]:
        """Return cached high-speed and differential net classes."""
        return build_carrier_board_net_classes()

    def net_classes(self) -> List[NetClassModel]:
        """Return high-speed and differential net classes."""
        return self.net_class_config

    @cached_property
    def design_rules_config(self) -> PCBDesignRulesModel:
        """Return cached PCB fabrication and layout design rules."""
        return build_carrier_board_design_rules()

    def design_rules(self) -> PCBDesignRulesModel:
        """Return PCB fabrication design rules."""
        return self.design_rules_config

    @cached_property
    def flex_zone_config(self) -> List[FlexZoneModel]:
        """Return cached flex zones."""
        return build_carrier_board_flex_zones()

    def flex_zones(self) -> List[FlexZoneModel]:
        """Return flex zones."""
        return self.flex_zone_config

    @cached_property
    def obstacle_config(self) -> List[PCBObstacleModel]:
        """Return cached 3D clearance keepouts and obstacles."""
        return build_carrier_board_obstacles()

    def obstacles(self) -> List[PCBObstacleModel]:
        """Return 3D obstacles."""
        return self.obstacle_config

    @cached_property
    def capacitive_sensor_config(self) -> List[CapacitiveElectrodeModel]:
        """Return cached capacitive sensing electrode definitions."""
        return build_carrier_board_capacitive_sensors()

    def capacitive_sensors(self) -> List[CapacitiveElectrodeModel]:
        """Return capacitive sensing electrodes."""
        return self.capacitive_sensor_config

    @property
    def wiring(self) -> Wiring:
        """Return in-memory wiring model."""
        return build_carrier_board_wiring(schematic_config=self.schematic_config)
```

> **Reviewer (Reviewer)**: can we combine these sets of two cached properties into a set of single cached properties?

#### **[MUST FIX]** [projects/carrier_board/carrier_board.py:L687-L704](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py#L687-L704)
<!-- comment-uuid: c6403df6-0b63-40c6-a55d-f3a382f9753e -->
<!-- comment-commit: working -->

```python
bdr.add(self.design_rules())
            with BuildNetClasses() as bnc:
                bnc.add(self.net_classes())
            with BuildFlexZones() as bfz:
                bfz.add(self.flex_zones())
            with BuildObstacles() as bo:
                bo.add(self.obstacles())
            with BuildCapacitiveSensors() as bcs:
                bcs.add(self.capacitive_sensors())
            with BuildStackup() as bst:
                bst.add(self.stackup())
            with BuildWiring() as bw:
                bw.add(self.wiring)
            with BuildSchematic() as bs:
                bs.add(self.sheets())
            with BuildAssemblyTests() as bat:
                bat.add(self.tests())
```

> **Reviewer (Reviewer)**: I’d prefer if the accessors invoked here (e.g. self.design_rules(), self.net_classes() etc. ) were all properties

#### **[MUST FIX]** [projects/carrier_board/carrier_board.py:L731-L745](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py#L731-L745)
<!-- comment-uuid: 1974ef72-82bc-45bd-a765-0f3748897ea2 -->
<!-- comment-commit: working -->

```python
for r in cr.regions:
                if r not in pcb.copper_regions:
                    pcb.copper_regions.append(r)

            with BuildSilkscreen() as silk:
                omitted_designators = [
                    fp.name for fp in self.wiring.footprints if getattr(fp, "omit_silkscreen", False)
                ]
                silk.omit_designators(omitted_designators)
                silk.add(self.silkscreen())
                silk.add(self.silkscreen_graphics())

            with BuildTraces() as bt:
                bt.add(self.traces())
            with BuildVias() as bv:
```

> **Reviewer (Reviewer)**: I’d prefer if the accessors invoked here (e.g. self.design_rules(), self.net_classes() etc. ) were all properties

### [`projects/carrier_board/pcb.py`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py) — ⏳ `PENDING`

#### **[MUST FIX]** [projects/carrier_board/pcb.py:L245-L249](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L245-L249)
<!-- comment-uuid: daa0c72a-746b-4bbd-8326-160a0d4ba8a2 -->
<!-- comment-commit: working -->

```python
if hasattr(pcb, "part") and pcb.part is not None:
            pcb.part.label = "carrier_board"
            pcb.part.urdf_label = "carrier_board"
        pcb.label = "carrier_board"
        pcb.urdf_label = "carrier_board"
```

> **Reviewer (Reviewer)**: can we fold this workaround logic into the BuildPcb context manager?

#### **[MUST FIX]** [projects/carrier_board/pcb.py:L335-L340](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L335-L340)
<!-- comment-uuid: ff7731b0-cbec-470d-ab1e-8de54b8be10b -->
<!-- comment-commit: working -->

```python
if hasattr(tail, "part") and tail.part is not None:
            tail.part.label = "flex_tail"
            tail.part.urdf_label = "flex_tail"
        tail.label = "flex_tail"
        tail.urdf_label = "flex_tail"
```

> **Reviewer (Reviewer)**: Can we fold this workaround logic into the BuilcPcb context manager?

#### **[MUST FIX]** [projects/carrier_board/pcb.py:L436-L447](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L436-L447)
<!-- comment-uuid: 8230e2f9-dfd6-4932-a026-51847d6b45da -->
<!-- comment-commit: working -->

```python
default_routing = self.wiring_path.parent / "routing.yaml"
        if default_routing.exists():
            return PCBAutoRouter.load_routing_yaml(default_routing)

        # 2. Automated routing across all nets via PCBAutoRouter
        base_cfg = self.get_pcb_config_without_routes()
        wiring = Wiring(str(self.wiring_path)) if self.wiring_path.exists() else None
        if base_cfg and wiring:
            router = PCBAutoRouter(base_cfg, wiring)
            return router.route_all_nets()
```

> **Reviewer (Reviewer)**: can we remove this fallback logic? we can just read the fixed routing path directly from settings

#### **[MUST FIX]** [projects/carrier_board/pcb.py:L685-L1369](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L685-L1369)
<!-- comment-uuid: 2391aee4-93f3-4d2a-9a0f-e2f11580a291 -->
<!-- comment-commit: working -->

```python
Component(
                name="U1",
                package="VFBGA-184",
                position=(0.0, 0.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="MCXN947VDFT",
                supplier_pn="568-MCXN947VDFT-ND",
            )
            Component(
                name="U2",
                package="QFN-20",
                position=(18.0, -9.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="IQS7222C101QNR",
                supplier_pn="1790-IQS7222C101QNRCT-ND",
                layer="B.Cu",
            )
            Component(
                name="U11",
                package="MOD-BLE-PCB-ANT",
                position=(0.0, -36.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="NINA-B312-02B",
                supplier_pn="1972-NINA-B312-02B-ND",
            )
            Component(
                name="J15",
                package="pin_header_2x5_1.27mm",
                position=(-14.5, -41.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="DNP",
                supplier_pn="N/A",
                dnp=True,
            )
            Component(
                name="SW2",
                package="SW_PUSH_SMD",
                position=(-14.5, -36.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="PTS645SL43SMTR92LFS",
                supplier_pn="CKN9012CT-ND",
            )
            Component(
                name="J2",
                package="FPC-30P-0.5MM",
                position=(0.0, 38.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="FH12-30S-0.5SH(55)",
                supplier_pn="HFJ130CT-ND",
                shape_ref="carrier_board",
            )
            Component(
                name="J4",
                package="FPC-30P-0.5MM",
                position=(0.0, -22.75, 0.0),
                rotation=(0.0, 0.0, 0.0),
                mpn="N/A - FPC Mating Tab (Male plug for J2)",
                supplier_pn="N/A",
                value="Male Plug for J2",
                dnp=True,
                shape_ref="flex_tail",
            )
            Component(
                name="J13",
                package="JST-PH-2P",
                position=(-23.0, 16.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="S2B-PH-K-S",
                supplier_pn="455-1165-ND",
            )
            Component(
                name="C13",
                package="0603",
                position=(-20.0, 14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A106KP8NNNC",
                supplier_pn="1276-1189-1-ND",
                value="10uF",
            )
            Component(
                name="R1",
                package="0402",
                position=(12.0, -6.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-074K7L",
                supplier_pn="311-4.7KLRCT-ND",
                layer="B.Cu",
                value="4.7k",
            )
            Component(
                name="R2",
                package="0402",
                position=(12.0, -4.5, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-074K7L",
                supplier_pn="311-4.7KLRCT-ND",
                layer="B.Cu",
                value="4.7k",
            )
            Component(
                name="C1",
                package="0402",
                position=(13.5, -14.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                value="0.1uF",
            )
            Component(
                name="C2",
                package="0402",
                position=(-8.0, -4.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                layer="B.Cu",
                value="0.1uF",
            )
            Component(
                name="C3",
                package="0603",
                position=(-13.0, -8.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A106KP8NNNC",
                supplier_pn="1276-1004-1-ND",
                value="10uF",
            )
            Component(
                name="J3",
                package="USB-C-16P",
                position=(-25.0, 0.0, 0.8),
                rotation=(0.0, 0.0, 270.0),
                mpn="TYPE-C-16P-3MD",
                supplier_pn="6652-TYPE-C-16P-3MDTR-ND",
            )
            Component(
                name="R3",
                package="0402",
                position=(-17.0, -4.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-075K1L",
                supplier_pn="311-5.1KLRCT-ND",
                value="5.1k",
            )
            Component(
                name="R4",
                package="0402",
                position=(-17.0, 4.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-075K1L",
                supplier_pn="311-5.1KLRCT-ND",
                value="5.1k",
            )
            Component(
                name="U3",
                package="SOT-23-5",
                position=(-19.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="AP2112K-3.3TRG1",
                supplier_pn="AP2112K-3.3-ND",
            )
            Component(
                name="C6",
                package="0603",
                position=(-24.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A475KP8NNNC",
                supplier_pn="1276-1188-1-ND",
                value="4.7uF",
            )
            Component(
                name="C7",
                package="0603",
                position=(-14.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A475KP8NNNC",
                supplier_pn="1276-1188-1-ND",
                value="4.7uF",
            )
            Component(
                name="U4",
                package="QFN-16-AMP",
                position=(-18.0, 21.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="MAX98357AETE+",
                supplier_pn="MAX98357A-ND",
            )
            Component(
                name="C8",
                package="0603",
                position=(-23.0, 21.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A105KP8NNNC",
                supplier_pn="1276-1002-1-ND",
                value="1uF",
            )
            Component(
                name="U5",
                package="piezo_speaker_12mm",
                position=(-18.0, 31.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CPT-1207-5LTH-T",
                supplier_pn="2223-CPT-1207-5LTH-T-ND",
            )
            Component(
                name="Y1",
                package="XTAL-3225-4P",
                position=(-9.0, 1.25, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="ECS-240-8-30B-CKM",
                supplier_pn="XC1842CT-ND",
            )
            Component(
                name="C9",
                package="0402",
                position=(-12.0, 2.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402JRNPO9BN120",
                supplier_pn="311-1032-1-ND",
                value="12pF",
            )
            Component(
                name="C10",
                package="0402",
                position=(-12.0, 0.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402JRNPO9BN120",
                supplier_pn="311-1032-1-ND",
                value="12pF",
            )
            Component(
                name="R5",
                package="0402",
                position=(-8.0, 8.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-0710KL",
                supplier_pn="311-10.0KLRCT-ND",
                value="10k",
            )
            Component(
                name="C11",
                package="0402",
                position=(-10.5, 8.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                value="0.1uF",
            )
            Component(
                name="R6",
                package="0402",
                position=(-9.0, -12.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-0710KL",
                supplier_pn="311-10.0KLRCT-ND",
                value="10k",
            )
            Component(
                name="C4",
                package="0402",
                position=(8.0, 8.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                value="0.1uF",
            )
            Component(
                name="C5",
                package="0402",
                position=(-6.0, -9.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                value="0.1uF",
            )
            Component(
                name="C12",
                package="0402",
                position=(14.0, -8.0, -0.8),
                rotation=(0.0, 0.0, 180.0),
                mpn="CC0402KRX5R6BB225",
                supplier_pn="311-1440-1-ND",
                layer="B.Cu",
                value="2.2uF",
            )
            Component(
                name="C14",
                package="0402",
                position=(14.0, -10.0, -0.8),
                rotation=(0.0, 0.0, 180.0),
                mpn="CC0402KRX5R6BB225",
                supplier_pn="311-1440-1-ND",
                layer="B.Cu",
                value="2.2uF",
            )
            Component(
                name="C15",
                package="0603",
                position=(13.0, 29.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="GRM188R61A106KE69D",
                supplier_pn="490-10uF-0603-ND",
                layer="B.Cu",
                value="10uF",
            )
            Component(
                name="C16",
                package="0603",
                position=(16.0, 29.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="GRM188R61A106KE69D",
                supplier_pn="490-10uF-0603-ND",
                layer="B.Cu",
                value="10uF",
            )
            Component(
                name="C17",
                package="0402",
                position=(13.0, 32.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                layer="B.Cu",
                value="0.1uF",
            )
            Component(
                name="D8",
                package="SOD-123",
                position=(16.0, 32.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="SMF05CT1G",
                supplier_pn="ONSEMI-SMF05C-ND",
                layer="B.Cu",
                value="TVS_3V3",
            )
            Component(
                name="J5",
                package="pin_header_2x5_1.27mm",
                position=(-18.0, -15.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="FTSH-105-01-L-DV-K",
                supplier_pn="SAMTEC-FTSH105-ND",
            )
            Component(
                name="J6",
                package="JST-PH-6P",
                position=(24.5, 32.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B6B-PH-K-S",
                supplier_pn="455-1708-ND",
            )
            Component(
                name="J7",
                package="JST-PH-6P",
                position=(24.5, 17.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B6B-PH-K-S",
                supplier_pn="455-1708-ND",
            )
            Component(
                name="J8",
                package="JST-PH-6P",
                position=(24.5, 2.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B6B-PH-K-S",
                supplier_pn="455-1708-ND",
            )
            Component(
                name="J9",
                package="JST-PH-7P",
                position=(24.5, -14.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B7B-PH-K-S",
                supplier_pn="455-1709-ND",
                pins=[
                    {
                        "number": "1",
                        "name": "1",
                        "pin_name": "SPI0_CS_N",
                        "label": "SPI0_CS_N",
                        "signal_name": "SPI0_CS_N",
                    },
                    {
                        "number": "2",
                        "name": "2",
                        "pin_name": "SPI0_MISO",
                        "label": "SPI0_MISO",
                        "signal_name": "SPI0_MISO",
                    },
                    {
                        "number": "3",
                        "name": "3",
                        "pin_name": "SPI0_MOSI",
                        "label": "SPI0_MOSI",
                        "signal_name": "SPI0_MOSI",
                    },
                    {
                        "number": "4",
                        "name": "4",
                        "pin_name": "SPI0_SCK",
                        "label": "SPI0_SCK",
                        "signal_name": "SPI0_SCK",
                    },
                    {
                        "number": "5",
                        "name": "5",
                        "pin_name": "EXP_INT_SPI",
                        "label": "EXP_INT_SPI",
                        "signal_name": "EXP_INT_SPI",
                    },
                    {
                        "number": "6",
                        "name": "6",
                        "pin_name": "PERIPH_3V3",
                        "label": "PERIPH_3V3",
                        "signal_name": "PERIPH_3V3",
                    },
                    {"number": "7", "name": "7", "pin_name": "GND", "label": "GND", "signal_name": "GND"},
                ],
            )
            Component(
                name="J10",
                package="JST-PH-7P",
                position=(24.5, -31.0, 0.8),
                rotation=(0.0, 0.0, -90.0),
                mpn="B7B-PH-K-S",
                supplier_pn="455-1709-ND",
                pins=[
                    {"number": "1", "name": "1", "pin_name": "GND", "label": "GND", "signal_name": "GND"},
                    {
                        "number": "2",
                        "name": "2",
                        "pin_name": "PERIPH_3V3",
                        "label": "PERIPH_3V3",
                        "signal_name": "PERIPH_3V3",
                    },
                    {"number": "3", "name": "3", "pin_name": "DTR_N", "label": "DTR_N", "signal_name": "DTR_N"},
                    {"number": "4", "name": "4", "pin_name": "CBUS2", "label": "CBUS2", "signal_name": "CBUS2"},
                    {"number": "5", "name": "5", "pin_name": "CBUS4", "label": "CBUS4", "signal_name": "CBUS4"},
                    {"number": "6", "name": "6", "pin_name": "DCD_N", "label": "DCD_N", "signal_name": "DCD_N"},
                    {"number": "7", "name": "7", "pin_name": "DSR_N", "label": "DSR_N", "signal_name": "DSR_N"},
                ],
            )
            Component(
                name="J14",
                package="pin_header_1x10",
                position=(19.0, -28.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="TSW-110-07-L-S",
                supplier_pn="SAM1034-10-ND",
                pins=[
                    {"number": "1", "name": "1", "pin_name": "GPIO0", "label": "GPIO0", "signal_name": "GPIO0"},
                    {"number": "2", "name": "2", "pin_name": "GPIO1", "label": "GPIO1", "signal_name": "GPIO1"},
                    {"number": "3", "name": "3", "pin_name": "GPIO2", "label": "GPIO2", "signal_name": "GPIO2"},
                    {"number": "4", "name": "4", "pin_name": "GPIO3", "label": "GPIO3", "signal_name": "GPIO3"},
                    {"number": "5", "name": "5", "pin_name": "3V3", "label": "3V3", "signal_name": "3V3"},
                    {"number": "6", "name": "6", "pin_name": "GND", "label": "GND", "signal_name": "GND"},
                    {"number": "7", "name": "7", "pin_name": "CBUS7", "label": "CBUS7", "signal_name": "CBUS7"},
                    {"number": "8", "name": "8", "pin_name": "CBUS5", "label": "CBUS5", "signal_name": "CBUS5"},
                    {"number": "9", "name": "9", "pin_name": "CBUS6", "label": "CBUS6", "signal_name": "CBUS6"},
                    {"number": "10", "name": "10", "pin_name": "CBUS3", "label": "CBUS3", "signal_name": "CBUS3"},
                ],
            )
            Component(
                name="U8",
                package="WSON-8",
                position=(15.0, 4.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="W25N01GVZEIG",
                supplier_pn="W25N01GVZEIG-ND",
            )
            Component(
                name="U6",
                package="TSSOP-16",
                position=(14.0, 14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LP5009PWR",
                supplier_pn="296-LP5009PWR-ND",
            )
            Component(
                name="D1",
                package="LED_RGB_4P",
                position=(17.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CLV1A-FKB-CK1VW1DE1BB7C3C3",
                supplier_pn="CLV1A-FKB-CK1VW1DE1BB7C3C3CT-ND",
            )
            Component(
                name="U7",
                package="TDFN-8",
                position=(-16.0, 16.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="MAX17048G+T10",
                supplier_pn="MAX17048G+T10-ND",
            )
            Component(
                name="U9",
                package="QFN-32",
                position=(-20.0, -32.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="FT232RNQ-REEL",
                supplier_pn="768-FT232RNQ-REEL-ND",
            )
            Component(
                name="U10",
                package="SOT-23-5",
                position=(18.0, 24.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TLV62568DBVR",
                supplier_pn="296-TLV62568DBVR-ND",
            )
            Component(
                name="SW1",
                package="SW_PUSH_SMD",
                position=(0.0, -11.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="PTS645SL43SMTR92LFS",
                supplier_pn="CKN9012CT-ND",
            )

        with BuildComponents(
            name="status_and_overrides", subassembly="status_and_overrides", parent_part=parent_part
        ) as status_comps:
            Component(
                name="JP1",
                package="pin_header_1x2",
                position=(10.5, -15.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TSW-102-07-L-S",
                supplier_pn="SAM1026-02-ND",
            )
            Component(
                name="JP2",
                package="pin_header_1x2",
                position=(10.5, -18.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TSW-102-07-L-S",
                supplier_pn="SAM1026-02-ND",
            )
            Component(
                name="JP3",
                package="pin_header_1x2",
                position=(10.5, -21.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TSW-102-07-L-S",
                supplier_pn="SAM1026-02-ND",
            )
            Component(
                name="JP4",
                package="pin_header_1x2",
                position=(10.5, -23.6, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TSW-102-07-L-S",
                supplier_pn="SAM1026-02-ND",
            )
            Component(
                name="D2",
                package="0603",
                position=(4.0, -24.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
            )
            Component(
                name="D3",
                package="0603",
                position=(4.0, -22.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
            )
            Component(
                name="D4",
                package="0603",
                position=(4.0, -20.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
            )
            Component(
                name="D5",
                package="0603",
                position=(4.0, -18.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
            )
            Component(
                name="D6",
                package="0603",
                position=(4.0, -16.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
            )
            Component(
                name="D7",
                package="0603",
                position=(4.0, -14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
            )
            Component(
                name="R7",
                package="0402",
                position=(6.5, -24.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
            )
            Component(
                name="R8",
                package="0402",
                position=(6.5, -22.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
            )
            Component(
                name="R9",
                package="0402",
                position=(6.5, -20.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
            )
            Component(
                name="R10",
                package="0402",
                position=(6.5, -18.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
            )
            Component(
                name="R11",
                package="0402",
                position=(6.5, -16.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
            )
            Component(
                name="R12",
                package="0402",
                position=(6.5, -14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
            )
            Component(
                name="C18",
                package="0402",
                position=(7.0, -35.2, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="GRM1555C1H301JA01D",
                supplier_pn="490-GRM1555C1H301JA01D-ND",
                value="300pF",
            )
            Component(
                name="C19",
                package="0402",
                position=(7.0, -37.3, 0.8),
                rotation=(0.0, 0.0, 270.0),
                mpn="GRM1555C1H301JA01D",
                supplier_pn="490-GRM1555C1H301JA01D-ND",
                value="300pF",
            )

        with BuildComponents(name="rf_interfaces", subassembly="rf_interfaces", parent_part=parent_part) as rf_comps:
            Component(
                name="J16",
                package="pin_header_1x2",
                position=(13.5, -36.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="22-28-4023",
                supplier_pn="WM6402-ND",
            )
```

> **Reviewer (Reviewer)**: canw e simplify these using the autoincrement component designator functionality you showed me?

#### **[MUST FIX]** [projects/carrier_board/pcb.py:L1052-L1534](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L1052-L1534)
<!-- comment-uuid: e83d0b2a-22a7-4507-bb9b-cf80f64db3b4 -->
<!-- comment-commit: working -->

```python
Component(
                name="J9",
                package="JST-PH-7P",
                position=(24.5, -14.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B7B-PH-K-S",
                supplier_pn="455-1709-ND",
                pins=[
                    {
                        "number": "1",
                        "name": "1",
                        "pin_name": "SPI0_CS_N",
                        "label": "SPI0_CS_N",
                        "signal_name": "SPI0_CS_N",
                    },
                    {
                        "number": "2",
                        "name": "2",
                        "pin_name": "SPI0_MISO",
                        "label": "SPI0_MISO",
                        "signal_name": "SPI0_MISO",
                    },
                    {
                        "number": "3",
                        "name": "3",
                        "pin_name": "SPI0_MOSI",
                        "label": "SPI0_MOSI",
                        "signal_name": "SPI0_MOSI",
                    },
                    {
                        "number": "4",
                        "name": "4",
                        "pin_name": "SPI0_SCK",
                        "label": "SPI0_SCK",
                        "signal_name": "SPI0_SCK",
                    },
                    {
                        "number": "5",
                        "name": "5",
                        "pin_name": "EXP_INT_SPI",
                        "label": "EXP_INT_SPI",
                        "signal_name": "EXP_INT_SPI",
                    },
                    {
                        "number": "6",
                        "name": "6",
                        "pin_name": "PERIPH_3V3",
                        "label": "PERIPH_3V3",
                        "signal_name": "PERIPH_3V3",
                    },
                    {"number": "7", "name": "7", "pin_name": "GND", "label": "GND", "signal_name": "GND"},
                ],
            )
            Component(
                name="J10",
                package="JST-PH-7P",
                position=(24.5, -31.0, 0.8),
                rotation=(0.0, 0.0, -90.0),
                mpn="B7B-PH-K-S",
                supplier_pn="455-1709-ND",
                pins=[
                    {"number": "1", "name": "1", "pin_name": "GND", "label": "GND", "signal_name": "GND"},
                    {
                        "number": "2",
                        "name": "2",
                        "pin_name": "PERIPH_3V3",
                        "label": "PERIPH_3V3",
                        "signal_name": "PERIPH_3V3",
                    },
                    {"number": "3", "name": "3", "pin_name": "DTR_N", "label": "DTR_N", "signal_name": "DTR_N"},
                    {"number": "4", "name": "4", "pin_name": "CBUS2", "label": "CBUS2", "signal_name": "CBUS2"},
                    {"number": "5", "name": "5", "pin_name": "CBUS4", "label": "CBUS4", "signal_name": "CBUS4"},
                    {"number": "6", "name": "6", "pin_name": "DCD_N", "label": "DCD_N", "signal_name": "DCD_N"},
                    {"number": "7", "name": "7", "pin_name": "DSR_N", "label": "DSR_N", "signal_name": "DSR_N"},
                ],
            )
            Component(
                name="J14",
                package="pin_header_1x10",
                position=(19.0, -28.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="TSW-110-07-L-S",
                supplier_pn="SAM1034-10-ND",
                pins=[
                    {"number": "1", "name": "1", "pin_name": "GPIO0", "label": "GPIO0", "signal_name": "GPIO0"},
                    {"number": "2", "name": "2", "pin_name": "GPIO1", "label": "GPIO1", "signal_name": "GPIO1"},
                    {"number": "3", "name": "3", "pin_name": "GPIO2", "label": "GPIO2", "signal_name": "GPIO2"},
                    {"number": "4", "name": "4", "pin_name": "GPIO3", "label": "GPIO3", "signal_name": "GPIO3"},
                    {"number": "5", "name": "5", "pin_name": "3V3", "label": "3V3", "signal_name": "3V3"},
                    {"number": "6", "name": "6", "pin_name": "GND", "label": "GND", "signal_name": "GND"},
                    {"number": "7", "name": "7", "pin_name": "CBUS7", "label": "CBUS7", "signal_name": "CBUS7"},
                    {"number": "8", "name": "8", "pin_name": "CBUS5", "label": "CBUS5", "signal_name": "CBUS5"},
                    {"number": "9", "name": "9", "pin_name": "CBUS6", "label": "CBUS6", "signal_name": "CBUS6"},
                    {"number": "10", "name": "10", "pin_name": "CBUS3", "label": "CBUS3", "signal_name": "CBUS3"},
                ],
            )
            Component(
                name="U8",
                package="WSON-8",
                position=(15.0, 4.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="W25N01GVZEIG",
                supplier_pn="W25N01GVZEIG-ND",
            )
            Component(
                name="U6",
                package="TSSOP-16",
                position=(14.0, 14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LP5009PWR",
                supplier_pn="296-LP5009PWR-ND",
            )
            Component(
                name="D1",
                package="LED_RGB_4P",
                position=(17.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CLV1A-FKB-CK1VW1DE1BB7C3C3",
                supplier_pn="CLV1A-FKB-CK1VW1DE1BB7C3C3CT-ND",
            )
            Component(
                name="U7",
                package="TDFN-8",
                position=(-16.0, 16.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="MAX17048G+T10",
                supplier_pn="MAX17048G+T10-ND",
            )
            Component(
                name="U9",
                package="QFN-32",
                position=(-20.0, -32.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="FT232RNQ-REEL",
                supplier_pn="768-FT232RNQ-REEL-ND",
            )
            Component(
                name="U10",
                package="SOT-23-5",
                position=(18.0, 24.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TLV62568DBVR",
                supplier_pn="296-TLV62568DBVR-ND",
            )
            Component(
                name="SW1",
                package="SW_PUSH_SMD",
                position=(0.0, -11.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="PTS645SL43SMTR92LFS",
                supplier_pn="CKN9012CT-ND",
            )

        with BuildComponents(
            name="status_and_overrides", subassembly="status_and_overrides", parent_part=parent_part
        ) as status_comps:
            Component(
                name="JP1",
                package="pin_header_1x2",
                position=(10.5, -15.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TSW-102-07-L-S",
                supplier_pn="SAM1026-02-ND",
            )
            Component(
                name="JP2",
                package="pin_header_1x2",
                position=(10.5, -18.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TSW-102-07-L-S",
                supplier_pn="SAM1026-02-ND",
            )
            Component(
                name="JP3",
                package="pin_header_1x2",
                position=(10.5, -21.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TSW-102-07-L-S",
                supplier_pn="SAM1026-02-ND",
            )
            Component(
                name="JP4",
                package="pin_header_1x2",
                position=(10.5, -23.6, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TSW-102-07-L-S",
                supplier_pn="SAM1026-02-ND",
            )
            Component(
                name="D2",
                package="0603",
                position=(4.0, -24.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
            )
            Component(
                name="D3",
                package="0603",
                position=(4.0, -22.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
            )
            Component(
                name="D4",
                package="0603",
                position=(4.0, -20.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
            )
            Component(
                name="D5",
                package="0603",
                position=(4.0, -18.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
            )
            Component(
                name="D6",
                package="0603",
                position=(4.0, -16.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
            )
            Component(
                name="D7",
                package="0603",
                position=(4.0, -14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
            )
            Component(
                name="R7",
                package="0402",
                position=(6.5, -24.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
            )
            Component(
                name="R8",
                package="0402",
                position=(6.5, -22.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
            )
            Component(
                name="R9",
                package="0402",
                position=(6.5, -20.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
            )
            Component(
                name="R10",
                package="0402",
                position=(6.5, -18.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
            )
            Component(
                name="R11",
                package="0402",
                position=(6.5, -16.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
            )
            Component(
                name="R12",
                package="0402",
                position=(6.5, -14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
            )
            Component(
                name="C18",
                package="0402",
                position=(7.0, -35.2, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="GRM1555C1H301JA01D",
                supplier_pn="490-GRM1555C1H301JA01D-ND",
                value="300pF",
            )
            Component(
                name="C19",
                package="0402",
                position=(7.0, -37.3, 0.8),
                rotation=(0.0, 0.0, 270.0),
                mpn="GRM1555C1H301JA01D",
                supplier_pn="490-GRM1555C1H301JA01D-ND",
                value="300pF",
            )

        with BuildComponents(name="rf_interfaces", subassembly="rf_interfaces", parent_part=parent_part) as rf_comps:
            Component(
                name="J16",
                package="pin_header_1x2",
                position=(13.5, -36.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="22-28-4023",
                supplier_pn="WM6402-ND",
            )

        with BuildWiring(name="power_nets") as pwr_nets:
            Net(
                name="GND",
                pins=[
                    ["U1", "J8"],
                    ["U2", "VSS"],
                    ["U11", "GND"],
                    ["J2", "GND"],
                    ["J2", "MP1"],
                    ["J2", "MP2"],
                    ["C1", "2"],
                    ["C2", "2"],
                    ["C3", "2"],
                    ["C15", "2"],
                    ["C16", "2"],
                    ["C17", "2"],
                    ["D8", "2"],
                    ["C18", "2"],
                    ["C19", "2"],
                    ["J15", "3"],
                    ["J15", "5"],
                    ["J3", "GND"],
                    ["J3", "GND2"],
                    ["J3", "SHIELD1"],
                    ["J3", "SHIELD2"],
                    ["J3", "SHIELD3"],
                    ["J3", "SHIELD4"],
                    ["R3", "2"],
                    ["R4", "2"],
                    ["U3", "2"],
                    ["C6", "2"],
                    ["C7", "2"],
                    ["Y1", "2"],
                    ["Y1", "4"],
                    ["C9", "2"],
                    ["C10", "2"],
                    ["C11", "2"],
                    ["R6", "2"],
                    ["C4", "2"],
                    ["C5", "2"],
                    ["C12", "2"],
                    ["C14", "2"],
                    ["U2", "EP"],
                    ["J13", "2"],
                    ["C13", "2"],
                    ["U8", "4"],
                    ["U8", "EP"],
                    ["U7", "1"],
                    ["U7", "4"],
                    ["U7", "6"],
                    ["U7", "EP"],
                    ["U6", "3"],
                    ["U6", "4"],
                    ["U6", "9"],
                    ["U6", "10"],
                    ["U6", "11"],
                    ["U6", "12"],
                    ["U6", "13"],
                    ["U6", "14"],
                    ["U6", "15"],
                    ["U9", "7"],
                    ["U9", "18"],
                    ["U9", "21"],
                    ["U9", "25"],
                    ["U9", "26"],
                    ["U9", "29"],
                    ["U9", "EP"],
                    ["J5", "3"],
                    ["J5", "5"],
                    ["J5", "7"],
                    ["J5", "8"],
                    ["J5", "9"],
                    ["U10", "2", "GND"],
                    ["U4", "GND", "GND"],
                    ["U4", "GAIN", "GAIN"],
                    ["C8", "2"],
                    ["J6", "5"],
                    ["J6", "6"],
                    ["J7", "5"],
                    ["J7", "6"],
                    ["J8", "5"],
                    ["J8", "6"],
                    ["J9", "7", "GND"],
                    ["J10", "1", "GND"],
                    ["J14", "6", "GND"],
                    ["SW1", "2"],
                    ["R7", "2"],
                    ["R8", "2"],
                    ["R9", "2"],
                    ["R10", "2"],
                    ["R11", "2"],
                    ["R12", "2"],
                    ["SW2", "2"],
                ],
                color="#475569",
            )
            Net(
                name="3V3",
                pins=[
                    ["U1", "H8"],
                    ["U2", "VDD"],
                    ["U2", "MCLR"],
                    ["U11", "3V3"],
                    ["U11", "VCC"],
                    ["J2", "3V3"],
                    ["R1", "1"],
                    ["R2", "1"],
                    ["C1", "1"],
                    ["C2", "1"],
                    ["C3", "1"],
                    ["C15", "1"],
                    ["C16", "1"],
                    ["C17", "1"],
                    ["D8", "1"],
                    ["U3", "5"],
                    ["C7", "1"],
                    ["U4", "VDD", "VDD"],
                    ["C8", "1"],
                    ["R5", "1"],
                    ["C4", "1"],
                    ["C5", "1"],
                    ["U8", "8"],
                    ["U7", "3"],
                    ["U6", "5"],
                    ["U6", "16"],
                    ["D1", "4"],
                    ["U9", "4"],
                    ["U9", "19"],
                    ["J5", "1"],
                    ["U10", "1", "VIN"],
                    ["J14", "5", "3V3"],
                    ["JP3", "1"],
                    ["D4", "1"],
                    ["D7", "1"],
                    ["J15", "1"],
                ],
                color="#dc2626",
            )
            Net(
                name="VBUS",
                pins=[["J3", "VBUS"], ["J3", "VBUS2"], ["U9", "20"], ["JP4", "1"], ["D3", "1"]],
                color="#b91c1c",
                priority=24,
            )
            Net(
                name="VBAT",
                pins=[["J13", "1"], ["C13", "1"], ["U3", "4"], ["U7", "2"], ["D2", "1"]],
                color="#f59e0b",
                priority=24,
            )
            Net(
                name="PERIPH_3V3",
                pins=[
                    ["U10", "5", "VOUT"],
                    ["J6", "1"],
                    ["J7", "1"],
                    ["J8", "1"],
                    ["J9", "6", "PERIPH_3V3"],
                    ["J10", "2", "PERIPH_3V3"],
                    ["D6", "1"],
                ],
                color="#dc2626",
                priority=25,
            )
```

> **Reviewer (Reviewer)**: why isn’t the net routing stuff using the [mcu.pin("VSS"), mcu_caps[0].pin(2), mcu_caps[1].pin(2), mcu_caps[2].pin(2)] syntax you showed me for better type safety? also, we should add a .named_pin property to the class of mcu_caps[2]

#### **[MUST FIX]** [projects/carrier_board/pcb.py:L1880-L1982](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L1880-L1982)
<!-- comment-uuid: 9b5c8e33-32ff-4995-86ea-be0a0ba9a515 -->
<!-- comment-commit: working -->

```python
{
            "name": "btle_host",
            "package": "board",
            "position": [-80.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "dimensions": [22.0, 50.0, 1.6],
            "color": "cornflowerblue",
            "label": {"text": "BTLE Wireless Host", "position": [-16.0, 0.0, 0.0], "align": ["max", "center"]},
            "pins": [
                {"name": "BLE_RX", "label": "RX (1Mb/s)", "side": "right"},
                {"name": "BLE_TX", "label": "TX (1Mb/s)", "side": "right"},
                {"name": "BLE_RTS", "label": "RTS", "side": "right"},
                {"name": "BLE_CTS", "label": "CTS", "side": "right"},
                {"name": "3V3", "label": "3V3", "side": "right"},
                {"name": "GND", "label": "GND", "side": "right"},
            ],
        },
        {
            "name": "usb_c",
            "package": "board",
            "position": [0.0, -80.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "dimensions": [30.0, 18.0, 1.6],
            "color": "darkorange",
            "label": {"text": "USB-C Source (5V)", "position": [0.0, -14.0, 0.0], "align": ["center", "max"]},
            "pins": [
                {"name": "VBUS", "label": "VBUS (5V)", "side": "top"},
                {"name": "CC", "label": "CC1/CC2", "side": "top"},
                {"name": "USB_D", "label": "D+/D-", "side": "top"},
                {"name": "GND", "label": "GND", "side": "top"},
            ],
        },
        {
            "name": "carrier_pcb",
            "package": "board",
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "dimensions": [60.0, 90.0, 1.6],
            "color": "forestgreen",
            "label": {"text": "Test Board Carrier PCB", "position": [0.0, 0.0, 0.0], "align": ["center", "center"]},
            "pins": [
                {"name": "BLE_RX", "label": "BLE_RX", "side": "left"},
                {"name": "BLE_TX", "label": "BLE_TX", "side": "left"},
                {"name": "BLE_RTS", "label": "BLE_RTS", "side": "left"},
                {"name": "BLE_CTS", "label": "BLE_CTS", "side": "left"},
                {"name": "BLE_3V3", "label": "3V3", "side": "left"},
                {"name": "BLE_GND", "label": "GND", "side": "left"},
                {"name": "USB_VBUS", "label": "VBUS", "side": "bottom"},
                {"name": "USB_CC", "label": "CC", "side": "bottom"},
                {"name": "USB_DATA", "label": "USB_D", "side": "bottom"},
                {"name": "USB_GND", "label": "GND", "side": "bottom"},
                {"name": "FPC_TX0", "label": "CAP_TX0", "side": "top"},
                {"name": "FPC_RX0", "label": "CAP_RX0", "side": "top"},
                {"name": "FPC_TX1", "label": "CAP_TX1", "side": "top"},
                {"name": "FPC_RX1", "label": "CAP_RX1", "side": "top"},
                {"name": "FPC_TX2", "label": "CAP_TX2", "side": "top"},
                {"name": "FPC_RX2", "label": "CAP_RX2", "side": "top"},
                {"name": "FPC_RX3", "label": "CAP_RX3", "side": "top"},
                {"name": "FPC_SHIELD", "label": "SHIELD", "side": "top"},
                {"name": "FPC_GND", "label": "GND", "side": "top"},
            ],
        },
        {
            "name": "flex_tail",
            "package": "board",
            "position": [0.0, 85.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "dimensions": [24.0, 54.0, 0.2],
            "color": "goldenrod",
            "label": {"text": "Capacitive Flex Tail Sensor", "position": [0.0, 32.0, 0.0], "align": ["center", "min"]},
            "pins": [
                {"name": "TX0", "label": "CH0_TX", "side": "bottom"},
                {"name": "RX0", "label": "CH0_RX", "side": "bottom"},
                {"name": "TX1", "label": "CH1_TX", "side": "bottom"},
                {"name": "RX1", "label": "CH1_RX", "side": "bottom"},
                {"name": "TX2", "label": "CH2_TX", "side": "bottom"},
                {"name": "RX2", "label": "CH2_RX", "side": "bottom"},
                {"name": "RX3", "label": "CH3_PROX", "side": "bottom"},
                {"name": "SHIELD", "label": "SHIELD", "side": "bottom"},
                {"name": "GND", "label": "GND", "side": "bottom"},
            ],
        },
    ]
    sys_nets_raw = [
        {"name": "ble_tx", "color": "blue", "pins": [["btle_host", "BLE_TX"], ["carrier_pcb", "BLE_RX"]]},
        {"name": "ble_rx", "color": "blue", "pins": [["btle_host", "BLE_RX"], ["carrier_pcb", "BLE_TX"]]},
        {"name": "ble_rts", "color": "purple", "pins": [["btle_host", "BLE_RTS"], ["carrier_pcb", "BLE_CTS"]]},
        {"name": "ble_cts", "color": "purple", "pins": [["btle_host", "BLE_CTS"], ["carrier_pcb", "BLE_RTS"]]},
        {"name": "pwr_3v3", "color": "red", "pins": [["btle_host", "3V3"], ["carrier_pcb", "BLE_3V3"]]},
        {"name": "gnd_ble", "color": "black", "pins": [["btle_host", "GND"], ["carrier_pcb", "BLE_GND"]]},
        {"name": "vbus_5v", "color": "red", "pins": [["usb_c", "VBUS"], ["carrier_pcb", "USB_VBUS"]]},
        {"name": "usb_cc", "color": "orange", "pins": [["usb_c", "CC"], ["carrier_pcb", "USB_CC"]]},
        {"name": "usb_data", "color": "cyan", "pins": [["usb_c", "USB_D"], ["carrier_pcb", "USB_DATA"]]},
        {"name": "gnd_usb", "color": "black", "pins": [["usb_c", "GND"], ["carrier_pcb", "USB_GND"]]},
        {"name": "cap_tx0", "color": "magenta", "pins": [["carrier_pcb", "FPC_TX0"], ["flex_tail", "TX0"]]},
        {"name": "cap_rx0", "color": "green", "pins": [["carrier_pcb", "FPC_RX0"], ["flex_tail", "RX0"]]},
        {"name": "cap_tx1", "color": "magenta", "pins": [["carrier_pcb", "FPC_TX1"], ["flex_tail", "TX1"]]},
        {"name": "cap_rx1", "color": "green", "pins": [["carrier_pcb", "FPC_RX1"], ["flex_tail", "RX1"]]},
        {"name": "cap_tx2", "color": "magenta", "pins": [["carrier_pcb", "FPC_TX2"], ["flex_tail", "TX2"]]},
        {"name": "cap_rx2", "color": "green", "pins": [["carrier_pcb", "FPC_RX2"], ["flex_tail", "RX2"]]},
        {"name": "cap_rx3", "color": "green", "pins": [["carrier_pcb", "FPC_RX3"], ["flex_tail", "RX3"]]},
        {"name": "cap_shield", "color": "yellow", "pins": [["carrier_pcb", "FPC_SHIELD"], ["flex_tail", "SHIELD"]]},
        {"name": "gnd_flex", "color": "black", "pins": [["carrier_pcb", "FPC_GND"], ["flex_tail", "GND"]]},
```

> **Reviewer (Reviewer)**: can we also use the [mcu.pin("VSS"), mcu_caps[0].pin(2), mcu_caps[1].pin(2), mcu_caps[2].pin(2)] syntax here

#### **[MUST FIX]** [projects/carrier_board/pcb.py:L1991-L3032](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L1991-L3032)
<!-- comment-uuid: 12ad5f49-3cc0-4879-9ae1-75943108e8b5 -->
<!-- comment-commit: working -->

```python
def build_carrier_board_pcb_config(provider: Optional[Any] = None) -> PCBConfig:
    """Build strongly-typed PCBConfig for Carrier Board and Flex Tail."""
    raw_pcb = {
        "name": "CarrierBoard",
        "board_type": "rigid-flex",
        "revision": "2.0",
        "shape_ref": "carrier_board",
        "sheet_size": "A4",
        "omitted_silkscreen_designators": [
            "D2",
            "D3",
            "D4",
            "D5",
            "D6",
            "D7",
            "JP1",
            "JP2",
            "JP3",
            "JP4",
            "R7",
            "R8",
            "R9",
            "R10",
            "R11",
            "R12",
            "SW1",
        ],
        "obstacles": [
            {
                "name": "U1",
                "shape": "box",
                "dimensions_mm": [12.0, 12.0, 2.0],
                "position_mm": [0.0, 0.0, 1.8],
                "description": "MCU BGA at center",
            },
            {
                "name": "U11",
                "shape": "box",
                "dimensions_mm": [10.0, 15.0, 2.23],
                "position_mm": [0.0, -36.0, 1.915],
                "description": "BTLE transceiver module with integrated PCB antenna",
            },
            {
                "name": "J15",
                "shape": "box",
                "dimensions_mm": [6.35, 3.81, 5.0],
                "position_mm": [-14.5, -41.0, 3.3],
                "description": "SWD recovery header",
            },
            {
                "name": "ble_antenna_keepout",
                "shape": "box",
                "dimensions_mm": [16.0, 5.0, 1.6],
                "position_mm": [0.0, -42.0, 0.8],
                "description": "RF ground plane keepout for integrated PCB antenna",
            },
            {
                "name": "J2",
                "shape": "box",
                "dimensions_mm": [25.0, 5.0, 2.0],
                "position_mm": [0.0, 38.0, 1.8],
                "description": "Hirose FPC-30P connector",
            },
            {
                "name": "J3",
                "shape": "box",
                "dimensions_mm": [9.0, 9.0, 4.0],
                "position_mm": [-25.0, 0.0, 2.8],
                "description": "USB Type-C receptacle",
            },
            {
                "name": "J5",
                "shape": "box",
                "dimensions_mm": [6.0, 12.0, 6.0],
                "position_mm": [-21.0, -7.0, 3.8],
                "description": "SWD 10-pin micro-header",
            },
            {
                "name": "J13",
                "shape": "box",
                "dimensions_mm": [6.0, 8.0, 7.0],
                "position_mm": [-23.0, 16.0, 4.3],
                "description": "Battery 2-pin JST-PH connector",
            },
            {
                "name": "J9",
                "shape": "box",
                "dimensions_mm": [6.0, 17.0, 7.0],
                "position_mm": [24.5, -14.0, 4.3],
                "description": "Expansion header on right edge",
            },
            {
                "name": "J10",
                "shape": "box",
                "dimensions_mm": [6.0, 17.0, 7.0],
                "position_mm": [24.5, -31.0, 4.3],
                "description": "Expansion header on right edge",
            },
            {
                "name": "flex_vacuum_plate",
                "shape": "box",
                "dimensions_mm": [30.0, 60.0, 4.0],
                "position_mm": [0.0, 0.0, -2.0],
                "description": "Flex tail vacuum fixture support plate",
            },
            {
                "name": "J4",
                "shape": "box",
                "dimensions_mm": [18.0, 5.0, 2.4],
                "position_mm": [0.0, -22.75, 1.2],
                "description": "FPC-30P interface connector on flex tail",
            },
        ],
        "design_rules": {
            "min_clearance_mm": 0.03,
            "min_fine_pitch_clearance_mm": 0.03,
            "fine_pitch_pad_threshold_mm": 0.35,
            "min_track_width_mm": 0.1,
            "default_track_width_mm": 0.12,
            "min_copper_edge_clearance_mm": 0.15,
            "min_hole_to_hole_mm": 0.03,
            "min_hole_clearance_mm": 0.03,
            "min_via_diameter_mm": 0.35,
            "default_via_diameter_mm": 0.36,
            "default_via_drill_mm": 0.16,
            "via_penalty": 2.0,
            "pad_to_mask_clearance_mm": 0.0,
            "rule_severities": {
                "hole_to_hole": "ignore",
                "hole_near_hole": "ignore",
                "lib_footprint_issues": "ignore",
                "text_height": "ignore",
                "silk_overlap": "ignore",
                "silk_over_copper": "ignore",
                "track_dangling": "ignore",
                "silk_edge_clearance": "ignore",
            },
        },
        "net_classes": [
            {
                "name": "BTLE_HIGH_SPEED_UART",
                "trace_width_mm": 0.12,
                "clearance_mm": 0.12,
                "via_dia_mm": 0.36,
                "via_drill_mm": 0.16,
                "interface_type": "uart",
                "description": "High-speed 1Mb/s UART interface between U1 MCU and U11 BTLE module",
                "single_nets": ["BLE_RX", "BLE_RTS", "BLE_TX", "BLE_CTS"],
            },
            {
                "name": "RF_2GHZ",
                "trace_width_mm": 0.13,
                "clearance_mm": 0.2,
                "via_dia_mm": 0.36,
                "via_drill_mm": 0.16,
                "interface_type": "rf",
                "coplanar_waveguide": True,
                "ground_gap_mm": 0.22,
                "keepout_clearance_mm": 1.5,
                "single_nets": ["RF_ANT_FEED"],
            },
            {
                "name": "I2C_BUS",
                "trace_width_mm": 0.12,
                "clearance_mm": 0.12,
                "via_dia_mm": 0.36,
                "via_drill_mm": 0.16,
                "interface_type": "digital",
                "single_nets": ["I2C_SDA", "I2C_SCL"],
            },
            {
                "name": "PWR_3V3",
                "trace_width_mm": 0.12,
                "clearance_mm": 0.2,
                "via_dia_mm": 0.36,
                "via_drill_mm": 0.16,
                "interface_type": "power",
                "single_nets": ["3V3"],
            },
        ],
        "flex_zones": [
            {
                "name": "flex_tail_ribbon",
                "start_x_mm": 30.0,
                "length_mm": 54.0,
                "substrate_thickness_mm": 0.05,
                "coverlay_thickness_mm": 0.025,
                "coverlay_color": "black",
                "min_bend_radius_mm": 3.0,
                "shape_ref": "flex_tail",
            }
        ],
        "capacitive_sensors": [
            {
                "name": "SLIDER_SEGMENT_1",
                "channel_id": 0,
                "electrode_type": "mutual",
                "shape": "interdigital",
                "area_mm": [10.0, 4.5],
                "pitch_mm": 1.2,
                "gap_mm": 0.3,
                "center_mm": [0.0, -13.0],
                "drive_shield": False,
                "hatch_ground_pour": True,
                "hatch_line_width_mm": 0.15,
                "hatch_pitch_mm": 0.5,
                "tx_pin": "CAP_TX0",
                "rx_pin": "CAP_RX0",
                "threshold_raw": 2200,
                "shape_ref": "flex_tail",
            },
            {
                "name": "SLIDER_SEGMENT_2",
                "channel_id": 1,
                "electrode_type": "mutual",
                "shape": "interdigital",
                "area_mm": [10.0, 4.5],
                "pitch_mm": 1.2,
                "gap_mm": 0.3,
                "center_mm": [0.0, -8.0],
                "drive_shield": False,
                "hatch_ground_pour": True,
                "hatch_line_width_mm": 0.15,
                "hatch_pitch_mm": 0.5,
                "tx_pin": "CAP_TX0",
                "rx_pin": "CAP_RX1",
                "threshold_raw": 2200,
                "shape_ref": "flex_tail",
            },
            {
                "name": "SLIDER_SEGMENT_3",
                "channel_id": 2,
                "electrode_type": "mutual",
                "shape": "interdigital",
                "area_mm": [10.0, 4.5],
                "pitch_mm": 1.2,
                "gap_mm": 0.3,
                "center_mm": [0.0, -3.0],
                "drive_shield": False,
                "hatch_ground_pour": True,
                "hatch_line_width_mm": 0.15,
                "hatch_pitch_mm": 0.5,
                "tx_pin": "CAP_TX1",
                "rx_pin": "CAP_RX1",
                "threshold_raw": 2500,
                "shape_ref": "flex_tail",
            },
            {
                "name": "SLIDER_SEGMENT_4",
                "channel_id": 3,
                "electrode_type": "mutual",
                "shape": "interdigital",
                "area_mm": [10.0, 4.5],
                "pitch_mm": 1.2,
                "gap_mm": 0.3,
                "center_mm": [0.0, 2.0],
                "drive_shield": False,
                "hatch_ground_pour": True,
                "hatch_line_width_mm": 0.15,
                "hatch_pitch_mm": 0.5,
                "tx_pin": "CAP_TX1",
                "rx_pin": "CAP_RX2",
                "threshold_raw": 2500,
                "shape_ref": "flex_tail",
            },
            {
                "name": "SLIDER_SEGMENT_5",
                "channel_id": 4,
                "electrode_type": "mutual",
                "shape": "interdigital",
                "area_mm": [10.0, 4.5],
                "pitch_mm": 1.2,
                "gap_mm": 0.3,
                "center_mm": [0.0, 7.0],
                "drive_shield": False,
                "hatch_ground_pour": True,
                "hatch_line_width_mm": 0.15,
                "hatch_pitch_mm": 0.5,
                "tx_pin": "CAP_TX2",
                "rx_pin": "CAP_RX2",
                "threshold_raw": 2800,
                "shape_ref": "flex_tail",
            },
            {
                "name": "ACTION_BUTTON",
                "channel_id": 5,
                "electrode_type": "mutual",
                "shape": "interdigital",
                "area_mm": [8.0, 6.0],
                "center_mm": [0.0, 18.0],
                "drive_shield": False,
                "hatch_ground_pour": True,
                "hatch_line_width_mm": 0.15,
                "hatch_pitch_mm": 0.5,
                "tx_pin": "CAP_TX2",
                "rx_pin": "CAP_RX2",
                "threshold_raw": 2000,
                "shape_ref": "flex_tail",
                "pitch_mm": 1.2,
                "gap_mm": 0.3,
            },
            {
                "name": "PROXIMITY_SENSOR",
                "channel_id": 6,
                "electrode_type": "self",
                "shape": "loop",
                "area_mm": [14.2, 42.0],
                "center_mm": [0.0, 3.5],
                "drive_shield": False,
                "hatch_ground_pour": False,
                "rx_pin": "CAP_RX3",
                "threshold_raw": 1500,
                "shape_ref": "flex_tail",
            },
        ],
        "schematic_sheets": [
            {
                "title": "USB-C Power & Battery Interface",
                "description": "USB-C connector, CC pull-down termination, Li-Ion battery connector, and MAX17048 fuel gauge",
                "components": ["J3", "R3", "R4", "J13", "C13", "U7", "C7", "C16"],
                "pin_breakouts": {
                    "J3": ["VBUS", "VBUS2", "GND", "GND2", "CC1", "CC2", "SHIELD1", "SHIELD2"],
                    "J13": ["1", "2"],
                    "C13": ["1", "2"],
                    "U7": ["1", "2", "3", "4", "5", "7", "8"],
                    "R3": ["1", "2"],
                    "R4": ["1", "2"],
                    "C7": ["1", "2"],
                    "C16": ["1", "2"],
                },
            },
            {
                "title": "3.3V Power Regulation & Distribution",
                "description": "Low-dropout linear voltage regulator with C8 bulk filtering, and system decoupling",
                "layout": {"cols_per_row": 4, "grid_positions": {"U3": [0, 0], "C8": [0, 1]}},
                "components": ["U3", "C6", "C1", "C2", "C3", "C8"],
                "pin_breakouts": {
                    "U3": ["1", "2", "3", "4", "5"],
                    "C8": ["1", "2"],
                    "C1": ["1", "2"],
                    "C2": ["1", "2"],
                    "C3": ["1", "2"],
                    "C6": ["1", "2"],
                },
            },
            {
                "title": "Peripheral Power Regulation & Gating",
                "description": "Dedicated 3.3V peripheral buck regulator (TLV62568) and power gating enable control",
                "components": ["U1", "U10", "D8", "C15"],
                "pin_sides": {
                    "U1": {"L5": "right"},
                    "U10": {"3": "left", "1": "left", "2": "left", "5": "right"},
                    "D8": {"1": "left", "2": "right"},
                },
                "pin_breakouts": {"U1": ["L5"], "U10": ["3", "1", "2", "5"], "D8": ["1", "2"], "C15": ["1", "2"]},
            },
            {
                "title": "Microcontroller Core, Clock & Reset",
                "description": "Primary microcontroller core, 24MHz crystal oscillator, power bypass, reset and boot circuitry",
                "layout": {"col_gap": 65.0},
                "components": ["U1", "Y1", "C9", "C10", "R5", "C11", "R6", "C4", "C5"],
                "pin_sides": {
                    "U1": {"J8": "left", "H8": "left", "F2": "right", "F1": "right", "F3": "left", "C14": "left"},
                    "Y1": {"1": "left", "3": "left", "2": "right", "4": "right"},
                },
                "pin_breakouts": {
                    "U1": ["J8", "H8", "F2", "F1", "F3", "C14"],
                    "Y1": ["1", "2", "3", "4"],
                    "C9": ["1", "2"],
                    "C10": ["1", "2"],
                    "R5": ["1", "2"],
                    "C11": ["1", "2"],
                    "R6": ["1", "2"],
                    "C4": ["1", "2"],
                    "C5": ["1", "2"],
                },
            },
            {
                "title": "External Serial NAND Storage Subsystem",
                "description": "Winbond W25N01GV 1Gb SLC serial NAND flash on FlexSPI Port A",
                "components": ["U1", "U8", "C17"],
                "pin_sides": {
                    "U1": {
                        "B17": "right",
                        "D14": "right",
                        "E14": "right",
                        "F15": "right",
                        "F17": "right",
                        "F16": "right",
                    },
                    "U8": {
                        "1": "left",
                        "6": "left",
                        "5": "left",
                        "2": "left",
                        "3": "left",
                        "7": "left",
                        "8": "right",
                        "4": "right",
                    },
                },
                "pin_breakouts": {
                    "U1": ["B17", "D14", "E14", "F15", "F17", "F16"],
                    "U8": ["1", "6", "5", "2", "3", "7", "8", "4"],
                    "C17": ["1", "2"],
                },
            },
            {
                "title": "Telemetry & Debug Communications",
                "description": "FTDI FT232RNQ high-speed USB-to-UART serial bridge and ARM 10-pin SWD debug micro-header",
                "components": ["U1", "U9", "J5"],
                "pin_sides": {
                    "U1": {
                        "B6": "right",
                        "A6": "right",
                        "F10": "right",
                        "E10": "right",
                        "A17": "right",
                        "A16": "right",
                    },
                    "U9": {
                        "1": "left",
                        "5": "left",
                        "3": "left",
                        "11": "left",
                        "4": "right",
                        "15": "right",
                        "16": "right",
                        "18": "right",
                        "19": "right",
                        "20": "right",
                        "21": "right",
                        "22": "right",
                        "23": "right",
                        "25": "right",
                        "26": "right",
                        "29": "right",
                        "7": "right",
                    },
                    "J5": {"1": "left", "2": "left", "3": "left", "4": "left", "5": "left"},
                },
                "pin_breakouts": {
                    "U1": ["B6", "A6", "F10", "E10", "A17", "A16"],
                    "U9": [
                        "1",
                        "5",
                        "3",
                        "11",
                        "4",
                        "15",
                        "16",
                        "18",
                        "19",
                        "20",
                        "21",
                        "22",
                        "23",
                        "25",
                        "26",
                        "29",
                        "7",
                    ],
                    "J5": ["1", "2", "3", "4", "5"],
                },
            },
            {
                "title": "User Interface & Status Indication",
                "description": "TI LP5009 9-channel I2C constant-current LED driver and high-brightness RGB status indicator",
                "components": ["U1", "U6", "D1"],
                "pin_sides": {
                    "U1": {"A10": "right", "B10": "right"},
                    "U6": {
                        "1": "left",
                        "2": "left",
                        "5": "left",
                        "3": "left",
                        "4": "left",
                        "15": "left",
                        "6": "right",
                        "7": "right",
                        "8": "right",
                        "16": "right",
                    },
                    "D1": {"1": "left", "2": "left", "3": "left", "4": "left"},
                },
                "pin_breakouts": {
                    "U1": ["A10", "B10"],
                    "U6": ["1", "2", "5", "3", "4", "15", "6", "7", "8", "16"],
                    "D1": ["1", "2", "3", "4"],
                },
            },
            {
                "title": "Capacitive Sensing & Control (Azoteq IQS7222A)",
                "description": "Azoteq IQS7222A ProxFusion controller, 5-button slider, action button, and proximity sensing flex tail, and I2C bus",
                "layout": {"col_gap": 65.0},
                "components": ["U1", "U2", "J2", "R1", "R2", "C12", "C14"],
                "pin_sides": {
                    "U1": {"C5": "right", "C6": "right", "C4": "right"},
                    "U2": {
                        "SCL": "left",
                        "SDA": "left",
                        "RDY": "left",
                        "VDD": "left",
                        "MCLR": "left",
                        "VSS": "left",
                        "EP": "left",
                        "CR0": "right",
                        "CR1": "right",
                        "CR2": "right",
                        "CR3": "right",
                        "CR4": "right",
                        "CR5": "right",
                        "CR6": "right",
                        "CR7": "right",
                        "CT8": "right",
                        "OUTA": "right",
                    },
                    "J2": {
                        "CAP_RX0": "left",
                        "CAP_RX1": "left",
                        "CAP_RX2": "left",
                        "CAP_RX3": "left",
                        "CAP_TX0": "left",
                        "CAP_TX1": "left",
                        "CAP_TX2": "left",
                        "CAP_SHIELD": "left",
                    },
                },
                "pin_breakouts": {
                    "U1": ["C5", "C6", "C4"],
                    "U2": [
                        "SCL",
                        "SDA",
                        "RDY",
                        "VDD",
                        "MCLR",
                        "VSS",
                        "EP",
                        "CR0",
                        "CR1",
                        "CR2",
                        "CR3",
                        "CR4",
                        "CR5",
                        "CR6",
                        "CR7",
                        "CT8",
                    ],
                    "J2": ["CAP_RX0", "CAP_RX1", "CAP_RX2", "CAP_RX3", "CAP_TX0", "CAP_TX1", "CAP_TX2", "CAP_SHIELD"],
                    "R1": ["1", "2"],
                    "R2": ["1", "2"],
                    "C12": ["1", "2"],
                    "C14": ["1", "2"],
                },
            },
            {
                "title": "Audio Subsystem",
                "description": "MAX98357A I2S/PDM digital audio amplifier and piezo speaker",
                "layout": {"cols_per_row": 3, "grid_positions": {"U1": [0, 0], "U4": [0, 1], "U5": [0, 2]}},
                "components": ["U4", "U5", "U1"],
                "pin_sides": {
                    "U1": {"G2": "right", "H1": "right", "J1": "right", "L4": "right"},
                    "U4": {
                        "BCLK": "left",
                        "DIN": "left",
                        "LRCLK": "left",
                        "SD_MODE": "left",
                        "VDD": "left",
                        "GND": "left",
                        "GAIN": "left",
                        "OUTP": "right",
                        "OUTN": "right",
                    },
                    "U5": {"1": "left", "2": "left"},
                },
                "pin_breakouts": {
                    "U1": ["G2", "H1", "J1", "L4"],
                    "U4": ["BCLK", "DIN", "LRCLK", "SD_MODE", "VDD", "GND", "GAIN", "OUTP", "OUTN"],
                    "U5": ["1", "2"],
                },
            },
            {
                "title": "High-Speed BTLE UART & Wireless Interface",
                "description": "BTLE transceiver module (U11) with 1Mb/s high-speed UART link, flow control, cap-touch pairing trigger, and integrated PCB antenna",
                "layout": {
                    "cols_per_row": 3,
                    "col_gap": 50.0,
                    "grid_positions": {"U1": [0, 0], "U11": [0, 1], "J16": [0, 2]},
                },
                "components": ["U11", "U1", "C18", "C19", "J16"],
                "pin_sides": {
                    "U1": {"T2": "left", "T1": "left", "T3": "left", "T4": "left"},
                    "U11": {
                        "RXD": "left",
                        "RTS": "left",
                        "TXD": "left",
                        "CTS": "left",
                        "RESET_N": "left",
                        "GND": "right",
                        "3V3": "right",
                        "NFC1": "right",
                        "NFC2": "right",
                    },
                    "C18": {"1": "left", "2": "right"},
                    "C19": {"1": "left", "2": "right"},
                    "J16": {"1": "left", "2": "left"},
                },
                "pin_breakouts": {
                    "U11": ["RXD", "RTS", "TXD", "CTS", "RESET_N", "GND", "3V3", "NFC1", "NFC2"],
                    "C18": ["1", "2"],
                    "C19": ["1", "2"],
                    "J16": ["1", "2"],
                    "U1": ["T2", "T1", "T3", "T4"],
                },
            },
            {
                "title": "BTLE Programming & Reset Interface (J15, SW2)",
                "description": "BLE SWD debug/recovery header (J15, DNP) and manual reset push button switch (SW2) for the NINA-B312 BLE module",
                "layout": {
                    "cols_per_row": 2,
                    "col_gap": 50.0,
                    "top_row_y": 110.0,
                    "grid_positions": {"J15": [0, 0], "SW2": [0, 1]},
                },
                "components": ["J15", "SW2"],
                "pin_sides": {
                    "J15": {"1": "left", "2": "left", "3": "left", "4": "left", "5": "left"},
                    "SW2": {"1": "left", "2": "right"},
                },
                "pin_breakouts": {"J15": ["1", "2", "3", "4", "5"], "SW2": ["1", "2"]},
            },
            {
                "title": "I2C Peripheral Expansion Interface (J6)",
                "description": "Primary I2C peripheral expansion connector (JST-PH-6P)",
                "components": ["U1", "J6"],
                "pin_sides": {
                    "U1": {"A1": "right", "B1": "right", "B2": "right"},
                    "J6": {"1": "left", "2": "left", "3": "left", "4": "left", "5": "left", "6": "left"},
                },
                "pin_breakouts": {"U1": ["B2", "A1", "B1"], "J6": ["1", "2", "3", "4", "5", "6"]},
            },
            {
                "title": "I3C Primary Controller Expansion Interface (J7)",
                "description": "High-speed I3C0 primary peripheral expansion connector (JST-PH-6P)",
                "components": ["U1", "J7"],
                "pin_sides": {
                    "U1": {"B8": "right", "A8": "right", "C8": "right"},
                    "J7": {"1": "left", "2": "left", "3": "left", "4": "left", "5": "left", "6": "left"},
                },
                "pin_breakouts": {"U1": ["B8", "A8", "C8"], "J7": ["1", "2", "3", "4", "5", "6"]},
            },
            {
                "title": "I3C Secondary Controller Expansion Interface (J8)",
                "description": "High-speed I3C1 secondary peripheral expansion connector (JST-PH-6P)",
                "components": ["U1", "J8"],
                "pin_sides": {
                    "U1": {"E4": "right", "F6": "right", "F4": "right"},
                    "J8": {"1": "left", "2": "left", "3": "left", "4": "left", "5": "left", "6": "left"},
                },
                "pin_breakouts": {"U1": ["E4", "F6", "F4"], "J8": ["1", "2", "3", "4", "5", "6"]},
            },
            {
                "title": "SPI Master Expansion Interface (J9)",
                "description": "High-speed SPI peripheral expansion connector (JST-PH-7P)",
                "components": ["U1", "J9"],
                "pin_sides": {
                    "U1": {"R9": "right", "R8": "right", "T7": "right", "T6": "right", "T8": "right"},
                    "J9": {"1": "left", "2": "left", "3": "left", "4": "left", "5": "left", "6": "left", "7": "left"},
                },
                "pin_breakouts": {"U1": ["R9", "R8", "T7", "T6", "T8"], "J9": ["1", "2", "3", "4", "5", "6", "7"]},
            },
            {
                "title": "UART & Control Expansion Interface (J10)",
                "description": "FTDI auxiliary UART and modem control expansion connector (JST-PH-7P)",
                "components": ["U9", "J10"],
                "pin_sides": {
                    "U9": {"2": "right", "13": "right", "12": "right", "10": "right", "9": "right"},
                    "J10": {
                        "1": "right",
                        "2": "right",
                        "3": "left",
                        "4": "left",
                        "5": "left",
                        "6": "left",
                        "7": "left",
                    },
                },
                "pin_breakouts": {"U9": ["2", "13", "12", "10", "9"], "J10": ["2", "1", "3", "4", "5", "6", "7"]},
            },
            {
                "title": "General Purpose I/O Expansion Header",
                "description": "10-pin multipurpose microcontroller GPIO expansion header",
                "components": ["U1", "J14"],
                "pin_sides": {
                    "U1": {"M8": "left", "N8": "left", "N10": "right", "T10": "right"},
                    "J14": {
                        "1": "left",
                        "2": "left",
                        "3": "left",
                        "4": "left",
                        "5": "left",
                        "6": "left",
                        "7": "right",
                        "8": "right",
                        "9": "right",
                        "10": "right",
                    },
                },
                "pin_breakouts": {
                    "U1": ["M8", "N8", "N10", "T10"],
                    "J14": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
                },
            },
            {
                "title": "Status and Overrides - MCU Reset & Bootloader",
                "description": "Manual reset pushbutton and FTDI hardware programming jumpers",
                "layout": {
                    "cols_per_row": 3,
                    "top_row_y": 152.0,
                    "grid_positions": {"SW1": [0, 0], "JP1": [0, 1], "JP2": [0, 2]},
                },
                "components": ["SW1", "JP1", "JP2"],
                "pin_sides": {
                    "SW1": {"1": "left", "2": "left"},
                    "JP1": {"1": "left", "2": "left"},
                    "JP2": {"1": "left", "2": "left"},
                },
            },
            {
                "title": "Status and Overrides - Power Isolation & Boot Mode",
                "description": "Boot configuration and USB charger isolation jumpers",
                "layout": {"cols_per_row": 2, "top_row_y": 152.0, "grid_positions": {"JP3": [0, 0], "JP4": [0, 1]}},
                "components": ["JP3", "JP4"],
                "pin_sides": {"JP3": {"1": "left", "2": "left"}, "JP4": {"1": "left", "2": "left"}},
            },
            {
                "title": "Status and Overrides - Primary Power LEDs",
                "description": "Visual rail power indicators and current limiters for VBAT, VBUS, and 3V3",
                "layout": {
                    "cols_per_row": 3,
                    "top_row_y": 168.0,
                    "row_step_y": 54.0,
                    "grid_positions": {
                        "D2": [0, 0],
                        "D3": [0, 1],
                        "D4": [0, 2],
                        "R7": [1, 0],
                        "R8": [1, 1],
                        "R9": [1, 2],
                    },
                },
                "components": ["D2", "D3", "D4", "R7", "R8", "R9"],
                "pin_sides": {
                    "D2": {"1": "left", "2": "left"},
                    "D3": {"1": "left", "2": "left"},
                    "D4": {"1": "left", "2": "left"},
                },
            },
            {
                "title": "Status and Overrides - Peripheral & MCU LEDs",
                "description": "Subsystem activity indicators and current limiters for Audio, Peripherals, and MCU",
                "layout": {
                    "cols_per_row": 3,
                    "top_row_y": 168.0,
                    "row_step_y": 54.0,
                    "grid_positions": {
                        "D5": [0, 0],
                        "D6": [0, 1],
                        "D7": [0, 2],
                        "R10": [1, 0],
                        "R11": [1, 1],
                        "R12": [1, 2],
                    },
                },
                "components": ["D5", "D6", "D7", "R10", "R11", "R12"],
                "pin_sides": {
                    "D5": {"1": "left", "2": "left"},
                    "D6": {"1": "left", "2": "left"},
                    "D7": {"1": "left", "2": "left"},
                },
            },
        ],
        "assembly_test": {
            "test_fixture": "flying_probe",
            "pass_criteria": "all_steps_within_tolerance",
            "instructions": [
                {
                    "step_id": "TEST_CONTINUITY_GND",
                    "description": "Verify solid low-impedance ground plane continuity across all copper layers",
                    "test_type": "continuity",
                    "net_or_points": ["GND", "IN1_GND", "IN3_PWR"],
                    "expected_nominal": 0.05,
                    "tolerance_pct": 20.0,
                    "unit": "ohm",
                },
                {
                    "step_id": "TEST_UART_BLE_SPEED",
                    "description": "Measure BTLE high-speed 1Mb/s UART signal integrity on BLE_TX / BLE_RX",
                    "test_type": "voltage",
                    "net_or_points": ["BLE_TX", "BLE_RX"],
                    "expected_nominal": 3.3,
                    "tolerance_pct": 3.0,
                    "unit": "V",
                    "stimulus": "1Mb/s PRBS UART serial test",
                },
                {
                    "step_id": "TEST_CAP_SENSE_CHAN0",
                    "description": "Measure baseline mutual capacitance on liquid level electrode Channel 0",
                    "test_type": "capacitance",
                    "net_or_points": ["CAP_TX0", "CAP_RX0"],
                    "expected_nominal": 12.5,
                    "tolerance_pct": 15.0,
                    "unit": "pF",
                    "stimulus": "250kHz 1.8V square",
                },
                {
                    "step_id": "TEST_CAP_SENSE_CHAN1",
                    "description": "Measure baseline mutual capacitance on liquid level electrode Channel 1",
                    "test_type": "capacitance",
                    "net_or_points": ["CAP_TX1", "CAP_RX1"],
                    "expected_nominal": 14.0,
                    "tolerance_pct": 15.0,
                    "unit": "pF",
                    "stimulus": "250kHz 1.8V square",
                },
                {
                    "step_id": "TEST_CAP_SENSE_CHAN2",
                    "description": "Measure baseline mutual capacitance on liquid level electrode Channel 2",
                    "test_type": "capacitance",
                    "net_or_points": ["CAP_TX2", "CAP_RX2"],
                    "expected_nominal": 15.5,
                    "tolerance_pct": 15.0,
                    "unit": "pF",
                    "stimulus": "250kHz 1.8V square",
                },
                {
                    "step_id": "TEST_CAP_SENSE_CHAN3",
                    "description": "Measure baseline self capacitance on liquid proximity electrode Channel 3",
                    "test_type": "capacitance",
                    "net_or_points": ["CAP_RX3"],
                    "expected_nominal": 8.0,
                    "tolerance_pct": 15.0,
                    "unit": "pF",
                    "stimulus": "250kHz 1.8V square",
                },
            ],
        },
    }
    cfg = PCBConfig(**raw_pcb)
    # Attach assembly test steps
    cb_steps = [
        AssemblyTestStepModel(**s)
        for s in [
            {
                "step_id": "TEST_CONTINUITY_GND",
                "description": "Verify solid low-impedance ground plane continuity across all copper layers",
                "test_type": "continuity",
                "net_name": "GND",
                "pad_a_mm": [-18.0, -22.0],
                "pad_b_mm": [-25.0, -4.2],
                "nominal": 0.05,
                "tolerance_pct": 20.0,
                "unit": "ohm",
                "stimulus": "100mA 4-wire Kelvin DC",
                "measured": 0.048,
            },
            {
                "step_id": "TEST_UART_BLE_SPEED",
                "description": "Measure BTLE high-speed 1Mb/s UART signal integrity on BLE_TX / BLE_RX",
                "test_type": "voltage",
                "net_name": "BLE_UART",
                "pad_a_mm": [-6.0, -22.0],
                "pad_b_mm": [-10.0, -22.0],
                "nominal": 3.3,
                "tolerance_pct": 3.0,
                "unit": "V",
                "stimulus": "1Mb/s PRBS UART serial transceiver test",
                "measured": 3.3,
            },
            {
                "step_id": "TEST_RAIL_3V3",
                "description": "Verify regulated system 3.3V power distribution rail",
                "test_type": "voltage",
                "net_name": "3V3",
                "pad_a_mm": [-10.0, -26.0],
                "pad_b_mm": [-18.0, -22.0],
                "nominal": 3.3,
                "tolerance_pct": 3.0,
                "unit": "V",
                "stimulus": "DC power rail regulation probe",
                "measured": 3.31,
            },
            {
                "step_id": "TEST_RAIL_VBAT",
                "description": "Verify battery input sensing rail continuity to charger",
                "test_type": "voltage",
                "net_name": "VBAT",
                "pad_a_mm": [-18.0, -26.0],
                "pad_b_mm": [-18.0, -22.0],
                "nominal": 3.7,
                "tolerance_pct": 5.0,
                "unit": "V",
                "stimulus": "Battery charge domain sensor",
                "measured": 3.72,
            },
            {
                "step_id": "TEST_IMP_USB_DIFF",
                "description": "Measure USB 2.0 / USB-C differential impedance on DP/DM",
                "test_type": "diff_pair",
                "net_name": "USB_DP_DM",
                "pad_a_mm": [-25.0, 0.5],
                "pad_b_mm": [-25.0, -0.5],
                "nominal": 90.0,
                "tolerance_pct": 10.0,
                "unit": "ohm",
                "stimulus": "200ps TDR step differential pulse",
                "measured": 89.8,
            },
            {
                "step_id": "TEST_UART_BLE_FLOW_CTRL",
                "description": "Verify BTLE hardware flow control handshake on BLE_RTS / BLE_CTS",
                "test_type": "voltage",
                "net_name": "BLE_FLOW_CTRL",
                "pad_a_mm": [-14.0, -22.0],
                "pad_b_mm": [-2.0, -22.0],
                "nominal": 3.3,
                "tolerance_pct": 3.0,
                "unit": "V",
                "stimulus": "Hardware RTS/CTS assert handshake probe",
                "measured": 3.3,
            },
            {
                "step_id": "TEST_I2C_PULLUPS",
                "description": "Measure I2C SDA/SCL pull-up resistance to 3.3V rail",
                "test_type": "resistance",
                "net_name": "I2C_BUS",
                "pad_a_mm": [14.0, -4.0],
                "pad_b_mm": [18.0, -4.0],
                "nominal": 4700.0,
                "tolerance_pct": 5.0,
                "unit": "ohm",
                "stimulus": "1.0V DC precision Ohmmeter",
                "measured": 4705.0,
            },
        ]
    ]
    flex_steps = [
        AssemblyTestStepModel(**s)
        for s in [
            {
                "step_id": "TEST_CAP_SENSE_CHAN0",
                "description": "Measure baseline mutual capacitance on liquid level electrode Channel 0",
                "test_type": "capacitance",
                "net_name": "CAP_CHAN0",
                "pad_a_mm": [0.0, -6.25],
                "pad_b_mm": [-3.0, -6.25],
                "nominal": 12.5,
                "tolerance_pct": 15.0,
                "unit": "pF",
                "stimulus": "250kHz 1.8V square wave",
                "measured": 12.6,
            },
            {
                "step_id": "TEST_CAP_SENSE_CHAN1",
                "description": "Measure baseline mutual capacitance on liquid level electrode Channel 1",
                "test_type": "capacitance",
                "net_name": "CAP_CHAN1",
                "pad_a_mm": [0.0, 5.25],
                "pad_b_mm": [-3.0, 5.25],
                "nominal": 14.0,
                "tolerance_pct": 15.0,
                "unit": "pF",
                "stimulus": "250kHz 1.8V square wave",
                "measured": 14.1,
            },
            {
                "step_id": "TEST_CAP_SENSE_CHAN2",
                "description": "Measure baseline mutual capacitance on liquid level electrode Channel 2",
                "test_type": "capacitance",
                "net_name": "CAP_CHAN2",
                "pad_a_mm": [0.0, 16.75],
                "pad_b_mm": [-3.0, 16.75],
                "nominal": 15.5,
                "tolerance_pct": 15.0,
                "unit": "pF",
                "stimulus": "250kHz 1.8V square wave",
                "measured": 15.4,
            },
            {
                "step_id": "TEST_CAP_SENSE_CHAN3",
                "description": "Measure baseline self capacitance on liquid proximity electrode Channel 3",
                "test_type": "capacitance",
                "net_name": "CAP_CHAN3",
                "pad_a_mm": [0.0, 24.75],
                "pad_b_mm": [0.0, -22.75],
                "nominal": 8.0,
                "tolerance_pct": 15.0,
                "unit": "pF",
                "stimulus": "250kHz 1.8V square wave self-cap",
                "measured": 8.1,
            },
            {
                "step_id": "TEST_CONTINUITY_TAIL_GND",
                "description": "Verify ground plane guard ring continuity along flex tail contour",
                "test_type": "continuity",
                "net_name": "FLEX_GND",
                "pad_a_mm": [-7.0, -20.0],
                "pad_b_mm": [7.0, -20.0],
                "nominal": 0.08,
                "tolerance_pct": 20.0,
                "unit": "ohm",
                "stimulus": "100mA 4-wire Kelvin DC",
                "measured": 0.078,
            },
            {
                "step_id": "TEST_CAP_MUTUAL_TOUCH_CHAN0",
                "description": "Simulate human finger touch proximity on liquid level Channel 0 mutual capacitance electrode",
                "test_type": "mutual_cap",
                "net_name": "CAP_CHAN0",
                "pad_a_mm": [0.0, -6.25],
                "pad_b_mm": [-3.0, -6.25],
                "nominal": 15.8,
                "tolerance_pct": 15.0,
                "unit": "pF",
                "stimulus": "Simulated finger proximity 250kHz 1.8V dielectric perturb",
                "measured": 15.9,
            },
            {
                "step_id": "TEST_CAP_MUTUAL_TOUCH_CHAN1",
                "description": "Simulate human finger touch proximity on liquid level Channel 1 mutual capacitance electrode",
                "test_type": "mutual_cap",
                "net_name": "CAP_CHAN1",
                "pad_a_mm": [0.0, 5.25],
                "pad_b_mm": [-3.0, 5.25],
                "nominal": 17.5,
                "tolerance_pct": 15.0,
                "unit": "pF",
                "stimulus": "Simulated finger proximity 250kHz 1.8V dielectric perturb",
                "measured": 17.6,
            },
        ]
    ]
```

> **Reviewer (Reviewer)**: All of this metadatastuff should be converted to the build123d context managers under a top-level PcbMetadata manager. rather than having a centrally defined PCB config table, the PCB config should be defined per-BuildPcb CM and merged at build time into a single PcbCOnfig model

#### **[MUST FIX]** [projects/carrier_board/pcb.py:L2841](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L2841)
<!-- comment-uuid: 2c1c4800-e218-4313-b35b-27470743ea02 -->
<!-- comment-commit: working -->

```python
cb_steps = [
```

> **Reviewer (Reviewer)**: > what happened to the per-Pcb BuildAssemblyTestSteps CM we talked about?

#### **[MUST FIX]** [projects/carrier_board/pcb.py:L2937-L3032](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L2937-L3032)
<!-- comment-uuid: dab9a6a0-a33a-47f9-acb3-6a7c02f63970 -->
<!-- comment-commit: working -->

```python
flex_steps = [
        AssemblyTestStepModel(**s)
        for s in [
            {
                "step_id": "TEST_CAP_SENSE_CHAN0",
                "description": "Measure baseline mutual capacitance on liquid level electrode Channel 0",
                "test_type": "capacitance",
                "net_name": "CAP_CHAN0",
                "pad_a_mm": [0.0, -6.25],
                "pad_b_mm": [-3.0, -6.25],
                "nominal": 12.5,
                "tolerance_pct": 15.0,
                "unit": "pF",
                "stimulus": "250kHz 1.8V square wave",
                "measured": 12.6,
            },
            {
                "step_id": "TEST_CAP_SENSE_CHAN1",
                "description": "Measure baseline mutual capacitance on liquid level electrode Channel 1",
                "test_type": "capacitance",
                "net_name": "CAP_CHAN1",
                "pad_a_mm": [0.0, 5.25],
                "pad_b_mm": [-3.0, 5.25],
                "nominal": 14.0,
                "tolerance_pct": 15.0,
                "unit": "pF",
                "stimulus": "250kHz 1.8V square wave",
                "measured": 14.1,
            },
            {
                "step_id": "TEST_CAP_SENSE_CHAN2",
                "description": "Measure baseline mutual capacitance on liquid level electrode Channel 2",
                "test_type": "capacitance",
                "net_name": "CAP_CHAN2",
                "pad_a_mm": [0.0, 16.75],
                "pad_b_mm": [-3.0, 16.75],
                "nominal": 15.5,
                "tolerance_pct": 15.0,
                "unit": "pF",
                "stimulus": "250kHz 1.8V square wave",
                "measured": 15.4,
            },
            {
                "step_id": "TEST_CAP_SENSE_CHAN3",
                "description": "Measure baseline self capacitance on liquid proximity electrode Channel 3",
                "test_type": "capacitance",
                "net_name": "CAP_CHAN3",
                "pad_a_mm": [0.0, 24.75],
                "pad_b_mm": [0.0, -22.75],
                "nominal": 8.0,
                "tolerance_pct": 15.0,
                "unit": "pF",
                "stimulus": "250kHz 1.8V square wave self-cap",
                "measured": 8.1,
            },
            {
                "step_id": "TEST_CONTINUITY_TAIL_GND",
                "description": "Verify ground plane guard ring continuity along flex tail contour",
                "test_type": "continuity",
                "net_name": "FLEX_GND",
                "pad_a_mm": [-7.0, -20.0],
                "pad_b_mm": [7.0, -20.0],
                "nominal": 0.08,
                "tolerance_pct": 20.0,
                "unit": "ohm",
                "stimulus": "100mA 4-wire Kelvin DC",
                "measured": 0.078,
            },
            {
                "step_id": "TEST_CAP_MUTUAL_TOUCH_CHAN0",
                "description": "Simulate human finger touch proximity on liquid level Channel 0 mutual capacitance electrode",
                "test_type": "mutual_cap",
                "net_name": "CAP_CHAN0",
                "pad_a_mm": [0.0, -6.25],
                "pad_b_mm": [-3.0, -6.25],
                "nominal": 15.8,
                "tolerance_pct": 15.0,
                "unit": "pF",
                "stimulus": "Simulated finger proximity 250kHz 1.8V dielectric perturb",
                "measured": 15.9,
            },
            {
                "step_id": "TEST_CAP_MUTUAL_TOUCH_CHAN1",
                "description": "Simulate human finger touch proximity on liquid level Channel 1 mutual capacitance electrode",
                "test_type": "mutual_cap",
                "net_name": "CAP_CHAN1",
                "pad_a_mm": [0.0, 5.25],
                "pad_b_mm": [-3.0, 5.25],
                "nominal": 17.5,
                "tolerance_pct": 15.0,
                "unit": "pF",
                "stimulus": "Simulated finger proximity 250kHz 1.8V dielectric perturb",
                "measured": 17.6,
            },
        ]
    ]
```

> **Reviewer (Reviewer)**: we should define a CM for assembly test steps that can reference nets and pins on a PCB object directly for better type safety

#### **[MUST FIX]** [projects/carrier_board/pcb.py:L3033-L3070](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L3033-L3070)
<!-- comment-uuid: c89703be-d087-40c5-833d-db435143c6c2 -->
<!-- comment-commit: working -->

```python
cfg.test_steps = cb_steps + flex_steps

    if provider is None:
        from .provider import CarrierBoardProvider

        provider = CarrierBoardProvider()

    s = provider.stackup()
    if isinstance(s, BuildStackup):
        cfg.stackup = s.to_model()
    elif isinstance(s, StackupModel):
        cfg.stackup = s

    cfg.mounting_holes = list(provider.mounting_holes())
    cfg.silkscreen_texts = list(provider.silkscreen())
    if hasattr(provider, "silkscreen_graphics"):
        cfg.silkscreen_graphics = list(provider.silkscreen_graphics())
    p_regions = provider.copper_regions()
    if p_regions:
        cfg.copper_regions = list(p_regions.regions if isinstance(p_regions, BuildCopperRegions) else p_regions)

    p_tps = provider.test_points()
    if p_tps:
        cfg.test_points = list(p_tps.test_points if isinstance(p_tps, BuildTestPoints) else p_tps)
    cfg.traces = list(provider.traces())
    cfg.vias = list(provider.vias())

    if cfg.shape_ref and cfg.shape_ref in provider.part:
        part_builder = provider.part[cfg.shape_ref]
        part_obj = part_builder(cfg.shape_ref, None, Mode.DEFAULT)
        pcb_meta = getattr(part_obj, "pcb_metadata", None)
        if pcb_meta is None and hasattr(part_obj, "part"):
            pcb_meta = getattr(part_obj.part, "pcb_metadata", None)
        if pcb_meta is not None:
            cfg.dimensions_mm = pcb_meta.dimensions_mm

    w = build_carrier_board_wiring()
    cfg.symbol_table = dict(w.symbol_table)
```

> **Reviewer (Reviewer)**: the code for instantinating the PCB config should be moved to the provider module. there’s no reason to keep redefining it for every project

### [`projects/cat_fountain/pcb.py`](file:///Users/<username>/gh/hardware/projects/cat_fountain/pcb.py) — ⏳ `PENDING`

#### **[MUST FIX]** [projects/cat_fountain/pcb.py:L2](file:///Users/<username>/gh/hardware/projects/cat_fountain/pcb.py#L2)
<!-- comment-uuid: 9d002d93-8530-4fe7-9aa5-7e90241b6cc6 -->
<!-- comment-commit: working -->

> **Reviewer (Reviewer)**: please apply the improvements discussed in [`@projects/carrier_board/pcb.py`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py) to this listing

#### **[MUST FIX]** [projects/cat_fountain/pcb.py:L336](file:///Users/<username>/gh/hardware/projects/cat_fountain/pcb.py#L336)
<!-- comment-uuid: ee5ceaa2-2d92-4aff-82dd-800735a5069e -->
<!-- comment-commit: working -->

```python
symbol_table=layout.symbol_table_entries,
```

> **Reviewer (Reviewer)**: can we remove this parameter from Wiring.from_models while retaining the symbol table functionality

### [`provider/pcb/test_steps.py`](file:///Users/<username>/gh/hardware/provider/pcb/test_steps.py) — ⏳ `PENDING`

#### **[MUST FIX]** [provider/pcb/test_steps.py:L12](file:///Users/<username>/gh/hardware/provider/pcb/test_steps.py#L12)
<!-- comment-uuid: b6026d89-c299-4de7-bf1e-30f7e0a3db93 -->
<!-- comment-commit: working -->

```python
class BuildTestSteps:
```

> **Reviewer (Reviewer)**: this is a good start, but doesn’t go far enough to provide a safe environment to build PCB config and assembly testing steps. see my comments in [`@projects/carrier_board/pcb.py`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py)

### [`provider/provider.py`](file:///Users/<username>/gh/hardware/provider/provider.py) — ⏳ `PENDING`

#### **[MUST FIX]** [provider/provider.py:L314-L348](file:///Users/<username>/gh/hardware/provider/provider.py#L314-L348)
<!-- comment-uuid: 4f134659-55da-4f50-af53-913c1fd58b5f -->
<!-- comment-commit: working -->

```python
@property
    def wiring_path(self) -> Path:
        """Return the path to the provider's wiring specification file."""
        w_yaml = self.project_dir / "wiring.yaml"
        if w_yaml.exists():
            return w_yaml
        pcb_py = self.project_dir / "pcb.py"
        if pcb_py.exists():
            return pcb_py
        return w_yaml

    @property
    def wiring(self) -> Optional[Any]:
        """Return the provider's Wiring container (in-memory or loaded from wiring_path)."""
        if hasattr(self, "_wiring") and self._wiring is not None:
            return self._wiring

        for p_name, part_builder in getattr(self, "part", {}).items():
            try:
                part_obj = part_builder(p_name, None, Mode.DEFAULT)
                w = getattr(part_obj, "wiring", None)
                if w is not None:
                    return w
                if hasattr(part_obj, "part") and getattr(part_obj.part, "wiring", None) is not None:
                    return part_obj.part.wiring
            except Exception:
                pass

        w_path = self.wiring_path
        if w_path and w_path.exists() and w_path.suffix == ".yaml":
            from model.wiring import Wiring

            return Wiring(w_path)

        return None
```

> **Reviewer (Reviewer)**: let’s remove the wiring_path property and use a provider property for returning wiring for each subassembly. then, all pcb.py has to do is overload the wiring property

#### **[MUST FIX]** [provider/provider.py:L351-L369](file:///Users/<username>/gh/hardware/provider/provider.py#L351-L369)
<!-- comment-uuid: 1e3f05ed-393d-485e-8562-2d7a2694302a -->
<!-- comment-commit: working -->

```python
def pcb_manifest_path(self) -> Path:
        """Return the path to the provider's PCB configuration file (pcb.yaml)."""
        return self.project_dir / "pcb.yaml"

    @property
    def pcb_manifest(self) -> Optional[dict[str, Any]]:
        """Return raw YAML data from pcb.yaml if it exists, or dump from pcb_config."""
        p = self.pcb_manifest_path
        if os.path.exists(p):
            import yaml

            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        if getattr(self, "_building_pcb_config", False):
            return None
        cfg = getattr(self, "pcb_config", None)
        if cfg is not None:
            return cfg.model_dump()
        return None
```

> **Reviewer (Reviewer)**: same idea here; we can remove the pcb_manifest_path and only read the pcb manifest from the pcb_config attr

### [`provider/templates/scope.html.j2`](file:///Users/<username>/gh/hardware/provider/templates/scope.html.j2) — ⏳ `PENDING`

#### **[MUST FIX]** [provider/templates/scope.html.j2:L1524](file:///Users/<username>/gh/hardware/provider/templates/scope.html.j2#L1524)
<!-- comment-uuid: 967809a5-da28-44f8-97d9-85b3d1e1b6a0 -->
<!-- comment-commit: working -->

```
if (state.currentMode === "SIMULATE" || (data.name && data.name.toLowerCase().includes("simulation"))) {
```

> **Reviewer (Reviewer)**: we should be doing this server side. can we update our learnings about rerun that we should only present the user data out of a captured rerun session, and not create our own facade of rerun?

### [`provider/vcs/git_engine.py`](file:///Users/<username>/gh/hardware/provider/vcs/git_engine.py) — ⏳ `PENDING`

#### **[MUST FIX]** [provider/vcs/git_engine.py:L35-L37](file:///Users/<username>/gh/hardware/provider/vcs/git_engine.py#L35-L37)
<!-- comment-uuid: 3f57a99f-6e20-42b5-abad-682ad8805a70 -->
<!-- comment-commit: working -->

```python
MAX_DIFF_LINE_LENGTH: int = 1000
MAX_DIFF_FILE_SIZE_BYTES: int = 500 * 1024  # 500 KB limit for generating line-by-line diffs
MAX_DIFF_LINES: int = 4500  # 4,500 lines limit for full side-by-side matching
```

> **Reviewer (Reviewer)**: pls remove this limit and stop the git engine from hanging on large files instead, or show a progress bar for large file

### [`tools/build.py`](file:///Users/<username>/gh/hardware/tools/build.py) — ⏳ `PENDING`

#### **[MUST FIX]** [tools/build.py:L563-L566](file:///Users/<username>/gh/hardware/tools/build.py#L563-L566)
<!-- comment-uuid: 9c4d7eb9-dbe4-4f4e-97f4-6dc2b3f8216f -->
<!-- comment-commit: working -->

```python
if wiring is None:
                    wiring_file = getattr(provider, "wiring_path", None)
                    if wiring_file and Path(wiring_file).exists():
                        wiring = Wiring(Path(wiring_file))
```

> **Reviewer (Reviewer)**: let’s remove the wiring_path fallback logic here

## Action Items Checklist

- [x] **[MUST FIX]** [`model/wiring.py:L417-L427`](file:///Users/<username>/gh/hardware/model/wiring.py#L417-L427): can we remove this? <!-- uuid:29f34525-045c-4672-861d-cb18bb3ef1d3 -->
- [x] **[MUST FIX]** [`projects/carrier_board/cad.py:L659-L685`](file:///Users/<username>/gh/hardware/projects/carrier_board/cad.py#L659-L685): let’s remove this property, there’s no use case for it <!-- uuid:37285658-901e-48e5-a647-98c029ff4af3 -->
- [x] **[MUST FIX]** [`projects/carrier_board/carrier_board.py:L1326-L1328`](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py#L1326-L1328): This seems bad to me, we’re creating a separate BuildPcb CM just for definign the board wiring. We should remove this second definition!! <!-- uuid:98484bb2-40b2-40af-827e-c79ea6f36f68 -->
- [x] **[MUST FIX]** [`projects/carrier_board/carrier_board.py:L2327-L2349`](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py#L2327-L2349): We def shouldn’t require the user to manipulate the symbol table in their project code. This should all be handled transparently in the provider module when building the wiring object <!-- uuid:8b65070e-3c35-4017-9cbd-9b4523445f27 -->
- [x] **[MUST FIX]** [`projects/carrier_board/carrier_board.py:L2463`](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py#L2463): can we remove this parameter from Wiring.from_models while retaining the symbol table functionality <!-- uuid:a2a98f2b-1d56-435f-8e23-1219d2e00381 -->
- [x] **[MUST FIX]** [`projects/carrier_board/carrier_board.py:L562-L628`](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py#L562-L628): can we combine these sets of two cached properties into a set of single cached properties? <!-- uuid:c1616d76-62e9-428e-8f94-640cfef21a69 -->
- [x] **[MUST FIX]** [`projects/carrier_board/carrier_board.py:L687-L704`](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py#L687-L704): I’d prefer if the accessors invoked here (e.g. self.design_rules(), self.net_classes() etc. ) were all properties <!-- uuid:c6403df6-0b63-40c6-a55d-f3a382f9753e -->
- [x] **[MUST FIX]** [`projects/carrier_board/carrier_board.py:L731-L745`](file:///Users/<username>/gh/hardware/projects/carrier_board/carrier_board.py#L731-L745): I’d prefer if the accessors invoked here (e.g. self.design_rules(), self.net_classes() etc. ) were all properties <!-- uuid:1974ef72-82bc-45bd-a765-0f3748897ea2 -->
- [x] **[MUST FIX]** [`projects/carrier_board/pcb.py:L245-L249`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L245-L249): can we fold this workaround logic into the BuildPcb context manager? <!-- uuid:daa0c72a-746b-4bbd-8326-160a0d4ba8a2 -->
- [x] **[MUST FIX]** [`projects/carrier_board/pcb.py:L335-L340`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L335-L340): Can we fold this workaround logic into the BuilcPcb context manager? <!-- uuid:ff7731b0-cbec-470d-ab1e-8de54b8be10b -->
- [x] **[MUST FIX]** [`projects/carrier_board/pcb.py:L436-L447`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L436-L447): can we remove this fallback logic? we can just read the fixed routing path directly from settings <!-- uuid:8230e2f9-dfd6-4932-a026-51847d6b45da -->
- [x] **[MUST FIX]** [`projects/carrier_board/pcb.py:L685-L1369`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L685-L1369): canw e simplify these using the autoincrement component designator functionality you showed me? <!-- uuid:2391aee4-93f3-4d2a-9a0f-e2f11580a291 -->
- [x] **[MUST FIX]** [`projects/carrier_board/pcb.py:L1052-L1534`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L1052-L1534): why isn’t the net routing stuff using the [mcu.pin("VSS"), mcu_caps[0].pin(2), mcu_caps[1].pin(2), mcu_caps[2].pin(2)] syntax you showed me for better type safety? also, we should add a .named_pin property to the class of mcu_caps[2] <!-- uuid:e83d0b2a-22a7-4507-bb9b-cf80f64db3b4 -->
- [x] **[MUST FIX]** [`projects/carrier_board/pcb.py:L1880-L1982`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L1880-L1982): can we also use the [mcu.pin("VSS"), mcu_caps[0].pin(2), mcu_caps[1].pin(2), mcu_caps[2].pin(2)] syntax here <!-- uuid:9b5c8e33-32ff-4995-86ea-be0a0ba9a515 -->
- [x] **[MUST FIX]** [`projects/carrier_board/pcb.py:L1991-L3032`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L1991-L3032): All of this metadatastuff should be converted to the build123d context managers under a top-level PcbMetadata manager. rather than having a centrally defined PCB config table, the PCB config should be defined per-BuildPcb CM and merged at build time into a single PcbCOnfig model <!-- uuid:12ad5f49-3cc0-4879-9ae1-75943108e8b5 -->
- [x] **[MUST FIX]** [`projects/carrier_board/pcb.py:L2841`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L2841): > what happened to the per-Pcb BuildAssemblyTestSteps CM we talked about? <!-- uuid:2c1c4800-e218-4313-b35b-27470743ea02 -->
- [x] **[MUST FIX]** [`projects/carrier_board/pcb.py:L2937-L3032`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L2937-L3032): we should define a CM for assembly test steps that can reference nets and pins on a PCB object directly for better type safety <!-- uuid:dab9a6a0-a33a-47f9-acb3-6a7c02f63970 -->
- [x] **[MUST FIX]** [`projects/carrier_board/pcb.py:L3033-L3070`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py#L3033-L3070): the code for instantinating the PCB config should be moved to the provider module. there’s no reason to keep redefining it for every project <!-- uuid:c89703be-d087-40c5-833d-db435143c6c2 -->
- [x] **[MUST FIX]** [`projects/cat_fountain/pcb.py:L2`](file:///Users/<username>/gh/hardware/projects/cat_fountain/pcb.py#L2): please apply the improvements discussed in [`@projects/carrier_board/pcb.py`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py) to this listing <!-- uuid:9d002d93-8530-4fe7-9aa5-7e90241b6cc6 -->
- [x] **[MUST FIX]** [`projects/cat_fountain/pcb.py:L336`](file:///Users/<username>/gh/hardware/projects/cat_fountain/pcb.py#L336): can we remove this parameter from Wiring.from_models while retaining the symbol table functionality <!-- uuid:ee5ceaa2-2d92-4aff-82dd-800735a5069e -->
- [x] **[MUST FIX]** [`provider/pcb/test_steps.py:L12`](file:///Users/<username>/gh/hardware/provider/pcb/test_steps.py#L12): this is a good start, but doesn’t go far enough to provide a safe environment to build PCB config and assembly testing steps. see my comments in [`@projects/carrier_board/pcb.py`](file:///Users/<username>/gh/hardware/projects/carrier_board/pcb.py) <!-- uuid:b6026d89-c299-4de7-bf1e-30f7e0a3db93 -->
- [x] **[MUST FIX]** [`provider/provider.py:L314-L348`](file:///Users/<username>/gh/hardware/provider/provider.py#L314-L348): let’s remove the wiring_path property and use a provider property for returning wiring for each subassembly. then, all pcb.py has to do is overload the wiring property <!-- uuid:4f134659-55da-4f50-af53-913c1fd58b5f -->
- [x] **[MUST FIX]** [`provider/provider.py:L351-L369`](file:///Users/<username>/gh/hardware/provider/provider.py#L351-L369): same idea here; we can remove the pcb_manifest_path and only read the pcb manifest from the pcb_config attr <!-- uuid:1e3f05ed-393d-485e-8562-2d7a2694302a -->
- [x] **[MUST FIX]** [`provider/templates/scope.html.j2:L1524`](file:///Users/<username>/gh/hardware/provider/templates/scope.html.j2#L1524): we should be doing this server side. can we update our learnings about rerun that we should only present the user data out of a captured rerun session, and not create our own facade of rerun? <!-- uuid:967809a5-da28-44f8-97d9-85b3d1e1b6a0 -->
- [x] **[MUST FIX]** [`provider/vcs/git_engine.py:L35-L37`](file:///Users/<username>/gh/hardware/provider/vcs/git_engine.py#L35-L37): pls remove this limit and stop the git engine from hanging on large files instead, or show a progress bar for large file <!-- uuid:3f57a99f-6e20-42b5-abad-682ad8805a70 -->
- [x] **[MUST FIX]** [`tools/build.py:L563-L566`](file:///Users/<username>/gh/hardware/tools/build.py#L563-L566): let’s remove the wiring_path fallback logic here <!-- uuid:9c4d7eb9-dbe4-4f4e-97f4-6dc2b3f8216f -->
