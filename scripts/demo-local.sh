#!/usr/bin/env bash
# Pretty local MCP demo for one tool. Never prints secrets.
# Args: TOOL_SHORT_NAME  JSON_ARGS  (JSON via DEMO_ARGS env preferred)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOL="${1:?tool short name e.g. eu-company-verify}"
ARGS_JSON="${DEMO_ARGS:-${2:-}}"
if [[ -z "$ARGS_JSON" ]]; then
  echo "Provide JSON args as \$2 or DEMO_ARGS"; exit 2
fi
FULL="dataandbeyond--${TOOL}"
echo "════════════════════════════════════════════════════════"
echo " Demo: open-data-mcp / ${TOOL}"
echo " Local stdio → official open data APIs (no Apify token)"
echo "════════════════════════════════════════════════════════"
echo
# Show a safe display form (single-quoted)
echo "\$ node scripts/demo-mcp-call.mjs ${FULL} '${ARGS_JSON}'"
echo
cd "$ROOT"
node scripts/demo-mcp-call.mjs "$FULL" "$ARGS_JSON"
echo
echo "Done."
