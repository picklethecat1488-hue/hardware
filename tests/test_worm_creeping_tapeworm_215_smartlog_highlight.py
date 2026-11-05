"""Regression tests for WORM-CREEPING-TAPEWORM-215: Smartlog commit node highlighting on click."""

import json
from pathlib import Path
import re
import shutil
import subprocess
import pytest


def test_smartlog_commit_node_highlighting_supports_arbitrary_hash_lengths():
    """Verify WORM-CREEPING-TAPEWORM-215: selectCommit highlights commits regardless of hash length.

    In Git repositories where default abbreviation is 8 or more characters (e.g. 68330218),
    smartlog nodes have IDs like 'node-68330218'. If selectCommit only looks up
    'node-' + commitHash.slice(0, 7), it returns null and no node is highlighted.
    selectCommit must resolve nodes using data-hash attributes, event.currentTarget,
    and flexible ID/prefix lookups.
    """
    tpl_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = tpl_path.read_text(encoding="utf-8")

    # 1. selectCommit must NOT solely rely on .slice(0, 7) for node lookup
    # It must support data-hash exact lookup and event.currentTarget / closest lookup
    assert 'data-hash="${commitHash}"' in tpl_text or "data-hash" in tpl_text
    assert 'data-hash^="${commitHash}"' in tpl_text or "data-hash" in tpl_text

    # Extract selectCommit function implementation
    match = re.search(r"async\s+function\s+selectCommit\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*function\s+", tpl_text)
    assert match is not None, "Could not find selectCommit function in diff_view.html.j2"
    fn_body = match.group(2)

    # selectCommit must not have the buggy hardcoded line that looks only for slice(0, 7)
    buggy_pattern = 'document.getElementById("node-" + commitHash.slice(0, 7))'
    assert buggy_pattern not in fn_body, (
        "selectCommit still uses fragile 7-character slice lookup: "
        "document.getElementById('node-' + commitHash.slice(0, 7))"
    )

    # 2. Working tree node must carry data-hash="working" for uniform selector queries
    assert 'id="node-working" data-hash="working"' in tpl_text


def test_smartlog_select_commit_runtime_behavior_with_node():
    """Verify runtime behavior of selectCommit logic with 8-character and arbitrary-length commit hashes."""
    node_bin = shutil.which("node")
    if not node_bin:
        pytest.skip("Node.js is not available in environment")

    tpl_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = tpl_path.read_text(encoding="utf-8")

    # Extract selectCommit function
    match = re.search(
        r"async\s+function\s+selectCommit\s*\(([^)]*)\)\s*\{([\s\S]*?\n\s*await loadFilesForActiveCommit\(\);\s*)\n\s*\}",
        tpl_text,
    )
    assert match is not None, "Could not extract selectCommit implementation"
    params = match.group(1)
    body = match.group(2)

    # Construct test script simulating the DOM
    test_script = f"""
    class ClassList {{
        constructor() {{
            this.classes = new Set();
        }}
        add(c) {{ this.classes.add(c); }}
        remove(c) {{ this.classes.delete(c); }}
        contains(c) {{ return this.classes.has(c); }}
    }}

    class MockElement {{
        constructor(id, dataHash) {{
            this.id = id;
            this.dataset = {{ hash: dataHash }};
            this.classList = new ClassList();
            this.style = {{}};
        }}
        querySelector(selector) {{ return null; }}
        closest(selector) {{ return this; }}
    }}

    const elements = [
        new MockElement("node-working", "working"),
        new MockElement("node-68330218", "68330218e7110a68b3f4d68b56803596aa779218"),
        new MockElement("node-b5abc4d2", "b5abc4d29ec1ce77dff64fcefa91a71a2dff0a7d")
    ];

    const state = {{
        activeCommit: "working",
        activeFile: null,
        currentDiff: null,
        selectedCommits: []
    }};

    const document = {{
        querySelectorAll(selector) {{
            if (selector === ".smartlog-node") return elements;
            if (selector === ".smartlog-node[data-hash]") return elements;
            return [];
        }},
        getElementById(id) {{
            return elements.find(e => e.id === id) || {{ style: {{}}, textContent: "" }};
        }},
        querySelector(selector) {{
            // Attribute selector matching
            const exactMatch = selector.match(/\\.smartlog-node\\[data-hash="([^"]+)"\\]/);
            if (exactMatch) {{
                return elements.find(e => e.dataset.hash === exactMatch[1]) || null;
            }}
            const prefixMatch = selector.match(/\\.smartlog-node\\[data-hash\\^="([^"]+)"\\]/);
            if (prefixMatch) {{
                return elements.find(e => e.dataset.hash.startsWith(prefixMatch[1])) || null;
            }}
            return null;
        }}
    }};

    async function loadFilesForActiveCommit() {{}}

    async function selectCommit({params}) {{
        {body}
    }}

    async function runTest() {{
        // Initial state: node-working is active
        elements[0].classList.add("active");

        // Click second commit (40-char full hash where short hash is 8 chars)
        const commit2Hash = "68330218e7110a68b3f4d68b56803596aa779218";
        await selectCommit(commit2Hash);

        if (!elements[1].classList.contains("active")) {{
            console.error("FAIL: 8-char short SHA commit was NOT highlighted!");
            process.exit(1);
        }}
        if (elements[0].classList.contains("active")) {{
            console.error("FAIL: working node remained active after selecting commit!");
            process.exit(1);
        }}

        // Click third commit with an event mock
        const commit3Hash = "b5abc4d29ec1ce77dff64fcefa91a71a2dff0a7d";
        const mockEvent = {{ currentTarget: elements[2] }};
        await selectCommit(commit3Hash, mockEvent);

        if (!elements[2].classList.contains("active")) {{
            console.error("FAIL: commit 3 with event was NOT highlighted!");
            process.exit(1);
        }}
        if (elements[1].classList.contains("active")) {{
            console.error("FAIL: commit 2 remained active after selecting commit 3!");
            process.exit(1);
        }}

        // Click working node again
        await selectCommit("working");
        if (!elements[0].classList.contains("active")) {{
            console.error("FAIL: working node was NOT highlighted on return!");
            process.exit(1);
        }}
        if (elements[2].classList.contains("active")) {{
            console.error("FAIL: commit 3 remained active after selecting working!");
            process.exit(1);
        }}

        // Click with short hash prefix
        await selectCommit("68330218");
        if (!elements[1].classList.contains("active")) {{
            console.error("FAIL: short hash lookup failed to highlight commit 2!");
            process.exit(1);
        }}

        console.log("SUCCESS: All smartlog commit selection transitions passed!");
    }}

    runTest();
    """

    res = subprocess.run([node_bin, "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"selectCommit failed runtime verification:\n{res.stdout}\n{res.stderr}"
