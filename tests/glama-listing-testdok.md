# Glama server-listing — testdokumentation (29/10/2026 Europe/Copenhagen)

Repo: markatdataandbeyond/open-data-mcp  
Suite: `python3 tests/test_glama_listing.py` → **11/11 PASS**  
Ingen tokens i Dockerfile/README/glama.json. Intet indsendt i Glama-UI af denne agent.

## Resultat vs dbu-waste-finder
| | dbu-waste-finder | open-data-mcp (før) | open-data-mcp (efter repo-fix) |
|---|---|---|---|
| Glama **server** `/mcp/servers/OWNER/REPO` | 200, has-glama på awesome #17879 | **404** | stadig 404 (kræver VL Add MCP Server) |
| Glama **connector** (registry) | — | live, unhealthy uden test-profil | uændret |
| glama.json | mangler i repo | findes | findes, maintainers OK |
| Dockerfile i repo | mangler (Glama AI/admin) | ENTRYPOINT | **CMD + USER node** |
| GitHub topics | inkl. `mcp` | tomme | `mcp`, `model-context-protocol`, `apify`, `open-data` |
| README Glama-badge | nej | nej | badge-URL tilføjet (viser "not listed" indtil server findes) |

## Tests
### Overordnede
01 Dockerfile har CMD (ikke ENTRYPOINT) + USER node — PASS  
02 glama.json schema + maintainers — PASS  
03 README indeholder badge + server-URL — PASS  
04 Ingen secrets i Dockerfile/README/glama.json — PASS  
05 Godkendt kort tekst i katalog-tekster.json — PASS  

### Live-stikprøver
06 Connector 200, server 404 — PASS (dokumenterer gap)  
07 Badge-SVG siger "not listed" — PASS  
08 dbu-waste-finder server 200 — PASS  

### Kanttilfælde
09 Ingen `ENV/ARG APIFY_TOKEN=…` i Dockerfile — PASS  
10 package.json start matcher CMD — PASS  
11 GitHub topics indeholder mcp + model-context-protocol — PASS  

## Godkendt kort beskrivelse (ordret, til Glama-feltet)
Ten tools I built to get facts from official open data, not guesses.

## Venture Lead: præcise browser-trin (IKKE kørt her)
1. Åbn https://glama.ai/mcp/servers → **Add MCP Server** (ikke Connectors).
2. GitHub URL: `https://github.com/markatdataandbeyond/open-data-mcp`
3. Display name: `open-data-mcp`
4. Description (kort, ordret): `Ten tools I built to get facts from official open data, not guesses.`
5. Submit. Vent til siden `https://glama.ai/mcp/servers/markatdataandbeyond/open-data-mcp` giver 200 (ikke 404).
6. **Claim ownership** med GitHub som `markatdataandbeyond` (repo er under personlig konto; glama.json har allerede maintainers).
7. Admin → **Dockerfile**: peg på repoets Dockerfile (eller indsæt indholdet). CMD skal være `["node","src/index.js"]`. Env: valgfri `APIFY_TOKEN` (tom til introspection).
8. Build / Deploy test → server skal starte og svare på initialize + tools/list **uden** token → Make Release hvis UI kræver det.
9. Tjek at badge ikke længere siger "not listed": https://glama.ai/mcp/servers/markatdataandbeyond/open-data-mcp/badges/score.svg
10. Opdater awesome PR #17857: indsæt badge efter beskrivelsen:
    `[![markatdataandbeyond/open-data-mcp MCP server](https://glama.ai/mcp/servers/markatdataandbeyond/open-data-mcp/badges/score.svg)](https://glama.ai/mcp/servers/markatdataandbeyond/open-data-mcp)`
11. **Connector** (valgfrit, separat): https://glama.ai/mcp/connectors/io.github.markatdataandbeyond/open-data-mcp → Claim → Manage → sæt beskrivelse til samme korte tekst (og "Use Glama listing details" hvis registry ellers overskriver). Tilføj test-profil med API key = Apify-token så health check bliver grøn.

Bemærk: connector ≠ server. awesome `missing-glama` kræver **server**-siden + badge, som dbu fik.
