/**
 * Local open-data tool implementations. Call official APIs directly.
 * Optional env: OPENALEX_API_KEY, NCBI_API_KEY. Never requires APIFY_TOKEN.
 */
import { j, sleep, validateInput, notFound, UA } from './http.js';
import { makeVies } from './vies.js';
import { makeGeocoder } from './geocode.js';

const vies = makeVies({ ua: UA });
const geocode = makeGeocoder({ ua: UA });

function okItems(items) {
  return { items: Array.isArray(items) ? items : [items] };
}

// --- eu-company-verify ---
const EU = 'AT BE BG CY CZ DE DK EE EL ES FI FR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK XI'.split(' ');
const isLei = (q) => /^[A-Z0-9]{18}[0-9]{2}$/.test(q);
const leiChecksumOk = (q) => BigInt([...q].map((c) => (/[A-Z]/.test(c) ? c.charCodeAt(0) - 55 : c)).join('')) % 97n === 1n;
function parseVat(q, dc) {
  const s = q.replace(/[\s.\-]/g, '').toUpperCase();
  const cc = s.slice(0, 2);
  if (EU.includes(cc) || cc === 'GR') return { cc: cc === 'GR' ? 'EL' : cc, num: s.slice(2) };
  if (/^\d{6,12}$/.test(s) && dc) return { cc: dc.toUpperCase(), num: s };
  return null;
}
function slimLei(rec) {
  if (!rec) return null;
  const a = rec.attributes, e = a.entity;
  return {
    lei: a.lei, legalName: e.legalName?.name, status: e.status, legalForm: e.legalForm?.id, jurisdiction: e.jurisdiction,
    registeredAs: e.registeredAs, registeredAt: e.registeredAt?.id,
    legalAddress: e.legalAddress && { lines: e.legalAddress.addressLines, city: e.legalAddress.city, postalCode: e.legalAddress.postalCode, country: e.legalAddress.country },
    registrationStatus: a.registration?.status, nextRenewalDate: a.registration?.nextRenewalDate, lastUpdate: a.registration?.lastUpdateDate,
  };
}
async function parent(lei, kind) {
  const r = await j(`https://api.gleif.org/api/v1/lei-records/${lei}/${kind}-parent`);
  return r?.data ? slimLei(r.data) : null;
}
async function gleifSearch(f, v, size = 3) {
  const r = await j(`https://api.gleif.org/api/v1/lei-records?filter%5B${f}%5D=${encodeURIComponent(v)}&page%5Bsize%5D=${size}`);
  return r?.data || [];
}
const SUFFIX = /\b(a\/s|aps|as|asa|ab|oy|oyj|ag|gmbh|se|sa|s\.a\.|nv|n\.v\.|bv|b\.v\.|plc|ltd|limited|inc|llc|spa|s\.p\.a\.|srl|sas|kg)\.?$/i;
const normName = (s) => String(s || '').toLowerCase().replace(/[.,]/g, ' ').replace(/\s+/g, ' ').trim();
function rankByName(recs, q) {
  const nq = normName(q);
  const score = (d) => {
    const a = d.attributes, nm = normName(a.entity.legalName?.name), base = nm.replace(SUFFIX, '').trim();
    return (a.entity.status === 'ACTIVE' && a.registration?.status === 'ISSUED' ? 100 : 0) + (nm === nq || base === nq ? 50 : nm.startsWith(nq) ? 20 : 0) - Math.min(nm.length, 99) / 100;
  };
  return recs.map((d) => [score(d), d]).sort((x, y) => y[0] - x[0]).map((x) => x[1]);
}

export async function runEuCompanyVerify(raw) {
  const inp = validateInput(raw);
  const queries = (inp.queries || []).map(String).map((s) => s.trim()).filter(Boolean).slice(0, inp.maxItems || 1000);
  const withParents = inp.includeParents !== false, dc = inp.defaultCountry || null;
  if (!queries.length) throw new Error('Provide at least one item in "queries" (VAT number, LEI, or company name).');
  const items = [];
  for (const q of queries) {
    const out = {
      query: q, inputType: null, vat: null, lei: null, directParent: null, ultimateParent: null, otherLeiMatches: [],
      verdict: 'NOT_FOUND', checkedAt: new Date().toISOString(),
      sources: ['GLEIF LEI data, CC0 1.0 (gleif.org)', 'EU VIES (ec.europa.eu/taxation_customs/vies)'],
    };
    let leiRecs = [];
    if (isLei(q.toUpperCase()) && !leiChecksumOk(q.toUpperCase())) {
      out.inputType = 'LEI'; out.verdict = 'INVALID_LEI'; out.status = 'INVALID_INPUT';
      out.error = 'invalid LEI: ISO 17442 check digits do not match (mod 97 != 1). Not looked up.';
      items.push(out); continue;
    }
    if (isLei(q.toUpperCase())) {
      out.inputType = 'LEI';
      const r = await j(`https://api.gleif.org/api/v1/lei-records/${q.toUpperCase()}`);
      if (r?.data) leiRecs = [r.data];
    } else if (parseVat(q, dc)) {
      out.inputType = 'VAT';
      const { cc, num } = parseVat(q, dc);
      out.vat = { countryCode: cc, number: num, ...(await vies(cc, num)) };
      leiRecs = (await gleifSearch('entity.registeredAs', num)).filter(
        (d) => (d.attributes.entity.legalAddress?.country || '') === (cc === 'EL' ? 'GR' : cc === 'XI' ? 'GB' : cc),
      );
      if (!leiRecs.length && out.vat?.name) leiRecs = await gleifSearch('entity.legalName', out.vat.name);
    } else {
      out.inputType = 'NAME';
      leiRecs = await gleifSearch('entity.legalName', q, 20);
      if (!leiRecs.length) leiRecs = await gleifSearch('fulltext', q, 20);
      leiRecs = rankByName(leiRecs, q).slice(0, 5);
    }
    if (leiRecs.length) {
      out.lei = slimLei(leiRecs[0]);
      out.otherLeiMatches = leiRecs.slice(1).map(slimLei).map((x) => ({ lei: x.lei, legalName: x.legalName, country: x.legalAddress?.country }));
      if (withParents) {
        out.directParent = await parent(out.lei.lei, 'direct');
        out.ultimateParent = await parent(out.lei.lei, 'ultimate');
      }
    }
    const vatOk = out.vat?.valid === true;
    const leiOk = out.lei?.status === 'ACTIVE' && out.lei?.registrationStatus === 'ISSUED';
    out.verdict = vatOk && leiOk ? 'VERIFIED' : vatOk || leiOk ? 'PARTIAL' : out.vat?.valid === false ? 'VAT_INVALID' : out.lei ? 'LEI_INACTIVE_OR_LAPSED' : 'NOT_FOUND';
    if (out.inputType === 'NAME' && out.lei) out.verdict = leiOk ? 'LEI_MATCH_BY_NAME' : 'LEI_INACTIVE_OR_LAPSED';
    if (out.verdict === 'NOT_FOUND') {
      out.status = 'NOT_FOUND';
      out.message = `No results for ${JSON.stringify(q)} in VIES or GLEIF.`;
    }
    items.push(out);
  }
  return okItems(items);
}

// --- dk-statistics ---
const STAT_API = 'https://api.statbank.dk/v1';
const SRC_DK = 'Kilde/Source: Danmarks Statistik, statistikbanken.dk (CC BY 4.0)';
async function statCall(path, body) {
  for (let i = 0; i < 3; i++) {
    try {
      const r = await fetch(STAT_API + path, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'User-Agent': UA },
        body: JSON.stringify(body), signal: AbortSignal.timeout(30000),
      });
      const t = await r.text();
      if (r.ok) return t;
      if (r.status < 500) throw new Error(`Statbank ${r.status}: ${t.slice(0, 300)}`);
    } catch (e) {
      if (String(e.message).startsWith('Statbank')) throw e;
    }
    await sleep(1500 * (i + 1));
  }
  throw new Error('Statbank unavailable');
}

export async function runDkStatistics(raw) {
  const inp = validateInput(raw);
  const lang = inp.language || 'en';
  const mode = inp.mode || (inp.tableId ? 'data' : 'search');
  if (mode === 'search') {
    inp.search = String(inp.search ?? '').trim();
    if (!inp.search) throw new Error('Provide "search" (keywords) or set mode=data with "tableId".');
    const DA_SYN = { 'arbejdsløshed': 'ledig', 'arbejdsløse': 'ledig', 'arbejdsløs': 'ledig', 'ledighed': 'ledig', 'fødsler': 'fødte', 'dødsfald': 'døde' };
    const words = inp.search.toLowerCase().split(/\s+/).filter(Boolean);
    const daWords = words.map((w) => DA_SYN[w] || w);
    const find = async (lg, ws = words) => {
      const tables = JSON.parse(await statCall('/tables', { lang: lg, format: 'JSON', includeInactive: false }));
      return tables
        .map((t) => ({ t, s: ws.filter((w) => (t.id + ' ' + t.text + ' ' + t.variables.join(' ')).toLowerCase().includes(w)).length }))
        .filter((x) => x.s === ws.length)
        .sort((a, b) => b.t.updated.localeCompare(a.t.updated))
        .slice(0, inp.maxTables || 20);
    };
    let hits = await find(lang);
    if (!inp.language && (!hits.length || /[æøå]/i.test(inp.search))) {
      let da = await find('da');
      if (!da.length && daWords.join() !== words.join()) da = await find('da', daWords);
      if (da.length) {
        const ids = new Set(da.map((x) => x.t.id));
        const en = JSON.parse(await statCall('/tables', { lang, format: 'JSON', includeInactive: false })).filter((t) => ids.has(t.id));
        hits = da.map((x) => ({ t: { ...(en.find((e) => e.id === x.t.id) || x.t), matchedInDanish: true } }));
      }
    }
    const items = [];
    for (const { t } of hits) {
      const info = JSON.parse(await statCall('/tableinfo', { table: t.id, lang, format: 'JSON' }));
      items.push({
        type: 'table', tableId: t.id, title: t.text, unit: t.unit, updated: t.updated,
        firstPeriod: t.firstPeriod, latestPeriod: t.latestPeriod,
        variables: info.variables.map((v) => ({
          code: v.id, label: v.text, isTime: !!v.time, valueCount: v.values.length,
          sampleValues: v.values.slice(0, 8).map((x) => ({ code: x.id, label: x.text })),
        })),
        howToFetch: { mode: 'data', tableId: t.id, filters: Object.fromEntries(info.variables.map((v) => [v.id, v.time ? ['(latest)'] : [v.values[0].id]])) },
        source: SRC_DK,
      });
    }
    if (!items.length) items.push(notFound(inp.search, 'Statistics Denmark table list'));
    return okItems(items);
  }
  const table = String(inp.tableId).toUpperCase();
  const filters = inp.filters || {};
  const info = JSON.parse(await statCall('/tableinfo', { table, lang, format: 'JSON' }));
  const variables = info.variables.map((v) => {
    let vals = filters[v.id] ?? filters[v.id.toLowerCase()];
    if (!vals) vals = v.time ? [v.values.at(-1).id] : [v.values[0].id];
    vals = vals.map((x) => (x === '(latest)' ? v.values.at(-1).id : String(x)));
    if (v.time && inp.lastNPeriods) vals = v.values.slice(-inp.lastNPeriods).map((x) => x.id);
    return { code: v.id, values: vals };
  }).filter((v) => v.values.length);
  const csv = await statCall('/data', { table, format: 'BULK', lang, valuePresentation: 'CodeAndValue', delimiter: 'Semicolon', variables });
  const [head, ...lines] = csv.trim().split(/\r?\n/);
  const cols = head.split(';');
  const max = inp.maxRows || 10000;
  const items = [];
  for (const ln of lines.slice(0, max)) {
    const c = ln.split(';');
    const row = { tableId: table };
    cols.forEach((k, i) => {
      if (k === 'INDHOLD') row.value = c[i] === '..' || c[i] === '' ? null : Number(c[i].replace(',', '.'));
      else row[k] = c[i];
    });
    row.unit = info.unit;
    row.source = SRC_DK;
    items.push(row);
  }
  return okItems(items);
}

// --- scholar-search ---
const strip = (s) => (s || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
async function crossref(q, fromYear) {
  const f = fromYear ? `&filter=from-pub-date:${fromYear}` : '';
  const r = await j(`https://api.crossref.org/works?query.bibliographic=${encodeURIComponent(q)}&rows=50${f}&mailto=mark@dataandbeyond.dk`);
  return (r?.message?.items || []).map((w) => ({
    title: strip(w.title?.[0]), doi: w.DOI?.toLowerCase() || null, year: w.issued?.['date-parts']?.[0]?.[0] || null,
    authors: (w.author || []).map((a) => [a.given, a.family].filter(Boolean).join(' ')).slice(0, 20),
    venue: w['container-title']?.[0] || null, type: w.type, citedByCount: w['is-referenced-by-count'] ?? null,
    url: w.URL, pdfUrl: (w.link || []).find((l) => l['content-type'] === 'application/pdf')?.URL || null,
    license: w.license?.[0]?.URL || null, source: 'crossref',
  }));
}
async function arxiv(q, fromYear) {
  const phrase = q.replace(/"/g, '').trim();
  const xml = await j(
    `https://export.arxiv.org/api/query?search_query=${encodeURIComponent(`ti:"${phrase}"`)}+OR+all:${phrase.split(/\s+/).map(encodeURIComponent).join('+AND+all:')}&start=0&max_results=50&sortBy=relevance`,
    { headers: { Accept: 'application/atom+xml' } },
  );
  if (typeof xml !== 'string') return [];
  const tag = (s, t) => strip((s.match(new RegExp(`<${t}[^>]*>([\\s\\S]*?)</${t}>`)) || [])[1]);
  return xml.split('<entry>').slice(1).map((e) => {
    const id = tag(e, 'id');
    const axId = (id.match(/abs\/([^v]+?)(v\d+)?$/) || [])[1];
    const doi = tag(e, 'arxiv:doi') || (axId ? `10.48550/arxiv.${axId}` : '');
    return {
      title: tag(e, 'title'), doi: doi ? doi.toLowerCase() : null, year: +tag(e, 'published').slice(0, 4) || null,
      authors: [...e.matchAll(/<name>([^<]+)<\/name>/g)].map((m) => m[1]).slice(0, 20),
      venue: 'arXiv', type: 'preprint', citedByCount: null, url: id, pdfUrl: id.replace('/abs/', '/pdf/'),
      abstract: tag(e, 'summary'), license: 'arXiv metadata CC0 1.0', source: 'arxiv',
    };
  }).filter((p) => !fromYear || p.year >= fromYear);
}
async function openalex(q, fromYear) {
  const OA_KEY = process.env.OPENALEX_API_KEY || '';
  if (!OA_KEY) return [];
  const f = fromYear ? `&filter=from_publication_date:${fromYear}-01-01` : '';
  const r = await j(`https://api.openalex.org/works?search=${encodeURIComponent(q)}&per-page=50${f}&select=title,doi,publication_year,authorships,primary_location,type,cited_by_count,id,open_access&api_key=${encodeURIComponent(OA_KEY)}`);
  return (r?.results || []).map((w) => ({
    title: w.title, doi: w.doi ? w.doi.replace('https://doi.org/', '').toLowerCase() : null, year: w.publication_year,
    authors: (w.authorships || []).map((a) => a.author?.display_name).slice(0, 20),
    venue: w.primary_location?.source?.display_name || null, type: w.type, citedByCount: w.cited_by_count,
    url: w.doi || w.id, pdfUrl: w.open_access?.oa_url || null, isOpenAccess: w.open_access?.is_oa ?? null,
    license: 'OpenAlex CC0 1.0', source: 'openalex',
  }));
}

export async function runScholarSearch(raw) {
  const inp = validateInput(raw);
  const queries = (inp.queries || []).map((q) => String(q).trim()).filter(Boolean);
  const max = Math.min(inp.maxResultsPerQuery || 20, 200);
  let sources = inp.sources || ['crossref', 'arxiv', 'openalex'];
  if (!process.env.OPENALEX_API_KEY) sources = sources.filter((x) => x !== 'openalex');
  if (!sources.length) sources = ['crossref', 'arxiv'];
  const fromYear = inp.fromYear || null;
  if (!queries.length) throw new Error('Provide at least one search query in "queries".');
  const fns = { crossref: (q) => crossref(q, fromYear), arxiv: (q) => arxiv(q, fromYear), openalex: (q) => openalex(q, fromYear) };
  const items = [];
  for (const q of queries) {
    const settled = await Promise.allSettled(sources.map((s) => (fns[s] ? fns[s](q) : [])));
    const sourcesFailed = [], warnings = [];
    settled.forEach((r, i) => {
      if (r.status === 'rejected') {
        sourcesFailed.push(sources[i]);
        warnings.push(`${sources[i]} failed: ${r.reason?.message || r.reason}`);
      }
    });
    if (sources.length && sourcesFailed.length === sources.length) {
      throw new Error(`Upstream API failed (all sources: ${sources.join(', ')}): ${warnings.join(' | ')}`);
    }
    const lists = settled.map((r) => (r.status === 'fulfilled' ? r.value : []));
    const seen = new Map();
    for (const p of lists.flat()) {
      const k = p.doi || p.title?.toLowerCase();
      if (!k || !p.title) continue;
      if (seen.has(k)) {
        const o = seen.get(k);
        o.foundIn.push(p.source);
        if ((p.citedByCount || 0) > (o.citedByCount || 0)) o.citedByCount = p.citedByCount;
        for (const [kk, v] of Object.entries(p)) if (o[kk] == null && v != null) o[kk] = v;
      } else seen.set(k, { query: q, ...p, foundIn: [p.source] });
    }
    const nrm = (t) => String(t || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
    const nq = nrm(q), words = nq.split(' ').filter((w) => w.length > 2);
    const score = (p) => {
      const t = nrm(p.title);
      return (t === nq ? 4 : t.includes(nq) ? 3 : 0) + (words.length ? (2 * words.filter((w) => t.includes(w)).length) / words.length : 0)
        + 1.5 * Math.log10((p.citedByCount || 0) + 1) - (p.type === 'book-chapter' || p.type === 'other' ? 2 : 0);
    };
    const ranked = [...seen.values()].filter((p) => p.authors?.length).map((p) => [score(p), p]).sort((a, b) => b[0] - a[0]).map((x) => x[1]);
    if (!ranked.length) items.push(notFound(q, sources.filter((s) => !sourcesFailed.includes(s)).join(' + '), { sourcesFailed, warnings }));
    for (const p of ranked.slice(0, max)) {
      delete p.source;
      p.sourcesFailed = sourcesFailed;
      p.warnings = warnings;
      items.push(p);
    }
  }
  return okItems(items);
}

// --- pubmed ---
export async function runPubmedSearch(raw) {
  const inp = validateInput(raw);
  const queries = (inp.queries || []).filter(Boolean);
  const max = Math.min(inp.maxResultsPerQuery || 20, 1000);
  if (!queries.length) throw new Error('Provide at least one PubMed query in "queries".');
  const keyEnv = process.env.NCBI_API_KEY || inp.ncbiApiKey || '';
  const key = keyEnv ? `&api_key=${encodeURIComponent(keyEnv)}` : '';
  const base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils';
  const gap = keyEnv ? 120 : 400;
  const items = [];
  for (const q of queries) {
    const sort = inp.sort === 'date' ? '&sort=pub_date' : '';
    const s = await j(`${base}/esearch.fcgi?db=pubmed&retmode=json&retmax=${max}&term=${encodeURIComponent(q)}${sort}&tool=open-data-mcp&email=mark@dataandbeyond.dk${key}`);
    const ids = s?.esearchresult?.idlist || [];
    let n = 0;
    for (let i = 0; i < ids.length; i += 100) {
      await sleep(gap);
      const r = await j(`${base}/esummary.fcgi?db=pubmed&retmode=json&id=${ids.slice(i, i + 100).join(',')}&tool=open-data-mcp&email=mark@dataandbeyond.dk${key}`);
      for (const id of ids.slice(i, i + 100)) {
        const a = r?.result?.[id];
        if (!a) continue;
        const aid = (t) => (a.articleids || []).find((x) => x.idtype === t)?.value || null;
        items.push({
          query: q, pmid: id, title: a.title, journal: a.fulljournalname, journalAbbrev: a.source,
          pubDate: a.pubdate, sortPubDate: a.sortpubdate?.slice(0, 10),
          authors: (a.authors || []).map((x) => x.name).slice(0, 25),
          firstAuthor: a.sortfirstauthor || null, lastAuthor: a.lastauthor || null,
          volume: a.volume, issue: a.issue, pages: a.pages, doi: aid('doi'), pmcid: aid('pmc'),
          publicationTypes: a.pubtype, language: a.lang, hasAbstract: (a.attributes || []).includes('Has Abstract'),
          url: `https://pubmed.ncbi.nlm.nih.gov/${id}/`,
          pmcUrl: aid('pmc') ? `https://pmc.ncbi.nlm.nih.gov/articles/${aid('pmc')}/` : null,
          totalMatches: +s.esearchresult.count,
        });
        n++;
      }
    }
    if (!n) items.push(notFound(q, 'PubMed'));
  }
  return okItems(items);
}


// --- eu-tenders ---
export async function runEuTenders(raw) {
  const inp = validateInput(raw);
  const iso2to3 = { AT:'AUT',BE:'BEL',BG:'BGR',CY:'CYP',CZ:'CZE',DE:'DEU',DK:'DNK',EE:'EST',ES:'ESP',FI:'FIN',FR:'FRA',GR:'GRC',EL:'GRC',HR:'HRV',HU:'HUN',IE:'IRL',IT:'ITA',LT:'LTU',LU:'LUX',LV:'LVA',MT:'MLT',NL:'NLD',PL:'POL',PT:'PRT',RO:'ROU',SE:'SWE',SI:'SVN',SK:'SVK',NO:'NOR',IS:'ISL',CH:'CHE',LI:'LIE',UK:'GBR',GB:'GBR' };
  const c3 = (c) => (c.length === 2 ? iso2to3[c.toUpperCase()] : c.length === 3 ? c.toUpperCase() : undefined);
  const parts = [];
  if (inp.keywords) parts.push(`FT~"${String(inp.keywords).replace(/"/g, '')}"`);
  const badC = (inp.countries || []).filter((c) => !c3(String(c).trim()) || !Object.values(iso2to3).includes(c3(String(c).trim())));
  if (badC.length) throw new Error(`Unknown country code: ${badC.join(', ')}. Use ISO 2-letter codes, e.g. DK, DE, FR.`);
  const badCpv = (inp.cpvCodes || []).map(String).map((s) => s.trim()).filter((c) => !/^\d{8}(-\d)?$/.test(c));
  if (badCpv.length) throw new Error(`Invalid CPV code: ${badCpv.join(', ')}.`);
  if (inp.countries?.length) parts.push(`buyer-country IN (${inp.countries.map((c) => c3(String(c).trim())).filter(Boolean).join(' ')})`);
  if (inp.cpvCodes?.length) parts.push(`classification-cpv IN (${inp.cpvCodes.map((c) => String(c).replace(/\D/g, '').slice(0, 8)).join(' ')})`);
  const days = inp.publishedWithinDays ?? 30;
  const from = inp.publishedFrom ? inp.publishedFrom.replace(/-/g, '') : new Date(Date.now() - days * 864e5).toISOString().slice(0, 10).replace(/-/g, '');
  parts.push(`publication-date>=${from}`);
  if (inp.onlyOpenCalls) parts.push('notice-type IN (cn-standard cn-social cn-desg pin-cfc-standard pin-cfc-social qu-sy)');
  const query = inp.rawQuery || parts.join(' AND ');
  const max = Math.min(inp.maxResults || 100, 5000);
  const lang = (inp.language || 'eng').toLowerCase();
  const fields = ['publication-number','notice-title','buyer-name','buyer-country','buyer-city','publication-date','notice-type','procedure-type','contract-nature','classification-cpv','deadline-receipt-tender-date-lot','estimated-value-lot','estimated-value-cur-lot','place-of-performance','total-value','total-value-cur','winner-name'];
  const pick = (o) => { if (!o) return null; if (typeof o === 'string') return o; const v = o[lang] || o.eng || Object.values(o)[0]; return Array.isArray(v) ? v[0] : v; };
  const uniq = (a) => [...new Set((a || []).filter(Boolean))];
  const items = [];
  let n = 0, page = 1;
  while (n < max) {
    const r = await j('https://api.ted.europa.eu/v3/notices/search', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: `${query} SORT BY publication-date DESC`, fields, limit: Math.min(250, max - n), page, scope: 'ACTIVE' }),
    });
    const notices = r?.notices || [];
    if (!notices.length) break;
    for (const x of notices) {
      const id = x['publication-number'];
      const val = uniq(x['estimated-value-lot']).map(Number);
      const cur = uniq(x['estimated-value-cur-lot'])[0] || null;
      items.push({
        publicationNumber: id, title: pick(x['notice-title']), buyerName: pick(x['buyer-name']),
        buyerCountry: uniq(x['buyer-country']).join(','), buyerCity: pick(x['buyer-city']),
        publicationDate: x['publication-date']?.slice(0, 10), noticeType: x['notice-type'],
        procedureType: x['procedure-type'], contractNature: uniq(x['contract-nature']),
        cpvCodes: uniq(x['classification-cpv']), tenderDeadline: uniq(x['deadline-receipt-tender-date-lot']).sort()[0] || null,
        estimatedValue: val.length ? val.reduce((a, b) => a + b, 0) : null, estimatedValueCurrency: cur,
        awardedTotalValue: x['total-value'] ? Number([].concat(x['total-value'])[0]) : null,
        winners: uniq([].concat(pick(x['winner-name']) || [])), placeOfPerformance: uniq(x['place-of-performance']),
        url: `https://ted.europa.eu/en/notice/-/detail/${id}`, pdfUrl: `https://ted.europa.eu/en/notice/${id}/pdf`,
        source: 'TED (Publications Office of the EU), reuse under Commission Decision 2011/833/EU',
      });
      n++;
      if (n >= max) break;
    }
    if (notices.length < 250) break;
    page++;
    await sleep(500);
  }
  if (!items.length) items.push(notFound(inp.rawQuery || inp.keywords || query, 'TED', { tedQuery: query }));
  return okItems(items);
}

// --- france ---
export async function runFranceCompanySearch(raw) {
  const inp = validateInput(raw);
  const queries = (inp.queries || []).map(String).map((s) => s.trim()).filter(Boolean);
  const CAP = 1000;
  const per = Math.min(inp.maxResultsPerQuery || 5, CAP);
  if (!queries.length) throw new Error('Provide "queries": company names, SIREN (9 digits) or SIRET (14 digits).');
  const slim = (c, q) => {
    const s = c.siege || {};
    return {
      query: q, siren: c.siren, siretHeadOffice: s.siret, name: c.nom_complet, legalName: c.nom_raison_sociale, acronym: c.sigle,
      legalFormCode: c.nature_juridique, nafCode: c.activite_principale, section: c.section_activite_principale,
      employeeBand: c.tranche_effectif_salarie, employeeBandYear: c.annee_tranche_effectif_salarie, companyCategory: c.categorie_entreprise,
      createdOn: c.date_creation, closedOn: c.date_fermeture, status: c.etat_administratif === 'A' ? 'ACTIVE' : 'CLOSED',
      establishments: c.nombre_etablissements, openEstablishments: c.nombre_etablissements_ouverts,
      headOffice: { address: s.adresse, postalCode: s.code_postal, city: s.libelle_commune, lat: s.latitude ? +s.latitude : null, lon: s.longitude ? +s.longitude : null },
      vatNumber: c.siren ? `FR${String((12 + 3 * (+c.siren % 97)) % 97).padStart(2, '0')}${c.siren}` : null,
      finances: c.finances || null,
      flags: { isAssociation: !!c.complements?.est_association, isPublicBody: !!c.complements?.est_service_public, isESS: !!c.complements?.est_ess, isRGE: !!c.complements?.est_rge, hasBio: !!c.complements?.est_bio },
      url: `https://annuaire-entreprises.data.gouv.fr/entreprise/${c.siren}`,
      source: "Recherche d'entreprises API (DINUM/INSEE), Licence Ouverte 2.0",
    };
  };
  const items = [];
  for (const q of queries) {
    let n = 0, page = 1, pages = 1;
    while (n < per && page <= pages) {
      const p = new URLSearchParams({ q: /^\d[\d\s]+$/.test(q) ? q.replace(/\s/g, '') : q, per_page: '25', page: String(page) });
      if (inp.postalCode) p.set('code_postal', inp.postalCode);
      if (inp.nafCode) p.set('activite_principale', inp.nafCode);
      if (inp.onlyActive !== false) p.set('etat_administratif', 'A');
      const r = await j(`https://recherche-entreprises.api.gouv.fr/search?${p}`);
      pages = r?.total_pages ?? 1;
      for (const c of r?.results || []) {
        if (String(c.nature_juridique || '').startsWith('1')) continue;
        if (n >= per) break;
        n++;
        items.push(slim(c, q));
      }
      page++;
      await sleep(160);
    }
    if (!n) items.push(notFound(q, "Recherche d'entreprises (France)"));
  }
  return okItems(items);
}

// --- nordic ---
export async function runNordicCompanyRegistry(raw) {
  const inp = validateInput(raw);
  const queries = (inp.queries || []).map(String).map((s) => s.trim()).filter(Boolean);
  const per = Math.min(inp.maxResultsPerQuery || 3, 50);
  const asked = (inp.countries || ['NO', 'FI']).map((c) => String(c).toUpperCase());
  const unsupported = asked.filter((c) => !['NO', 'FI'].includes(c));
  const countries = asked.filter((c) => ['NO', 'FI'].includes(c));
  const why = (c) => (c === 'SE' ? 'Sweden is not supported (Bolagsverket has no free open API for this)' : c === 'DK' ? 'Denmark is not supported (use CVR directly)' : `${c} is not supported`);
  if (unsupported.length && !countries.length) throw new Error(`${unsupported.map(why).join('; ')}. Supported countries: NO, FI.`);
  if (!queries.length) throw new Error('Provide "queries": company names, Norwegian org.nr (9 digits) or Finnish Business ID (1234567-8).');
  const en = (d) => (d || []).find((x) => x.languageCode === '3')?.description || d?.[0]?.description || null;
  function noRec(e, q) {
    const a = e.forretningsadresse || e.postadresse || {};
    return {
      query: q, country: 'NO', registryId: e.organisasjonsnummer,
      vatNumber: e.registrertIMvaregisteret ? `NO${e.organisasjonsnummer}MVA` : null, name: e.navn,
      legalForm: e.organisasjonsform?.kode, legalFormDescription: e.organisasjonsform?.beskrivelse,
      industryCode: e.naeringskode1?.kode, industryDescription: e.naeringskode1?.beskrivelse,
      status: e.konkurs ? 'BANKRUPT' : e.underAvvikling || e.underTvangsavviklingEllerTvangsopplosning ? 'IN_LIQUIDATION' : e.slettedato ? 'DELETED' : 'ACTIVE',
      foundedOn: e.stiftelsesdato || null, registeredOn: e.registreringsdatoEnhetsregisteret || null,
      employees: e.antallAnsatte ?? null, website: e.hjemmeside || null, partOfGroup: !!e.erIKonsern,
      shareCapital: e.kapital ? { amount: e.kapital.belop, currency: e.kapital.valuta || 'NOK' } : null,
      lastAnnualAccountsYear: e.sisteInnsendteAarsregnskap ? +e.sisteInnsendteAarsregnskap : null,
      address: { street: (a.adresse || []).join(', '), postalCode: a.postnummer, city: a.poststed, municipality: a.kommune, country: a.landkode },
      formerNames: (e.historiskeNavn || []).map((h) => h.navn),
      url: `https://virksomhet.brreg.no/nb/oppslag/enheter/${e.organisasjonsnummer}`,
      source: 'Enhetsregisteret, Brønnøysundregistrene (NLOD 2.0)',
    };
  }
  function fiRec(c, q) {
    const a = (c.addresses || []).find((x) => x.type === 1) || c.addresses?.[0] || {};
    const nm = (c.names || []).filter((n) => n.type === '1');
    return {
      query: q, country: 'FI', registryId: c.businessId?.value,
      vatNumber: c.businessId?.value ? `FI${c.businessId.value.replace('-', '')}` : null,
      name: (nm.find((n) => !n.endDate) || nm[0])?.name,
      legalForm: c.companyForms?.find((f) => !f.endDate)?.type || null,
      legalFormDescription: en(c.companyForms?.find((f) => !f.endDate)?.descriptions),
      industryCode: c.mainBusinessLine?.type || null, industryDescription: en(c.mainBusinessLine?.descriptions),
      status: (c.companySituations || []).length ? en(c.companySituations[0].descriptions)?.toUpperCase() : c.status === '2' ? 'ACTIVE' : 'INACTIVE_OR_UNKNOWN',
      foundedOn: c.businessId?.registrationDate || null, registeredOn: c.registrationDate || null,
      employees: null, website: c.website?.url || null, partOfGroup: null, shareCapital: null, lastAnnualAccountsYear: null,
      address: { street: [a.street, a.buildingNumber].filter(Boolean).join(' '), postalCode: a.postCode, city: a.postOffices?.find((p) => p.languageCode === '1')?.city || a.postOffices?.[0]?.city, municipality: null, country: 'FI' },
      formerNames: nm.filter((n) => n.endDate).map((n) => n.name),
      parallelOrAuxNames: (c.names || []).filter((n) => n.type !== '1' && !n.endDate).map((n) => n.name),
      euId: c.euId?.value || null, url: `https://tietopalvelu.ytj.fi/yritys/${c.businessId?.value}`,
      source: 'YTJ open data, Finnish Patent and Registration Office (CC BY 4.0)',
    };
  }
  const LF = /\b(asa|as|sa|ans|da|ba|nuf|oyj|oy|abp|ab|ky|ry|osk|ltd|gmbh)\b\.?/g;
  const nrm = (s) => String(s || '').toLowerCase().replace(/[.,()]/g, ' ').replace(/\s+/g, ' ').trim();
  function rel(name, q) {
    const n = nrm(name), nq = nrm(q), base = n.replace(LF, ' ').replace(/\s+/g, ' ').trim(), words = nq.split(' ');
    const toks = n.split(' ');
    if (!words.every((w) => toks.some((t) => t.startsWith(w)))) return -1;
    if (base === nq || n === nq) return 100;
    if (n.startsWith(nq + ' ')) return 60;
    if ((' ' + n + ' ').includes(' ' + nq + ' ')) return 30;
    return 5;
  }
  const soleNO = new Set(['ENK']);
  const isSoleFI = (c) => /elinkeinonharjoittaja|private trader|sole/i.test(JSON.stringify(c.companyForms || []));
  async function no(q) {
    const id = q.replace(/^NO/i, '').replace(/\s/g, '');
    if (/^\d{9}$/.test(id)) {
      const e = await j(`https://data.brreg.no/enhetsregisteret/api/enheter/${id}`);
      return e && !soleNO.has(e.organisasjonsform?.kode) ? [{ ...noRec(e, q), _score: 100 }] : [];
    }
    const r = await j(`https://data.brreg.no/enhetsregisteret/api/enheter?navn=${encodeURIComponent(q)}&size=100`);
    return (r?._embedded?.enheter || [])
      .filter((e) => !soleNO.has(e.organisasjonsform?.kode))
      .filter((e) => rel(e.navn, q) >= 0)
      .map((e) => [rel(e.navn, q) + (e.slettedato ? -20 : 0) + Math.log10((e.antallAnsatte || 0) + 1), e])
      .sort((a, b) => b[0] - a[0])
      .slice(0, per)
      .map((x) => ({ ...noRec(x[1], q), _score: x[0] }));
  }
  async function fi(q) {
    const id = q.replace(/^FI/i, '').trim();
    const url = /^\d{7}-\d$/.test(id)
      ? `https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=${id}`
      : `https://avoindata.prh.fi/opendata-ytj-api/v3/companies?name=${encodeURIComponent(q)}`;
    const r = await j(url);
    const byId = /^\d{7}-\d$/.test(id);
    return (r?.companies || [])
      .filter((c) => !isSoleFI(c))
      .map((c) => fiRec(c, q))
      .filter((x) => x.name)
      .filter((x) => byId || rel(x.name, q) >= 0)
      .map((x) => [byId ? 100 : rel(x.name, q) + (x.status === 'ACTIVE' ? 1 : -20), x])
      .sort((a, b) => b[0] - a[0])
      .slice(0, per)
      .map((x) => ({ ...x[1], _score: x[0] }));
  }
  const isSE = (q) => /^SE\s*\d{10}(01)?$/i.test(q.replace(/[\s-]/g, '')) || /^\d{6}-\d{4}$/.test(q.trim());
  const items = [];
  for (const q of queries) {
    if (isSE(q)) {
      items.push({ query: q, status: 'NOT_SUPPORTED', message: `${why('SE')}. Supported countries: NO, FI.` });
      continue;
    }
    let cs = countries;
    if (/^NO\s*\d/i.test(q) || /^\d{9}$/.test(q.replace(/\s/g, ''))) cs = ['NO'];
    if (/^FI\s*\d/i.test(q) || /^\d{7}-\d$/.test(q)) cs = ['FI'];
    const recs = (await Promise.all(cs.map((c) => (c === 'NO' ? no(q) : c === 'FI' ? fi(q) : []))))
      .flat()
      .sort((a, b) => b._score - a._score)
      .map(({ _score, ...r }) => r);
    for (const r of recs) items.push(r);
    if (!recs.length) items.push(notFound(q, `company registers (${cs.join(', ')})`));
    await sleep(200);
  }
  return okItems(items);
}

// --- clinical trials ---
export async function runClinicalTrials(raw) {
  const inp = validateInput(raw);
  for (const k of ['condition', 'intervention', 'sponsor', 'searchTerm', 'location']) {
    if (typeof inp[k] === 'string') inp[k] = inp[k].trim();
  }
  const max = Math.min(inp.maxResults || 50, 5000);
  const p = new URLSearchParams({ pageSize: String(Math.min(max, 1000)), format: 'json' });
  if (inp.condition) p.set('query.cond', inp.condition);
  if (inp.intervention) p.set('query.intr', inp.intervention);
  if (inp.sponsor) p.set('query.spons', inp.sponsor);
  if (inp.searchTerm) p.set('query.term', inp.searchTerm);
  if (inp.location) p.set('query.locn', inp.location);
  if (inp.statuses?.length) p.set('filter.overallStatus', inp.statuses.join(','));
  const ids = (inp.nctIds || []).map((x) => String(x).trim().toUpperCase()).filter(Boolean);
  const badIds = ids.filter((x) => !/^NCT\d{8}$/.test(x));
  const goodIds = ids.filter((x) => /^NCT\d{8}$/.test(x));
  const items = [];
  for (const b of badIds) items.push({ nctId: b, error: 'Invalid NCT ID format (expected NCT followed by 8 digits)' });
  if (ids.length && !goodIds.length) return okItems(items);
  if (goodIds.length) p.set('filter.ids', goodIds.join(','));
  if (inp.phases?.length) p.set('aggFilters', 'phase:' + inp.phases.map((x) => String(x).replace(/\D/g, '') || '0').join(' '));
  if (![...p.keys()].some((k) => k.startsWith('query') || k.startsWith('filter'))) {
    throw new Error('Provide at least one of: condition, intervention, sponsor, searchTerm, location, nctIds.');
  }
  let n = 0, token = null;
  const seen = new Set();
  do {
    if (token) p.set('pageToken', token);
    const r = await j(`https://clinicaltrials.gov/api/v2/studies?${p}`);
    if (!r) break;
    for (const s of r.studies || []) {
      const ps = s.protocolSection || {};
      const id = ps.identificationModule || {}, st = ps.statusModule || {}, d = ps.designModule || {}, sp = ps.sponsorCollaboratorsModule || {};
      const locs = ps.contactsLocationsModule?.locations || [];
      const item = {
        nctId: id.nctId, title: id.briefTitle, officialTitle: id.officialTitle, acronym: id.acronym || null,
        overallStatus: st.overallStatus, whyStopped: st.whyStopped || null, phases: d.phases || [], studyType: d.studyType,
        enrollment: d.enrollmentInfo?.count ?? null, allocation: d.designInfo?.allocation || null, primaryPurpose: d.designInfo?.primaryPurpose || null,
        leadSponsor: sp.leadSponsor?.name, leadSponsorClass: sp.leadSponsor?.class,
        collaborators: (sp.collaborators || []).map((c) => c.name),
        conditions: ps.conditionsModule?.conditions || [], keywords: ps.conditionsModule?.keywords || [],
        interventions: (ps.armsInterventionsModule?.interventions || []).map((i) => ({ type: i.type, name: i.name })),
        primaryOutcomes: (ps.outcomesModule?.primaryOutcomes || []).map((o) => o.measure).slice(0, 5),
        briefSummary: ps.descriptionModule?.briefSummary?.slice(0, 1500) || null,
        startDate: st.startDateStruct?.date || null, primaryCompletionDate: st.primaryCompletionDateStruct?.date || null,
        completionDate: st.completionDateStruct?.date || null, firstPosted: st.studyFirstPostDateStruct?.date || null,
        lastUpdated: st.lastUpdatePostDateStruct?.date || null, hasResults: !!s.hasResults,
        countries: [...new Set(locs.map((l) => l.country).filter(Boolean))], siteCount: locs.length,
        minAge: ps.eligibilityModule?.minimumAge || null, maxAge: ps.eligibilityModule?.maximumAge || null, sex: ps.eligibilityModule?.sex || null,
        url: `https://clinicaltrials.gov/study/${id.nctId}`, source: 'ClinicalTrials.gov (U.S. National Library of Medicine)',
      };
      seen.add(item.nctId);
      items.push(item);
      n++;
      if (n >= max) break;
    }
    token = r.nextPageToken;
    await sleep(300);
  } while (token && n < max);
  for (const id of goodIds) if (!seen.has(id) && n < max) items.push(notFound(id, 'ClinicalTrials.gov', { nctId: id }));
  if (!n && !goodIds.length) {
    items.push(notFound([inp.condition, inp.intervention, inp.sponsor, inp.searchTerm, inp.location].filter(Boolean).join(' / '), 'ClinicalTrials.gov'));
  }
  return okItems(items);
}

// --- vin ---
export async function runVinDecoderRecalls(raw) {
  const inp = validateInput(raw);
  const vins = [...new Set((inp.vins || []).map((v) => String(v).trim().toUpperCase()).filter(Boolean))].slice(0, inp.maxItems || 10000);
  if (!vins.length) throw new Error('Provide at least one VIN in "vins".');
  const withRecalls = inp.includeRecalls !== false;
  const recallCache = new Map();
  const valid = (v) => /^[A-HJ-NPR-Z0-9]{11,17}$/.test(v);
  const nz = (v) => (v === '' || v === 'Not Applicable' || v == null ? null : v);
  async function recalls(make, model, year) {
    const k = `${make}|${model}|${year}`;
    if (recallCache.has(k)) return recallCache.get(k);
    const r = await j(`https://api.nhtsa.gov/recalls/recallsByVehicle?make=${encodeURIComponent(make)}&model=${encodeURIComponent(model)}&modelYear=${year}`, { allowStatus: [400] });
    if (r && r.Count == null) throw new Error(`NHTSA Recalls API returned an unexpected answer for ${make} ${model} ${year}`);
    const out = (r?.results || []).map((x) => ({
      campaignNumber: x.NHTSACampaignNumber, reportDate: x.ReportReceivedDate, component: x.Component,
      summary: x.Summary, consequence: x.Consequence, remedy: x.Remedy, parkIt: x.parkIt, parkOutside: x.parkOutSide, overTheAirUpdate: x.overTheAirUpdate,
    }));
    recallCache.set(k, out);
    return out;
  }
  const items = [];
  for (let i = 0; i < vins.length; i += 50) {
    const batch = vins.slice(i, i + 50);
    const ok = batch.filter(valid);
    const r = ok.length
      ? await j('https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesBatch/', {
          method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: `format=json&data=${encodeURIComponent(ok.join(';'))}`,
        })
      : null;
    const byVin = new Map((r?.Results || []).map((x) => [x.VIN?.toUpperCase(), x]));
    for (const v of batch) {
      const d = byVin.get(v);
      if (!d) {
        items.push({ vin: v, valid: false, error: valid(v) ? 'Decode failed' : 'Invalid VIN format' });
        continue;
      }
      if (!nz(d.Make)) {
        items.push(notFound(v, 'NHTSA vPIC', { vin: v, valid: false, decodeWarnings: d.ErrorText || null }));
        continue;
      }
      const errCode = String(d.ErrorCode || '0');
      const make = nz(d.Make), model = nz(d.Model), year = nz(d.ModelYear);
      const item = {
        vin: v, valid: errCode.split(',').every((c) => c.trim() === '0'),
        decodeWarnings: errCode === '0' ? null : d.ErrorText, make, model, modelYear: year ? +year : null,
        trim: nz(d.Trim), series: nz(d.Series), bodyClass: nz(d.BodyClass), vehicleType: nz(d.VehicleType),
        doors: nz(d.Doors) ? +d.Doors : null, driveType: nz(d.DriveType), transmission: nz(d.TransmissionStyle),
        engine: { cylinders: nz(d.EngineCylinders) ? +d.EngineCylinders : null, displacementL: nz(d.DisplacementL) ? +(+d.DisplacementL).toFixed(2) : null, hp: nz(d.EngineHP) ? +d.EngineHP : null, model: nz(d.EngineModel) },
        fuelType: nz(d.FuelTypePrimary), electrification: nz(d.ElectrificationLevel), gvwr: nz(d.GVWR),
        manufacturer: nz(d.Manufacturer), plant: { city: nz(d.PlantCity), country: nz(d.PlantCountry) },
        safety: { abs: nz(d.ABS), esc: nz(d.ESC), frontAirbags: nz(d.AirBagLocFront), sideAirbags: nz(d.AirBagLocSide), adaptiveCruise: nz(d.AdaptiveCruiseControl) },
        recalls: null, recallCount: null, openRecallFlag: null, doNotDrive: null, parkOutside: null, recallCheckUrl: null,
        source: 'NHTSA vPIC + NHTSA Recalls API (U.S. public domain)', modelYearNote: null,
      };
      if (/^.{3}ZZZ/.test(v) || (/^[S-Z]/.test(v) && !model)) {
        item.modelYear = null;
        item.modelYearNote = 'European VIN (ISO 3779): position 10 is not a reliable model-year code outside North America, so modelYear is null and no recall lookup is made.';
      }
      if (withRecalls && make && model && item.modelYear) {
        item.recalls = await recalls(make, model, item.modelYear);
        item.recallCount = item.recalls.length;
        item.openRecallFlag = item.recallCount > 0;
        item.doNotDrive = item.recalls.some((x) => x.parkIt === true);
        item.parkOutside = item.recalls.some((x) => x.parkOutside === true);
        item.recallCheckUrl = `https://www.nhtsa.gov/recalls?vin=${v}`;
        await sleep(150);
      }
      items.push(item);
    }
  }
  return okItems(items);
}

// --- weather ---
export async function runWeatherForecast(raw) {
  const inp = validateInput(raw);
  const locs = (inp.locations || []).filter(Boolean);
  const mode = inp.output || 'daily';
  const days = Math.min(inp.days || 7, 10);
  if (locs.some((l) => typeof l === 'string' && !/[\p{L}\p{N}]/u.test(l))) {
    throw new Error('Each location must contain a place name or "lat,lon" coordinates; separator-only values are not valid.');
  }
  if (!locs.length) throw new Error('Provide "locations": place names ("Copenhagen", "Paris, US") or "lat,lon" coordinates.');
  const SYM = (s) => (s || '').replace(/_(day|night|polartwilight)$/, '');
  const items = [];
  for (const l of locs) {
    let lat, lon, name = String(l), geo = {};
    const m = String(l).match(/^\s*(-?\d+(\.\d+)?)\s*,\s*(-?\d+(\.\d+)?)\s*$/);
    if (m) { lat = +m[1]; lon = +m[3]; }
    else if (l && typeof l === 'object' && l.lat != null) { lat = +l.lat; lon = +l.lon; name = l.name || `${lat},${lon}`; }
    else {
      const hits = await geocode(String(l).trim());
      if (!hits.length) { items.push(notFound(l, 'OpenStreetMap Nominatim (place name)', { location: l })); continue; }
      ({ lat, lon } = hits[0]);
      name = hits[0].name;
      geo = {
        countryCode: hits[0].countryCode,
        geocodedBy: 'OpenStreetMap Nominatim (ODbL, © OpenStreetMap contributors)',
        geocodeAlternatives: hits.slice(1).filter((h, i, a) => h.name !== hits[0].name && a.findIndex((x) => x.name === h.name) === i).slice(0, 5).map((h) => ({ name: h.name, lat: h.lat, lon: h.lon, countryCode: h.countryCode })),
      };
    }
    if (!(Math.abs(lat) <= 90 && Math.abs(lon) <= 180)) {
      items.push({ location: l, error: 'Coordinates out of range (lat -90..90, lon -180..180)' });
      continue;
    }
    const r = await j(`https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=${lat.toFixed(4)}&lon=${lon.toFixed(4)}`);
    const ts = r?.properties?.timeseries;
    if (!ts) { items.push({ location: l, error: 'Forecast unavailable' }); continue; }
    const rows = ts.map((t) => ({
      time: t.time, temperatureC: t.data.instant.details.air_temperature,
      windSpeedMs: t.data.instant.details.wind_speed, windDirectionDeg: t.data.instant.details.wind_from_direction,
      humidityPct: t.data.instant.details.relative_humidity, cloudPct: t.data.instant.details.cloud_area_fraction,
      pressureHpa: t.data.instant.details.air_pressure_at_sea_level,
      precipitationMm: t.data.next_1_hours?.details?.precipitation_amount ?? t.data.next_6_hours?.details?.precipitation_amount ?? null,
      precipPeriodH: t.data.next_1_hours ? 1 : t.data.next_6_hours ? 6 : null,
      symbol: SYM(t.data.next_1_hours?.summary?.symbol_code || t.data.next_6_hours?.summary?.symbol_code),
    }));
    const base = {
      location: l, resolvedName: name, lat, lon, ...geo, timezone: null,
      updatedAt: r.properties.meta.updated_at,
      units: { temperature: '°C', wind: 'm/s', precipitation: 'mm' },
      source: 'MET Norway Locationforecast 2.0 (CC BY 4.0, api.met.no)',
    };
    let item;
    if (mode === 'hourly') item = { ...base, hourly: rows.filter((x) => new Date(x.time) < Date.now() + days * 864e5) };
    else {
      const by = {};
      for (const x of rows) { const d = x.time.slice(0, 10); (by[d] ||= []).push(x); }
      item = {
        ...base,
        daily: Object.entries(by).slice(0, days).map(([date, xs]) => {
          const t = xs.map((x) => x.temperatureC);
          const sy = {};
          xs.forEach((x) => x.symbol && (sy[x.symbol] = (sy[x.symbol] || 0) + 1));
          let p = 0, cover = 0;
          for (const x of xs) {
            const tt = new Date(x.time).getTime();
            if (tt >= cover && x.precipitationMm != null) { p += x.precipitationMm; cover = tt + x.precipPeriodH * 36e5; }
          }
          return {
            date, minTempC: Math.min(...t), maxTempC: Math.max(...t), precipitationMm: +p.toFixed(1),
            maxWindMs: Math.max(...xs.map((x) => x.windSpeedMs)),
            dominantSymbol: Object.entries(sy).sort((a, b) => b[1] - a[1])[0]?.[0] || null,
          };
        }),
      };
    }
    items.push(item);
    await sleep(100);
  }
  return okItems(items);
}
