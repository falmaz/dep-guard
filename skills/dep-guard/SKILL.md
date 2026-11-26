---
name: dep-guard
description: >-
  Deterministic dependency, font, asset, and CDN license compliance audit powered by Trivy.
  Use when adding dependencies/assets, before shipping to production, or when the user asks to
  check licenses, copyright/DMCA risks, or generate THIRD_PARTY_NOTICES.
---

# dep-guard — Builder-Friendly License & Asset Audit

Run deterministic license compliance checks using Trivy (with automatic zero-dependency fallback) plus font/SVG/asset provenance and CDN scanning.

## When to Run
- After installing new packages (`npm`, `pnpm`, `yarn`, `pip`, `uv`, `cargo`, `go`)
- After adding fonts (`.ttf`, `.otf`, `.woff2`), icons (`.svg`), or datasets (`.parquet`, `.sqlite`, `.db`)
- Before shipping a commercial SaaS/app release, or when the user asks to audit dependencies/licenses

## Procedure

1. **Run the deterministic scan** in the project root:
   ```bash
   dep-guard --format json .
   ```
   *(If `dep-guard` is not on `PATH`, run `python3 <plugin_root>/bin/dep-guard --format json .`. Add `--deep` to enable Trivy `--license-full` source-level scanning.)*

2. **Interpret findings in plain English for the builder:**
   - **BLOCK (`CC-BY-NC-*`, `AGPL-*`, `SSPL`, `BUSL`, `NonCommercial` fonts/SVGs):**
     Explain *why* in one sentence (e.g., *"This package/font is licensed for non-commercial use only and risks DMCA takedowns or settlement demands in a paid product"*).
   - **WARN (`GPL-*`, `LGPL-*`, `UNKNOWN`, untracked fonts/datasets, commercial CDNs):**
     Flag clearly and ask whether the user has a commercial license or wants a permissive alternative.

3. **Propose immediate drop-in replacements:**
   - For blocked packages: suggest a well-known permissive (`MIT`, `Apache-2.0`, `BSD-3-Clause`, `ISC`) alternative.
   - For blocked fonts/icons: suggest `OFL-1.1` fonts (e.g., Google Fonts self-hosted / Inter / Geist) or `MIT`/`ISC` icon packs (`lucide`, `heroicons`, `tabler-icons`).
   - For untracked legitimate assets: run `dep-guard --init-assets .` and fill in verified `license` and `source` fields in `ASSETS_LICENSES.json`.

4. **Re-run to verify exit code 0** after applying fixes.
