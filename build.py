# build.py

import logging
import math
import numpy as np
import pytest
import cadquery as cq

class Builder:
    def __init__(self):
        self.ver = 4
        self.thickness = 3
        self.outer_diameter = 63.5
        self.inner_diameter = self.outer_diameter - self.thickness
        self.clamp_len = 50.4 # 2 inches

        # Define the raw measurements taken here 
        measurements = {
            1: np.array([443, 152, 521]),
            2: np.array([652, 205, 500]),
            3: np.array([565, 356, 352]),
            4: np.array([555, 327, 0]),
            5: np.array([480, 343, 0]),
            6: np.array([347, 279, 382]),
            7: np.array([410, 350, 0]),
            8: np.array([392, 300, 0]),
            9: np.array([200, 0, 520]),
            10: np.array([895, 0, 525]),
        }

        # Do some data correction here
        outlet_arrays = np.stack([measurements[9], measurements[10]])
        outlet_height = np.mean(outlet_arrays[:, 2]) 
        measurements[9][2] = measurements[10][2] = outlet_height

        vc_arrays = np.stack([measurements[1], measurements[2]])
        vc_depth, vc_height = np.mean(vc_arrays[:, 1]), np.mean(vc_arrays[:, 2])
        measurements[1][1] = measurements[2][1] = vc_depth
        measurements[1][2] = measurements[2][2] = vc_height

        for idx in [3, 6, 9, 10]:
            measurements[idx][2] = measurements[idx][2] - (self.outer_diameter / 2)

        # We need to rotate the driver exhaust inlet up by 15 degrees
        def dir_vector(start, end):
            return (end - start) / np.linalg.norm(end - start)
            
        theta = np.radians(15)
        c, s = np.cos(theta), np.sin(theta)
        R_driver_inlet = np.array([[1, 0, 0], 
                        [0, c, -s], 
                        [0, s, c]])
        
        self.names = ["driver", "passenger"]
            
        self.P = {
            "driver_inlet": measurements[6],
            "driver_outlet": measurements[9],
            "passenger_inlet": measurements[3],
            "passenger_outlet": measurements[10],
        }
            
        self.V = {
            "driver_inlet": dir_vector(measurements[7], measurements[8]) @ R_driver_inlet,
            "driver_outlet": np.array([-1, 0, 0]),
            "passenger_inlet": dir_vector(measurements[5], measurements[4]),
            "passenger_outlet": np.array([1, 0, 0]),
        }

    def build_wire(self, 
                   name,
                   trim_start     = 0,
                   trim_end       = 0):
        def create_wire(p_start, v_start, p_end, v_end):
            p1 = p_start                            # Manifold start
            p2 = p_start + v_start * self.clamp_len # Spline start
            p3 = p_end                              # Spline end
            p4 = p_end + v_end * self.clamp_len     # Manifold end
            wire = (
                cq.Wire.assembleEdges(
                    [
                        cq.Edge.makeLine(cq.Vector(*p1), cq.Vector(*p2)), 
                        cq.Edge.makeSpline(
                            listOfVector=[cq.Vector(*p2), cq.Vector(*p3)],
                            tangents=(cq.Vector(*v_start), cq.Vector(*v_end)),
                            periodic=False
                        ), 
                        cq.Edge.makeLine(cq.Vector(*p3), cq.Vector(*p4))
                    ]
                )
            )
            path = (
                cq.Workplane("XY")
                .add(wire)
            )
            return path, path.val()
        def trim_wire(path, path_obj, start, end):
            s, e = path_obj.positionAt(start), path_obj.positionAt(end)
            dx, dy, dz = (
                abs(s.x - e.x), 
                abs(s.y - e.y), 
                abs(s.z - e.z)
            )
            cx, cy, cz = (
                (s.x + e.x) / 2.0, 
                (s.y + e.y) / 2.0,
                (s.z + e.z) / 2.0,
            )

            # Create a trim box to remove unwanted portions of the wire
            clip_region = (
                cq.Workplane("XY")
                .center(cx, cy)
                .workplane(offset=cz)
                .box(dx, dy, dz)
            )
            trimmed_path = (
                cq.Workplane("XY").add(
                    path_obj.intersect(clip_region.val())
                            .Wires()[0]
                )
            )
            return trimmed_path, trimmed_path.val() 
            
        # Create the wire which defines the manifold shape
        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
        path, path_obj = create_wire(self.P[inlet_key], self.V[inlet_key], self.P[outlet_key], self.V[outlet_key])
                                        
        # Apply wire trimming if needed
        if (trim_start > 0) or (trim_end > 0):
            length = path_obj.Length()
            s = trim_start / length
            e = (length - trim_end) / length
            path, path_obj = trim_wire(path, path_obj, s, e)
        return path, path_obj

    def build_manifold(self,
                       name, 
                       start_deg      = 0,
                       end_deg        = 0,
                       trim_start     = 0,
                       trim_end       = 0,
                       edge_rounding  = 0.5,
                       **kwargs):
        path, path_obj = self.build_wire(name, 
                                        trim_start = trim_start, 
                                        trim_end = trim_end)
        start_point, start_tangent = path_obj.positionAt(0), path_obj.tangentAt(0)
        inner_radius = kwargs.pop("inner_radius", self.inner_diameter / 2) 
        outer_radius = kwargs.pop("outer_radius", self.outer_diameter / 2)
            
        if (start_deg != 0) or (end_deg != 0):
            # We might want to cut a portion of the circle to use in building only part of the tube profile
            circle = (
                cq.Sketch()
                  .circle(outer_radius)
                  .circle(inner_radius, "s")
            )
            pie_slice = (
                cq.Sketch()
                  .arc((0, 0), outer_radius, start_deg, end_deg - start_deg)
                  .segment((0, 0))
                  .close()
                  .assemble()
            )
            # Make the sides of the tube more rounded
            profile = (
                (circle * pie_slice).vertices()
                                    .fillet(edge_rounding)
            )
            tube = (
                cq.Workplane(cq.Plane(origin=start_point, normal=start_tangent))
                  .placeSketch(profile)
                  .sweep(path, transition="round")
            )
                
        else:
            # Create our hollow tube profile instead
            tube = (
                cq.Workplane(cq.Plane(origin=start_point, normal=start_tangent))
                  .circle(outer_radius)
                  .circle(inner_radius)
                  .sweep(path, transition="round")
            )
        # Round the ends of the tube 
        if (trim_start == 0) and (trim_end == 0):
            tube = (
                tube.edges("%Circle")
                    .fillet(edge_rounding)
            )
        return tube
    
    def build_manifold_half(self, name, right=False):
        if right:
            return self.build_manifold(name, start_deg = 180, end_deg = 360)
        else:
            return self.build_manifold(name, end_deg = 180)
        
    def build_guide(self, name, right = False):
        angle = 0 if right else 180
        sweep_off = 10
        space = 0.1
        guide1 = self.build_manifold(name, 
                                     inner_radius  = (self.outer_diameter - space) / 2,
                                     outer_radius  = (self.outer_diameter + self.thickness + space) / 2,
                                     start_deg     = angle - sweep_off,
                                     end_deg       = angle,
                                     trim_start    = self.clamp_len,   
                                     trim_end      = self.clamp_len)
        guide2 = self.build_manifold(name, 
                                     inner_radius  = (self.outer_diameter + space) / 2,
                                     outer_radius  = (self.outer_diameter + self.thickness + space) / 2,
                                     start_deg     = angle - sweep_off,
                                     end_deg       = angle + sweep_off,
                                     trim_start    = self.clamp_len,   
                                     trim_end      = self.clamp_len)
        guide = (
            guide1.union(guide2)
        )
        return guide
    
    def build_part(self, name, right=False):
        part = (
            self.build_manifold_half(name, right=right)
                .union(self.build_guide(name, right=right))
        )
        return part

    def build_back_manifold(self, name):
        left_guide, right_guide = self.build_guide(name), self.build_guide(name, right=True)
        left_part, right_part = self.build_part(name), self.build_part(name, right=True)
        manifold = self.build_manifold(name)
        manifold_from_parts = (
            left_part.union(right_part)
                    .cut(left_guide)
                    .cut(right_guide)
        )
        return manifold, manifold_from_parts

    def calc_part_error(self, name):
        manifold, manifold_from_parts = self.build_back_manifold(name)
        manifold_vol, manifold_from_parts_vol = manifold.val().Volume(), manifold_from_parts.val().Volume()
        error_pct = abs(manifold_vol - manifold_from_parts_vol) / (manifold_vol + manifold_from_parts_vol) / 2 * 100
        return error_pct
    
    def export_parts(self, name):
        def prepare_part(name, start, end, right=False):
            def rot_angle(start, end):
                # We rotate the part slope about the x axis to try and place it as close to the bed as possible
                dy, dz = (end[1] - start[1]), (end[2] - start[2])
                return -math.degrees(-math.atan2(dy, dz)) - 90
        
            angle_x = rot_angle(start, end)
            part = self.build_part(name, right=right)
            prepared_part = part.rotate((0,0,0), (1,0,0), angle_x)
            if right:
                # Flip right half upside down
                prepared_part = prepared_part.mirror("XY")
            # Ensure that the part is sitting directly on the bed
            z_min = prepared_part.val().BoundingBox().zmin
            prepared_part = prepared_part.translate((0, 0, -z_min))
            return prepared_part
        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
        file_prefix = f"exhaust_manifolds_v{self.ver}"
        
        for side in ["left", "right"]:
            mesh_file_name = f"{file_prefix}_{name}_{side}.stl"
            prepared_part = prepare_part(name, self.P[inlet_key], self.P[outlet_key], right=("right" in side))
            cq.exporters.export(prepared_part, mesh_file_name)
            print(f"Done writing {mesh_file_name}.") 

    def export_all_parts(self):
        for name in self.names:
            self.export_parts(name)

class TestBuilder:
    def pytest_generate_tests(self, metafunc):
        if "name" in metafunc.fixturenames:
            builder = Builder()
            metafunc.parametrize("name", builder.names)

    @pytest.fixture(scope="class")
    def builder(self):
        return Builder()

    def test_measurements(self, builder):
        # Do some validation of the pointlists based on the measurements I took on graph paper.
        # Adjust coordinates to be 2D, then check how the driver and passenger inlets and outlets related to each other
        # The inlets are connected to midpipes with slip ring connectors, while the exhaust pipes have cuff style clamps
        def dist(p1, p2):
            x1, y1, z1 = p1
            x2, y2, z2 = p2
            return round(math.sqrt((x2 - x1)**2 + (y2 - y1)**2)) 
        def get_end_points(name):
            inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
            return (
                builder.P[inlet_key], # Inlet start
                builder.P[inlet_key] + builder.V[inlet_key] * builder.clamp_len, # Inlet end
                builder.P[outlet_key], # Outlet start
                builder.P[outlet_key] + builder.V[outlet_key] * builder.clamp_len, # Outlet end
            )
        driver_inlet_start, driver_inlet_end, driver_outlet_start, driver_outlet_end = get_end_points("driver")
        passenger_inlet_start, passenger_inlet_end, passenger_outlet_start, passenger_outlet_end = get_end_points("passenger")

        # Check dist between inlets
        assert dist(passenger_inlet_start, driver_inlet_start) == pytest.approx(231)
        assert round(driver_inlet_end[2] - driver_inlet_start[2]) == pytest.approx(12)

        # Check dist between outlets
        assert dist(driver_outlet_start, passenger_outlet_start) == pytest.approx(695)
        assert abs(round(passenger_inlet_end[2] - passenger_inlet_start[2])) == pytest.approx(0)

        # Check dist between driver inlet and outlet
        assert dist(driver_inlet_start, driver_outlet_start) == pytest.approx(315)
        assert round(driver_outlet_start[2] - driver_inlet_start[2]) == pytest.approx(140)

        # Check dist between passenger inlet and outlet
        assert dist(passenger_inlet_start, passenger_outlet_start) == pytest.approx(485)
        assert round(passenger_outlet_start[2] - passenger_inlet_start[2]) == pytest.approx(170)
        
    def test_wire(self, name, builder):
        def calc_point_err(v, p):
            return abs((v - cq.Vector([p[0], p[1], p[2]])).Length)
        wire, wire_obj = builder.build_wire(name)
        length = wire_obj.Length()
        inlet_clamp_start = wire_obj.positionAt(0.0)
        inlet_clamp_end = wire_obj.positionAt(builder.clamp_len / length)
        outlet_clamp_start = wire_obj.positionAt((length - builder.clamp_len) / length)
        outlet_clamp_end = wire_obj.positionAt(1.0)
        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
            
        # Make sure the clamp starts are correct
        assert calc_point_err(inlet_clamp_start, builder.P[inlet_key]) == pytest.approx(0)
        assert calc_point_err(outlet_clamp_start, builder.P[outlet_key]) == pytest.approx(0)

        # Check clamp direction and length
        assert calc_point_err(
            (inlet_clamp_end - inlet_clamp_start).normalized(), builder.V[inlet_key]
        ) == pytest.approx(0)
        assert calc_point_err(
            (outlet_clamp_end - outlet_clamp_start).normalized(), builder.V[outlet_key]
        ) == pytest.approx(0)
        assert (inlet_clamp_end - inlet_clamp_start).Length == pytest.approx(builder.clamp_len)
        assert (outlet_clamp_end - outlet_clamp_start).Length == pytest.approx(builder.clamp_len)

    def test_wire_trim(self, name, builder):
        wire, wire_obj = builder.build_wire(name)
        guide_wire, guide_wire_obj = builder.build_wire(name, trim_start=builder.clamp_len, trim_end=builder.clamp_len)
        max_error = 5e-2
        assert abs(wire_obj.Length() - guide_wire_obj.Length() - 2 * builder.clamp_len) < max_error

    def test_intersection(self, builder):
        def parts_intersect(part1, part2):
            intersection = part1.intersect(part2)
            return (intersection.val() is not None) and (intersection.val().Volume() > 1e-6)
        driver_manifold, passenger_manifold = builder.build_manifold("driver"), builder.build_manifold("passenger")
        
        assert (parts_intersect(driver_manifold, passenger_manifold) == False)
        
    def test_diameter(self, name, builder):
        def calc_outer(tube):
            circular_edges = tube.edges("%CIRCLE").vals()
            radii = [e.radius() for e in circular_edges]
            # Extract radii
            return (max(radii) * 2)
        outer = calc_outer(builder.build_manifold(name))
        assert (outer == pytest.approx(builder.outer_diameter))

    def test_part_error(self, name, builder):  
        error_pct = builder.calc_part_error(name)
        assert (error_pct < 2)
    
if __name__ == "__main__":
    logging.basicConfig(
        filename="out.txt",
        level=logging.DEBUG,
        filemode='w'
    )
    builder = Builder()
    builder.export_all_parts()