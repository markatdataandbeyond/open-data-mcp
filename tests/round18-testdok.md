# Testdok runde 18: Demo-materiale (cast/GIF/PNG) — lokalt, 28-10-2026 Europe/Copenhagen

**Status:** Tests grønne lokalt.
**Testresultat:** offline PASS alle (fail=0); `--live` PASS (eu LEI, Honda Accord, KGE-titler). **Ingen push** til GitHub og **ingen PUT** til Apify actor-sider før Venture Lead bekræfter.

## Ændring
- Live-demo af `eu-company-verify`, `vin-decoder-recalls`, `scholar-search`: direkte Apify API (`run-sync-get-dataset-items`) **og** via stdio MCP-proxy (`scripts/demo-mcp-call.mjs` → `mcp.apify.com`).
- Asciinema `.cast` → GIF (`agg`) + PNG (`scripts/cast_to_png.py`).
- Filer i `assets/demo/` (+ `assets/demo/live/` med JSON/MCP-output til stikprøver).
- README: ny **Demo**-sektion med GIF/PNG og raw.githubusercontent-URL'er.
- Kladde til actor-README: `apify-actors/drafts/demo-actor-readme-snippets.md` (ikke applied).

## 1. Overordnede tests
Kør: `python3 tests/test_round18.py` (valgfrit `--live` genkører 3 API-kald).

Dækker (`test_round18.py`: **227 PASS / 0 FAIL** offline; `--live` tilføjer 3 API-re-runs):
- `manifest.json`, alle `.cast`/`.gif`/`.png` findes med fornuftige størrelser
- README har `## Demo` og linker de 3 GIF'er
- raw GitHub-URL'er i manifest
- demo-scripts findes (`demo-actor.sh`, `demo-mcp-call.mjs`, `record-demos.sh`, `cast_to_png.py`)

## 2. Live-stikprøver (optagelse 28/10 Europe/Copenhagen)

| Actor | Input | Direct | MCP runId | Match |
|---|---|---|---|---|
| eu-company-verify | `Novo Nordisk A/S` | NOVO NORDISK A/S, LEI `549300DAQ1CVT6CXN342`, verdict LEI_MATCH_BY_NAME | `h1ZZkQjXbJic0JJWh` SUCCEEDED | cast + live JSON + MCP dataset |
| vin-decoder-recalls | VIN `1HGCM82633A004352` | HONDA Accord 2003, recalls=24 | `LqTMizQ8qjzcoF8bg` SUCCEEDED | cast + live JSON + MCP dataset |
| scholar-search | `knowledge graph embedding` (3) | Hyperplanes 2014 (cited 3906), Survey 2017 (2626), ConvE 2018 (2485) | `gKz8mS98cL0BeK8E7` SUCCEEDED | cast + live JSON + MCP dataset |

Stikprøver asserts: cast indeholder firmanavn/VIN/paper-titler; MCP `runId` i cast == live mcp.txt; manifest.highlights udfyldt.

## 3. Kanttilfælde (≥3)
1. **Secret-scan** af README, alle `.cast`, scripts, `live/*`, OCR af PNG: ingen `apify_api_…`, ingen `APIFY_TOKEN=værdi`, ingen `Authorization: Bearer <token>`, ingen OpenAlex-nøgle. Kun `$APIFY_TOKEN` / `<APIFY_TOKEN>` tilladt.
2. **GIF-længde**: playback ≤35s, ≥4 frames, GIF-magic OK.
3. **Cast-header**: asciinema v2; `env` lækker ikke token-værdi.
4. **OCR (rapidocr; tesseract-binær ikke tilgængelig via apt på boxen)**: PNG'er genkender Novo/LEI, HONDA/VIN, Knowledge/SUCCEEDED; OCR-tekst secret-scannes.
5. **Draft-snippets** til actor-sider findes og secret-scannes (endnu ikke PUT).

## 4. Artefakter
| Fil | Formål |
|---|---|
| `assets/demo/{actor}.cast` | asciinema-optagelse |
| `assets/demo/{actor}.gif` | kort demo-GIF |
| `assets/demo/{actor}.png` | terminal-screenshot |
| `assets/demo/manifest.json` | run-meta + raw URL'er |
| `assets/demo/live/*` | rå live JSON/MCP til regression |
| `drafts/demo-actor-readme-snippets.md` | tekst+URL klar til actor-PUT |

## 5. Ikke gjort (afventer Venture Lead)
- `git push` af open-data-mcp
- PUT/README-opdatering på Apify for de 3 actors (grænse 5 publikationer/24t; aldrig pricingInfos/isPublic)

## Kommandoer
```bash
cd /workspace/venture/open-data-mcp
python3 tests/test_round18.py          # offline checks + OCR
python3 tests/test_round18.py --live   # + 3 friske API-kald (kræver APIFY_TOKEN i env)
```
