#!/usr/bin/env python3
"""Repo tests for open-data-mcp. Prints only PASS/FAIL, never secret values."""
import json, os, re, subprocess, sys, glob, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTORS = ["eu-company-verify","dk-statistics","scholar-search","pubmed-search","eu-tenders",
          "france-company-search","nordic-company-registry","clinical-trials","vin-decoder-recalls","weather-forecast"]
results = []
def check(name, ok, note=""):
    results.append((name, ok)); print(("PASS" if ok else "FAIL"), name, ("- "+note if note else ""))

def files():
    out = subprocess.run(["git","ls-files","-co","--exclude-standard"],cwd=ROOT,capture_output=True,text=True).stdout.split()
    return [f for f in out if os.path.isfile(os.path.join(ROOT,f))]
def read(f): return open(os.path.join(ROOT,f),encoding="utf-8",errors="ignore").read()

# a) secret scan (regex) + known local secret values, value never printed
PATTERNS = [r"apify_api_[A-Za-z0-9]{20,}", r"gh[pousr]_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{30,}",
            r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}",
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"\b[A-Z0-9]{4}-[A-Z0-9]{4}\b(?=.*device)"]
known = [v for k,v in os.environ.items() if k in ("APIFY_TOKEN","OPENALEX_API_KEY") and len(v)>8]
hits = 0
for f in files():
    if f.startswith("tests/"): continue
    t = read(f)
    hits += sum(1 for p in PATTERNS if re.search(p,t)) + sum(1 for v in known if v in t)
check("a) secret-scan regex + kendte nøgler", hits==0, f"{hits} fund" if hits else "")
check("a2) ingen .env/log-filer i repo", not any(re.search(r"(^|/)\.env|\.log$|login",f) for f in files()))

# b) links in README return 200
readme = read("README.md") if os.path.exists(os.path.join(ROOT,"README.md")) else ""
links = sorted(set(re.findall(r"https?://[^\s)\"'<>`]+", readme)))
links = [l for l in links if "mcp.apify.com" not in l and "api.apify.com" not in l]
bad, pend = [], []
for l in links:
    try:
        req = urllib.request.Request(l, headers={"User-Agent":"Mozilla/5.0 repo-test"})
        code = urllib.request.urlopen(req, timeout=20).status
    except urllib.error.HTTPError as e: code = e.code
    except Exception: code = 0
    if code != 200:
        bad.append((l,code))
for l,c in bad: print("  BAD", l, c)
check("b) alle README-links giver 200", len(links)>=10 and not bad, f"{len(links)} links")

# c) example configs valid JSON with placeholder
cfgs = sorted(glob.glob(os.path.join(ROOT,"examples","*.json")))
okc = len(cfgs)>=3
for c in cfgs:
    try:
        t=open(c).read(); json.loads(t); okc = okc and "<APIFY_TOKEN>" in t
    except Exception: okc=False
check("c) eksempelkonfig er gyldig JSON med <APIFY_TOKEN>", okc, f"{len(cfgs)} filer")
try: json.load(open(os.path.join(ROOT,"server.json"))); check("c2) server.json gyldig JSON", True)
except Exception: check("c2) server.json gyldig JSON", False)

# d) no I-sentences, no buzzwords
texts = " ".join(read(f) for f in files() if f.endswith(".md") and not f.startswith("tests/"))
first = re.findall(r"(?i)\b(I|I'm|I've|my|we|we're|our)\b", re.sub(r"```.*?```","",texts,flags=re.S))
first = [w for w in first if w != "I" or True]
buzz = re.findall(r"(?i)\b(seamless(ly)?|cutting[- ]edge|revolutionary|game[- ]chang\w*|supercharge\w*|unlock\w*|leverag\w*|robust|empower\w*|blazing\w*|next[- ]gen\w*|world[- ]class|agent[- ]ready|effortless\w*)\b", texts)
check("d) ingen jeg/vi-sætninger", not first, f"{len(first)} fund" if first else "")
check("d2) ingen buzzwords", not buzz, ",".join(sorted({b[0].lower() for b in buzz})))

# e) edge cases
gi = read(".gitignore") if os.path.exists(os.path.join(ROOT,".gitignore")) else ""
check("e1) .gitignore dækker .env, secrets, logs", all(x in gi for x in (".env","*secret*","*.log")))
check("e2) ingen absolutte /home/box- eller /workspace-stier", not any(re.search(r"/home/box|/workspace/", read(f)) for f in files() if not f.startswith("tests/")))
ok = all(f"apify.com/dataandbeyond/{a}" in readme for a in ACTORS)
allcfg = " ".join(open(c).read() for c in cfgs)+read("server.json")
ok = ok and all(f"dataandbeyond/{a}" in allcfg for a in ACTORS)
named = set(re.findall(r"(?<![a-z])dataandbeyond/([a-z0-9-]+)", readme+allcfg))
check("e3) actor-navne matcher de 10 på Apify", ok and named <= set(ACTORS), ",".join(sorted(named-set(ACTORS))))
check("e4) LICENSE er MIT med Data and Beyond ApS", "MIT License" in read("LICENSE") and "Data and Beyond ApS" in read("LICENSE"))
check("e5) server.json repo-URL peger på markatdataandbeyond", "github.com/markatdataandbeyond/open-data-mcp" in read("server.json"))
# f) README prices match live Store pricing, all actors public, pubmed title fixed
live = {}
for a in ACTORS:
    try:
        d = json.load(urllib.request.urlopen(f"https://api.apify.com/v2/acts/dataandbeyond~{a}", timeout=20))["data"]
        live[a] = d
    except Exception: live[a] = None
check("f1) alle 10 actors er offentlige", all(d and d.get("isPublic") for d in live.values()),
      ",".join(a for a,d in live.items() if not (d and d.get("isPublic"))))
def prices(d):
    p = (d.get("pricingInfos") or [{}])[-1]
    ev = (p.get("pricingPerEvent") or {}).get("actorChargeEvents") or {}
    return sorted({f"{v['eventPriceUsd']:g}" for v in ev.values()})
mism = []
for a,d in live.items():
    if not d: mism.append(a); continue
    row = next((ln for ln in readme.splitlines() if f"apify.com/dataandbeyond/{a})" in ln), "")
    cell = row.split("|")[-2] if row.count("|")>=4 else ""
    if sorted(set(re.findall(r"\d+\.\d+", cell))) != prices(d): mism.append(a)
check("f2) README-priser matcher live Store-priser", not mism, ",".join(mism))
pt = (live.get("pubmed-search") or {}).get("title","")
check("f3) pubmed-search har rettet titel", pt == "PubMed Search API: Articles with DOI, PMCID and Authors", pt)

# g) Cline marketplace logo (assets/logo-400.png)
import struct
LOGO_REL = "assets/logo-400.png"
LOGO_PATH = os.path.join(ROOT, LOGO_REL)
RAW_LOGO = "https://raw.githubusercontent.com/markatdataandbeyond/open-data-mcp/main/assets/logo-400.png"
logo_exists = os.path.isfile(LOGO_PATH)
check("g1) assets/logo-400.png findes", logo_exists)
png_ok, wh, size_b = False, None, 0
if logo_exists:
    raw = open(LOGO_PATH, "rb").read()
    size_b = len(raw)
    png_ok = raw[:8] == b"\x89PNG\r\n\x1a\n"
    if png_ok and len(raw) >= 24:
        wh = struct.unpack(">II", raw[16:24])
check("g2) logo er 400x400 PNG (magic + IHDR)", png_ok and wh == (400, 400), str(wh))
check("g3) logo-filstørrelse acceptabel til GitHub-issue (1KB–500KB)", 1024 <= size_b <= 500*1024, str(size_b))

# Live raw URL (must be 200 + image/png after push). Set SKIP_RAW_LOGO=1 to run pre-push.
skip_raw = os.environ.get("SKIP_RAW_LOGO") == "1"
if skip_raw:
    check("g4) raw-URL HTTP 200 + image/png (SKIPPED pre-push)", True, "SKIP_RAW_LOGO=1")
else:
    try:
        req = urllib.request.Request(RAW_LOGO, headers={"User-Agent": "Mozilla/5.0 repo-test"})
        with urllib.request.urlopen(req, timeout=25) as r:
            code = r.status
            ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            body = r.read(16)
        check("g4) raw-URL HTTP 200 + image/png", code == 200 and ctype == "image/png" and body[:4] == b"\x89PNG",
              f"code={code} ctype={ctype}")
    except Exception as e:
        check("g4) raw-URL HTTP 200 + image/png", False, type(e).__name__)

# Edge cases
fake_raw = "https://raw.githubusercontent.com/markatdataandbeyond/open-data-mcp/main/assets/logo-DOES-NOT-EXIST.png"
fake_code = 0
try:
    urllib.request.urlopen(urllib.request.Request(fake_raw, headers={"User-Agent": "Mozilla/5.0 repo-test"}), timeout=20)
    fake_code = 200
except urllib.error.HTTPError as e:
    fake_code = e.code
except Exception:
    fake_code = 0
check("g5) kant: manglende logo-raw giver ikke 200 (404/ikke-fundet)", fake_code != 200, str(fake_code))
# Wrong format would fail: a renamed .png that is not PNG — ensure our file is not JPEG magic
jpeg_magic = open(LOGO_PATH, "rb").read(3) == b"\xff\xd8\xff" if logo_exists else True
check("g6) kant: logo er ikke JPEG forklædt som PNG", logo_exists and not jpeg_magic)
check("g7) kant: forkert dimension fanget (ikke 0x0 / ikke 1x1)", wh == (400, 400))

n_ok = sum(o for _,o in results); print(f"\n{n_ok}/{len(results)} passed")
sys.exit(0 if n_ok==len(results) else 1)
