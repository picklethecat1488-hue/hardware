"""Unit tests for the license compliance scanner script."""

import sys
import os
import json
from unittest.mock import patch, MagicMock, mock_open
import pytest

# Ensure parent directory is in sys.path to import the scripts module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import scripts.license_compliance as lc


def test_check_licenses():
    """Test check_licenses with allowed and disallowed licenses."""
    allowlist = {"mit", "apache-2.0"}

    # Case 1: All licenses in allowlist
    licenses = {
        "pkg1": ["mit"],
        "pkg2": ["apache-2.0"],
    }
    violations = lc.check_licenses(licenses, allowlist)
    assert not violations

    # Case 2: One license not in allowlist
    licenses = {
        "pkg1": ["mit"],
        "pkg2": ["gpl-3.0"],
    }
    violations = lc.check_licenses(licenses, allowlist)
    assert violations == {"pkg2": ["gpl-3.0"]}

    # Case 3: Unknown or empty license
    licenses = {
        "pkg1": ["unknown"],
        "pkg2": [""],
    }
    violations = lc.check_licenses(licenses, allowlist)
    assert violations == {"pkg1": ["unknown"], "pkg2": ["unknown"]}


def test_parse_report_packages():
    """Test parse_report with package-level metadata."""
    report_data = {
        "packages": [
            {
                "name": "pkg1",
                "licenses": [{"license_key": "mit"}],
            },
            {
                "package_name": "pkg2",
                "licenses": [{"short_name": "apache-2.0"}],
            },
            {
                "path": "pkg3",
                "licenses": [{"key": "bsd-3-clause"}],
            },
            {
                "package_url": "pkg4",
                "other_license": "gpl-3.0",
            },
        ]
    }

    mock_json = json.dumps(report_data)
    with patch("builtins.open", mock_open(read_data=mock_json)):
        with patch("os.path.exists", return_value=True):
            licenses = lc.parse_report("dummy_report.json")
            assert licenses == {
                "pkg1": ["mit"],
                "pkg2": ["apache-2.0"],
                "pkg3": ["bsd-3-clause"],
                "pkg4": ["gpl-3.0"],
            }


def test_parse_report_files_fallback():
    """Test parse_report falling back to file-level scan when packages is empty."""
    report_data = {
        "packages": [],
        "files": [
            {
                "path": "src/main.py",
                "licenses": [{"license_key": "mit"}],
            },
            {
                "path": "src/helper.py",
                "licenses": [{"short_name": "apache-2.0"}],
            },
        ],
    }

    mock_json = json.dumps(report_data)
    with patch("builtins.open", mock_open(read_data=mock_json)):
        with patch("os.path.exists", return_value=True):
            licenses = lc.parse_report("dummy_report.json")
            assert licenses == {
                "src/main.py": ["mit"],
                "src/helper.py": ["apache-2.0"],
            }


def test_parse_report_not_found():
    """Test parse_report exit behavior when report file is missing."""
    with patch("os.path.exists", return_value=False):
        with pytest.raises(SystemExit) as exc_info:
            lc.parse_report("nonexistent.json")
        assert exc_info.value.code == 2


@patch("shutil.which")
@patch("subprocess.run")
def test_run_scancode_success(mock_run, mock_which):
    """Test successful run of run_scancode."""
    mock_which.return_value = "/usr/local/bin/scancode"

    lc.run_scancode("src", "report.json")

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "scancode"
    assert "src" in cmd
    assert "report.json" in cmd


@patch("shutil.which")
def test_run_scancode_missing_executable(mock_which):
    """Test run_scancode when scancode is not installed on host."""
    mock_which.return_value = None

    with pytest.raises(SystemExit) as exc_info:
        lc.run_scancode("src", "report.json")
    assert exc_info.value.code == 1


@patch("scripts.license_compliance.run_scancode")
@patch("scripts.license_compliance.parse_report")
@patch("scripts.license_compliance.check_licenses")
def test_main_success(mock_check, mock_parse, mock_run):
    """Test successful main execution flow."""
    mock_parse.return_value = {"pkg1": ["mit"]}
    mock_check.return_value = {}  # No violations

    with patch("sys.argv", ["license_compliance.py", "--run-scan"]):
        with pytest.raises(SystemExit) as exc_info:
            lc.main()
        assert exc_info.value.code == 0

    mock_run.assert_called_once_with(".", "scancode-report.json")


@patch("scripts.license_compliance.run_scancode")
@patch("scripts.license_compliance.parse_report")
@patch("scripts.license_compliance.check_licenses")
def test_main_violation(mock_check, mock_parse, mock_run):
    """Test main execution flow when violations are detected."""
    mock_parse.return_value = {"pkg1": ["gpl-2.0"]}
    mock_check.return_value = {"pkg1": ["gpl-2.0"]}  # Violation

    with patch("sys.argv", ["license_compliance.py"]):
        with pytest.raises(SystemExit) as exc_info:
            lc.main()
        assert exc_info.value.code == 1

    mock_run.assert_not_called()
