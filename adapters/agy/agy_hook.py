#!/usr/bin/env python3
"""
Antigravity (agy) Stop hook for dep-guard.
Runs once per turn on normal completion (skips when continuationActive is true
to avoid loops). Blocks stop with remediation guidance only on BLOCK violations.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parent
# Works both in-repo (adapters/agy/) and when installed into ~/.gemini/config/plugins/dep-guard/
DEP_GUARD_CANDIDATES = [
    HOOK_DIR / "bin" / "dep-guard",
    HOOK_DIR.parent.parent / "bin" / "dep-guard",
]


def find_dep_guard() -> Path | None:
    for cand in DEP_GUARD_CANDIDATES:
        if cand.is_file():
            return cand
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print("{}")
        return 0

    if payload.get("continuationActive"):
        print("{}")
        return 0

    if payload.get("terminationReason") != "NO_TOOL_CALL":
        print("{}")
        return 0

    dep_guard = find_dep_guard()
    if not dep_guard:
        print("{}")
        return 0

    cwd = payload.get("cwd") or (payload.get("workspacePaths") or [os.getcwd()])[0]
    proc = subprocess.run(
        [sys.executable, str(dep_guard), "--format", "json", cwd],
        capture_output=True,
        text=True,
        timeout=55,
    )

    try:
        report = json.loads(proc.stdout)
    except Exception:
        print("{}")
        return 0

    blocks = report.get("block_count", 0)
    if blocks > 0:
        lines = [
            f"- [{f['severity']}] {f['target']} ({f['license']}): {f['reason']}"
            for f in report.get("findings", [])
            if f.get("severity") == "BLOCK"
        ][:15]
        reason = (
            f"dep-guard blocked {blocks} commercial-license violation(s):\n"
            + "\n".join(lines)
            + "\nExplain the risk in plain English and propose or apply a commercial-safe replacement (MIT/Apache-2.0/BSD/OFL-1.1)."
        )
        print(json.dumps({"decision": "continue", "reason": reason}))
        return 0

    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
