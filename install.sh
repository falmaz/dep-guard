#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${DEP_GUARD_REPO:-https://github.com/falmaz/dep-guard.git}"
INSTALL_DIR="${DEP_GUARD_HOME:-${HOME}/.local/share/dep-guard}"
MODE="--all"
INSTALL_TRIVY=1

for arg in "$@"; do
  case "$arg" in
    --cc|--codex|--agy|--all) MODE="$arg" ;;
    --no-trivy) INSTALL_TRIVY=0 ;;
    -h|--help)
      echo "Usage: install.sh [--all | --cc | --codex | --agy] [--no-trivy]"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: install.sh [--all | --cc | --codex | --agy] [--no-trivy]" >&2
      exit 2
      ;;
  esac
done

# Support both local execution (./install.sh) and piped execution (curl ... | bash)
SCRIPT_DIR=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  CANDIDATE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ -f "${CANDIDATE}/bin/dep-guard" ]]; then
    SCRIPT_DIR="$CANDIDATE"
  fi
fi

if [[ -n "$SCRIPT_DIR" ]]; then
  REPO_DIR="$SCRIPT_DIR"
else
  if [[ -d "${INSTALL_DIR}/.git" ]]; then
    echo "[dep-guard] Updating ${INSTALL_DIR}..."
    git -C "$INSTALL_DIR" pull --ff-only --quiet
  else
    echo "[dep-guard] Cloning ${REPO_URL} -> ${INSTALL_DIR}..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --depth 1 --quiet "$REPO_URL" "$INSTALL_DIR"
  fi
  REPO_DIR="$INSTALL_DIR"
fi

maybe_install_trivy() {
  if command -v trivy >/dev/null 2>&1; then
    echo "[trivy] Already installed ($(trivy --version | head -n 1))"
    return
  fi
  if [[ "$INSTALL_TRIVY" -eq 1 ]] && command -v brew >/dev/null 2>&1; then
    echo "[trivy] Installing via Homebrew..."
    brew install trivy >/dev/null && echo "[trivy] Installed." || echo "[trivy] Optional install skipped (continuing with built-in scanner)."
  else
    echo "[trivy] Not found (optional). Install later via 'brew install trivy' for full transitive scanning."
  fi
}

install_cli() {
  local bin_dir="${HOME}/.local/bin"
  mkdir -p "$bin_dir"
  chmod +x "${REPO_DIR}/bin/dep-guard" "${REPO_DIR}/hooks/cc_post_tool.py" "${REPO_DIR}/adapters/agy/agy_hook.py"
  ln -sf "${REPO_DIR}/bin/dep-guard" "${bin_dir}/dep-guard"
  echo "[cli] Linked dep-guard -> ${bin_dir}/dep-guard"
  if [[ ":${PATH}:" != *":${bin_dir}:"* ]]; then
    echo "[cli] Add to your shell profile if needed: export PATH=\"\${HOME}/.local/bin:\${PATH}\""
  fi
}

install_cc() {
  local skill_dir="${HOME}/.claude/skills/dep-guard"
  mkdir -p "$skill_dir"
  cp "${REPO_DIR}/skills/dep-guard/SKILL.md" "${skill_dir}/SKILL.md"
  echo "[claude-code] Installed skill -> ${skill_dir}/SKILL.md"
  echo "[claude-code] For automatic PostToolUse hooks: claude --plugin-dir \"${REPO_DIR}\""
}

install_codex() {
  local skill_dir="${HOME}/.codex/skills/dep-guard"
  mkdir -p "$skill_dir"
  cp "${REPO_DIR}/skills/dep-guard/SKILL.md" "${skill_dir}/SKILL.md"
  echo "[codex] Installed skill -> ${skill_dir}/SKILL.md"
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

maybe_install_trivy

case "$MODE" in
  --cc)    install_cli; install_cc ;;
  --codex) install_cli; install_codex ;;
  --agy)   install_cli; install_agy ;;
  --all)   install_cli; install_cc; install_codex; install_agy ;;
esac

echo ""
echo "Done! Try: dep-guard ."
