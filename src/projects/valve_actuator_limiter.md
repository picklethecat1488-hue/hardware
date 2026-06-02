# Valve Actuator Limiter

This project addresses issues where exhaust valve actuators rotate beyond their intended range when aftermarket exhaust components are installed. The limiter plate provides a mechanical stop to prevent diagnostic trouble codes (DTCs) and dashboard warning lights.

The design features a lightweight aluminum or stainless steel plate that mounts between the actuator and the mounting bracket, restricting the sweep of the actuator arm to the OEM specification.

## Releases

- **V5** Initial release for testing fitment on standard valve actuators.

## Build Files

After running `build.py`, you should see these files in your build output organized by project subdirectories:

- **build/valve_actuator_limiter/limiter_plate_left.stl** - The limiter plate for the left-side actuator.
- **build/valve_actuator_limiter/limiter_plate_right.stl** - The limiter plate for the right-side actuator.

## Visualization

To view the limiter plate in the CAD viewer:
```bash
python src/view.py valve_actuator_limiter/limiter_plate
```