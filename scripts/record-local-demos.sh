#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="$ROOT/assets/demo"
mkdir -p "$DEMO"

record_one() {
  local name="$1"
  local tool="$2"
  local args="$3"
  local cast="$DEMO/${name}.cast"
  local gif="$DEMO/${name}.gif"
  local png="$DEMO/${name}.png"
  echo "---- Recording $name ----"
  rm -f "$cast"
  # Export DEMO_ARGS so nested bash/asciinema keep JSON intact
  asciinema rec "$cast" \
    --overwrite \
    --cols 100 \
    --rows 28 \
    --title "open-data-mcp / $name" \
    --command "env DEMO_ARGS=$(printf %q "$args") bash -lc 'cd \"$ROOT\" && bash scripts/demo-local.sh \"$tool\"'" \
    2>/tmp/asciinema-${name}.err
  test -s "$cast"
  echo "cast bytes: $(wc -c < "$cast")"
  # Verify JSON actually ran
  if grep -q "Invalid JSON" "$cast"; then
    echo "ERROR: Invalid JSON still in cast for $name"; exit 1
  fi
  if ! grep -qE "items:|NOVO|HONDA|valid" "$cast"; then
    echo "WARN: cast may lack live result markers for $name"
    # dump text preview
    python3 -c "import json; t=''.join(json.loads(L)[2] for L in open('$cast') if L.strip().startswith('[') for _ in [0]); print(t[:500])" || true
  fi
  agg --idle-time-limit 0.8 --speed 1.15 --font-size 13 "$cast" "$gif"
  echo "gif bytes: $(wc -c < "$gif")"
  python3 "$ROOT/scripts/cast_to_png.py" "$cast" "$png"
  echo "png bytes: $(wc -c < "$png")"
}

record_one "eu-company-verify" "eu-company-verify" '{"queries":["DK24256790"]}'
record_one "vin-decoder-recalls" "vin-decoder-recalls" '{"vins":["1HGCM82633A004352"]}'

# Refresh scholar with local call too
record_one "scholar-search" "scholar-search" '{"queries":["knowledge graph embedding"],"maxResults":3}'

python3 - "$DEMO" <<'PY'
import json, os, hashlib, sys
from datetime import datetime, timezone
demo = sys.argv[1]
actors = ["eu-company-verify", "vin-decoder-recalls", "scholar-search"]
man = {"generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "mode": "local-stdio", "actors": {}}
for a in actors:
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
        "files": files,
        "rawGithub": {
            "gif": f"https://raw.githubusercontent.com/markatdataandbeyond/open-data-mcp/main/assets/demo/{a}.gif",
            "png": f"https://raw.githubusercontent.com/markatdataandbeyond/open-data-mcp/main/assets/demo/{a}.png",
            "cast": f"https://raw.githubusercontent.com/markatdataandbeyond/open-data-mcp/main/assets/demo/{a}.cast",
        },
    }
json.dump(man, open(f"{demo}/manifest.json", "w"), indent=2, ensure_ascii=False)
print("manifest ok", list(man["actors"]))
PY
echo "ALL LOCAL DEMOS RECORDED"
ls -la "$DEMO"/*.{cast,gif,png}
