# Round 20 — lokale demos + katalog-PR (testdokumentation)

Dato: 2026-10-29 Europe/Copenhagen  
Repo: `markatdataandbeyond/open-data-mcp`  
Suite: `python3 tests/test_round20.py` → **37/37 PASS** (round20 + round19)  
Ingen tokens i repo (secret-scan). Ingen Reddit/HN/issue-kommentarer postet.

## Formål
1. Opdatere Demo-sektion med rigtige lokale live-kald (VIES + NHTSA + scholar).
2. Indsende via GitHub-PR hvor muligt; liste browser/login-kataloger.
3. Forberede Reddit-udkast (ikke postet) i Line Krogh-tone.

## Overordnede tests
| # | Test | Resultat |
|---|---|---|
| 01 | Demo-filer (.cast/.gif/.png) for 3 tools | PASS |
| 02–04 | Cast-tekst indeholder live output (NOVO/HONDA/DOI) | PASS |
| 05 | manifest.json mode=local-stdio | PASS |
| 06 | README Demo: lokal stdio, VIES/NHTSA, record-local-demos | PASS |
| 07 | demo-scripts kræver ikke APIFY_TOKEN | PASS |
| 08 | Secret-scan af demo-assets | PASS |
| 14 | tools/list → 10 tools uden nøgler | PASS |
| 15 | index.js uden mcp.apify.com | PASS |
| R19 01–08 | Round19 filer/Docker/secret/list | PASS |

## Live stikprøver (rigtigt output)
| Tool | Input | Stikprøve (forkortet) | Resultat |
|---|---|---|---|
| eu-company-verify | DK24256790 | NOVO NORDISK A/S, vat.valid=true, VERIFIED | PASS |
| vin-decoder-recalls | 1HGCM82633A004352 | HONDA Accord 2003, recalls til stede | PASS |
| scholar-search (cast) | knowledge graph embedding | 2019 Knowledge graph embedding with concepts (DOI …) | PASS |
| Round19 live ×10 | (samme som round19) | alle 10 tools returnerer JSON | PASS |

## Kanttilfælde (≥3)
| # | Case | Resultat |
|---|---|---|
| 11 | Tom queries [] → fejl | PASS |
| 12 | Ugyldigt VIN !!!INVALID!!! → valid:false / Invalid | PASS |
| 13 | Kun-mellemrum i queries → fejl | PASS |
| R19 20–23 | empty / invalid VIN / spaces / unknown tool | PASS |

## Artefakter
- Screenshots: `assets/demo/eu-company-verify.png`, `vin-decoder-recalls.png`, `scholar-search.png`
- GIF + cast: samme prefix under `assets/demo/`
- Scripts: `scripts/demo-mcp-call.mjs`, `demo-local.sh`, `record-local-demos.sh`
- Reddit-udkast: `/workspace/venture/apify-actors/drafts/reddit-localllama-claudeai.md`
- Browser-liste: `/workspace/venture/apify-actors/drafts/katalog-browser-liste-2026-10-29.md`

## Katalogstatus
- PR opdateret: https://github.com/punkpeye/awesome-mcp-servers/pull/17857 (🏠 lokal)
- appcypher: branch klar, PR API blocked — manuel compare i browser-listen
- Ingen issue-kommentarer (mcp.so/Cline) pga. stående regel
