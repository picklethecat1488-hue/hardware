"""Unit tests for Blender rendering backend and camera viewports."""

import os
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from provider.blender import BlenderRenderer, CameraViewport, RenderConfig
from provider.room import Room


class TestBlenderRenderer:
    """Test suite for BlenderRenderer, CameraViewport, and RenderConfig."""

    def test_camera_viewport_from_named_views(self):
        """Verify CameraViewport calculation for standard named views."""
        center = (0.0, 0.0, 0.05)
        b_rad = 0.10

        vp_iso = CameraViewport.from_view_string("iso", center=center, bounding_radius=b_rad)
        assert vp_iso.target == center
        assert vp_iso.location[2] > center[2]

        vp_front = CameraViewport.from_view_string("front", center=center, bounding_radius=b_rad)
        assert vp_front.target == center
        # Front faces from South (-Y)
        assert vp_front.location[1] < center[1]

        vp_top = CameraViewport.from_view_string("top", center=center, bounding_radius=b_rad)
        assert vp_top.target == center
        assert vp_top.location[2] > center[2]

        vp_left = CameraViewport.from_view_string("left", center=center, bounding_radius=b_rad)
        assert vp_left.target == center
        assert vp_left.location[0] < center[0]

    def test_camera_viewport_from_coordinate_string(self):
        """Verify CameraViewport parses raw coordinate tuples."""
        center = (0.0, 0.0, 0.0)
        vp_coord = CameraViewport.from_view_string("(0.25, -0.35, 0.40)", center=center)
        assert vp_coord.target == center
        assert vp_coord.location == (0.25, -0.35, 0.40)

        vp_coord_unwrapped = CameraViewport.from_view_string("0.1, -0.2, 0.3", center=center)
        assert vp_coord_unwrapped.location == (0.1, -0.2, 0.3)

    def test_find_blender_binary(self):
        """Verify find_blender_binary finds an executable or respects BLENDER_BIN env var."""
        with patch.dict(os.environ, {"BLENDER_BIN": "/custom/path/to/blender"}, clear=False):
            with patch("os.path.exists", return_value=True), patch("os.path.isfile", return_value=True):
                assert BlenderRenderer.find_blender_binary() == "/custom/path/to/blender"

        with patch.dict(os.environ, {"BLENDER_PATH": "/opt/custom/blender"}, clear=False):
            with patch("os.path.exists", return_value=True), patch("os.path.isfile", return_value=True):
                assert BlenderRenderer.find_blender_binary() == "/opt/custom/blender"

    def test_find_blender_binary_ci_and_linux_paths(self):
        """Verify find_blender_binary resolves standard Linux/CI paths and glob patterns."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("shutil.which", return_value=None):
                with patch("glob.glob") as mock_glob:
                    mock_glob.side_effect = lambda pat, **kwargs: (
                        ["/opt/blender-5.1.0/blender"] if "/opt/blender*" in pat else []
                    )
                    with patch("os.path.exists", return_value=False), patch("os.path.isfile", return_value=True):
                        assert BlenderRenderer.find_blender_binary() == "/opt/blender-5.1.0/blender"

    def test_find_ffmpeg_binary(self):
        """Verify find_ffmpeg_binary discovers ffmpeg across env vars, conda, and standard paths."""
        with patch.dict(os.environ, {"FFMPEG_BIN": "/custom/ffmpeg"}, clear=False):
            with patch("os.path.exists", return_value=True), patch("os.path.isfile", return_value=True):
                assert BlenderRenderer.find_ffmpeg_binary() == "/custom/ffmpeg"

        with patch.dict(os.environ, {}, clear=True):
            with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
                assert BlenderRenderer.find_ffmpeg_binary() == "/usr/bin/ffmpeg"

    @patch("subprocess.run")
    def test_is_available(self, mock_run):
        """Verify is_available returns True on successful version check."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Blender 5.1.2\n")
        assert BlenderRenderer.is_available() is True

        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        assert BlenderRenderer.is_available() is False

    @patch("subprocess.run")
    def test_render_still_execution(self, mock_run):
        """Verify render_still exports scene data and executes Blender script."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Render success", stderr="")
        room = Room()
        from build123d import Box

        room.add("cube", Box(10, 10, 10), color=(1.0, 0.0, 0.0, 1.0))

        cfg = RenderConfig(view_from="iso", samples=16)
        out_path = BlenderRenderer.render_still(room, "build/test_still.png", config=cfg)
        assert os.path.basename(out_path) == "test_still.png"
        assert mock_run.called

    @patch("provider.blender.BlenderRenderer._encode_frames_to_mp4")
    @patch("subprocess.run")
    def test_render_turntable_execution(self, mock_run, mock_encode):
        """Verify render_turntable_to_mp4 exports room, sets turntable flag, runs blender, and encodes MP4."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Turntable success", stderr="")
        room = Room()
        from build123d import Box

        room.add("cube", Box(10, 10, 10), color=(0.2, 0.6, 0.9, 0.8))

        cfg = RenderConfig(fps=30, samples=16, view_from="iso")
        out_path = BlenderRenderer.render_turntable_to_mp4(
            room, "build/test_turntable.mp4", duration_sec=1.0, config=cfg
        )
        assert os.path.basename(out_path) == "test_turntable.mp4"
        assert mock_run.called
        assert mock_encode.called

    @patch("provider.blender.BlenderRenderer._encode_frames_to_mp4")
    @patch("subprocess.run")
    def test_render_simulation_to_mp4_execution(self, mock_run, mock_encode):
        """Verify render_simulation_to_mp4 exports frames and rigid transforms."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Sim render success", stderr="")
        room = Room()
        from build123d import Box

        room.add("casing", Box(20, 20, 20), color=(0.8, 0.8, 0.8, 1.0))

        water_meshes = [
            {"pool": (np.array([[0.0, 0.0, 0.0], [0.01, 0.0, 0.0], [0.0, 0.01, 0.0]]), np.array([[0, 1, 2]]))}
        ]
        transforms = [{"casing": ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])}]

        cfg = RenderConfig(fps=30, samples=16)
        out_path = BlenderRenderer.render_simulation_to_mp4(
            room=room,
            output_mp4="build/test_sim.mp4",
            sim_steps=1,
            config=cfg,
            water_meshes_per_frame=water_meshes,
            rigid_transforms_per_frame=transforms,
        )
        assert os.path.basename(out_path) == "test_sim.mp4"
        assert mock_run.called
        assert mock_encode.called

    def test_write_blender_script_jinja2_template(self, tmp_path):
        """Verify _write_blender_script correctly loads Jinja2 template and produces valid Python code."""
        script_file = tmp_path / "test_render_script.py"
        scene_file = tmp_path / "scene_data.json"
        output_image = tmp_path / "frame.png"

        cfg = RenderConfig(resolution=(2560, 1440), fps=60, samples=32, engine="BLENDER_EEVEE")
        BlenderRenderer._write_blender_script(
            script_path=str(script_file),
            scene_data_path=str(scene_file),
            output_path=str(output_image),
            is_animation=False,
            config=cfg,
            total_frames=1,
        )

        assert script_file.exists()
        code = script_file.read_text(encoding="utf-8")
        assert "import bpy" in code
        assert "BLENDER_EEVEE" in code
        assert "2560" in code
        assert "1440" in code
        # Check Python compilation of generated script
        compile(code, str(script_file), "exec")

    def test_write_blender_script_micro_polygon_dicing_and_ssfr(self, tmp_path):
        """Verify _write_blender_script generates micro-polygon dicing, SSFR, and Geometry Nodes fluid code."""
        script_file = tmp_path / "test_advanced_script.py"
        scene_file = tmp_path / "scene_data.json"
        output_image = tmp_path / "frame_####.png"

        cfg = RenderConfig(
            resolution=(2560, 1440),
            fps=60,
            samples=32,
            engine="CYCLES",
            use_geometry_nodes_fluid=True,
            use_micro_polygon_dicing=True,
            dicing_rate=0.5,
            use_ssfr=True,
            fluid_voxel_size=0.0003,
            fluid_point_radius=0.0011,
            fluid_surface_threshold=0.40,
            fluid_adaptivity=0.05,
        )
        BlenderRenderer._write_blender_script(
            script_path=str(script_file),
            scene_data_path=str(scene_file),
            output_path=str(output_image),
            is_animation=True,
            config=cfg,
            total_frames=5,
        )

        assert script_file.exists()
        code = script_file.read_text(encoding="utf-8")
        assert "scene.cycles.dicing_rate = 0.5" in code
        assert "use_adaptive_subdivision = True" in code
        assert "SSFR_Compositor" in code
        assert "FluidGeometryNodes" in code
        assert "GeometryNodePointsToVolume" in code
        assert "GeometryNodeVolumeToMesh" in code
        assert "p2v_voxel.default_value = v_size" in code
        assert "p2v_radius.default_value = p_rad" in code
        assert "v2m_thresh.default_value = v_thresh" in code
        assert "v2m_adapt.default_value = v_adapt" in code
        assert 'meta.get("fluid_voxel_size", 0.0003)' in code
        assert 'meta.get("fluid_point_radius", 0.0011)' in code
        assert 'meta.get("fluid_surface_threshold", 0.4)' in code
        assert 'meta.get("fluid_adaptivity", 0.05)' in code
        assert "b_blur.sigma_color = 0.05" in code
        assert "key_light_data.energy = 28.0" in code
        assert 'scene.view_settings.view_transform = "AgX"' in code
        assert "cprefs.peer_memory = True" in code
        # Check Python compilation of generated script
        compile(code, str(script_file), "exec")

    def test_render_config_fluid_defaults(self):
        """Verify RenderConfig default parameters for crisp liquid fluid meshing."""
        cfg = RenderConfig()
        assert cfg.fluid_point_radius == 0.0034
        assert cfg.fluid_surface_threshold == 0.12
        assert cfg.fluid_voxel_size == 0.0003
        assert cfg.fluid_adaptivity == 0.0
        assert cfg.fluid_smooth_iterations == 4
        assert cfg.fluid_smooth_factor == 0.60
        assert cfg.use_ssfr is False

    def test_export_room_inverts_initial_transforms_for_links(self, tmp_path):
        """Verify that link meshes are exported in link-local coordinates using inverse initial transform.

        Regression test: Prevents double-transformation where assembled parts were levitated in Blender.
        """
        import trimesh
        from build123d import Box, Location

        room = Room()
        # Box centered at (0, 0, 100) mm -> 0.100 m
        box = Box(20, 20, 20).locate(Location((0, 0, 100)))
        room.add("lid", box, color=(0.1, 0.5, 0.9, 0.7))

        initial_transforms = {
            "lid": ([0.0, 0.0, 0.100], [0.0, 0.0, 0.0, 1.0]),
        }
        cfg = RenderConfig()
        scene_file = tmp_path / "scene.json"
        BlenderRenderer._export_room_to_dir(
            room=room,
            target_dir=str(tmp_path),
            scene_data_path=str(scene_file),
            config=cfg,
            initial_transforms=initial_transforms,
        )

        lid_obj_path = tmp_path / "lid.obj"
        assert lid_obj_path.exists()
        tm = trimesh.load(str(lid_obj_path))
        # With inverse transform applied, vertices should be centered at Z=0 (local frame), not Z=0.100
        z_mean = float(tm.vertices[:, 2].mean())
        assert abs(z_mean) < 1e-4, f"Link vertices not in local coordinates: z_mean={z_mean}"

    def test_turntable_and_voxel_pitch_defaults(self):
        """Verify RenderConfig defaults for 10s turntable rotation and 0.3mm voxel pitch."""
        cfg = RenderConfig()
        assert cfg.turntable is True
        assert cfg.fluid_voxel_size == 0.0003
        assert cfg.fluid_point_radius == 0.0034

    @patch("provider.blender.BlenderRenderer._encode_frames_to_mp4")
    @patch("subprocess.run")
    def test_render_simulation_with_particle_positions(self, mock_run, mock_encode):
        """Verify render_simulation_to_mp4 exports particle points for Geometry Nodes when provided."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Sim render success", stderr="")
        room = Room()
        from build123d import Box

        room.add("casing", Box(20, 20, 20), color=(0.8, 0.8, 0.8, 1.0))

        particle_positions = [np.array([[0.0, 0.0, 0.05], [0.01, 0.0, 0.05], [0.0, 0.01, 0.05]], dtype=np.float32)]
        transforms = [{"casing": ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])}]

        cfg = RenderConfig(fps=30, samples=16, use_geometry_nodes_fluid=True)
        out_path = BlenderRenderer.render_simulation_to_mp4(
            room=room,
            output_mp4="build/test_sim_points.mp4",
            sim_steps=1,
            config=cfg,
            particle_positions_per_frame=particle_positions,
            rigid_transforms_per_frame=transforms,
        )
        assert os.path.basename(out_path) == "test_sim_points.mp4"
        assert mock_run.called
        assert mock_encode.called

    def test_resolve_item_material_with_materials_model(self):
        """Verify resolve_item_material resolves PBR properties directly from MaterialsModel."""
        from model import MaterialModel, MaterialsModel

        custom_mats = MaterialsModel(
            material={
                "custom_resin": MaterialModel(
                    roughness=0.08,
                    ior=1.52,
                    transmission=0.90,
                    metallic=0.1,
                    specular=0.70,
                )
            }
        )

        dummy_geom = MagicMock()
        dummy_geom.urdf_material = "custom_resin"

        mat_params = BlenderRenderer.resolve_item_material(
            name="test_part",
            geom=dummy_geom,
            rgba=(0.1, 0.5, 0.9, 0.4),
            materials=custom_mats,
        )

        assert mat_params["material_type"] == "custom_resin"
        assert mat_params["rgba"] == [0.1, 0.5, 0.9, 0.4]
        assert mat_params["roughness"] == 0.08
        assert mat_params["ior"] == 1.52
        assert mat_params["transmission"] == 0.90
        assert mat_params["metallic"] == 0.1
        assert mat_params["specular"] == 0.70

    def test_resolve_water_material_from_yaml_schema(self):
        """Verify resolve_item_material resolves fluid meshing parameters from print_materials.yaml."""
        water_geom = MagicMock()
        water_geom.urdf_material = "water"

        mat_params = BlenderRenderer.resolve_item_material(
            name="water",
            geom=water_geom,
            rgba=(0.05, 0.65, 0.95, 0.35),
        )

        assert mat_params["material_type"] == "water"
        assert mat_params["roughness"] == 0.08
        assert mat_params["ior"] == 1.333
        assert mat_params["transmission"] == 0.95
        assert mat_params["fluid_voxel_size"] == 0.0003
        assert mat_params["fluid_point_radius"] == 0.0034
        assert mat_params["fluid_surface_threshold"] == 0.12
        assert mat_params["fluid_adaptivity"] == 0.0
        assert mat_params["fluid_smooth_iterations"] == 4
        assert mat_params["fluid_smooth_factor"] == 0.60
        assert mat_params["use_ssfr"] is False

    def test_materials_model_from_yaml(self):
        """Verify MaterialsModel loads correctly from print_materials.yaml."""
        from model import MaterialsModel

        mats = MaterialsModel.default()
        assert "petg" in mats
        assert "utr8100" in mats
        assert "water" in mats

        petg = mats.get("petg")
        assert petg is not None
        assert petg.roughness == 0.28
        assert petg.ior == 1.57

        utr = mats.get("utr8100")
        assert utr is not None
        assert utr.transmission == 0.85
        assert utr.ior == 1.51

        water = mats.get("water")
        assert water is not None
        assert water.roughness == 0.08
        assert water.ior == 1.333
        assert water.transmission == 0.95
        assert water.fluid_voxel_size == 0.0003
        assert water.fluid_point_radius == 0.0034
        assert water.fluid_surface_threshold == 0.12
        assert water.fluid_adaptivity == 0.0
        assert water.fluid_smooth_iterations == 4
        assert water.fluid_smooth_factor == 0.60
        assert water.use_ssfr is False

    @patch("provider.blender.BlenderRenderer._encode_frames_to_mp4")
    @patch("subprocess.run")
    def test_parallel_multi_gpu_workers(self, mock_run, mock_encode):
        """Verify BlenderRenderer parallelizes frame rendering across multiple workers with chunked frame ranges."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Frame rendered", stderr="")
        room = Room()
        from build123d import Box

        room.add("casing", Box(10, 10, 10), color=(0.8, 0.8, 0.8, 1.0))
        transforms = [{"casing": ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])} for _ in range(8)]

        # 4 workers configured for 8 simulation steps
        cfg = RenderConfig(fps=30, samples=16, workers=4)
        with patch.object(BlenderRenderer, "get_available_gpu_devices", return_value=[0, 1, 2, 3]):
            out_path = BlenderRenderer.render_simulation_to_mp4(
                room=room,
                output_mp4="build/test_parallel.mp4",
                sim_steps=8,
                config=cfg,
                rigid_transforms_per_frame=transforms,
            )

        assert os.path.basename(out_path) == "test_parallel.mp4"
        # 4 subprocess workers should have been invoked
        assert mock_run.call_count == 4
        # Verify frame ranges and GPU device assignments across worker calls
        called_envs = sorted(
            [call.kwargs.get("env") for call in mock_run.call_args_list if "env" in call.kwargs],
            key=lambda env: int(env["RENDER_FRAME_START"]),
        )
        assert len(called_envs) == 4
        assert [env["RENDER_FRAME_START"] for env in called_envs] == ["0", "2", "4", "6"]
        assert [env["RENDER_FRAME_END"] for env in called_envs] == ["2", "4", "6", "8"]
        assert [env["CUDA_VISIBLE_DEVICES"] for env in called_envs] == ["0", "1", "2", "3"]

    def test_turntable_rotation_spans_full_animation(self, tmp_path):
        """Verify render_blender.py.j2 script scales turntable period to the full animation frame count."""
        script_file = tmp_path / "test_turntable_script.py"
        scene_file = tmp_path / "scene_data.json"
        output_image = tmp_path / "frame_####.png"

        cfg = RenderConfig(fps=30, turntable=True)
        BlenderRenderer._write_blender_script(
            script_path=str(script_file),
            scene_data_path=str(scene_file),
            output_path=str(output_image),
            is_animation=True,
            config=cfg,
            total_frames=1800,
        )

        assert script_file.exists()
        code = script_file.read_text(encoding="utf-8")
        assert "turntable_period_frames = tot_f if tot_f > 1 else max(30 * 60.0, 1.0)" in code
        assert 'f_start = int(os.environ.get("RENDER_FRAME_START", 0))' in code
        assert 'f_end = int(os.environ.get("RENDER_FRAME_END", tot_f))' in code

    def test_anti_flicker_render_settings_and_material_invariants(self, tmp_path):
        """Verify BlenderRenderer generates anti-flicker raytracing and fluid settings.

        Regression test: Guards against fluid mesh adaptivity popping, screen-space
        adaptive subdivision jitter, OptiX animation flickering, and low-sample noise.
        """
        script_file = tmp_path / "test_anti_flicker_script.py"
        scene_file = tmp_path / "scene_data.json"
        output_image = tmp_path / "frame_####.png"

        cfg = RenderConfig()
        assert cfg.fluid_adaptivity == 0.0
        assert cfg.use_micro_polygon_dicing is False
        assert cfg.samples >= 64

        BlenderRenderer._write_blender_script(
            script_path=str(script_file),
            scene_data_path=str(scene_file),
            output_path=str(output_image),
            is_animation=True,
            config=cfg,
            total_frames=10,
        )

        code = script_file.read_text(encoding="utf-8")
        assert 'scene.cycles.denoiser = "OPENIMAGEDENOISE"' in code
        assert "scene.cycles.sample_clamp_indirect = 2.0" in code
        assert "scene.cycles.adaptive_threshold = 0.005" in code
        assert "scene.cycles.adaptive_min_samples = 32" in code
        assert "use_adaptive_subdivision" not in code

    def test_fluid_geometry_nodes_sheet_bridging_invariant(self):
        """Verify OpenVDB particle bridging distance prevents thin film popping and fracturing.

        Regression test: In SPH fluid dynamics, particles on the lid spread horizontally
        with inter-particle spacing d ~ 3.5 - 4.5 mm. In Blender Geometry Nodes Points to Volume,
        particles use quadratic falloff w(r) = (1 - (r/R)^2)^2. For adjacent particles separated
        by d, the midpoint density is D_mid = 2 * (1 - (d / 2R)^2)^2. For an isosurface to bridge
        at threshold T, d <= 2 * R * sqrt(1 - sqrt(T / 2)).
        If d_max < 4.5 mm, slight lateral particle drift causes continuous liquid sheets to
        repeatedly shatter into disconnected droplets and reform frame-to-frame, appearing
        as violent size fluctuations and flickering.
        """
        import math
        from model import MaterialsModel

        water = MaterialsModel.default().get("water")
        assert water is not None
        r_splat = water.fluid_point_radius
        thresh = water.fluid_surface_threshold

        assert r_splat is not None and thresh is not None
        # Maximum bridging distance between two particles before isosurface breaks
        d_bridge_max = 2.0 * r_splat * math.sqrt(1.0 - math.sqrt(thresh / 2.0))

        # Must bridge spreading monolayer particles with spacing up to 4.5mm
        assert d_bridge_max >= 0.0045, (
            f"Bridging distance {d_bridge_max * 1e3:.2f} mm < 4.5 mm allows thin film shattering"
        )
        # Surface threshold must be bounded to prevent excessive metaball bloating while maintaining cohesion
        assert 0.10 <= thresh <= 0.16, f"Surface threshold {thresh} outside optimal cohesion range [0.10, 0.16]"
        assert 0.0028 <= r_splat <= 0.0035, f"Point radius {r_splat} outside optimal splat range [0.0028, 0.0035]"
