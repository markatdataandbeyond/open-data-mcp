#!/usr/bin/env bash
# Record asciinema casts for 3 actors, convert to GIF+PNG. Never prints secrets.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="$ROOT/assets/demo"
WORK="${DEMO_WORK:-/tmp/demo-work}"
mkdir -p "$DEMO" "$WORK"

if [[ -z "${APIFY_TOKEN:-}" ]]; then
  echo "APIFY_TOKEN required"; exit 1
fi

export COLUMNS="${COLUMNS:-100}"
export LINES="${LINES:-30}"

record_one() {
  local actor="$1"
  local cast="$DEMO/${actor}.cast"
  local gif="$DEMO/${actor}.gif"
  local png="$DEMO/${actor}.png"
  echo "---- Recording $actor ----"
  rm -f "$cast"
  asciinema rec "$cast" \
    --overwrite \
    --cols 100 \
    --rows 32 \
    --title "dataandbeyond/$actor demo" \
    --command "bash -lc 'cd \"$ROOT\" && bash scripts/demo-actor.sh \"$actor\" \"$WORK\"'" \
    2>"$WORK/${actor}-asciinema.err"
  echo "cast bytes: $(wc -c < "$cast")"
  agg --idle-time-limit 0.8 --speed 1.15 --font-size 13 \
    "$cast" "$gif"
  echo "gif bytes: $(wc -c < "$gif")"
  python3 -c "from PIL import Image; im=Image.open('$gif'); print('frames', im.n_frames, im.size)"
  python3 "$ROOT/scripts/cast_to_png.py" "$cast" "$png"
}

for a in eu-company-verify vin-decoder-recalls scholar-search; do
  record_one "$a"
done

python3 - "$DEMO" "$WORK" <<'PY'
import json, os, re, sys, hashlib
from datetime import datetime, timezone
demo, work = sys.argv[1], sys.argv[2]
actors = ["eu-company-verify", "vin-decoder-recalls", "scholar-search"]
man = {"generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "actors": {}}
for a in actors:
    meta_path = f"{work}/{a}-direct.meta.json"
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    mcp = open(f"{work}/{a}-mcp.txt").read() if os.path.exists(f"{work}/{a}-mcp.txt") else ""
    m = re.search(r"runId: (\S+)", mcp) or re.search(r'"runId"\s*:\s*"([^"]+)"', mcp)
    mcp_run = m.group(1) if m else None
    files = {}
    for ext in ("cast", "gif", "png"):
        p = f"{demo}/{a}.{ext}"
        if os.path.exists(p):
            files[ext] = {
                "path": f"assets/demo/{a}.{ext}",
                "bytes": os.path.getsize(p),
                "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest()[:16],
            }
    man["actors"][a] = {
        "direct": meta,
        "mcpRunId": mcp_run,
        "files": files,
        "rawGithub": {
            "gif": f"https://raw.githubusercontent.com/markatdataandbeyond/open-data-mcp/main/assets/demo/{a}.gif",
            "png": f"https://raw.githubusercontent.com/markatdataandbeyond/open-data-mcp/main/assets/demo/{a}.png",
            "cast": f"https://raw.githubusercontent.com/markatdataandbeyond/open-data-mcp/main/assets/demo/{a}.cast",
        },
    }
json.dump(man, open(f"{demo}/manifest.json", "w"), indent=2, ensure_ascii=False)
print(json.dumps({k: {"mcpRunId": v["mcpRunId"], "highlights": v["direct"].get("highlights"), "files": list(v["files"])} for k,v in man["actors"].items()}, indent=2))
PY

echo "ALL DEMOS RECORDED"
ls -la "$DEMO"
