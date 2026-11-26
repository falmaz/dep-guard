# License & Asset Compliance Rule (dep-guard)

- Only introduce commercial-safe dependencies (`MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`, `ISC`, `0BSD`, `OFL-1.1`).
- Never add `CC-BY-NC-*`, `AGPL-*`, `SSPL`, or non-commercial fonts/icons/datasets to a commercial project without explicit user approval.
- After installing packages or adding fonts/SVGs/datasets, run `dep-guard .` (or invoke the `dep-guard` skill) and resolve any `BLOCK` findings before finishing.
- Record verified fonts/datasets in `ASSETS_LICENSES.json` (run `dep-guard --init-assets .` to scaffold).
