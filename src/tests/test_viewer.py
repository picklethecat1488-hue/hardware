"""Unit tests for the Viewer class."""

import fnmatch
import pytest
from unittest.mock import MagicMock, patch, PropertyMock, call
from view import Viewer
from provider import Action, TargetList, Mode


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

    @patch("view.show")
    def test_show_view_metadata_alignment(self, mock_show, viewer):
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
        viewer.manager.router.run.side_effect = [
            [(t1, MagicMock())],  # Result for t1
            [("p1", MagicMock())],  # Result for t2
        ]
        viewer.manager.router.get_color.return_value = (1, 0, 0, 0.5)

        viewer.show_view([t1, t2])

        kwargs = mock_show.call_args[1]
        # Colors/Alphas should have 2 entries each to match the 2 objects
        assert len(kwargs["colors"]) == 2
        assert len(kwargs["alphas"]) == 2
        # Diagram index should have default values
        assert kwargs["colors"][1] == (1.0, 1.0, 1.0)
        assert kwargs["alphas"][1] == 1.0

    def test_list_targets(self, viewer):
        """Verify list_targets formatting and Enum coercion."""
        viewer.manager.router.manifest = {"p1/t1": {Action.PART: {"modes": [Mode.PRINT], "subassemblies": ["left"]}}}
        viewer.list_targets()

        # Check that logger was called with expected formatted strings
        calls = viewer.logger.print.call_args_list

        # Verify consolidated output format: p1/t1 [part(modes=['print'], subassemblies=['left'])]
        target_call = next(str(c) for c in calls if "p1/t1" in str(c))
        assert "part" in target_call
        assert "modes=['print']" in target_call
        assert "subassemblies=['left']" in target_call

    @patch("view.show")
    def test_show_view_room(self, mock_show, viewer):
        """Verify show_view handles Action.VIEW targets."""
        target_name = "tube/wire"
        viewer.manager.router.targets.__iter__.return_value = iter([target_name])
        viewer.manager.router.targets.__getitem__.return_value = target_name
        viewer.manager.router.manifest = {target_name: {Action.VIEW: {}}}

        mock_geom = MagicMock()
        viewer.manager.router.run.return_value = [(target_name, [(mock_geom, (1, 0, 1, 1))])]

        viewer.show_view([target_name])

        mock_show.assert_called_once()
        args, kwargs = mock_show.call_args
        assert args[0] == mock_geom
        assert kwargs["names"] == [f"{target_name}/item_0"]
        assert kwargs["colors"] == [(1, 0, 1)]
        assert kwargs["alphas"] == [1]

    @patch("view.show")
    def test_show_view_part(self, mock_show, viewer):
        """Verify show_view handles Action.PART targets."""
        target_name = "tube/driver"
        viewer.manager.router.targets.__iter__.return_value = iter([target_name])
        viewer.manager.router.targets.__getitem__.return_value = target_name
        viewer.manager.router.manifest = {target_name: {Action.PART: {}}}

        mock_geom = MagicMock()
        viewer.manager.router.run.return_value = [(target_name, mock_geom)]
        viewer.manager.router.get_color.return_value = (1, 0, 0, 1)

        viewer.show_view([target_name])

        mock_show.assert_called_once()
        args, kwargs = mock_show.call_args
        assert args[0] == mock_geom
        assert kwargs["names"] == [target_name]
        assert kwargs["colors"] == [(1, 0, 0)]

    @patch("view.show")
    def test_show_view_diagram(self, mock_show, viewer):
        """Verify show_view handles Action.DIAGRAM targets."""
        target_name = "tube/diagram"
        viewer.manager.router.targets.__iter__.return_value = iter([target_name])
        viewer.manager.router.targets.__getitem__.return_value = target_name
        viewer.manager.router.manifest = {target_name: {Action.DIAGRAM: {}}}

        mock_assy = MagicMock()
        viewer.manager.router.run.return_value = [("tube", mock_assy)]

        viewer.show_view([target_name])

        mock_show.assert_called_once()
        args, kwargs = mock_show.call_args
        assert args[0] == mock_assy
        assert kwargs["names"] == ["tube_diagram"]

    @patch("view.show")
    def test_show_view_multiple_targets(self, mock_show, viewer):
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
        viewer.manager.router.run.side_effect = [[(t1, MagicMock())], [(t2, MagicMock())]]
        viewer.manager.router.get_color.return_value = (1, 1, 1, 1)

        viewer.show_view([t1, t2])

        assert mock_show.call_count == 1
        kwargs = mock_show.call_args[1]
        assert len(kwargs["names"]) == 2
        assert t1 in kwargs["names"]
        assert t2 in kwargs["names"]

    def test_show_view_not_found(self, viewer):
        """Verify error when target is not found."""
        viewer.manager.router.targets.for_targets.return_value = []
        with pytest.raises(ValueError, match="not found in any registered provider"):
            viewer.show_view(["missing"])

    def test_show_view_unsupported_action(self, viewer):
        """Verify error when target supports no visual actions."""
        target_name = "tube/config_only"
        viewer.manager.router.targets.__iter__.return_value = iter([target_name])
        viewer.manager.router.targets.__getitem__.return_value = target_name
        viewer.manager.router.manifest = {target_name: {Action.CONFIG: {}}}

        with pytest.raises(ValueError, match="No geometry generated for the specified targets"):
            viewer.show_view([target_name])
