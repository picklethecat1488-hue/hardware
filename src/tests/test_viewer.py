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

    def test_resolve_targets_parsing(self, viewer):
        """Verify parsing of provider/target/action/subassembly strings."""
        target_path = "p1/t1"
        viewer.manager.router.manifest = {target_path: {Action.PART: {}}}

        # Mock for_targets to return a list containing the matched target
        viewer.manager.router.targets.for_targets.side_effect = lambda names: (
            [target_path] if names[0] in [target_path, "t1"] else []
        )

        # Case 1: Full hierarchy
        targets, action, sub = viewer._resolve_targets("p1/t1/part/left")
        assert list(targets) == [target_path]
        assert action == "part"
        assert sub == "left"

        # Case 2: Implicit action (target/sub)
        targets, action, sub = viewer._resolve_targets("p1/t1/right")
        assert action is None
        assert sub == "right"

        # Case 3: Action override (target/action)
        targets, action, sub = viewer._resolve_targets("p1/t1/view")
        assert action == "view"
        assert sub is None

    def test_resolve_subassemblies_wildcards(self, viewer):
        """Verify wildcard resolution for subassemblies."""
        manifest = {Action.PART: {"subassemblies": ["left", "right", "center"]}}

        # Wildcard match
        subs = viewer._resolve_subassemblies("*t", manifest, Action.PART, "t1", has_wildcards=True)
        assert subs == ["left", "right"]

        # Literal match
        subs = viewer._resolve_subassemblies("left", manifest, Action.PART, "t1", has_wildcards=False)
        assert subs == ["left"]

        # No match (warning case)
        subs = viewer._resolve_subassemblies("missing", manifest, Action.PART, "t1", has_wildcards=True)
        assert subs is None

    @patch("cadquery.Color", side_effect=lambda *args: args)
    @patch("cadquery.Assembly")
    @patch("cadquery.Shape.cast")
    @patch("view.show")
    def test_show_view_metadata_alignment(self, mock_show, mock_cast, mock_assy_cls, mock_color, viewer):
        """Verify color/alpha lists are aligned even with mixed metadata."""
        t1, t2 = "p1/part", "p1/diagram"

        # Ensure mocks returned by for_targets support iteration AND have a provider attribute
        m1 = MagicMock(spec=TargetList, provider=viewer.manager.router.targets.provider, modes=[Mode.DEFAULT])
        m1.__iter__.return_value = iter([t1])
        m1.__len__.return_value = 1
        m1.__getitem__.return_value = t1

        m2 = MagicMock(spec=TargetList, provider=viewer.manager.router.targets.provider, modes=[Mode.DEFAULT])
        m2.__iter__.return_value = iter([t2])
        m2.__len__.return_value = 1
        m2.__getitem__.return_value = t2

        viewer.manager.router.targets.for_targets.side_effect = [m1, m2]
        viewer.manager.router.manifest = {t1: {Action.PART: {}}, t2: {Action.DIAGRAM: {}}}

        # Part has color, Diagram does not (None)
        mock_geom_1 = MagicMock(spec=Part)
        mock_geom_1.wrapped = "fake_wrapped_1"
        mock_diag_room = Room()
        mock_diag_room.add("diagram", MagicMock(spec=Part, wrapped="fake_wrapped_diag"))

        viewer.manager.router.run.side_effect = [
            [(t1, mock_geom_1)],  # Result for t1
            [("p1", mock_diag_room)],  # Result for t2
        ]
        viewer.manager.router.get_color.return_value = (1, 0, 0, 0.5)

        viewer.show_view([t1, t2])

        mock_assy = mock_assy_cls.return_value
        # 3 calls: 1 for internal diagram item, 1 for p1_part, 1 for p1_diagram
        assert mock_assy.add.call_count == 3

        # Verify p1_part color/alignment
        c1_args, c1_kwargs = mock_assy.add.call_args_list[1]
        assert c1_kwargs["name"] == "p1_part"
        assert c1_kwargs["color"] == (1.0, 0.0, 0.0, 0.5)

        # Verify p1_diagram (Diagrams return an assembly/compound which handles its own color)
        c2_args, c2_kwargs = mock_assy.add.call_args_list[2]
        assert c2_kwargs["name"] == "p1_diagram"

    def test_list_targets(self, viewer):
        """Verify list_targets formatting and Enum coercion."""
        viewer.manager.router.manifest = {"p1/t1": {Action.PART: {"modes": [Mode.PRINT], "subassemblies": ["left"]}}}
        viewer.list_targets()

        # Check that logger was called with expected formatted strings
        calls = viewer.logger.print.call_args_list
        call_args = [c[0][0] for c in calls]

        # Verify that all valid argument combinations are printed
        assert "Found 1 targets:" in call_args
        assert "p1/t1" in call_args
        assert "p1/t1/part" in call_args
        assert "p1/t1/part/left" in call_args
        assert "p1/t1/left" in call_args

    @patch("cadquery.Color", side_effect=lambda *args: args)
    @patch("cadquery.Assembly")
    @patch("cadquery.Shape.cast")
    @patch("view.show")
    def test_show_view_room(self, mock_show, mock_cast, mock_assy_cls, mock_color, viewer):
        """Verify show_view handles Action.VIEW targets."""
        target_name = "tube/wire"
        viewer.manager.router.targets.__iter__.return_value = iter([target_name])
        viewer.manager.router.targets.__getitem__.return_value = target_name
        viewer.manager.router.manifest = {target_name: {Action.VIEW: {}}}

        mock_geom = MagicMock()
        del mock_geom.toCompound
        mock_geom.wrapped = "fake_wrapped"
        # VIEW actions return a list of (target, Room) tuples
        mock_room = Room()
        mock_room.add("item_0", mock_geom, color=(1, 0, 1))
        viewer.manager.router.run.return_value = [(target_name, mock_room)]

        viewer.show_view([target_name])

        mock_show.assert_called_once()
        mock_assy = mock_assy_cls.return_value
        mock_assy.add.assert_called_once()
        args, kwargs = mock_assy.add.call_args
        assert args[0] == mock_cast.return_value
        assert kwargs["name"] == "tube_wire_item_0"
        assert kwargs["color"] == (1, 0, 1, 1)

    @patch("cadquery.Color", side_effect=lambda *args: args)
    @patch("cadquery.Assembly")
    @patch("cadquery.Shape.cast")
    @patch("view.show")
    def test_show_view_part(self, mock_show, mock_cast, mock_assy_cls, mock_color, viewer):
        """Verify show_view handles Action.PART targets."""
        target_name = "tube/driver"
        viewer.manager.router.targets.__iter__.return_value = iter([target_name])
        viewer.manager.router.targets.__getitem__.return_value = target_name
        viewer.manager.router.manifest = {target_name: {Action.PART: {}}}

        mock_geom = MagicMock(spec=Part)
        mock_geom.wrapped = "fake_wrapped"
        viewer.manager.router.run.return_value = [(target_name, mock_geom)]
        viewer.manager.router.get_color.return_value = (1, 0, 0, 1)

        viewer.show_view([target_name])

        mock_show.assert_called_once()
        mock_assy = mock_assy_cls.return_value
        mock_assy.add.assert_called_once()
        args, kwargs = mock_assy.add.call_args
        assert args[0] == mock_cast.return_value
        assert kwargs["name"] == "tube_driver"
        assert kwargs["color"] == (1, 0, 0, 1)

    @patch("cadquery.Color", side_effect=lambda *args: args)
    @patch("cadquery.Assembly")
    @patch("cadquery.Shape.cast")
    @patch("view.show")
    def test_show_view_diagram(self, mock_show, mock_cast, mock_assy_cls, mock_color, viewer):
        """Verify show_view handles Action.DIAGRAM targets."""
        target_name = "tube/diagram"
        viewer.manager.router.targets.__iter__.return_value = iter([target_name])
        viewer.manager.router.targets.__getitem__.return_value = target_name
        viewer.manager.router.manifest = {target_name: {Action.DIAGRAM: {}}}

        mock_diag_room = Room()
        mock_diag_room.add("item", MagicMock(spec=Part, wrapped="fake_wrapped_diag"))
        viewer.manager.router.run.return_value = [("tube", mock_diag_room)]

        viewer.show_view([target_name])

        mock_show.assert_called_once()
        mock_assy = mock_assy_cls.return_value
        # 2 calls: 1 for item inside diagram room, 1 for tube_diagram itself
        assert mock_assy.add.call_count == 2
        args, kwargs = mock_assy.add.call_args_list[1]
        assert kwargs["name"] == "tube_diagram"

    @patch("cadquery.Color", side_effect=lambda *args: args)
    @patch("cadquery.Assembly")
    @patch("cadquery.Shape.cast")
    @patch("view.show")
    def test_show_view_multiple_targets(self, mock_show, mock_cast, mock_assy_cls, mock_color, viewer):
        """Verify show_view handles multiple targets at once."""
        t1, t2 = "tube/driver", "tube/passenger"
        viewer.manager.router.targets.__iter__.side_effect = [iter([t1]), iter([t2])]

        # Return configured mocks from for_targets to satisfy iteration and attribute access
        m1 = MagicMock(
            __iter__=lambda x: iter([t1]), provider=viewer.manager.router.targets.provider, modes=[Mode.DEFAULT]
        )
        m2 = MagicMock(
            __iter__=lambda x: iter([t2]), provider=viewer.manager.router.targets.provider, modes=[Mode.DEFAULT]
        )
        viewer.manager.router.targets.for_targets.side_effect = [m1, m2]

        viewer.manager.router.manifest = {t1: {Action.PART: {}}, t2: {Action.PART: {}}}

        # Return one geom for each target run
        g1, g2 = MagicMock(spec=Part), MagicMock(spec=Part)
        g1.wrapped, g2.wrapped = "w1", "w2"
        viewer.manager.router.run.side_effect = [[(t1, g1)], [(t2, g2)]]
        viewer.manager.router.get_color.return_value = (1, 1, 1, 1)

        viewer.show_view([t1, t2])

        assert mock_show.call_count == 1
        mock_assy = mock_assy_cls.return_value
        assert mock_assy.add.call_count == 2
        names = [c[1]["name"] for c in mock_assy.add.call_args_list]
        assert "tube_driver" in names
        assert "tube_passenger" in names

    @patch("cadquery.Color", side_effect=lambda *args: args)
    @patch("cadquery.Assembly")
    @patch("cadquery.Shape.cast")
    @patch("view.show")
    def test_show_view_name_collision_deduplication(self, mock_show, mock_cast, mock_assy_cls, mock_color, viewer):
        """Verify that items with colliding names are de-duplicated with suffixes."""
        t1, t2 = "p1/t1", "p2/t1"

        # Mocking for_targets
        m1 = MagicMock(spec=TargetList, provider=viewer.manager.router.targets.provider, modes=[Mode.DEFAULT])
        m1.__iter__.return_value = iter([t1])
        m1.__len__.return_value = 1
        m2 = MagicMock(spec=TargetList, provider=viewer.manager.router.targets.provider, modes=[Mode.DEFAULT])
        m2.__iter__.return_value = iter([t2])
        m2.__len__.return_value = 1
        viewer.manager.router.targets.for_targets.side_effect = [m1, m2]

        viewer.manager.router.manifest = {t1: {Action.PART: {}}, t2: {Action.PART: {}}}

        # Return one geom for each target run, forcing a name collision on "duplicate"
        g1, g2 = MagicMock(spec=Part), MagicMock(spec=Part)
        g1.wrapped, g2.wrapped = "w1", "w2"
        viewer.manager.router.run.side_effect = [[("duplicate", g1)], [("duplicate", g2)]]
        viewer.manager.router.get_color.return_value = (1, 1, 1, 1)

        viewer.show_view([t1, t2])

        mock_assy = mock_assy_cls.return_value
        assert mock_assy.add.call_count == 2
        names = [c[1]["name"] for c in mock_assy.add.call_args_list]
        assert "duplicate" in names
        assert "duplicate_1" in names

    def test_show_view_not_found(self, viewer):
        """Verify error when target is not found."""
        viewer.manager.router.targets.for_targets.return_value = []
        with pytest.raises(ValueError, match="not found in any registered provider"):
            viewer.show_view(["missing"])

    @patch("cadquery.Color", side_effect=lambda *args: args)
    @patch("cadquery.Assembly")
    @patch("cadquery.Shape.cast")
    @patch("view.show")
    def test_show_view_unpacks_builders(self, mock_show, mock_cast, mock_assy_cls, mock_color, viewer):
        """Verify show_view unpacks BuildPart, BuildSketch, BuildLine objects."""
        # Mock BuildPart, BuildSketch, BuildLine and their .part/.sketch/.line attributes
        mock_part_obj = MagicMock(spec=Part)
        mock_part_obj.wrapped = "wp"
        mock_build_part = MagicMock(spec=BuildPart)
        mock_build_part.part = mock_part_obj

        mock_sketch_obj = MagicMock(spec=Sketch)
        mock_sketch_obj.wrapped = "ws"
        mock_build_sketch = MagicMock(spec=BuildSketch)
        mock_build_sketch.sketch = mock_sketch_obj

        mock_line_obj = MagicMock(spec=Wire)
        mock_line_obj.wrapped = "wl"
        mock_build_line = MagicMock(spec=BuildLine)
        mock_build_line.line = mock_line_obj

        # Mock a provider that returns these builder objects
        target_name = "mock/builders"
        viewer.manager.router.targets.__iter__.return_value = iter([target_name])
        viewer.manager.router.targets.__getitem__.return_value = target_name
        viewer.manager.router.manifest = {target_name: {Action.VIEW: {}}}

        # Simulate _get_view_items returning builder objects inside a Room
        mock_room = Room()
        mock_room.add("part", mock_build_part, color=(1, 0, 0))
        mock_room.add("sketch", mock_build_sketch, color=(0, 1, 0))
        mock_room.add("line", mock_build_line, color=(0, 0, 1))
        viewer.manager.router.run.return_value = [(target_name, mock_room)]

        viewer.show_view([target_name])

        mock_show.assert_called_once()
        mock_assy = mock_assy_cls.return_value
        assert mock_assy.add.call_count == 3
        names = [c[1]["name"] for c in mock_assy.add.call_args_list]
        assert names == ["mock_builders_part", "mock_builders_sketch", "mock_builders_line"]

    def test_show_view_unsupported_action(self, viewer):
        """Verify error when target supports no visual actions."""
        target_name = "tube/config_only"
        viewer.manager.router.targets.__iter__.return_value = iter([target_name])
        viewer.manager.router.targets.__getitem__.return_value = target_name
        viewer.manager.router.manifest = {target_name: {Action.CONFIG: {}}}

        with pytest.raises(ValueError, match="No geometry generated for the specified targets"):
            viewer.show_view([target_name])
