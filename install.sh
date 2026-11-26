#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:---all}"

install_cli() {
  local bin_dir="${HOME}/.local/bin"
  mkdir -p "$bin_dir"
  ln -sf "${REPO_DIR}/bin/dep-guard" "${bin_dir}/dep-guard"
  chmod +x "${REPO_DIR}/bin/dep-guard" "${REPO_DIR}/hooks/cc_post_tool.py" "${REPO_DIR}/adapters/agy/agy_hook.py"
  echo "[cli] Linked dep-guard -> ${bin_dir}/dep-guard"
}

install_cc() {
  local skill_dir="${HOME}/.claude/skills/dep-guard"
  mkdir -p "$skill_dir"
  cp "${REPO_DIR}/skills/dep-guard/SKILL.md" "${skill_dir}/SKILL.md"
  echo "[claude-code] Installed skill -> ${skill_dir}/SKILL.md"
  echo "[claude-code] To load the full plugin (with automatic PostToolUse hooks):"
  echo "              claude --plugin-dir \"${REPO_DIR}\""
}

install_codex() {
  local skill_dir="${HOME}/.codex/skills/dep-guard"
  mkdir -p "$skill_dir"
  cp "${REPO_DIR}/skills/dep-guard/SKILL.md" "${skill_dir}/SKILL.md"
  echo "[codex] Installed skill -> ${skill_dir}/SKILL.md"
  echo "[codex] Optional: append ${REPO_DIR}/adapters/codex/AGENTS.md to your project's AGENTS.md"
}

install_agy() {
  local plugin_dir="${HOME}/.gemini/config/plugins/dep-guard"
  mkdir -p "${plugin_dir}/bin" "${plugin_dir}/rules" "${plugin_dir}/skills/dep-guard"
  cp "${REPO_DIR}/adapters/agy/plugin.json" "${plugin_dir}/plugin.json"
  cp "${REPO_DIR}/adapters/agy/hooks.json" "${plugin_dir}/hooks.json"
  cp "${REPO_DIR}/adapters/agy/agy_hook.py" "${plugin_dir}/agy_hook.py"
  cp "${REPO_DIR}/policy.json" "${plugin_dir}/policy.json"
  cp "${REPO_DIR}/bin/dep-guard" "${plugin_dir}/bin/dep-guard"
  cp "${REPO_DIR}/skills/dep-guard/SKILL.md" "${plugin_dir}/skills/dep-guard/SKILL.md"
  cp "${REPO_DIR}/adapters/codex/AGENTS.md" "${plugin_dir}/rules/AGENTS.md"
  chmod +x "${plugin_dir}/bin/dep-guard" "${plugin_dir}/agy_hook.py"
  echo "[agy] Installed native Antigravity plugin -> ${plugin_dir}"
}

case "$MODE" in
  --cc)    install_cli; install_cc ;;
  --codex) install_cli; install_codex ;;
  --agy)   install_cli; install_agy ;;
  --all)   install_cli; install_cc; install_codex; install_agy ;;
  *)
    echo "Usage: $0 [--cc | --codex | --agy | --all]" >&2
    exit 2
    ;;
esac

if ! command -v trivy >/dev/null 2>&1; then
  echo ""
  echo "Tip: Install Trivy for full transitive & file-level license scanning:"
  echo "     brew install trivy"
fi
