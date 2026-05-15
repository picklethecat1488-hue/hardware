"""Contains Build system unit tests."""

import argparse
from build import Logger
from config import Configurator, get_args, main
import cadquery as cq
import pytest


class TestConfigurator:
    """Configurator unit tests."""

    @pytest.fixture(scope="class")
    def configurator(self):
        """Return the test fixture for the manifold builder.

        :return _type_: A configurator object
        """
        return Configurator()

    def test_environment_not_modified(self, configurator):
        """Test that, when run, config.py does not produce any changes to the default .env file.

        :param _type_ configurator: The configurator to test.
        """
        configurator.configure_all()

        assert not configurator.config.model_has_changed, "changes to environment detected, run config.py"
