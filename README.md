# Open-Data MCP Tools by Data and Beyond

10 agent-ready tools built on **official open-data APIs** (no scraping), callable from Claude, Cursor or any MCP client through the [Apify MCP server](https://docs.apify.com/platform/integrations/mcp). Pay per result in USD, no start fee.

| Tool | What it does | Price (USD) |
|---|---|---|
| [eu-company-verify](https://apify.com/dataandbeyond/eu-company-verify) | EU VAT (VIES) + LEI (GLEIF) company verification | 0.004/company |
| [dk-statistics](https://apify.com/dataandbeyond/dk-statistics) | Statistics Denmark (Statbank) tables | 0.003/table + 0.002/100 rows |
| [scholar-search](https://apify.com/dataandbeyond/scholar-search) | Academic papers via Crossref/arXiv/OpenAlex | 0.002/paper |
| [pubmed-search](https://apify.com/dataandbeyond/pubmed-search) | PubMed biomedical literature | 0.002/article |
| [eu-tenders](https://apify.com/dataandbeyond/eu-tenders) | EU public tenders (TED) | 0.003/tender |
| [france-company-search](https://apify.com/dataandbeyond/france-company-search) | French companies (SIREN/SIRET, Sirene) | 0.003/company |
| [nordic-company-registry](https://apify.com/dataandbeyond/nordic-company-registry) | Norway + Finland company registries | 0.003/company |
| [clinical-trials](https://apify.com/dataandbeyond/clinical-trials) | ClinicalTrials.gov v2 | 0.003/trial |
| [vin-decoder-recalls](https://apify.com/dataandbeyond/vin-decoder-recalls) | VIN decode + NHTSA recalls | 0.002/VIN |
| [weather-forecast](https://apify.com/dataandbeyond/weather-forecast) | MET Norway worldwide forecast | 0.001/forecast |

## Use with MCP
```json
{ "mcpServers": { "dataandbeyond": {
  "url": "https://mcp.apify.com/?tools=dataandbeyond/eu-company-verify,dataandbeyond/dk-statistics,dataandbeyond/scholar-search,dataandbeyond/pubmed-search,dataandbeyond/eu-tenders,dataandbeyond/france-company-search,dataandbeyond/nordic-company-registry,dataandbeyond/clinical-trials,dataandbeyond/vin-decoder-recalls,dataandbeyond/weather-forecast",
  "headers": { "Authorization": "Bearer <YOUR_APIFY_TOKEN>" } } } }
```
Get a token at https://console.apify.com/settings/integrations (free plan includes monthly credit).

## Use over HTTP
```bash
curl -X POST "https://api.apify.com/v2/acts/dataandbeyond~eu-tenders/run-sync-get-dataset-items?token=$APIFY_TOKEN" -H 'Content-Type: application/json' -d '{}'
```

## Data licenses
Each tool's Store page lists its source and license (CC0, CC BY 4.0, Etalab 2.0, NLOD 2.0, US public domain, EU reuse decision). No personal data: sole traders and directors are filtered out.

## License
This repository (docs and config) is MIT licensed. Made by Data and Beyond ApS, Copenhagen.
