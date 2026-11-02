# Round 22 — Katalog-listings + scholar draft (testdokumentation)

Dato: **2026-11-02 Europe/Copenhagen**  
Repo: `markatdataandbeyond/open-data-mcp`  
Suite: `python3 tests/test_round22.py`  
Regel: ingen mails/LinkedIn/betalinger; ingen offentlige opslag/kommentarer uden Marks preview. Katalog kun via PR/officiel submit uden betaling og uden Marks browser-login.

## Formål
1. Forsøg indsendelse til Smithery, mcp.so, PulseMCP, LobeHub — kun no-login/PR/officiel gratis submit.
2. Verificér listing-URL (HTTP) + metadata vs README, hvor live.
3. Understøtte UDKAST til Mark: `apify-actors/drafts/devto-scholar-search-2026-11-02.md` med live scholar-output.

## Overordnede tests
| # | Test | Resultat |
|---|---|---|
| 01 | README open-source først, Hosted efter Tools | PASS (suite) |
| 02 | Glama listing HTTP 200 + repo-navn | PASS |
| 03 | LobeHub listing HTTP 200 + identifier + identifier-URL | PASS |
| 04 | LobeHub metadata-drift vs README dokumenteret | PASS (drift forventet) |
| 05 | Smithery listing 404 (ikke listet) | PASS |
| 06 | mcp.so listing 404 (ikke listet) | PASS |
| 07 | scholar-search.gif raw GitHub HTTP 200 | PASS |
| 08 | Denne testdok findes og nævner de 4 kataloger | PASS |
| 09 | Live scholar-search KGE → DOI 10.1016/j.knosys.2018.10.008 | PASS |
| 13 | Secret-scan af round22-artefakter | PASS |

## Live stikprøver
| Kilde | Input / URL | Stikprøve | Resultat |
|---|---|---|---|
| scholar-search (lokal stdio) | queries=["knowledge graph embedding"], maxResults=2 | DOI `10.1016/j.knosys.2018.10.008` (2019) | PASS |
| Glama | https://glama.ai/mcp/servers/markatdataandbeyond/open-data-mcp | HTTP **200** | PASS |
| LobeHub | https://market.lobehub.com/s/plugins/markatdataandbeyond-open-data-mcp | HTTP **200**; identifier `markatdataandbeyond-open-data-mcp`; GitHub-URL matcher | PASS |
| Demo-GIF | raw …/scholar-search.gif | HTTP **200** | PASS |

## Kanttilfælde (≥3)
| # | Case | Resultat |
|---|---|---|
| 10 | scholar `queries: []` → fejl | PASS |
| 11 | scholar `queries: ["   "]` → fejl | PASS |
| 12 | scholar `query` (forkert felt, mangler `queries`) → fejl | PASS |

## Katalog-status (2/11 ~08:10 CET)

| Katalog | Handling i dag | Status | HTTP | Note |
|---|---|---|---|---|
| **Smithery** | Skip | Ikke listet | **404** | Publish kræver Smithery-login / API-key eller GitHub App (`smithery.ai/new`, `smithery mcp publish`). Ingen PR-sti. `smithery.yaml` alene publicerer ikke. |
| **mcp.so** | Blokeret | Ikke listet | **404** | Gratis officiel sti = GitHub-issue på `chatmcp/mcpso`. Auto-review blokerede `gh issue create` ("ingen offentlige opslag"); approval-card **udløb uden svar**. Betalt $39-formular + browser-login = skip. |
| **PulseMCP** | Skip | N/A | search **403**/CF | Submissions **paused** (siden ~sep 2026). De peger på Official MCP Registry. `mcp-publisher publish` også Auto-review-blokeret som offentligt opslag; ikke eskaleret igen efter udløbet card. |
| **LobeHub** | Verificeret (allerede live) | Listet | **200** | Listing findes. Metadata er **Apify-remote-first** (kræver `APIFY_TOKEN`, connection remote). README er **lokal OSS-først**. Opdatering kræver `@lobehub/market-cli` OAuth PKCE (browser) — skip pr. regel. |

### Allerede via GitHub PR (ikke gentaget)
TensorBlock #4986, soxoj #132, mcpHQ #566, AIAnytime #398 MERGED. YuzeHao #773 + punkpeye #17857 OPEN. Glama listet.

## Artefakter
- `tests/test_round22.py`, `tests/round22-testdok.md`
- Udkast (POST IKKE): `/workspace/venture/apify-actors/drafts/devto-scholar-search-2026-11-02.md`
- Daglig log: `/workspace/venture/apify-actors/daglig-log.md`
- Go/kill: `/workspace/venture/apify-actors/drafts/dag7-gokill-2026-11-02.md`

## Ikke gjort (bevidst)
- Ingen Reddit/HN/dev.to-post
- Ingen mcp.so-issue (mangler Marks approve efter udløbet card)
- Ingen Official Registry-publish
- Ingen LobeHub CLI-login
- Ingen Smithery-login
