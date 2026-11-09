#!/usr/bin/env bash
# Idempotent Artifact skill installer for Claude Code / Codex (local).
# Grok Bot server surface: see ../harness/grok-bot.md
set -euo pipefail

WRITE_SNIPPETS=0
PREFIX="${HOME}"

usage() {
  cat <<'USAGE'
Usage: bash scripts/install.sh [--user] [--write-snippets] [--prefix DIR]

  --user            Install under $HOME (default)
  --write-snippets  Write/refresh marker-guarded snippets in ~/.claude/CLAUDE.md
                    and ~/.agents/AGENTS.md (replaces old ARTIFACT SKILL block)
  --prefix DIR      Override home-like prefix (default: $HOME)
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) shift ;;
    --write-snippets) WRITE_SNIPPETS=1; shift ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CLAUDE_SKILL="${PREFIX}/.claude/skills/artifact"
CODEX_SKILL="${PREFIX}/.agents/skills/artifact"
BIN_DIR="${PREFIX}/.local/bin"
STORE_DIR="${PREFIX}/.artifact"
WRAPPER="${BIN_DIR}/artifact"
SHARE_DIR="${PREFIX}/.local/share/artifact-skill"

copy_skill() {
  local dest="$1"
  mkdir -p "${dest}"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude 'scripts/__pycache__' \
      --exclude 'mcp/__pycache__' \
      --exclude '.git' \
      --exclude '.artifact' \
      "${PKG_DIR}/" "${dest}/"
  else
    mkdir -p "${dest}/references" "${dest}/scripts" "${dest}/harness" "${dest}/mcp" "${dest}/store"
    cp -f "${PKG_DIR}/SKILL.md" "${dest}/SKILL.md"
    find "${PKG_DIR}/references" -maxdepth 1 -type f -exec cp -f {} "${dest}/references/" \;
    find "${PKG_DIR}/scripts" -maxdepth 1 -type f -exec cp -f {} "${dest}/scripts/" \;
    find "${PKG_DIR}/harness" -maxdepth 1 -type f -exec cp -f {} "${dest}/harness/" \;
    find "${PKG_DIR}/mcp" -maxdepth 1 -type f -exec cp -f {} "${dest}/mcp/" \;
    find "${PKG_DIR}/store" -maxdepth 1 -type f -exec cp -f {} "${dest}/store/" \;
    [[ -f "${PKG_DIR}/README.md" ]] && cp -f "${PKG_DIR}/README.md" "${dest}/README.md"
    chmod +x "${dest}/scripts/"*.py "${dest}/scripts/"*.sh "${dest}/mcp/"*.py 2>/dev/null || true
  fi
}

install_wrapper() {
  mkdir -p "${BIN_DIR}" "${SHARE_DIR}"
  copy_skill "${SHARE_DIR}"
  {
    echo '#!/usr/bin/env bash'
    echo "exec python3 \"${SHARE_DIR}/scripts/artifact_cli.py\" \"\$@\""
  } > "${WRAPPER}"
  chmod +x "${WRAPPER}"
}

refresh_snippet() {
  local file="$1"
  mkdir -p "$(dirname "${file}")"
  export ARTIFACT_SHARE_DIR="${SHARE_DIR}"
  python3 - "${file}" <<'PY'
import os, sys
from pathlib import Path

path = Path(sys.argv[1])
share = os.environ.get("ARTIFACT_SHARE_DIR", str(Path.home() / ".local/share/artifact-skill"))
begin = "# BEGIN ARTIFACT SKILL"
end = "# END ARTIFACT SKILL"
new_block = f"""{begin}
# Artifact skill (local harness hint)
# Skill: ~/.claude/skills/artifact  and  ~/.agents/skills/artifact
# Tools (CLI): artifact upsert|resolve|attach|query|classes|paths
# Tools (MCP): python3 {share}/mcp/server.py
#
# Per-turn class list inject (CODE, not model) — run at turn / agent-loop start:
#   artifact classes --inject
#   # or: python3 {share}/scripts/harness_inject.py --format prompt
# Paste/append that output into the system/append-system fragment.
#
# Store resolution:
#   1) ARTIFACT_STORE env
#   2) ./.artifact/store.json if present (or: artifact --project …)
#   3) ~/.artifact/store.json
# Docs: {share}/harness/
{end}"""

text = path.read_text(encoding="utf-8") if path.exists() else ""
b = text.find(begin)
e = text.find(end)
if b >= 0 and e >= 0 and e > b:
    e2 = e + len(end)
    updated = text[:b].rstrip() + "\n\n" + new_block + "\n" + text[e2:].lstrip("\n")
    action = "refreshed"
else:
    updated = (text.rstrip() + "\n\n" + new_block + "\n") if text.strip() else (new_block + "\n")
    action = "appended"
path.write_text(updated, encoding="utf-8")
print(f"{action} snippet: {path}")
PY
}

echo "== Artifact skill install =="
echo "package: ${PKG_DIR}"
echo "prefix:  ${PREFIX}"

mkdir -p "${STORE_DIR}"
if [[ ! -f "${STORE_DIR}/store.json" ]]; then
  cp "${PKG_DIR}/store/schema.json" "${STORE_DIR}/store.json"
  echo "created store: ${STORE_DIR}/store.json"
fi

mkdir -p "$(dirname "${CLAUDE_SKILL}")" "$(dirname "${CODEX_SKILL}")"
copy_skill "${CLAUDE_SKILL}"
echo "installed Claude skill: ${CLAUDE_SKILL}"
copy_skill "${CODEX_SKILL}"
echo "installed Codex skill:  ${CODEX_SKILL}"

install_wrapper
echo "installed CLI wrapper:  ${WRAPPER} -> ${SHARE_DIR}/scripts/artifact_cli.py"
echo "runtime package copy: ${SHARE_DIR}"

if [[ "${WRITE_SNIPPETS}" -eq 1 ]]; then
  refresh_snippet "${PREFIX}/.claude/CLAUDE.md"
  refresh_snippet "${PREFIX}/.agents/AGENTS.md"
else
  echo "snippets not auto-written (pass --write-snippets to append/refresh marker blocks)"
  echo "  preview: ${PKG_DIR}/harness/claude-code.md and ${PKG_DIR}/harness/codex.md"
fi

case ":${PATH}:" in
  *":${BIN_DIR}:"*) ;;
  *)
    echo "NOTE: add to PATH: export PATH=\"${BIN_DIR}:\$PATH\""
    ;;
esac

echo ""
echo "Next steps:"
echo "  1. Ensure ${BIN_DIR} is on PATH"
echo "  2. Restart Claude Code / Codex (or reload skills)"
echo "  3. Smoke: artifact --project upsert --name demo --reference art://demo"
echo "           artifact --project attach --reference art://demo --key class --value 示例类"
echo "           artifact --project classes --inject"
echo "  4. MCP:   python3 ${SHARE_DIR}/mcp/server.py"
echo "  5. Grok Bot: read ${SHARE_DIR}/harness/grok-bot.md"
echo "Done."
