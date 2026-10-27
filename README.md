# open-data-mcp

Ten Apify Actors from Data and Beyond ApS that wrap official open-data APIs. They can be called from Claude, Cursor, VS Code or any other MCP client through the [Apify MCP server](https://docs.apify.com/platform/integrations/mcp), or directly over the Apify API.

This repository holds only documentation and client configuration. The Actor code runs on Apify.

## The Actors

Prices are pay-per-event in USD, charged by Apify.

| Actor | Data source | Price (USD) |
|---|---|---|
| [eu-company-verify](https://apify.com/dataandbeyond/eu-company-verify) | EU VAT check in VIES, plus LEI and parent companies from GLEIF | 0.004 per company found |
| [dk-statistics](https://apify.com/dataandbeyond/dk-statistics) | Statistics Denmark (Statbank) tables, search in English or Danish | 0.003 per table + 0.002 per 100 rows |
| [scholar-search](https://apify.com/dataandbeyond/scholar-search) | Academic papers from OpenAlex, Crossref and arXiv | 0.002 per paper |
| [pubmed-search](https://apify.com/dataandbeyond/pubmed-search) | PubMed via NCBI E-utilities: PMID, DOI, PMCID, authors | 0.002 per article |
| [eu-tenders](https://apify.com/dataandbeyond/eu-tenders) | EU public tenders from TED | 0.003 per tender |
| [france-company-search](https://apify.com/dataandbeyond/france-company-search) | French companies (SIREN/SIRET) from Sirene | 0.003 per company |
| [nordic-company-registry](https://apify.com/dataandbeyond/nordic-company-registry) | Company registries in Norway and Finland | 0.003 per company |
| [clinical-trials](https://apify.com/dataandbeyond/clinical-trials) | ClinicalTrials.gov API v2 | 0.003 per trial |
| [vin-decoder-recalls](https://apify.com/dataandbeyond/vin-decoder-recalls) | VIN decoding and NHTSA recalls | 0.001 per VIN, 0.003 with recall check |
| [weather-forecast](https://apify.com/dataandbeyond/weather-forecast) | MET Norway forecasts for any place name or coordinates | 0.001 per forecast |

## Setup

You need an Apify account and an API token from https://console.apify.com/settings/integrations. Replace `<APIFY_TOKEN>` in the config with your token, and keep the token out of version control.

- Cursor: [examples/cursor.json](examples/cursor.json) goes in `.cursor/mcp.json` or `~/.cursor/mcp.json`.
- Claude Desktop: [examples/claude-desktop.json](examples/claude-desktop.json) uses `mcp-remote` to connect to the remote server.
- VS Code: [examples/vscode.json](examples/vscode.json) goes in `.vscode/mcp.json`.
- Other clients: point a streamable HTTP connection at the URL below with the header `Authorization: Bearer <APIFY_TOKEN>`.

```
https://mcp.apify.com/?tools=dataandbeyond/eu-company-verify,dataandbeyond/dk-statistics,dataandbeyond/scholar-search,dataandbeyond/pubmed-search,dataandbeyond/eu-tenders,dataandbeyond/france-company-search,dataandbeyond/nordic-company-registry,dataandbeyond/clinical-trials,dataandbeyond/vin-decoder-recalls,dataandbeyond/weather-forecast
```

To load fewer tools, remove Actors from the `tools=` list.

## Without MCP

```bash
curl -X POST "https://api.apify.com/v2/acts/dataandbeyond~weather-forecast/run-sync-get-dataset-items" \
  -H "Authorization: Bearer $APIFY_TOKEN" -H "Content-Type: application/json" \
  -d '{"locations": ["Copenhagen"]}'
```

## Notes

- On Apify's free plan, run one Actor at a time. Several parallel runs can fail with HTTP 402.
- Each Actor's Store page lists its data source and the source's license.

## License

The documentation and configuration in this repository are MIT licensed. See [LICENSE](LICENSE).
