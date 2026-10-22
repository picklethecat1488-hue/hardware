"""Unit tests for Provider and ProviderRouter Orchestrators."""

import pytest
from unittest.mock import MagicMock, patch
from provider.provider import ProviderOrchestrator
from provider.provider_router import ProviderRouterOrchestrator
from provider import Section, Mode, MODES, SUBASSEMBLIES
from provider.room import Room


@pytest.fixture
def mock_provider():
    """Create a mock provider with a basic manifest."""
    provider = MagicMock()
    provider.name = "mock_p"
    provider.manifest = {
        "part_a": {
            Section.PART: {MODES: [Mode.DEFAULT], SUBASSEMBLIES: ["left"]},
            Section.CONFIG: {MODES: ["mount"]},
        }
    }
    provider.targets = ["part_a"]
    provider.part = {
        "part_a": MagicMock(return_value="geom"),
    }
    provider.diagram = {}
    provider.config = {
        "mount": MagicMock(return_value=None),
    }
    return provider


class TestProviderOrchestrator:
    """Tests for ProviderOrchestrator logic."""

    def test_pre_handler_validation(self, mock_provider):
        """Verify validation of actions, modes, and subassemblies."""
        orch = ProviderOrchestrator(mock_provider)

        # Unsupported mode
        with pytest.raises(ValueError, match="Mode 'print' is not supported for action 'part'"):
            orch.pre_handler(("part_a",), Section.PART, ("left",), (Mode.PRINT,))

        # Unsupported subassembly
        with pytest.raises(ValueError, match="Subassembly 'right' is not supported"):
            orch.pre_handler(("part_a",), Section.PART, ("right",), (Mode.DEFAULT,))


class TestProviderRouterOrchestrator:
    """Tests for ProviderRouterOrchestrator routing and merging."""

    @pytest.fixture
    def controller_context(self, mock_provider):
        """Set up a controller with one provider."""
        controller = MagicMock()
        controller.providers = [mock_provider]
        return controller

    def test_collect_mapping(self, controller_context, mock_provider):
        """Verify targets are correctly mapped to providers."""
        orch = ProviderRouterOrchestrator(controller_context)
        groups = orch.collect(("mock_p/part_a",))

        assert mock_provider in groups
        assert groups[mock_provider] == [0]

    def test_merge_zipping(self, controller_context, mock_provider):
        """Verify results are zipped back into (target, result) tuples."""
        orch = ProviderRouterOrchestrator(controller_context)

        # simulate return from provider runs: (provider, indices, provider_results)
        raw_results = [(mock_provider, [0], [("part_a", "geom_obj")])]

        merged = orch.merge(Section.PART, ("mock_p/part_a",), raw_results)
        assert merged == [("mock_p/part_a", "geom_obj")]

    def test_merge_diagram_special_case(self, controller_context, mock_provider):
        """Verify diagram merging returns provider-named tuples."""
        orch = ProviderRouterOrchestrator(controller_context)

        mock_room = MagicMock(spec=Room)
        raw_results = [(mock_provider, [0], mock_room)]
        merged = orch.merge(Section.DIAGRAM, ("mock_p/part_a",), raw_results)

        assert merged == [("mock_p", mock_room)]

    def test_missing_result_detection(self, controller_context, mock_provider):
        """Verify error if a result is unexpectedly None after merge."""
        orch = ProviderRouterOrchestrator(controller_context)

        # raw_results missing index 0
        raw_results = []
        with pytest.raises(ValueError, match="results for targets.*were not collected"):
            orch.merge(Section.PART, ("mock_p/part_a",), raw_results)

    @patch("concurrent.futures.ThreadPoolExecutor.map")
    def test_execute_parallel_call(self, mock_map, controller_context):
        """Verify that execute uses the thread pool executor."""
        orch = ProviderRouterOrchestrator(controller_context)
        # Mock a valid return value to satisfy validation in merge()
        provider = controller_context.providers[0]
        mock_map.return_value = [(provider, [0], [("part_a", "geom")])]

        orch.execute(("mock_p/part_a",), Section.PART)
        assert mock_map.called
