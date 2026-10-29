const TEMP = /MS_UNAVAILABLE|MS_MAX_CONCURRENT_REQ|GLOBAL_MAX_CONCURRENT_REQ|SERVICE_UNAVAILABLE|TIMEOUT/;

export function makeVies({
  fetchFn = fetch,
  sleep = (ms) => new Promise((s) => setTimeout(s, ms)),
  tries = 4,
  ua = 'open-data-mcp/1.1',
} = {}) {
  return async function vies(cc, num) {
    let reason = '';
    for (let i = 0; i < tries; i++) {
      if (i) await sleep(1000 * 2 ** (i - 1));
      let r, body;
      try {
        r = await fetchFn('https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number', {
          method: 'POST',
          headers: { 'User-Agent': ua, 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ countryCode: cc, vatNumber: num }),
          signal: AbortSignal.timeout(20000),
        });
        body = JSON.parse((await r.text()) || '{}');
      } catch (e) {
        reason = e.name === 'TimeoutError' ? 'timeout after 20 s' : e.message;
        continue;
      }
      if (r.status === 429 || r.status >= 500) {
        reason = `HTTP ${r.status}`;
        continue;
      }
      const errs = JSON.stringify(body.errorWrappers || '');
      if (r.ok && (body.actionSucceed === false || body.errorWrappers)) {
        reason = errs;
        if (TEMP.test(errs)) continue;
        return { checked: false, error: `VIES error: ${errs}` };
      }
      if (!r.ok) return { checked: false, error: `VIES rejected: HTTP ${r.status} ${errs}` };
      return {
        checked: true,
        valid: body.valid,
        name: body.name && body.name !== '---' ? body.name : null,
        address: body.address && body.address !== '---' ? body.address.trim() : null,
        requestDate: body.requestDate,
      };
    }
    return { checked: false, error: `VIES unavailable after ${tries} attempts: ${reason}` };
  };
}
