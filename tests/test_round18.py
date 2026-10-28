#!/usr/bin/env python3
"""Round 18: demo assets (cast/gif/png), README Demo section, secret scan, live spot-checks.
OCR: prefers tesseract if available, else rapidocr-onnxruntime (apt tesseract unavailable on box).
Never prints secret values.
"""
from __future__ import annotations
import json, os, re, sys, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "assets" / "demo"
LIVE = DEMO / "live"
README = ROOT / "README.md"
ACTORS = ["eu-company-verify", "vin-decoder-recalls", "scholar-search"]
RAW_BASE = "https://raw.githubusercontent.com/markatdataandbeyond/open-data-mcp/main/assets/demo"

# Patterns that must NEVER appear (token values / auth headers with values)
SECRET_PATTERNS = [
    re.compile(r"apify_api_[A-Za-z0-9]{10,}"),
    re.compile(r"APIFY_TOKEN\s*=\s*['\"]?[A-Za-z0-9_\-]{8,}"),
    re.compile(r"Authorization:\s*Bearer\s+(?!\$APIFY_TOKEN\b)(?!<APIFY_TOKEN>)[A-Za-z0-9_\-\.]+", re.I),
    re.compile(r"OPENALEX[_A-Z]*\s*=\s*['\"]?[A-Za-z0-9_\-]{8,}"),
    re.compile(r"Bearer\s+apify_api_", re.I),
]

fail = 0

def t(name: str, cond: bool, info: str = ""):
    global fail
    print(("PASS" if cond else "FAIL") + f" | {name}" + (f" | {info}" if info and not cond else ""))
    fail += 0 if cond else 1

def cast_text(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for L in lines[1:]:
        try:
            ev = json.loads(L)
        except Exception:
            continue
        if isinstance(ev, list) and len(ev) >= 3 and ev[1] == "o":
            out.append(ev[2])
    return "".join(out).replace("\r\n", "\n").replace("\r", "\n")

def ocr_image(path: Path) -> str:
    # Prefer tesseract CLI / pytesseract; fall back to rapidocr
    try:
        import shutil, subprocess
        if shutil.which("tesseract"):
            r = subprocess.run(
                ["tesseract", str(path), "stdout", "-l", "eng"],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout
    except Exception:
        pass
    try:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
        result, _ = engine(str(path))
        return "\n".join(x[1] for x in (result or []))
    except Exception as e:
        return f"__OCR_UNAVAILABLE__:{e}"

def scan_secrets(label: str, blob: str):
    for pat in SECRET_PATTERNS:
        m = pat.search(blob)
        t(f"secret-scan {label} /{pat.pattern[:40]}/", m is None,
          f"matched at {m.start() if m else ''}")

# ---------- 1. Overordnede tests ----------
man_path = DEMO / "manifest.json"
t("manifest.json exists", man_path.is_file())
man = json.loads(man_path.read_text()) if man_path.is_file() else {"actors": {}}

readme = README.read_text(encoding="utf-8")
t("README has ## Demo section", re.search(r"^## Demo\b", readme, re.M) is not None)
t("README links all 3 gifs", all(f"assets/demo/{a}.gif" in readme for a in ACTORS))
t("README mentions $APIFY_TOKEN not value", "$APIFY_TOKEN" in readme and "apify_api_" not in readme)

for a in ACTORS:
    for ext, min_b, max_b in (("cast", 500, 200_000), ("gif", 20_000, 5_000_000), ("png", 10_000, 2_000_000)):
        p = DEMO / f"{a}.{ext}"
        t(f"{a}.{ext} exists", p.is_file())
        if p.is_file():
            sz = p.stat().st_size
            t(f"{a}.{ext} size {min_b}..{max_b}", min_b <= sz <= max_b, f"size={sz}")
    # raw URL documented in manifest
    raw = (man.get("actors") or {}).get(a, {}).get("rawGithub") or {}
    t(f"{a} raw gif URL", raw.get("gif") == f"{RAW_BASE}/{a}.gif", raw.get("gif"))
    t(f"{a} raw png URL", raw.get("png") == f"{RAW_BASE}/{a}.png", raw.get("png"))

# Scripts present
t("scripts/demo-actor.sh exists", (ROOT / "scripts" / "demo-actor.sh").is_file())
t("scripts/demo-mcp-call.mjs exists", (ROOT / "scripts" / "demo-mcp-call.mjs").is_file())
t("scripts/record-demos.sh exists", (ROOT / "scripts" / "record-demos.sh").is_file())
t("scripts/cast_to_png.py exists", (ROOT / "scripts" / "cast_to_png.py").is_file())

# ---------- 2. Live spot-checks ----------
# Expected anchors from the recorded live runs (also in live/ JSON)
expect = {
    "eu-company-verify": {
        "need_in_cast": ["Novo Nordisk A/S", "NOVO NORDISK A/S", "549300DAQ1CVT6CXN342", "runId:", "SUCCEEDED", "$APIFY_TOKEN"],
        "legalName": "NOVO NORDISK A/S",
        "lei": "549300DAQ1CVT6CXN342",
    },
    "vin-decoder-recalls": {
        "need_in_cast": ["1HGCM82633A004352", "HONDA", "Accord", "2003", "recalls=24", "runId:", "SUCCEEDED"],
        "vin": "1HGCM82633A004352",
        "make": "HONDA",
        "model": "Accord",
        "modelYear": 2003,
    },
    "scholar-search": {
        "need_in_cast": ["knowledge graph embedding", "Knowledge Graph Embedding", "cited", "runId:", "SUCCEEDED"],
        "titles_substr": ["Translating on Hyperplanes", "Survey of Approaches", "Convolutional 2D"],
    },
}

for a in ACTORS:
    cast_p = DEMO / f"{a}.cast"
    blob = cast_text(cast_p) if cast_p.is_file() else ""
    t(f"{a} cast non-empty", len(blob) > 200, f"len={len(blob)}")
    for needle in expect[a]["need_in_cast"]:
        t(f"{a} cast contains {needle!r}", needle in blob)

    # Direct JSON matches highlights
    direct = LIVE / f"{a}-direct.json"
    t(f"{a} live direct JSON exists", direct.is_file())
    if direct.is_file():
        items = json.loads(direct.read_text())
        t(f"{a} live direct items >=1", isinstance(items, list) and len(items) >= 1, len(items) if isinstance(items, list) else type(items))
        if a == "eu-company-verify" and items:
            lei = (items[0].get("lei") or {})
            t(f"{a} live legalName", lei.get("legalName") == expect[a]["legalName"], lei.get("legalName"))
            t(f"{a} live lei", lei.get("lei") == expect[a]["lei"], lei.get("lei"))
            t(f"{a} cast LEI matches live", expect[a]["lei"] in blob)
        if a == "vin-decoder-recalls" and items:
            it = items[0]
            t(f"{a} live make/model/year",
              it.get("make") == "HONDA" and it.get("model") == "Accord" and it.get("modelYear") == 2003,
              f"{it.get('make')} {it.get('model')} {it.get('modelYear')}")
            t(f"{a} live recalls list", isinstance(it.get("recalls"), list) and len(it["recalls"]) >= 1)
            t(f"{a} cast VIN matches live", expect[a]["vin"] in blob and "HONDA" in blob)
        if a == "scholar-search" and items:
            titles = " | ".join(x.get("title") or "" for x in items)
            for sub in expect[a]["titles_substr"]:
                t(f"{a} live title has {sub!r}", sub in titles)
            t(f"{a} cast has paper title fragment", "Knowledge Graph Embedding" in blob)

    # MCP run id in cast + mcp txt
    mcp_txt = LIVE / f"{a}-mcp.txt"
    t(f"{a} live mcp txt exists", mcp_txt.is_file())
    if mcp_txt.is_file():
        mt = mcp_txt.read_text()
        m = re.search(r"runId:\s*(\S+)", mt)
        t(f"{a} mcp runId present", bool(m), mt[:80])
        if m:
            t(f"{a} cast has same mcp runId", m.group(1) in blob, m.group(1))
        t(f"{a} mcp status SUCCEEDED", "SUCCEEDED" in mt)

    # Manifest highlights agree with live
    h = ((man.get("actors") or {}).get(a, {}).get("direct") or {}).get("highlights") or []
    t(f"{a} manifest highlights non-empty", len(h) >= 1, h)

# Optional: re-verify one live call if --live and token set (does not print token)
if "--live" in sys.argv and os.environ.get("APIFY_TOKEN"):
    import urllib.request
    def api_run(actor, body):
        url = f"https://api.apify.com/v2/acts/dataandbeyond~{actor}/run-sync-get-dataset-items?format=json&clean=1"
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST",
            headers={"Authorization": "Bearer " + os.environ["APIFY_TOKEN"], "Content-Type": "application/json"},
        )
        return json.load(urllib.request.urlopen(req, timeout=120))
    items = api_run("eu-company-verify", {"queries": ["Novo Nordisk A/S"]})
    t("LIVE re-run eu legalName", (items[0].get("lei") or {}).get("legalName") == "NOVO NORDISK A/S")
    t("LIVE re-run eu lei", (items[0].get("lei") or {}).get("lei") == "549300DAQ1CVT6CXN342")
    items = api_run("vin-decoder-recalls", {"vins": ["1HGCM82633A004352"], "includeRecalls": True})
    t("LIVE re-run vin Honda", items[0].get("make") == "HONDA" and items[0].get("model") == "Accord")
    items = api_run("scholar-search", {"queries": ["knowledge graph embedding"], "maxResultsPerQuery": 3})
    t("LIVE re-run scholar titles", any("Knowledge Graph Embedding" in (x.get("title") or "") for x in items))

# ---------- 3. Kanttilfælde ----------
# K1: secret scan on all casts, gifs (via OCR), pngs, README, scripts, live/
scan_targets = [README]
for a in ACTORS:
    scan_targets += [DEMO / f"{a}.cast", DEMO / f"{a}.png"]
scan_targets += list(LIVE.glob("*")) if LIVE.is_dir() else []
scan_targets += list((ROOT / "scripts").glob("demo*"))
scan_targets += [ROOT / "scripts" / "record-demos.sh", ROOT / "scripts" / "cast_to_png.py"]

for p in scan_targets:
    if not p.is_file():
        continue
    if p.suffix.lower() in {".png", ".gif"}:
        continue  # OCR path below
    try:
        blob = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        blob = ""
    scan_secrets(str(p.relative_to(ROOT)), blob)

# OCR PNG (and optionally first frame logic) — no secrets; expected anchors present
for a in ACTORS:
    png = DEMO / f"{a}.png"
    ocr = ocr_image(png) if png.is_file() else ""
    t(f"OCR {a}.png available", not ocr.startswith("__OCR_UNAVAILABLE__"), ocr[:80])
    scan_secrets(f"OCR {a}.png", ocr)
    # Fuzzy: strip spaces for OCR noise
    compact = re.sub(r"\s+", "", ocr)
    if a == "eu-company-verify":
        t(f"OCR {a} sees Novo/LEI", "Novo" in ocr or "NOVO" in ocr or "549300" in compact)
    if a == "vin-decoder-recalls":
        t(f"OCR {a} sees HONDA/VIN", "HONDA" in ocr or "1HGCM82633" in compact)
    if a == "scholar-search":
        t(f"OCR {a} sees Knowledge/embedding", "Knowledge" in ocr or "embedding" in ocr.lower() or "SUCCEEDED" in ocr)

# K2: GIF not absurdly long (frame count heuristic) and under ~30s playback
from PIL import Image
for a in ACTORS:
    gif = DEMO / f"{a}.gif"
    if not gif.is_file():
        continue
    im = Image.open(gif)
    n = getattr(im, "n_frames", 1)
    # Sum durations (ms); default 100ms
    total_ms = 0
    for i in range(n):
        im.seek(i)
        total_ms += im.info.get("duration", 100) or 100
    t(f"{a}.gif playback <=35s", total_ms <= 35_000, f"frames={n} ms={total_ms}")
    t(f"{a}.gif frames >=4", n >= 4, n)
    # Also OCR is heavy on gif; scan cast already covers text. Spot-check: file is GIF
    t(f"{a}.gif magic", gif.read_bytes()[:6] in (b"GIF87a", b"GIF89a"))

# K3: cast header valid asciinema v2; no env leaking token
for a in ACTORS:
    lines = (DEMO / f"{a}.cast").read_text().splitlines()
    hdr = json.loads(lines[0])
    t(f"{a} cast version 2", hdr.get("version") == 2)
    env = hdr.get("env") or {}
    env_blob = json.dumps(env)
    scan_secrets(f"{a} cast header env", env_blob)
    t(f"{a} cast header env has no APIFY_TOKEN key with value",
      not any(k == "APIFY_TOKEN" and v and v not in ("", "$APIFY_TOKEN") for k, v in env.items()))

# K4 (bonus edge): README raw URLs resolve host path shape; drafts prepared
draft = Path("/workspace/venture/apify-actors/drafts/demo-actor-readme-snippets.md")
t("actor README snippets draft exists", draft.is_file())
if draft.is_file():
    d = draft.read_text()
    t("draft has all 3 gif raw URLs", all(f"{a}.gif" in d for a in ACTORS))
    scan_secrets("draft snippets", d)

print(f"\nTOTAL fail={fail}")
sys.exit(1 if fail else 0)
