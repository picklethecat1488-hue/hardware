"""Unit tests for the Viewer class."""

import fnmatch
import pytest
from unittest.mock import MagicMock, patch, PropertyMock, call
from view import Viewer, BuildPart, BuildSketch, BuildLine, Part, Sketch, Wire
from provider import Action, TargetList, Mode, Room


class TestViewer:
    """Viewer unit tests."""

    @pytest.fixture
    def mock_manager(self):
        """Mock ProviderManager fixture."""
        manager = MagicMock()
        # Configure targets mock to support chaining and basic list behavior
        targets_mock = MagicMock(spec=TargetList)
        targets_mock.provider = MagicMock()
        targets_mock.modes = [Mode.DEFAULT]
        targets_mock.for_targets.return_value = targets_mock
        targets_mock.supporting.return_value = targets_mock
        # Ensure the mock is truthy for the 'if not targets' validation check
        targets_mock.__len__.return_value = 1
        targets_mock.__iter__.return_value = iter(["mock/target"])
        manager.router.targets = targets_mock
        return manager

    @pytest.fixture
    def mock_logger(self):
        """Mock Logger fixture."""
        return MagicMock()

    @pytest.fixture
    def viewer(self, mock_manager, mock_logger):
        """Viewer fixture."""
        return Viewer(mock_manager, mock_logger)

    def test_get_summary_truncation(self, viewer):
        """Verify summary logic for short and long lists."""
        assert viewer.get_summary(["a", "b"]) == "a, b"
        long_list = [str(i) for i in range(20)]
        summary = viewer.get_summary(long_list)
        assert summary.startswith("0, 1, 2, 3, 4, 5, 6, 7")
        assert "(20 items)" in summary

    @patch("view.show")
    def test_show_view_metadata_alignment(self, mock_show, viewer):
        """Verify color/alpha lists are aligned even with mixed metadata."""
        t1, t2 = "p1/part", "p1/diagram"

        # Ensure mocks returned by for_targets support iteration AND have a provider attribute
        m1 = MagicMock(spec=TargetList, provider=viewer.manager.router.targets.provider, modes=[Mode.DEFAULT])
        m1.__iter__.return_value = iter([t1])
        m1.__len__.return_value = 1
        m1.__getitem__.return_value = t1
        m1.subassemblies = []

        m2 = MagicMock(spec=TargetList, provider=viewer.manager.router.targets.provider, modes=[Mode.DEFAULT])
        m2.__iter__.return_value = iter([t2])
        m2.__len__.return_value = 1
        m2.__getitem__.return_value = t2
        m2.subassemblies = []

        viewer.target_parser.resolve = MagicMock(side_effect=[None, m1, m2])
        viewer.manager.router.manifest = {t1: {Action.PART: {}}, t2: {Action.DIAGRAM: {}}}

        with patch("provider.room.Compound", side_effect=lambda children: MagicMock(children=children)):
            # Part has color, Diagram does not (None)
            mock_geom_1 = MagicMock(spec=Part, label=None)
            mock_geom_1.wrapped = "fake_wrapped_1"
            mock_diag_room = Room()
            mock_diag_geom = MagicMock(spec=Part, label=None, wrapped="fake_wrapped_diag")
            mock_diag_room.add("diagram", mock_diag_geom)

            viewer.manager.router.run.side_effect = [
                [(t1, mock_geom_1)],  # Result for t1
                [("p1", mock_diag_room)],  # Result for t2
            ]
            viewer.manager.router.get_color.return_value = (1, 0, 0, 0.5)

            viewer.show_view([t1, t2])

            assert mock_show.called
            assy = mock_show.call_args[0][0]
            # Verify labels are present in the compound
            labels = [c.label for c in assy.children]
            assert "p1_part" in labels
            assert "p1_diagram" in labels

    def test_list_targets(self, viewer):
        """Verify list_targets formatting and Enum coercion."""
        viewer.manager.router.manifest = {"p1/t1": {Action.PART: {"modes": [Mode.PRINT], "subassemblies": ["left"]}}}
        viewer.list_targets()

        # Check that logger was called with expected formatted strings
        calls = viewer.logger.print.call_args_list
        call_args = [c[0][0] for c in calls]

        # Verify that all valid argument combinations are printed
        assert any("Found 6 targets:" in arg for arg in call_args)
        assert any("p1/t1" in arg for arg in call_args)
        assert any("p1/t1:part" in arg for arg in call_args)
        assert any("p1/t1_left:part" in arg for arg in call_args)
        assert any("p1/t1_left" in arg for arg in call_args)

    @patch("view.show")
    def test_show_view_room(self, mock_show, viewer):
        """Verify show_view handles Action.VIEW targets."""
        target_name = "tube/wire"
        mock_targets = MagicMock(spec=TargetList)
        mock_targets.__iter__.return_value = iter([target_name])
        mock_targets.__len__.return_value = 1
        mock_targets.subassemblies = []
        viewer.target_parser.resolve = MagicMock(side_effect=[mock_targets, None, None])
        viewer.manager.router.manifest = {target_name: {Action.VIEW: {}}}

        with patch("provider.room.Compound", side_effect=lambda children: MagicMock(children=children)):
            mock_geom = MagicMock(label=None)
            del mock_geom.toCompound
            mock_geom.wrapped = "fake_wrapped"
            # VIEW actions return a list of (target, Room) tuples
            mock_room = Room()
            mock_room.add("item_0", mock_geom, color=(1, 0, 1))
            viewer.manager.router.run.return_value = [(target_name, mock_room)]

            viewer.show_view([target_name])

            mock_show.assert_called_once()
            assy = mock_show.call_args[0][0]
            assert any(c.label == "tube_wire_item_0" for c in assy.children)

    @patch("view.show")
    def test_show_view_part(self, mock_show, viewer):
        """Verify show_view handles Action.PART targets."""
        target_name = "tube/driver"
        mock_targets = MagicMock(spec=TargetList)
        mock_targets.__iter__.return_value = iter([target_name])
        mock_targets.__len__.return_value = 1
        mock_targets.subassemblies = []
        viewer.target_parser.resolve = MagicMock(side_effect=[None, mock_targets, None])
        viewer.manager.router.manifest = {target_name: {Action.PART: {}}}

        with patch("provider.room.Compound", side_effect=lambda children: MagicMock(children=children)):
            mock_geom = MagicMock(spec=Part, label=None)
            mock_geom.wrapped = "fake_wrapped"
            viewer.manager.router.run.return_value = [(target_name, mock_geom)]
            viewer.manager.router.get_color.return_value = (1, 0, 0, 1)

            viewer.show_view([target_name])

            mock_show.assert_called_once()
            assy = mock_show.call_args[0][0]
            assert any(c.label == "tube_driver" for c in assy.children)

    @patch("view.show")
    def test_show_view_diagram(self, mock_show, viewer):
        """Verify show_view handles Action.DIAGRAM targets."""
        target_name = "tube/diagram"
        mock_targets = MagicMock(spec=TargetList)
        mock_targets.__iter__.return_value = iter([target_name])
        mock_targets.__len__.return_value = 1
        viewer.target_parser.resolve = MagicMock(side_effect=[None, None, mock_targets])
        viewer.manager.router.manifest = {target_name: {Action.DIAGRAM: {}}}

        with patch("provider.room.Compound", side_effect=lambda children: MagicMock(children=children)):
            mock_diag_room = Room()
            mock_diag_geom = MagicMock(spec=Part, label=None, wrapped="fake_wrapped_diag")
            mock_diag_room.add("item", mock_diag_geom)
            viewer.manager.router.run.return_value = [("tube", mock_diag_room)]

            viewer.show_view([target_name])

            mock_show.assert_called_once()
            assy = mock_show.call_args[0][0]
            # Verify diagram label is present in the compound
            assert any(c.label == "tube_diagram" for c in assy.children)

    @patch("view.show")
    def test_show_view_multiple_targets(self, mock_show, viewer):
        """Verify show_view handles multiple targets at once."""
        t1, t2 = "tube/driver", "tube/passenger"

        # Return configured mocks from for_targets to satisfy iteration and attribute access
        m1 = MagicMock(spec=TargetList, provider=viewer.manager.router.targets.provider, modes=[Mode.DEFAULT])
        m1.__iter__.return_value = iter([t1, t2])
        m1.__len__.return_value = 2
        m1.subassemblies = []

        viewer.target_parser.resolve = MagicMock(side_effect=[None, m1, None, m1])

        viewer.manager.router.manifest = {t1: {Action.PART: {}}, t2: {Action.PART: {}}}

        with patch("provider.room.Compound", side_effect=lambda children: MagicMock(children=children)):
            # Return one geom for each target run
            g1, g2 = MagicMock(spec=Part, label=None), MagicMock(spec=Part, label=None)
            g1.wrapped, g2.wrapped = "w1", "w2"
            viewer.manager.router.run.return_value = [(t1, g1), (t2, g2)]
            viewer.manager.router.get_color.return_value = (1, 1, 1, 1)

            viewer.show_view([t1, t2])

            assert mock_show.call_count == 1
            assy = mock_show.call_args[0][0]
            names = [c.label for c in assy.children]
            assert "tube_driver" in names
            assert "tube_passenger" in names

    @patch("view.show")
    def test_show_view_name_collision_deduplication(self, mock_show, viewer):
        """Verify that items with colliding names are de-duplicated with suffixes."""
        t1, t2 = "p1/t1", "p2/t1"

        m1 = MagicMock(spec=TargetList, provider=viewer.manager.router.targets.provider, modes=[Mode.DEFAULT])
        m1.__iter__.return_value = iter([t1, t2])
        m1.__len__.return_value = 2
        m1.subassemblies = []

        viewer.target_parser.resolve = MagicMock(side_effect=[None, m1, None, m1])

        viewer.manager.router.manifest = {t1: {Action.PART: {}}, t2: {Action.PART: {}}}

        with patch("provider.room.Compound", side_effect=lambda children: MagicMock(children=children)):
            # Return one geom for each target run, forcing a name collision on "duplicate"
            g1, g2 = MagicMock(spec=Part, label=None), MagicMock(spec=Part, label=None)
            g1.wrapped, g2.wrapped = "w1", "w2"
            viewer.manager.router.run.return_value = [("duplicate", g1), ("duplicate", g2)]
            viewer.manager.router.get_color.return_value = (1, 1, 1, 1)

            viewer.show_view([t1, t2])

            assy = mock_show.call_args[0][0]
            names = [c.label for c in assy.children]
            assert "duplicate" in names
            assert "duplicate_1" in names

    def test_show_view_not_found(self, viewer):
        """Verify error when target is not found."""
        viewer.target_parser.resolve = MagicMock(
            side_effect=ValueError("No geometry generated for the specified targets.")
        )
        with pytest.raises(ValueError, match="No geometry generated for the specified targets."):
            viewer.show_view(["missing"])

    @patch("view.show")
    def test_show_view_unpacks_builders(self, mock_show, viewer):
        """Verify show_view unpacks BuildPart, BuildSketch, BuildLine objects."""
        with patch("provider.room.Compound", side_effect=lambda children: MagicMock(children=children)):
            # Mock BuildPart, BuildSketch, BuildLine and their .part/.sketch/.line attributes
            mock_part_obj = MagicMock(spec=Part, label=None)
            mock_part_obj.wrapped = "wp"
            mock_build_part = MagicMock(spec=BuildPart)
            mock_build_part.part = mock_part_obj

            mock_sketch_obj = MagicMock(spec=Sketch, label=None)
            mock_sketch_obj.wrapped = "ws"
            mock_build_sketch = MagicMock(spec=BuildSketch)
            mock_build_sketch.sketch = mock_sketch_obj

            mock_line_obj = MagicMock(spec=Wire, label=None)
            mock_line_obj.wrapped = "wl"
            mock_build_line = MagicMock(spec=BuildLine)
            mock_build_line.line = mock_line_obj

            # Mock a provider that returns these builder objects
            target_name = "mock/builders"
            mock_targets = MagicMock(spec=TargetList)
            mock_targets.__iter__.return_value = iter([target_name])
            mock_targets.__len__.return_value = 1
            viewer.target_parser.resolve = MagicMock(side_effect=[mock_targets, None, None])
            viewer.manager.router.manifest = {target_name: {Action.VIEW: {}}}

            # Simulate _get_view_items returning builder objects inside a Room
            mock_room = Room()
            mock_room.add("part", mock_build_part, color=(1, 0, 0))
            mock_room.add("sketch", mock_build_sketch, color=(0, 1, 0))
            mock_room.add("line", mock_build_line, color=(0, 0, 1))
            viewer.manager.router.run.return_value = [(target_name, mock_room)]

            viewer.show_view([target_name])

            mock_show.assert_called_once()
            assy = mock_show.call_args[0][0]
            names = [c.label for c in assy.children]
            assert names == ["mock_builders_part", "mock_builders_sketch", "mock_builders_line"]

    def test_show_view_unsupported_action(self, viewer):
        """Verify error when target supports no visual actions."""
        target_name = "tube/config_only"
        viewer.manager.router.targets.__iter__.return_value = iter([target_name])
        viewer.manager.router.targets.__getitem__.return_value = target_name
        viewer.manager.router.manifest = {target_name: {Action.CONFIG: {}}}

        with pytest.raises(ValueError, match="No geometry generated for the specified targets"):
            viewer.show_view([target_name])
