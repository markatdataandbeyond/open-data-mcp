#!/usr/bin/env python3
"""TDD for LobeHub submission prep (manifest + approved texts). Does not publish."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = Path("/workspace/venture/apify-actors/drafts")
TEKSTER = json.loads((DRAFTS / "katalog-tekster.json").read_text())
MANIFEST = json.loads((ROOT / "lhm.plugin.json").read_text())
ACTORS = [
    "eu-company-verify",
    "dk-statistics",
    "scholar-search",
    "pubmed-search",
    "eu-tenders",
    "france-company-search",
    "nordic-company-registry",
    "clinical-trials",
    "vin-decoder-recalls",
    "weather-forecast",
]
results = []


def check(name, ok, note=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), name, ("- " + note) if note else "")


def http_code(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 lobehub-test"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


# --- overall ---
check("a1) lhm.plugin.json exists", (ROOT / "lhm.plugin.json").is_file())
check("a2) required fields identifier/name/version", all(MANIFEST.get(k) for k in ("identifier", "name", "version")))
check(
    "a3) identifier matches ^[0-9a-z][0-9a-z_-]*$",
    bool(re.fullmatch(r"[\da-z][\d_a-z-]*", MANIFEST.get("identifier", ""))),
    MANIFEST.get("identifier", ""),
)
check("a4) description == Marks kort-tekst", MANIFEST.get("description") == TEKSTER["kort"], repr(MANIFEST.get("description")))
loc = next((x for x in (MANIFEST.get("localizations") or []) if x.get("locale") == "en-US"), None)
check("a5) en-US summary == Marks lang-tekst", bool(loc) and loc.get("summary") == TEKSTER["lang"])
check("a6) name is open-data-mcp", MANIFEST.get("name") == "open-data-mcp")
check(
    "a7) homepage is markatdataandbeyond repo",
    MANIFEST.get("homepage") == "https://github.com/markatdataandbeyond/open-data-mcp",
)
check("a8) cloudEndpoint er mcp.apify.com med tools=", "mcp.apify.com/?tools=" in (MANIFEST.get("cloudEndpoint") or ""))
check(
    "a9) cloudEndpoint indeholder alle 10 actors",
    all(f"dataandbeyond/{a}" in (MANIFEST.get("cloudEndpoint") or "") for a in ACTORS),
)
tools = MANIFEST.get("tools") or []
check("a10) tools array har 10", len(tools) == 10, str(len(tools)))
check(
    "a11) tool-navne er dataandbeyond--*",
    sorted(t.get("name") for t in tools) == sorted(f"dataandbeyond--{a}" for a in ACTORS),
)

# --- live link checks ---
links = [
    MANIFEST.get("homepage"),
    MANIFEST.get("authorUrl"),
    MANIFEST.get("icon"),
    "https://lobehub.com/mcp",
    "https://market.lobehub.com/s/publish-mcp",
]
bad = []
for u in links:
    if not u:
        bad.append((u, "missing"))
        continue
    code = http_code(u)
    # raw.githubusercontent.com and github usually 200; lobehub may vary
    if code not in (200, 301, 302):
        bad.append((u, code))
check("b1) kritiske links svarer 200/3xx", not bad, str(bad))

# repo raw logo
logo = MANIFEST.get("icon")
logo_ok = False
if logo:
    try:
        req = urllib.request.Request(logo, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            logo_ok = r.status == 200 and (r.headers.get("Content-Type") or "").startswith("image/")
    except Exception:
        logo_ok = False
check("b2) icon raw PNG er live image/*", logo_ok, logo or "")

# --- edge cases ---
check(
    "c1) kant: forkert identifier med store bogstaver falder igennem regex",
    not bool(re.fullmatch(r"[\da-z][\d_a-z-]*", "MarkAtDataAndBeyond-Open")),
)
# cloudEndpoint must be absolute https
check("c2) kant: cloudEndpoint er https URL", (MANIFEST.get("cloudEndpoint") or "").startswith("https://"))
# description must not accidentally be the long text
check(
    "c3) kant: description er kort (≠ lang) og ≤ 200 tegn",
    MANIFEST.get("description") != TEKSTER["lang"] and len(MANIFEST.get("description") or "") <= 200,
    str(len(MANIFEST.get("description") or "")),
)
# no secrets in manifest
blob = json.dumps(MANIFEST)
tok = os.environ.get("APIFY_TOKEN")
check("c4) kant: ingen APIFY_TOKEN i manifest", not (tok and tok in blob))
check("c5) kant: ingen apify_api_ i manifest", "apify_api_" not in blob)

# Document that publish is blocked without login (probe CLI auth status — expect not logged in / error, not publish)
probe = subprocess.run(
    ["npx", "-y", "@lobehub/market-cli", "auth", "status", "--output", "json"],
    capture_output=True,
    text=True,
    timeout=120,
)
out = (probe.stdout or "") + (probe.stderr or "")
# Never print credentials paths contents; only classify
logged_in = '"status":"authenticated"' in out.replace(" ", "") or '"status": "authenticated"' in out
check(
    "d1) CLI auth status: ikke authenticated (login påkrævet før publish)",
    probe.returncode != 0 or not logged_in,
    f"exit={probe.returncode} authenticated={logged_in}",
)

n_ok = sum(1 for _, o in results if o)
print(f"\n{n_ok}/{len(results)} passed")
sys.exit(0 if n_ok == len(results) else 1)
