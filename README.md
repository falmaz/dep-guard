# dep-guard

Deterministic, Trivy-backed **license, font, asset, and CDN compliance guardrails** for builders using **Claude Code** (first priority), **Codex**, and **Antigravity (agy)** — plus CI & pre-commit.

## Why?
AI coding agents make shipping fast, but a single `CC-BY-NC`, `AGPL`, commercial SDK, or proprietary font (`Monotype` / `Linotype` / `Adobe`) can trigger DMCA takedowns or settlement demands once your SaaS/app gets traction.

`dep-guard` puts a **deterministic, zero-noise guardrail** in front of builders:
- **Dependencies:** Runs `trivy fs --scanners license` alongside a zero-dependency lockfile/manifest parser (`package-lock.json`, `package.json`, `pyproject.toml`). Detects unscanned `yarn.lock` / `pnpm-lock.yaml` / `requirements.txt` / `poetry.lock` / `uv.lock` coverage gaps and resolves them on demand with `--online` (via Google's `deps.dev` API).
- **Fonts & Assets:** Parses embedded `.ttf`, `.otf`, and `.woff` binary `name` tables (Python stdlib only) to block `NonCommercial` / `BY-NC` and unverified commercial foundry fonts (`Monotype`, `Linotype`, `Adobe Systems`, `All Rights Reserved`), while allowing open fonts (`OFL-1.1`, `Apache`, `MIT`). Checks asset provenance via `ASSETS_LICENSES.json` or `REUSE.toml`.
- **External CDNs:** Flags commercial/unapproved font & icon CDNs (`use.typekit.net`, `kit.fontawesome.com`, etc.) in HTML/CSS/JS while ignoring template placeholders and test files.
- **Agentic Remediation:** Hooks stay silent on normal code edits and fire only when manifests, package installs, or assets change—blocking violations so your agent explains the risk in plain English and swaps in a commercial-safe alternative (`MIT`, `Apache-2.0`, `OFL-1.1`).

---

## Get Started

### One-Step Install (CLI + Claude Code + Codex + Antigravity + Trivy)
```bash
curl -fsSL https://raw.githubusercontent.com/falmaz/dep-guard/main/install.sh | bash
```
This installs `dep-guard` to `~/.local/share/dep-guard`, links `~/.local/bin/dep-guard`, installs `trivy` via Homebrew if available, and sets up the skill/plugin for **Claude Code**, **Codex**, and **Antigravity**.

*(Target a single agent or skip Trivy: `... | bash -s -- --cc`, `--codex`, `--agy`, or `--no-trivy`.)*

### Enable Automatic Claude Code Hooks (optional)
```bash
claude --plugin-dir ~/.local/share/dep-guard
# or via Claude Code plugin marketplace:
# /plugin marketplace add falmaz/dep-guard
# /plugin install dep-guard@falmaz-dep-guard
```

### Run a Scan (CLI or CI)
```bash
dep-guard .                        # Fast offline scan (dependencies, fonts, assets, CDNs)
dep-guard --online .               # Also resolve unscanned requirements.txt / yarn / pnpm via deps.dev
dep-guard --format json .          # Machine-readable JSON output
dep-guard --deep .                 # Enable Trivy --license-full source-level scan
dep-guard --include-dev .          # Include devDependencies and test/e2e paths
dep-guard --strict .               # Exit 1 on WARN as well as BLOCK
dep-guard --init-assets .          # Scaffold ASSETS_LICENSES.json for existing fonts/assets
```

### Add to GitHub Actions (optional)
```yaml
- name: License & Asset Audit
  run: |
    git clone --depth 1 https://github.com/falmaz/dep-guard.git /tmp/dep-guard
    /tmp/dep-guard/bin/dep-guard --online .
```

### Customizing Policy
Drop a `.dep-guard.json` in your project root (using [`policy.json`](./policy.json) as a template) to override allowed/blocked SPDX licenses, commercial font patterns, excluded paths, or CDN allowlists.

## Contributing
Issues and PRs are welcome! See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License
MIT
