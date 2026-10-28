#!/usr/bin/env bash
# Safe demo: never echoes APIFY_TOKEN value. Requires APIFY_TOKEN in env.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ACTOR="${1:?actor name}"
OUTDIR="${2:-/tmp/demo-work}"
mkdir -p "$OUTDIR"

if [[ -z "${APIFY_TOKEN:-}" ]]; then
  echo "APIFY_TOKEN env var required (value not shown)"
  exit 1
fi

echo "════════════════════════════════════════════════════"
echo " Demo: dataandbeyond/$ACTOR"
echo "════════════════════════════════════════════════════"
echo
echo "▸ Direct Apify API (token from \$APIFY_TOKEN, never printed)"
echo
sleep 0.8

case "$ACTOR" in
  eu-company-verify)
    BODY='{"queries":["Novo Nordisk A/S"],"includeParents":true}'
    LABEL="Novo Nordisk A/S"
    ;;
  vin-decoder-recalls)
    BODY='{"vins":["1HGCM82633A004352"],"includeRecalls":true}'
    LABEL="VIN 1HGCM82633A004352"
    ;;
  scholar-search)
    BODY='{"queries":["knowledge graph embedding"],"maxResultsPerQuery":3}'
    LABEL="knowledge graph embedding"
    ;;
  *)
    echo "Unknown actor: $ACTOR"; exit 2
    ;;
esac

URL="https://api.apify.com/v2/acts/dataandbeyond~${ACTOR}/run-sync-get-dataset-items?format=json&clean=1"
echo "\$ curl -sS -X POST \\"
echo "    \"$URL\" \\"
echo "    -H \"Authorization: Bearer \$APIFY_TOKEN\" \\"
echo "    -H \"Content-Type: application/json\" \\"
echo "    -d '$BODY'"
echo

RAW="$OUTDIR/${ACTOR}-direct.json"
META="$OUTDIR/${ACTOR}-direct.meta.json"
# Capture response headers for run id if present
HTTP_CODE=$(curl -sS -o "$RAW" -w "%{http_code}" -X POST "$URL" \
  -H "Authorization: Bearer ${APIFY_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$BODY" \
  -D "$OUTDIR/${ACTOR}-direct.headers")

sleep 0.4
echo "HTTP $HTTP_CODE  input: $LABEL"
# Extract useful fields with python (no token in output)
python3 - "$RAW" "$ACTOR" "$META" <<'PY'
import json,sys,os,re
raw,actor,meta_path=sys.argv[1],sys.argv[2],sys.argv[3]
items=json.load(open(raw))
if not isinstance(items,list):
    print("Unexpected response shape"); sys.exit(1)
print(f"dataset items: {len(items)}")
meta={"actor":actor,"itemCount":len(items),"highlights":[]}
for it in items[:5]:
    if actor=="eu-company-verify":
        name=(it.get("lei") or {}).get("legalName") or it.get("query")
        lei=(it.get("lei") or {}).get("lei")
        verdict=it.get("verdict")
        line=f"  • {it.get('query')} → {name} | LEI {lei} | {verdict}"
        meta["highlights"].append({"query":it.get("query"),"legalName":name,"lei":lei,"verdict":verdict})
    elif actor=="vin-decoder-recalls":
        nrec=len(it.get("recalls") or [])
        line=f"  • VIN {it.get('vin')}: {it.get('make')} {it.get('model')} {it.get('modelYear')} | recalls={nrec}"
        meta["highlights"].append({"vin":it.get("vin"),"make":it.get("make"),"model":it.get("model"),"modelYear":it.get("modelYear"),"recallCount":nrec})
    else:
        line=f"  • {it.get('year')} | cited {it.get('citedByCount')} | {it.get('title')}"
        meta["highlights"].append({"title":it.get("title"),"year":it.get("year"),"doi":it.get("doi"),"citedByCount":it.get("citedByCount"),"query":it.get("query")})
    print(line)
# Try to find run id from headers file sibling
hdr=raw.replace("-direct.json","-direct.headers")
run_id=None
if os.path.exists(hdr):
    h=open(hdr).read()
    m=re.search(r"(?i)x-apify-run-id:\s*(\S+)",h)
    if m: run_id=m.group(1).strip()
    m2=re.search(r"(?i)x-apify-dataset-id:\s*(\S+)",h)
    if m2: meta["datasetId"]=m2.group(1).strip()
meta["runId"]=run_id
json.dump(meta,open(meta_path,"w"),indent=2,ensure_ascii=False)
if run_id:
    print(f"runId: {run_id}")
print(f"saved: {raw}")
PY

echo
sleep 1.0
echo "▸ Via MCP stdio proxy (open-data-mcp → mcp.apify.com)"
echo "  \$ node scripts/demo-mcp-call.mjs dataandbeyond--${ACTOR} '$BODY'"
echo
sleep 0.6
MCP_OUT="$OUTDIR/${ACTOR}-mcp.txt"
node "$ROOT/scripts/demo-mcp-call.mjs" "dataandbeyond--${ACTOR}" "$BODY" | tee "$MCP_OUT"
# If MCP returned a datasetId, fetch a few items (still using env token, never printed)
DS=$(python3 -c "import re,sys; t=open(sys.argv[1]).read(); m=re.search(r'datasetId: (\S+)',t); print(m.group(1) if m else '')" "$MCP_OUT" || true)
if [[ -n "$DS" ]]; then
  echo
  echo "▸ Fetch dataset items for MCP run (datasetId=$DS)"
  MCP_JSON="$OUTDIR/${ACTOR}-mcp-items.json"
  curl -sS -o "$MCP_JSON"     "https://api.apify.com/v2/datasets/${DS}/items?format=json&clean=1&limit=5"     -H "Authorization: Bearer ${APIFY_TOKEN}"
  python3 - "$MCP_JSON" "$ACTOR" <<'PY2'
import json,sys
items=json.load(open(sys.argv[1])); actor=sys.argv[2]
print(f"MCP dataset items: {len(items)}")
for it in items[:3]:
    if actor=="eu-company-verify":
        print(f"  • {it.get('query')} → {(it.get('lei') or {}).get('legalName')} | {(it.get('lei') or {}).get('lei')}")
    elif actor=="vin-decoder-recalls":
        print(f"  • VIN {it.get('vin')}: {it.get('make')} {it.get('model')} {it.get('modelYear')} | recalls={len(it.get('recalls') or [])}")
    else:
        print(f"  • {it.get('year')} | cited {it.get('citedByCount')} | {it.get('title')}")
PY2
fi
sleep 1.2
echo
echo "Done. Artifacts in $OUTDIR"
sleep 1.5
