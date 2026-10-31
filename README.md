# open-data-mcp

[![markatdataandbeyond/open-data-mcp MCP server](https://glama.ai/mcp/servers/markatdataandbeyond/open-data-mcp/badges/score.svg)](https://glama.ai/mcp/servers/markatdataandbeyond/open-data-mcp)
[![Listed on mcpservers.org](https://mcpservers.org/badge.svg)](https://mcpservers.org/servers/markatdataandbeyond/open-data-mcp)

Ten tools I built to get facts from official open data, not guesses. This repository is an **open-source MCP server** (stdio). Each tool calls the official source API directly from your machine — no Apify token required for the local server.

Optional env keys (never commit them):

- `OPENALEX_API_KEY` — enables OpenAlex in scholar-search (free key from openalex.org)
- `NCBI_API_KEY` — higher PubMed rate limits (free from NCBI)

## Try in 30 seconds

```bash
npm ci
node scripts/demo-mcp-call.mjs dataandbeyond--eu-company-verify '{"queries":["DK24256790"]}'
```

Live output (2026-10-31, Europe/Copenhagen): `DK24256790 → NOVO NORDISK A/S`, VIES `valid=true`, LEI `549300DAQ1CVT6CXN342`. No API key required for this call.

## Tools

| Tool | Official source |
|---|---|
| `dataandbeyond--eu-company-verify` | EU VIES + GLEIF |
| `dataandbeyond--dk-statistics` | Statistics Denmark (Statbank) |
| `dataandbeyond--scholar-search` | Crossref, arXiv (+ OpenAlex with key) |
| `dataandbeyond--pubmed-search` | NCBI PubMed E-utilities |
| `dataandbeyond--eu-tenders` | TED API v3 |
| `dataandbeyond--france-company-search` | Recherche d'entreprises (INSEE/DINUM) |
| `dataandbeyond--nordic-company-registry` | Brønnøysund + PRH/YTJ |
| `dataandbeyond--clinical-trials` | ClinicalTrials.gov API v2 |
| `dataandbeyond--vin-decoder-recalls` | NHTSA vPIC + Recalls |
| `dataandbeyond--weather-forecast` | MET Norway (+ Nominatim geocode) |

## Run locally

```bash
npm ci
node src/index.js
```

Point your MCP client at the stdio command `node /path/to/open-data-mcp/src/index.js` (or the Docker image built from the Dockerfile in this repo). `tools/list` works with no environment variables.

Docker:

```bash
docker build -t open-data-mcp .
docker run --rm -i open-data-mcp
```

## Hosted version

The same ten tools are also available as **pay-per-event Apify Actors** if you want a hosted endpoint instead of running the server yourself:

| Actor | Store | Price (USD) |
|---|---|---|
| [eu-company-verify](https://apify.com/dataandbeyond/eu-company-verify) | VIES + GLEIF | 0.004 per company verified |
| [dk-statistics](https://apify.com/dataandbeyond/dk-statistics) | Statbank | 0.003 per table described + 0.002 per 100 rows |
| [scholar-search](https://apify.com/dataandbeyond/scholar-search) | papers | 0.002 per paper |
| [pubmed-search](https://apify.com/dataandbeyond/pubmed-search) | PubMed | 0.002 per article |
| [eu-tenders](https://apify.com/dataandbeyond/eu-tenders) | TED | 0.003 per tender notice |
| [france-company-search](https://apify.com/dataandbeyond/france-company-search) | Sirene | 0.003 per company |
| [nordic-company-registry](https://apify.com/dataandbeyond/nordic-company-registry) | NO+FI | 0.003 per company |
| [clinical-trials](https://apify.com/dataandbeyond/clinical-trials) | ClinicalTrials.gov | 0.003 per trial |
| [vin-decoder-recalls](https://apify.com/dataandbeyond/vin-decoder-recalls) | NHTSA | 0.001 per VIN / 0.003 with recalls |
| [weather-forecast](https://apify.com/dataandbeyond/weather-forecast) | MET Norway | 0.001 per forecast |

Hosted MCP URL (requires your Apify token):

```
https://mcp.apify.com/?tools=dataandbeyond/eu-company-verify,dataandbeyond/dk-statistics,dataandbeyond/scholar-search,dataandbeyond/pubmed-search,dataandbeyond/eu-tenders,dataandbeyond/france-company-search,dataandbeyond/nordic-company-registry,dataandbeyond/clinical-trials,dataandbeyond/vin-decoder-recalls,dataandbeyond/weather-forecast
```

Client config examples for the hosted path: [examples/cursor.json](examples/cursor.json), [examples/claude-desktop.json](examples/claude-desktop.json), [examples/vscode.json](examples/vscode.json).

## Demo

Short terminal recordings of the local stdio server calling official open data APIs. No API keys required for these demos.

| Tool | What you see | GIF | Screenshot |
|---|---|---|---|
| `eu-company-verify` | EU VIES check for DK24256790 → NOVO NORDISK A/S | ![eu-company-verify demo](assets/demo/eu-company-verify.gif) | [PNG](assets/demo/eu-company-verify.png) |
| `vin-decoder-recalls` | NHTSA decode of a Honda Accord VIN + recall count | ![vin-decoder-recalls demo](assets/demo/vin-decoder-recalls.gif) | [PNG](assets/demo/vin-decoder-recalls.png) |
| `scholar-search` | Crossref/arXiv papers for "knowledge graph embedding" | ![scholar-search demo](assets/demo/scholar-search.gif) | [PNG](assets/demo/scholar-search.png) |

Replay a cast with [asciinema](https://asciinema.org/): `asciinema play assets/demo/eu-company-verify.cast`. Re-record with `bash scripts/record-local-demos.sh`.

## License

MIT. See [LICENSE](LICENSE).
