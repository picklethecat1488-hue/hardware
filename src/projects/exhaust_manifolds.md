# Exhaust Manifolds

I got an IE exhaust kit for my car and after looking around, decided the best way to add some exhaust tips to the kit and make it look nice was by creating some custom exhaust manifolds to connect the midpipe section of the kit to the tips I got.

I initially prototyped the manifolds shapes mesh generation in Jupyter Lab using mainly cadquery and numpy, but have since totally redesigned my code to have it's own build and configuration processes, as well as many design and functional tests suites.

The manifolds themselves include a 3" clamp bed in the middle, as well as lap jointing to ensure they are align with each other correctly. The outer diameter is 2.5" with a 3mm wall thickness. The production process is 316L stainless steel using SLM.

## Releases

I'm not anticipating any more releases of the manifolds tubing after V4 completes production, but there is a potential to design some kind of blockoff plate or dummy exhaust valve for a dash light I'm getting in a future release:

- **V3** This completed production with the supplier after about 3 weeks. There were a couple issues, but the main issue was that half these parts are unusuable due to a geometry error I introduced attempting to place them flat on the print bed. Oops!!
- **V4** These are currenty being scheduled for production. They are pretty much a total redesign of V3, and include a bunch of fixed issues.

There are two manifolds, driver and passenger. The manifolds are further separated into left and right sides, and must be sealed together with a high temperature adhesive or gasket sealer to prevent leaks:

![Diagram](exhaust_manifolds_diagram.svg)

*Exploded assembly diagram.*

## Build Files

After running `build.py`, you should see these files in your build output organized by project subdirectories:

- **build/exhaust_manifolds/exhaust_manifolds_diagram.svg** - An exploded diagram of the manifolds assembly process.  
- **build/exhaust_manifolds/driver_left.stl** - The left side of the driver manifold.  
- **build/exhaust_manifolds/driver_right.stl** - The right side of the driver manifold.  
- **build/exhaust_manifolds/passenger_left.stl** - The left side of the passenger manifold.  
- **build/exhaust_manifolds/passenger_right.stl** - The right side of the passenger manifold.