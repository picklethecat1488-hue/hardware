# Cat Fountain

This project designs a custom 3D-printable automatic pet cat water fountain. It features a bottom water bowl, a mechanical water spout, a vertical delivery tube, and a spout nozzle at the top to create a gentle flowing stream of water for cats. The complete design will incorporate an upper drinking level and enclosed 2L water storage tank, as well as a compartment for the motor controller.

The design utilizes precise build123d joint placement to ensure alignment of the impeller on the central shaft pin, and rigid mounting sockets for the water tube and spout nozzle.

![Diagram](cat_fountain_diagram.svg)

*Exploded assembly diagram.*

## Build Files

After running `build.py`, you should see these files in your build output organized by project subdirectories:

- **build/cat_fountain/cat_fountain_diagram.svg** - An exploded assembly diagram of the cat fountain.
- **build/cat_fountain/bowl.stl** / **bowl.obj** - The main bottom water bowl.
- **build/cat_fountain/impeller.stl** / **impeller.obj** - The spinning impeller blades.
- **build/cat_fountain/tube.stl** / **tube.obj** - The vertical water delivery tube.
- **build/cat_fountain/spout.stl** / **spout.obj** - The water spout nozzle.
- **build/cat_fountain/fountain.stl** / **fountain.obj** - The compiled full assembly.
- **build/cat_fountain/product.urdf** - The URDF definition file for visualization/simulation.

## Visualization & Simulation

To view the cat fountain assembly in the CAD viewer:
```bash
python src/view.py cat_fountain/product
```

To run the physics simulation of the cat fountain in PyBullet:
```bash
python src/view.py cat_fountain/product:view/simulate -s 1000
```
