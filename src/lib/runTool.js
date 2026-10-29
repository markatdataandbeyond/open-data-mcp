/**
 * Dispatch MCP tools/call to local open-data implementations.
 * No Apify dependency. Optional env: OPENALEX_API_KEY, NCBI_API_KEY.
 */
import {
  runEuCompanyVerify,
  runDkStatistics,
  runScholarSearch,
  runPubmedSearch,
  runEuTenders,
  runFranceCompanySearch,
  runNordicCompanyRegistry,
  runClinicalTrials,
  runVinDecoderRecalls,
  runWeatherForecast,
} from './tools-impl.js';

const RUNNERS = {
  'dataandbeyond--eu-company-verify': runEuCompanyVerify,
  'dataandbeyond--dk-statistics': runDkStatistics,
  'dataandbeyond--scholar-search': runScholarSearch,
  'dataandbeyond--pubmed-search': runPubmedSearch,
  'dataandbeyond--eu-tenders': runEuTenders,
  'dataandbeyond--france-company-search': runFranceCompanySearch,
  'dataandbeyond--nordic-company-registry': runNordicCompanyRegistry,
  'dataandbeyond--clinical-trials': runClinicalTrials,
  'dataandbeyond--vin-decoder-recalls': runVinDecoderRecalls,
  'dataandbeyond--weather-forecast': runWeatherForecast,
};

export function knownToolNames() {
  return Object.keys(RUNNERS);
}

export async function runTool(name, args = {}) {
  const fn = RUNNERS[name];
  if (!fn) {
    const err = new Error(`Unknown tool "${name}". Known tools: ${knownToolNames().join(', ')}`);
    err.code = 'UNKNOWN_TOOL';
    throw err;
  }
  const result = await fn(args || {});
  const items = result?.items ?? result;
  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify(items, null, 2),
      },
    ],
  };
}
