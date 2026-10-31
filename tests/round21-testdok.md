# Round 21 — Try in 30 seconds (testdokumentation)

Dato: 2026-10-31 Europe/Copenhagen  
Repo: `markatdataandbeyond/open-data-mcp`  
Actors (mest brugte efter totalRuns): `eu-company-verify` (25), `scholar-search` (21), `eu-tenders` (20)  
Suite: `python3 tests/test_round21.py` → **13/13 PASS**  
Ingen tokens i repo (secret-scan). Intet offentligt opslag.

## Formål
1. Kort **Try in 30 seconds**-sektion øverst i open-data-mcp README og på de 3 mest brugte actor-README'er.
2. Ét copy-paste-eksempel + rigtigt live-output pr. side.
3. TDD før push/Apify-opdatering.

## Overordnede tests
| # | Test | Resultat |
|---|---|---|
| 01 | open-data-mcp README har `## Try in 30 seconds` før `## Tools` | PASS |
| 02 | Sektionen har bash copy-paste + DK24256790 / NOVO / LEI | PASS |
| 03–05 | Actor-README'er (top 3) har sektionen nær toppen | PASS |
| 06 | eu-company-verify: curl + live verdict-felter | PASS |
| 07 | scholar-search: KGE-query + DOI | PASS |
| 08 | eu-tenders: TED-URL + live publicationNumber/buyer | PASS |
| 09 | Secret-scan af berørte README'er | PASS |

## Live stikprøver (rigtigt output, lokal MCP stdio)
| Tool | Input | Stikprøve | Resultat |
|---|---|---|---|
| eu-company-verify | DK24256790 | NOVO NORDISK A/S, valid=true, LEI 549300DAQ1CVT6CXN342 | PASS |
| scholar-search | knowledge graph embedding (max 2) | DOI 10.1016/j.knosys.2018.10.008 (2019) | PASS |
| eu-tenders | countries=["DK"], 14 dage, max 2 | 753508-2026 / I/S AffaldPlus | PASS |

## Kanttilfælde (≥3)
| # | Case | Resultat |
|---|---|---|
| 13 | eu-company `queries: []` → fejl | PASS |
| 14 | eu-company `queries: ["   "]` → fejl | PASS |
| 15 | eu-tenders `cpvCodes: ["abc"]` → Invalid CPV / fejl | PASS |

## Artefakter
- `tests/test_round21.py`, `tests/round21-testdok.md`
- README: `open-data-mcp/README.md`, `apify-actors/{eu-company-verify,scholar-search,eu-tenders}/README.md`
- Dag-7 go/kill: `/workspace/venture/apify-actors/drafts/dag7-gokill-2026-11-02.md`
