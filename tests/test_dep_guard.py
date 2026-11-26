#!/usr/bin/env python3
"""End-to-end deterministic tests for dep-guard CLI and agent hooks."""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEP_GUARD = REPO_ROOT / "bin" / "dep-guard"
CC_HOOK = REPO_ROOT / "hooks" / "cc_post_tool.py"
AGY_HOOK = REPO_ROOT / "adapters" / "agy" / "agy_hook.py"


def build_minimal_ttf(license_text: str) -> bytes:
    """Build a minimal valid TTF binary containing a 'name' table with NameID 13 (License)."""
    encoded = license_text.encode("utf-16-be")
    # Offset table: sfntVersion(4) + numTables(2) + searchRange(2) + entrySelector(2) + rangeShift(2) = 12
    offset_table = struct.pack(">IHHHH", 0x00010000, 1, 16, 0, 0)
    # 1 table directory entry = 16 bytes -> name table starts at offset 28
    name_table_offset = 28
    # Name table header: format(2) + count(2) + stringOffset(2) = 6
    # 1 name record = 12 bytes -> stringOffset = 18
    name_header = struct.pack(">HHH", 0, 1, 18)
    # platformID=3 (Windows), encodingID=1, langID=0x0409, nameID=13 (License), length, offset=0
    name_record = struct.pack(">HHHHHH", 3, 1, 0x0409, 13, len(encoded), 0)
    name_table = name_header + name_record + encoded
    table_dir = b"name" + struct.pack(">III", 0, name_table_offset, len(name_table))
    return offset_table + table_dir + name_table


def build_minimal_woff(license_text: str) -> bytes:
    """Build a minimal valid WOFF 1.0 binary with a zlib-compressed 'name' table."""
    encoded = license_text.encode("utf-16-be")
    name_header = struct.pack(">HHH", 0, 1, 18)
    name_record = struct.pack(">HHHHHH", 3, 1, 0x0409, 0, len(encoded), 0)  # nameID=0 (Copyright)
    name_table = name_header + name_record + encoded
    comp_table = zlib.compress(name_table)
    # WOFF header = 44 bytes, 1 table dir entry = 20 bytes -> table data at offset 64
    offset = 64
    total_len = offset + len(comp_table)
    woff_header = struct.pack(
        ">IIIHHIHHIIIII",
        0x774F4646,  # 'wOFF'
        0x00010000,  # flavor
        total_len,
        1,           # numTables
        0,           # reserved
        len(name_table) + 28,  # totalSfntSize
        1, 0,        # majorVersion, minorVersion
        0, 0, 0,     # metaOffset, metaLength, metaOrigLength
        0, 0,        # privOffset, privLength
    )
    table_dir = b"name" + struct.pack(">IIII", offset, len(comp_table), len(name_table), 0)
    return woff_header + table_dir + comp_table


class DepGuardTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, dict]:
        proc = subprocess.run(
            [sys.executable, str(DEP_GUARD), "--format", "json", *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
        data = json.loads(proc.stdout)
        return proc.returncode, data

    def test_clean_repo_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "package.json").write_text(json.dumps({"name": "demo", "license": "MIT"}), encoding="utf-8")
            (p / "index.html").write_text(
                '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">',
                encoding="utf-8",
            )
            code, report = self.run_cli("--no-trivy", tmp)
            self.assertEqual(code, 0)
            self.assertEqual(report["block_count"], 0)
            self.assertEqual(report["warn_count"], 0)

    def test_fallback_blocks_nc_and_agpl_and_warns_gpl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            lock = {
                "name": "demo",
                "lockfileVersion": 3,
                "packages": {
                    "": {"name": "demo", "license": "MIT"},
                    "node_modules/good-pkg": {"license": "MIT"},
                    "node_modules/bad-icons": {"license": "CC-BY-NC-4.0"},
                    "node_modules/viral-db": {"license": "AGPL-3.0-only"},
                    "node_modules/copyleft-lib": {"license": "GPL-3.0"},
                },
            }
            (p / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
            code, report = self.run_cli("--no-trivy", tmp)
            self.assertEqual(code, 1)
            self.assertEqual(report["block_count"], 2)
            self.assertEqual(report["warn_count"], 1)
            blocked_targets = {f["target"] for f in report["findings"] if f["severity"] == "BLOCK"}
            self.assertEqual(blocked_targets, {"bad-icons", "viral-db"})

    def test_trivy_real_scan_if_installed(self) -> None:
        if not shutil.which("trivy"):
            self.skipTest("trivy not installed")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            # Copy the real MIT LICENSE so Trivy's classifier detects it with confidence 1.0,
            # then verify our policy engine blocks it when MIT is in the custom blocked list.
            (p / "LICENSE").write_text((REPO_ROOT / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8")
            custom_policy = {
                "licenses": {"blocked": ["MIT"], "blocked_patterns": [], "warn": [], "allowed": []},
                "assets": {"require_manifest_for": [], "scan_metadata_for": [], "ignore_dirs": []},
                "cdns": {"allowed_hosts": [], "flagged_hosts": []},
            }
            policy_file = p / "custom-policy.json"
            policy_file.write_text(json.dumps(custom_policy), encoding="utf-8")
            code, report = self.run_cli("--deep", "--policy", str(policy_file), tmp)
            self.assertTrue(report["trivy_available"])
            self.assertEqual(code, 1)
            trivy_blocks = [
                f for f in report["findings"] if f["source"] == "trivy" and f["severity"] == "BLOCK"
            ]
            self.assertGreaterEqual(len(trivy_blocks), 1)

    def test_font_metadata_and_asset_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "fancy.ttf").write_bytes(build_minimal_ttf("Free for personal use only - NonCommercial"))
            code, report = self.run_cli("--no-trivy", tmp)
            self.assertEqual(code, 1)
            cats = {f["category"] for f in report["findings"]}
            self.assertIn("font_metadata", cats)
            self.assertIn("asset_provenance", cats)

            # Init assets manifest should clear the provenance warning
            subprocess.run([sys.executable, str(DEP_GUARD), "--init-assets", tmp], check=True, capture_output=True)
            _, report2 = self.run_cli("--no-trivy", tmp)
            cats2 = {f["category"] for f in report2["findings"]}
            self.assertNotIn("asset_provenance", cats2)
            self.assertIn("font_metadata", cats2)

    def test_svg_and_commercial_cdn_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "icon.svg").write_text(
                "<!-- SPDX-License-Identifier: CC-BY-NC-SA-4.0 --><svg></svg>",
                encoding="utf-8",
            )
            (p / "index.html").write_text(
                '<link rel="stylesheet" href="https://use.typekit.net/abc123.css">',
                encoding="utf-8",
            )
            code, report = self.run_cli("--no-trivy", tmp)
            self.assertEqual(code, 1)
            cats = {f["category"] for f in report["findings"]}
            self.assertIn("source_header", cats)
            self.assertIn("external_cdn", cats)

    def test_claude_code_hook_filtering_and_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            lock = {
                "lockfileVersion": 3,
                "packages": {"node_modules/bad-pkg": {"license": "CC-BY-NC-4.0"}},
            }
            (p / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")

            # 1. Normal code file edit -> zero noise (empty stdout)
            normal_payload = {
                "hook_event_name": "PostToolUse",
                "cwd": tmp,
                "tool_name": "Edit",
                "tool_input": {"file_path": str(p / "app.py")},
            }
            proc = subprocess.run(
                [sys.executable, str(CC_HOOK)],
                input=json.dumps(normal_payload),
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout.strip(), "")

            # 2. Bash npm install -> triggers scan & blocks
            install_payload = {
                "hook_event_name": "PostToolUse",
                "cwd": tmp,
                "tool_name": "Bash",
                "tool_input": {"command": "npm install bad-pkg"},
            }
            proc2 = subprocess.run(
                [sys.executable, str(CC_HOOK)],
                input=json.dumps(install_payload),
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(proc2.returncode, 0)
            out = json.loads(proc2.stdout)
            self.assertEqual(out["decision"], "block")
            self.assertIn("bad-pkg", out["reason"])

    def test_antigravity_stop_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "icon.svg").write_text("<!-- CC-BY-NC-4.0 --><svg/>", encoding="utf-8")

            # First stop -> returns continue with reason
            payload = {
                "cwd": tmp,
                "terminationReason": "NO_TOOL_CALL",
                "continuationActive": False,
            }
            proc = subprocess.run(
                [sys.executable, str(AGY_HOOK)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=30,
            )
            out = json.loads(proc.stdout)
            self.assertEqual(out["decision"], "continue")

            # When continuationActive is True -> does not loop
            payload["continuationActive"] = True
            proc2 = subprocess.run(
                [sys.executable, str(AGY_HOOK)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(json.loads(proc2.stdout), {})

    def test_malformed_bracketed_url_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "docs.html").write_text(
                '<a href="http://[not-an-ip]/x">bad</a>'
                '<a href="http://[Download]/font.woff2">bad2</a>'
                '<link rel="stylesheet" href="https://use.typekit.net/xyz.css">',
                encoding="utf-8",
            )
            code, report = self.run_cli("--no-trivy", tmp)
            self.assertEqual(code, 0)
            self.assertEqual(report["block_count"], 0)
            self.assertEqual(report["warn_count"], 1)
            self.assertEqual(report["findings"][0]["category"], "external_cdn")

    def test_mit0_allowed_and_dev_or_test_deps_excluded_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            web_lock = {
                "lockfileVersion": 3,
                "packages": {
                    "": {"name": "web", "license": "MIT"},
                    "node_modules/@csstools/color-helpers": {"license": "MIT-0"},
                    "node_modules/dev-gpl-tool": {"license": "GPL-3.0", "dev": True},
                },
            }
            (p / "package-lock.json").write_text(json.dumps(web_lock), encoding="utf-8")

            test_dir = p / "test" / "e2e" / "web"
            test_dir.mkdir(parents=True)
            e2e_lock = {
                "lockfileVersion": 3,
                "packages": {
                    "node_modules/axe-core": {"license": "MPL-2.0"},
                },
            }
            (test_dir / "package-lock.json").write_text(json.dumps(e2e_lock), encoding="utf-8")

            # Default scan: MIT-0 allowed, dev:true and test/** skipped
            code, report = self.run_cli("--no-trivy", tmp)
            self.assertEqual(code, 0)
            self.assertEqual(report["block_count"], 0)
            self.assertEqual(report["warn_count"], 0)

            # With --include-dev: both dev-gpl-tool and test/e2e axe-core are reported
            code2, report2 = self.run_cli("--no-trivy", "--include-dev", tmp)
            self.assertEqual(code2, 0)
            self.assertEqual(report2["warn_count"], 2)
            targets = {f["target"] for f in report2["findings"]}
            self.assertEqual(targets, {"dev-gpl-tool", "axe-core"})

    def test_worktrees_and_template_hosts_and_nested_tests_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            # 1. Agent worktree under .claude/worktrees/ should never be scanned
            wt_dir = p / ".claude" / "worktrees" / "branch-a" / "static"
            wt_dir.mkdir(parents=True)
            (wt_dir / "package-lock.json").write_text(
                json.dumps({"lockfileVersion": 3, "packages": {"node_modules/elkjs": {"license": "EPL-2.0"}}}),
                encoding="utf-8",
            )

            # 2. Template placeholder host in normal JS file should not be flagged
            src_dir = p / "static" / "src"
            src_dir.mkdir(parents=True)
            (src_dir / "app.js").write_text(
                'const a = `https://${ATTACKER}/f.woff`;\n'
                'const b = "https://localhost/font.woff2";\n'
                'const c = "https://<host>/font.ttf";\n',
                encoding="utf-8",
            )

            # 3. Nested __tests__ file with real commercial CDN is skipped by default, shown with --include-dev
            nested_test = p / "static" / "src" / "utils" / "__tests__"
            nested_test.mkdir(parents=True)
            (nested_test / "mermaidSafety.test.js").write_text(
                'const u = "https://use.typekit.net/test.css";\n',
                encoding="utf-8",
            )

            code, report = self.run_cli("--no-trivy", tmp)
            self.assertEqual(code, 0)
            self.assertEqual(report["block_count"], 0)
            self.assertEqual(report["warn_count"], 0)

            # --include-dev still skips .claude/worktrees/ and template hosts, but includes nested test file
            code2, report2 = self.run_cli("--no-trivy", "--include-dev", tmp)
            self.assertEqual(code2, 0)
            self.assertEqual(report2["warn_count"], 1)
            self.assertIn("mermaidSafety.test.js", report2["findings"][0]["target"])

    def test_woff_commercial_foundry_blocks_and_open_font_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "helvetica.woff").write_bytes(build_minimal_woff("Copyright 2020 Linotype GmbH. All Rights Reserved."))
            (p / "inter.woff").write_bytes(build_minimal_woff("Copyright 2020 Inter Authors. SIL Open Font License 1.1"))

            code, report = self.run_cli("--no-trivy", tmp)
            self.assertEqual(code, 1)
            blocks = [f for f in report["findings"] if f["severity"] == "BLOCK"]
            self.assertEqual(len(blocks), 1)
            self.assertEqual(blocks[0]["target"], "helvetica.woff")
            self.assertEqual(blocks[0]["category"], "font_metadata")

            # Once explicitly tracked in ASSETS_LICENSES.json, commercial foundry block clears
            (p / "ASSETS_LICENSES.json").write_text(
                json.dumps({"assets": [{"path": "helvetica.woff", "license": "Commercial", "source": "Linotype"}]}),
                encoding="utf-8",
            )
            code2, report2 = self.run_cli("--no-trivy", tmp)
            self.assertEqual(code2, 0)
            self.assertEqual(report2["block_count"], 0)

    def test_coverage_gaps_and_legacy_npm_strings_and_bare_homepage_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "requirements.txt").write_text("requests==2.32.0\n", encoding="utf-8")
            (p / "yarn.lock").write_text("# yarn lockfile v1\n", encoding="utf-8")
            (p / "package-lock.json").write_text(
                json.dumps(
                    {
                        "lockfileVersion": 3,
                        "packages": {
                            "node_modules/traverse": {"license": "MIT/X11"},
                            "node_modules/touch-punch": {
                                "license": "Dual licensed under the MIT or GPL Version 2 licenses."
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (p / "fontawesome.css").write_text("/* Font Awesome Free https://fontawesome.com */\n", encoding="utf-8")

            code, report = self.run_cli("--no-trivy", tmp)
            self.assertEqual(code, 0)
            self.assertEqual(report["block_count"], 0)
            self.assertEqual(report["warn_count"], 0)
            gap_files = {g["file"] for g in report["coverage_gaps"]}
            self.assertEqual(gap_files, {"requirements.txt", "yarn.lock"})


if __name__ == "__main__":
    unittest.main()
