# 🟢 `[BUG-VIBRANT-WOODBORER-940]` Create motor hub assembly

- **UUID**: `c90ede81-7e1b-4c52-9ff2-529904ec722a`
- **ID**: `BUG-VIBRANT-WOODBORER-940`
- **Status**: `CLOSED`
- **Severity**: `HIGH`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-10-23 22:54:57 UTC`
- **Resolved**: `2026-10-24 01:29:24 UTC`
- **Accepted**: `2026-10-24 01:29:24 UTC`

#### Description

Right now debugging motor issues is very difficult. Can we pls create a motor hub assembly which combines the hall sensor, motor, drive hub, and motor clip into a single subassembly unit which clips into the bottom of the bowl and interfaces magnetically with the impeller? See this additional feedback for more optimizations and improvements:

1. Center the Thrust Bearing (Reduce Friction Radius by 90%):
      • Remove the outer perimeter standoff ring on the drive hub at R = 15.6 mm.
      • Add a small PTFE (Teflon) thrust washer or tiny acetal/POM button directly around the 1.5 mm motor shaft collar at R ≤ 1.5
      mm.
      • Dropping the contact radius from 15.6 mm down to 1.5 mm reduces friction torque by over 90% (T_f ∝ R).

2. Optimize Magnetic Coupling Strength:
      • Increase the axial air gap from 1.5 mm to 2.0--2.5 mm. Magnetic attraction drops with 1/d² while rotational
      magnetic coupling torque remains sufficient for fluid pumping.

3. Speed Sensor Pocket Alignment:
      • Ensure that the Hall sensor pocket at Y = 18.5 mm directly aligns with the drive hub's magnet pitch circle so the Hall
      sensor receives strong alternating pulses to reliably output SPEED_SENSE (GP26). 
      • These are the hall sensors I purchased: 

https://www.amazon.com/FORIOT-Effect-Sensor-3144E-A3144/dp/B0H69BSJ4Z/ref=sr_1_4_pp?crid=ZUG52D2UM8C&dib=eyJ2IjoiMSJ9.lpKwwD9zXT4MytW_o1867YiT79Yl-lsXrO86wfgsgnShDxXo1Ptvdg432J9RLfUlPqg3sgQwgI4ajloN9FG2Zlo3KyUWIIIhG1epfbhZ8rnOzwoVy8yOpe6GIQNE5Si866q-1S70Y6wKyFPuvuxLJ8Qlbu4LJdNtf5Sjqjq45d-qswe8QjFcGbVlpS3Cpaxq770C7UN_pKv_ssgpbkmEzIl_EmazNDYryvgi4d-H-38.jt36wv_LPOYxzl2HI64T4n84lfvUbY3Z5gwIZfFs2bI&dib_tag=se&keywords=hall+sensor&qid=1792796296&sprefix=hall+senso%2Caps%2C183&sr=8-4

     • They are standard A3144 hall sensors which are mounted on PCBs and include mounting holes. I am able to bend the hall sensor off the PCB to vary its pitch, but the effective height is a few mm shorter than a standalone hall sensor.
 
4. Update the cat fountain docs with needed BOM updates

#### Resolution Notes

Replaced motor_clip and integrated enclosed well beneath the impeller with dedicated motor drive hub assembly (motor_hub) sliding into guide tracks on bowl base, while keeping drive_hub as separate rotating drive unit so motor and drive hub install and remove as a single unit without detaching.
