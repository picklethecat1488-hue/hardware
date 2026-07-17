#!/usr/bin/env python3
"""
License Compliance Scanner.

Runs scancode-toolkit via Docker and checks dependencies against an allowlist.
Exits with code 1 on violations to fail workflows, and code 0 on success.
"""

import argparse
import json
import os
import subprocess
import sys
import shutil

# Conservative default allowlist (lowercased when compared)
DEFAULT_ALLOWLIST = {
    "gpl-3.0-only",
    "gpl-3.0-or-later",
    "lgpl-2.1-only",
    "lgpl-2.1-or-later",
    "lgpl-3.0-only",
    "lgpl-3.0-or-later",
    "apache-2.0",
    "mit",
    "bsd-2-clause",
    "bsd-3-clause",
    "isc",
    "mpl-2.0",
}


def run_scancode(workspace_root: str, report_path: str):
    """Run scancode-toolkit on the workspace."""
    scancode_path = shutil.which("scancode")
    if scancode_path:
        print(f"Running license scan natively using {scancode_path}...")
        cmd = [
            "scancode",
            "--license",
            "--json-pp",
            report_path,
            "--ignore",
            "target",
            "--ignore",
            ".venv",
            "--ignore",
            ".git",
            "--ignore",
            "build",
            workspace_root,
        ]
        # Silence libmagic/libarchive UserWarnings by setting PYTHONWARNINGS=ignore for the subprocess
        env = os.environ.copy()
        env["PYTHONWARNINGS"] = "ignore"
        try:
            subprocess.run(cmd, check=True, env=env)
            print(f"Scan completed successfully. Report saved to {report_path}")
            return
        except subprocess.CalledProcessError as e:
            print(f"Error running scancode command: {e}", file=sys.stderr)
            sys.exit(1)

    print("Error: 'scancode' executable not found on host.", file=sys.stderr)
    print("To install it locally, run: pip install scancode-toolkit", file=sys.stderr)
    print("Or ensure it is available in your PATH.", file=sys.stderr)
    sys.exit(1)


def parse_report(report_path: str):
    """Parse scancode report and return a mapping of package/file -> list of license keys."""
    if not os.path.exists(report_path):
        print(f"Error: scancode report not found at {report_path}", file=sys.stderr)
        sys.exit(2)

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    licenses = {}

    # 1. Try to extract package-level dependencies (detected from Cargo.toml, package.json etc.)
    packages = data.get("packages", [])
    if isinstance(packages, list) and packages:
        for p in packages:
            name = p.get("name") or p.get("package_name") or p.get("path") or p.get("package_url") or "<unnamed>"
            lic_keys = set()
            for l in p.get("licenses", []):
                key = l.get("license_key") or l.get("short_name") or l.get("key")
                if key:
                    lic_keys.add(key)
            if not lic_keys and p.get("other_license"):
                lic_keys.add(p.get("other_license"))

            licenses[name] = sorted(list(lic_keys)) or ["unknown"]
    else:
        # 2. Fall back to scanning file-level license headers
        print("No package-level metadata found. Falling back to file-level scan...")
        for fnode in data.get("files", []):
            path = fnode.get("path")
            file_lics = set()
            for l in fnode.get("licenses", []):
                key = l.get("license_key") or l.get("short_name") or l.get("key")
                if key:
                    file_lics.add(key)
            if file_lics:
                licenses[path] = sorted(list(file_lics))

    return licenses


def check_licenses(licenses, allowlist):
    """Compare detected licenses against the allowlist and return violations."""
    problematic = {}
    for name, lic_list in licenses.items():
        found_violations = []
        for lk in lic_list:
            if not lk or lk == "unknown":
                found_violations.append("unknown")
            else:
                lk_norm = lk.strip().lower()
                if lk_norm not in allowlist:
                    found_violations.append(lk)
        if found_violations:
            problematic[name] = found_violations
    return problematic


def main():
    """Run the license compliance scan."""
    parser = argparse.ArgumentParser(description="License Compliance Checker")
    parser.add_argument(
        "--run-scan", action="store_true", help="Run scancode-toolkit via Docker to generate the report first"
    )
    parser.add_argument(
        "--report",
        default="scancode-report.json",
        help="Path to the scancode JSON report file (default: scancode-report.json)",
    )
    parser.add_argument("--workspace", default=".", help="Workspace root path to scan (default: current directory)")
    args = parser.parse_args()

    # 1. Run scancode if requested
    if args.run_scan:
        run_scancode(args.workspace, args.report)

    # 2. Parse the generated report
    print(f"Parsing scan report from {args.report}...")
    licenses = parse_report(args.report)

    # 3. Check for compliance violations
    problematic = check_licenses(licenses, DEFAULT_ALLOWLIST)

    if not problematic:
        print("\nSUCCESS: No potentially incompatible or unknown dependency licenses found.")
        sys.exit(0)

    # 4. Report violations and fail the run
    print("\n[Violation] Potentially incompatible or unknown licenses detected:")
    for pkg, lics in problematic.items():
        print(f"  - {pkg}: {', '.join(lics)}")

    print("\nThis scan uses a conservative allowlist. Please review the licenses above for compatibility with GPLv3.")
    sys.exit(1)


if __name__ == "__main__":
    main()
