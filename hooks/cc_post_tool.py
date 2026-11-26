#!/usr/bin/env python3
"""
Claude Code PostToolUse hook for dep-guard.
Only runs the deterministic scanner when a package install, dependency manifest,
or font/asset/CDN-bearing file was touched — zero noise on normal code edits.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent))
DEP_GUARD_BIN = PLUGIN_ROOT / "bin" / "dep-guard"

MANIFEST_NAMES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "pyproject.toml",
    "uv.lock",
    "poetry.lock",
    "cargo.toml",
    "cargo.lock",
    "go.mod",
    "go.sum",
    "gemfile.lock",
    "assets_licenses.json",
    "reuse.toml",
}

WATCHED_EXTS = {
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".svg",
    ".parquet",
    ".sqlite",
    ".db",
    ".html",
    ".css",
    ".scss",
}

PKG_INSTALL_RE = re.compile(
    r"\b(?:npm\s+(?:i|install|add)|pnpm\s+(?:i|install|add)|yarn\s+add|"
    r"pip3?\s+install|uv\s+(?:add|pip\s+install)|poetry\s+add|"
    r"cargo\s+add|go\s+get|bundle\s+add)\b",
    re.I,
)


def should_scan(tool_name: str, tool_input: dict) -> bool:
    if tool_name in ("Write", "Edit", "MultiEdit"):
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""
        p = Path(file_path)
        if p.name.lower() in MANIFEST_NAMES:
            return True
        if p.suffix.lower() in WATCHED_EXTS:
            return True
        return False

    if tool_name == "Bash":
        cmd = tool_input.get("command") or ""
        return bool(PKG_INSTALL_RE.search(cmd))

    return False


def format_findings_brief(report: dict) -> str:
    lines = []
    for f in report.get("findings", []):
        lines.append(f"- [{f['severity']}] {f['target']} ({f['license']}): {f['reason']}")
    return "\n".join(lines[:15])


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or os.getcwd()

    if not should_scan(tool_name, tool_input):
        return 0

    proc = subprocess.run(
        [sys.executable, str(DEP_GUARD_BIN), "--format", "json", cwd],
        capture_output=True,
        text=True,
        timeout=55,
    )

    try:
        report = json.loads(proc.stdout)
    except Exception:
        return 0

    blocks = report.get("block_count", 0)
    warns = report.get("warn_count", 0)

    if blocks > 0:
        reason = (
            f"dep-guard blocked {blocks} commercial-license violation(s):\n"
            f"{format_findings_brief(report)}\n"
            "Explain the license risk in plain English and propose a commercial-safe replacement (MIT/Apache-2.0/BSD/OFL-1.1)."
        )
        print(json.dumps({"decision": "block", "reason": reason}))
        return 0

    if warns > 0:
        ctx = (
            f"dep-guard found {warns} license/asset warning(s):\n"
            f"{format_findings_brief(report)}\n"
            "Briefly mention these to the user or record verified assets in ASSETS_LICENSES.json."
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": ctx,
                    }
                }
            )
        )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
