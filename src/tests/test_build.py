"""Contains Build main unit tests."""

import argparse
import hashlib
import io
import yaml
from build import Builder, main, get_args
from pathlib import Path
from build123d import BuildPart, Box
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from provider import Action, Mode, TargetList, Room, SUBASSEMBLIES


class TestBuildMain:
    """Build main unit tests."""

    @pytest.fixture
    def mock_logger(self):
        """Return a mock logger fixture."""
        return MagicMock()

    @pytest.fixture
    def mock_builder(self, mocker):
        """Patch Builder in the build module."""
        return mocker.patch("build.Builder")

    def test_get_args_parsing(self, mocker):
        """Test the argparse configuration directly."""
        mocker.patch("sys.argv", ["script.py", "-e", "foo.env", "-out", "tmp", "--", "part1/left"])
        args = get_args()
        assert args.env == "foo.env"
        assert args.outdir == "tmp"
        assert args.targets == ["part1/left"]

    def test_main_with_targets(self, mock_logger, mock_builder, tmp_path):
        """Verify that specific targets trigger both parts and diagram generation."""
        args = argparse.Namespace(outdir=tmp_path, env=None, targets=["part1"])
        main(mock_logger, args)

        mock_builder.return_value.generate_parts.assert_called_once_with(out_dir=tmp_path, names=["part1"])
        mock_builder.return_value.generate_diagram.assert_called_once_with(out_dir=tmp_path, names=["part1"])
        mock_builder.return_value._save_manifest.assert_called_once()

    def test_main_output_env_path(self, mock_logger, mock_builder, tmp_path):
        """Check if generate_diagram was called with correct unpacked gen_args."""
        args = argparse.Namespace(outdir=tmp_path, env=f"{tmp_path}.env", targets=[])
        main(mock_logger, args)
        mock_builder.return_value.config.dump_env.assert_called_once_with(f"{tmp_path}.env")
        mock_logger.done.assert_called_once()

    def test_main_generate_all_fallback(self, mock_logger, mock_builder, tmp_path):
        """Test the else block when no flags are provided."""
        args = argparse.Namespace(outdir=tmp_path, env=None, targets=[])
        main(mock_logger, args)
        mock_builder.return_value.generate_all.assert_called_once_with(out_dir=tmp_path)
        mock_builder.return_value._save_manifest.assert_called_once()
        mock_logger.done.assert_called_once()


class TestBuilderLogic:
    """Unit tests for Builder internal logic."""

    @pytest.fixture
    def builder(self):
        """Return a builder instance with a mocked manager."""
        manager = MagicMock()
        manager.config = MagicMock()
        return Builder(manager, logger=MagicMock())

    def test_get_summary(self, builder):
        """Verify target list truncation in log summary."""
        assert builder._get_summary(["a", "b"]) == "a, b"
        long_list = [str(i) for i in range(10)]
        summary = builder._get_summary(long_list)
        assert "..." in summary
        assert "(10 items)" in summary

    def test_resolve_subassemblies(self, builder):
        """Verify subassembly resolution logic."""
        # Case 1: base_subs is provided explicitly
        assert builder._resolve_subassemblies(MagicMock(spec=TargetList), ["left"]) == ["left"]

        # Case 2: base_subs is empty, resolve from manifest for multiple targets
        mock_targets = MagicMock(spec=TargetList)
        mock_targets.__iter__.side_effect = lambda: iter(["t1", "t2"])
        builder.manager.router.manifest = {
            "t1": {Action.PART: {SUBASSEMBLIES: ["a", "b"]}},
            "t2": {Action.PART: {SUBASSEMBLIES: ["b", "c"]}},
        }
        res = builder._resolve_subassemblies(mock_targets, [])
        assert res == ["a", "b", "c"]

        # Case 3: No subassemblies found in manifest
        mock_targets_empty = MagicMock(spec=TargetList)
        mock_targets_empty.__iter__.side_effect = lambda: iter(["t1"])
        builder.manager.router.manifest = {"t1": {Action.PART: {}}}
        assert builder._resolve_subassemblies(mock_targets_empty, []) == []

    def test_generate_parts_mixed_subassemblies(self, builder):
        """Verify that generate_parts handles a mix of subassembly and base targets."""
        # Setup mock base targets
        base_targets = MagicMock(spec=TargetList)
        base_targets.__iter__.side_effect = lambda: iter(["t_sub", "t_base"])
        base_targets.subassemblies = []
        # Mock subassembly filtering: "left" returns t_sub, others return empty
        base_targets.for_subassemblies.side_effect = lambda s: ["t_sub"] if "left" in s else []
        base_targets.for_targets.side_effect = lambda names: list(names)

        # Mock the resolver and router
        builder.target_parser = MagicMock()
        builder.target_parser.parse.return_value = MagicMock()
        builder.target_parser.resolve.return_value = base_targets
        builder.manager.router.manifest = {
            "t_sub": {Action.PART: {SUBASSEMBLIES: ["left"]}},
            "t_base": {Action.PART: {}},
        }
        builder.manager.router.run.return_value = []

        with patch.object(builder, "_export_parts"):
            builder.generate_parts("out", names=["test_target"])
            # Should have run "left" subassembly and then the remaining base target
            assert builder.manager.router.run.call_count == 2

    def test_get_part_hash(self, builder):
        """Verify part hashing logic."""
        part = Box(1, 1, 1)
        h1 = builder._get_part_hash(part)
        assert len(h1) == 40  # SHA1 length

        h2 = builder._get_part_hash(Box(1, 1, 1))
        assert h1 == h2

    def test_get_diagram_hash(self, builder):
        """Verify diagram hashing logic."""
        room = MagicMock(spec=Room)
        # Mock export_diagram to write something to the BytesIO stream
        room.export_diagram.side_effect = lambda s, o: s.write(b"svg_data")

        h = builder._get_diagram_hash(room, None)
        assert h == hashlib.sha1(b"svg_data").hexdigest()

    def test_load_manifest(self, builder, tmp_path):
        """Verify loading existing manifest from disk."""
        manifest_file = tmp_path / "build_manifest.yaml"

        # Test migration from flat format
        flat_data = {"p/t": "hash1"}
        manifest_file.write_text(yaml.dump(flat_data))

        builder._load_manifest(str(tmp_path))
        assert builder.build_manifest == {"brep": flat_data, "file": {}}
        assert builder._manifest_out_dir == str(tmp_path)

        # Verify it doesn't reload if directory is the same
        builder.build_manifest = {"manual": "edit"}
        builder._load_manifest(str(tmp_path))
        assert builder.build_manifest == {"manual": "edit"}

        # Test migration from old nested formats (sha1/stl -> file)
        old_nested_data = {"brep": {"p/t": "h1"}, "sha1": {"p/t": "s1"}}
        manifest_file.write_text(yaml.dump(old_nested_data))
        builder._manifest_out_dir = None  # Reset to force reload
        builder._load_manifest(str(tmp_path))
        assert builder.build_manifest == {"brep": {"p/t": "h1"}, "file": {"p/t": "s1"}}

        old_nested_data_stl = {"brep": {"p/t": "h1"}, "stl": {"p/t": "s1"}}
        manifest_file.write_text(yaml.dump(old_nested_data_stl))
        builder._manifest_out_dir = None
        builder._load_manifest(str(tmp_path))
        assert builder.build_manifest == {"brep": {"p/t": "h1"}, "file": {"p/t": "s1"}}

        # Test loading nested format
        nested_data = {"brep": {"p/t": "h1"}, "file": {"p/t": "s1"}}
        manifest_file.write_text(yaml.dump(nested_data))
        builder._manifest_out_dir = None  # Reset to force reload
        builder._load_manifest(str(tmp_path))
        assert builder.build_manifest == nested_data

    def test_save_manifest(self, builder, tmp_path):
        """Verify saving manifest to disk."""
        builder.build_manifest = {"brep": {"p/t": "h1"}, "file": {"p/t": "s1"}}
        builder._save_manifest(str(tmp_path))

        manifest_file = tmp_path / "build_manifest.yaml"
        assert manifest_file.exists()
        assert yaml.safe_load(manifest_file.read_text()) == builder.build_manifest

    def test_export_if_changed(self, builder, tmp_path):
        """Verify hash-based export skip logic."""
        path = tmp_path / "part.stl"
        manifest_key = "p/t"
        current_hash = "h1"
        file_hash = "f1"
        export_fn = MagicMock()

        # Mock _get_file_hash since export_fn doesn't actually write a file
        with patch.object(builder, "_get_file_hash", return_value=file_hash):
            # 1. No manifest, no file -> Export
            builder._export_if_changed(path, manifest_key, current_hash, export_fn)
            export_fn.assert_called_once()
            assert builder.build_manifest["brep"][manifest_key] == current_hash
            assert builder.build_manifest["file"][manifest_key] == file_hash

        # 2. Manifest matches and file exists -> Skip
        path.touch()
        builder.build_manifest["file"].pop(manifest_key, None)  # Ensure it's missing to test backfill
        export_fn.reset_mock()
        with patch.object(builder, "_get_file_hash", return_value=file_hash):
            builder._export_if_changed(path, manifest_key, current_hash, export_fn)
            export_fn.assert_not_called()
            assert builder.build_manifest["file"][manifest_key] == file_hash

        # 3. Hash mismatch -> Export
        export_fn.reset_mock()
        with patch.object(builder, "_get_file_hash", return_value=file_hash):
            builder._export_if_changed(path, manifest_key, "h2", export_fn)
            export_fn.assert_called_once()
            assert builder.build_manifest["brep"][manifest_key] == "h2"

        # 4. Force update -> Export
        export_fn.reset_mock()
        with patch.object(builder, "_get_file_hash", return_value=file_hash):
            builder._export_if_changed(path, manifest_key, "h2", export_fn, force_update=True)
            export_fn.assert_called_once()
