# Round 19 — lokal open-data MCP-server (testdokumentation)

Dato: 2026-10-29 Europe/Copenhagen  
Repo: `markatdataandbeyond/open-data-mcp`  
Suite: `python3 tests/test_round19.py` → **22/22 PASS** (21.6 s)  
Ingen tokens i repo (secret-scan). Intet Glama-UI. Intet push endnu (afventer aflevering af denne testdok).

## Formål
Glama afviste server-listing to gange fordi repoet var en Apify-proxy. Round 19 gør serveren til en ægte lokal open-source MCP-server: alle 10 tools kalder officielle gratis API'er direkte. Apify nævnes kun som **Hosted version** (betalt).

## Overordnede tests
| # | Test | Resultat |
|---|---|---|
| 01 | Påkrævede filer (Dockerfile, LICENSE, src/lib/*, catalog) | PASS |
| 02 | MIT-licens | PASS |
| 03 | README har "Hosted version" + Apify-links; ingen "thin proxy"-sprog | PASS |
| 04 | catalog/tools.json: 10 tools, schemas, ingen Actor-proxy-tekst | PASS |
| 05 | index.js kalder `runTool` (ingen mcp.apify.com / callUpstreamTool) | PASS |
| 06 | Secret-scan (apify_api_/gh_/sk- + env-værdier) | PASS |
| 07 | node tools/list uden nøgler → 10 tools | PASS |
| 08 | Docker build + container tools/list uden nøgler | PASS |

## Live stikprøver (rigtigt output, uden APIFY_TOKEN)
| Tool | Input | Stikprøve (forkortet) | Resultat |
|---|---|---|---|
| eu-company-verify | DK24256790 | `[   {     "query": "DK24256790",     "inputType": "VAT",     "vat": {       "countryCode": "DK",       "number": "24256790",       "checked": true,       "valid": true,       "name` | PASS |
| dk-statistics | population municipality | `[   {     "type": "table",     "tableId": "SBR01",     "title": "Hospital utilisation in the population",     "unit": "Number",     "updated": "2026-07-03T08:00:00",     "firstPeri` | PASS |
| scholar-search | knowledge graph embedding | `[   {     "query": "knowledge graph embedding",     "title": "Knowledge graph embedding with concepts",     "doi": "10.1016/j.knosys.2018.10.008",     "year": 2019,     "authors": ` | PASS |
| pubmed-search | crispr gene editing | `[   {     "query": "crispr gene editing",     "pmid": "42950026",     "title": "FOSL1-associated condensates modulate superenhancer-mediated selected IL-1 family gene activation in` | PASS |
| eu-tenders | software / DK | `[   {     "publicationNumber": "752128-2026",     "title": "Denmark – Software programming and consultancy services – Udbud af rammeaftale om levering af IT-konsulentydelser inden ` | PASS |
| france-company-search | SIREN 383474814 | `[   {     "query": "383474814",     "siren": "383474814",     "siretHeadOffice": "38347481400100",     "name": "AIRBUS",     "legalName": "AIRBUS",     "acronym": null,     "legalF` | PASS |
| nordic-company-registry | 923609016 (NO) | `[   {     "query": "923609016",     "country": "NO",     "registryId": "923609016",     "vatNumber": "NO923609016MVA",     "name": "EQUINOR ASA",     "legalForm": "ASA",     "legal` | PASS |
| clinical-trials | diabetes | `[   {     "nctId": "NCT07839429",     "title": "Effect of mHealth Intervention on Oral Health-Related Quality of Life Among Adult Patients With Chronic Systemic Diseases",     "off` | PASS |
| vin-decoder-recalls | 1HGCM82633A004352 | `[   {     "vin": "1HGCM82633A004352",     "valid": true,     "decodeWarnings": null,     "make": "HONDA",     "model": "Accord",     "modelYear": 2003,     "trim": "EX-V6",     "se` | PASS |
| weather-forecast | 55.6761,12.5683 | `[   {     "location": "55.6761,12.5683",     "resolvedName": "55.6761,12.5683",     "lat": 55.6761,     "lon": 12.5683,     "timezone": null,     "updatedAt": "2026-10-29T07:34:19Z` | PASS |

## Kanttilfælde (≥3)
| # | Case | Resultat |
|---|---|---|
| 20 | Tomt input (`locations: []`) → fejl/isError | PASS |
| 21 | Ugyldigt VIN (`!!!INVALID!!!`) → valid:false / Invalid | PASS |
| 22 | Kun-mellemrum i queries → Invalid input / isError | PASS |
| 23 | Ukendt tool-navn → Unknown tool | PASS |

## Implementation
- `src/lib/http.js`, `vies.js`, `geocode.js`, `tools-impl.js` (10 runners), `runTool.js`
- `src/index.js` v1.1.0 — lokal stdio MCP
- Dockerfile: `CMD ["node","src/index.js"]`, USER node
- README: lokal først; sektion **Hosted version** → Apify Actors
- Valgfri env: `OPENALEX_API_KEY`, `NCBI_API_KEY` (ikke påkrævet)
- `forward.js` er ikke længere brugt af index (kan fjernes senere)

## Næste skridt (ikke gjort her)
1. Venture Lead: Add MCP Server igen + Dockerfile i Glama Admin + kort tekst.
2. Claim connectors + test profile (stadig Unhealthy).
3. Push tilladt efter denne testdok er afleveret (stående regel).
