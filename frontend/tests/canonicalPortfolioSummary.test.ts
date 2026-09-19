import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {parseCanonicalPortfolioSummary,readCanonicalPortfolioSummary} from '../src/api/canonicalPortfolioSummary.ts';
const fixture=()=>({portfolio_id:'synthetic-portfolio',as_of:'2026-01-01T00:00:00+00:00',invested_value:'123456.123456789012345678',
  marked_value:'130001.123456789012345678',unrealized_pnl:'6545.000000000000000000',cash:null,cash_status:'UNKNOWN',holding_count:5,data_status:'PARTIAL',warnings:['CASH_UNKNOWN']});
test('canonical marked_value and unrealized_pnl map exactly without decimal coercion or total-return claim',()=>{
  const d=parseCanonicalPortfolioSummary(fixture())!;
  assert.equal(d.currentValue,fixture().marked_value);assert.equal(d.unrealizedPnL,fixture().unrealized_pnl);
  assert.equal(d.investedValue,fixture().invested_value);assert.equal(d.cashStatus,'UNKNOWN');assert.equal(d.cashAvailable,null);
  assert.ok(!('totalPnL' in d));assert.ok(!('portfolioRiskLevel' in d));
});
test('null canonical mark cannot fall back to an unrelated alias',()=>{
  assert.equal(parseCanonicalPortfolioSummary({...fixture(),marked_value:null,currentValue:'999'})?.currentValue,null);
});
test('malformed, missing, contradictory cash and precision-losing numeric payloads reject',()=>{
  for(const patch of [{cash:'0'},{cash_status:'KNOWN',cash:null},{marked_value:130001},{invested_value:'NaN'},
    {unrealized_pnl:undefined},{as_of:'2026-01-01T00:00:00'},{warnings:'none'},{holding_count:-1},{holding_count:1.5},
    {data_status:'FABRICATED'},{data_status:['COMPLETE']},{cash_status:['UNKNOWN']}]) {
    assert.equal(parseCanonicalPortfolioSummary({...fixture(),...patch}),null);
  }
  assert.equal(parseCanonicalPortfolioSummary({...fixture(),cash_status:'KNOWN',cash:'0'})?.cashAvailable,'0');
});
test('unknown extra fields are not forwarded and source warnings survive',()=>{
  const result=parseCanonicalPortfolioSummary({...fixture(),access_token:'synthetic-must-not-forward'})!;
  assert.ok(!JSON.stringify(result).includes('synthetic-must-not-forward'));assert.deepEqual(result.warnings,['CASH_UNKNOWN']);
});
test('real client uses exact GET, no route fallback, no-store and unknown freshness at canonical as-of',async()=>{
  const output=await build({stdin:{contents:`export {readCanonicalPortfolioSummary} from './src/api/canonicalPortfolioSummary';`,resolveDir:fileURLToPath(new URL('..',import.meta.url)),loader:'ts'},bundle:true,write:false,platform:'node',format:'cjs'});
  const calls:Array<[string,RequestInit]>=[];
  const module={exports:{} as {readCanonicalPortfolioSummary:(origin:string)=>Promise<unknown>}};
  const fakeFetch=async(url:URL,options:RequestInit)=>{calls.push([String(url),options]);return new Response(JSON.stringify(fixture()),{status:200});};
  new Function('require','module','exports','fetch',output.outputFiles[0].text)(createRequire(import.meta.url),module,module.exports,fakeFetch);
  const result=await module.exports.readCanonicalPortfolioSummary('http://127.0.0.1:8000') as {freshness:string;timestamp:string;status:string;data:unknown};
  assert.equal(calls.length,1);assert.equal(calls[0][0],'http://127.0.0.1:8000/api/v1/portfolio/summary');
  assert.equal(calls[0][1].cache,'no-store');assert.equal(calls[0][1].redirect,'error');
  assert.equal(result.freshness,'UNKNOWN');assert.equal(result.timestamp,fixture().as_of);assert.equal(result.status,'PARTIAL');
});
test('consumer orchestration never promotes generic HTTP LIVE/now metadata into retained source freshness',()=>{
  const hook=readFileSync(new URL('../src/components/senseedge/useSenseEdgeEvidence.ts',import.meta.url),'utf8');
  assert.match(hook,/freshness:response.freshness === 'STALE' \? 'STALE' : 'UNKNOWN', timestamp:asOf/);
  assert.match(hook,/watch\.data\?\.watchAsOf/);
  assert.match(hook,/readCanonicalPortfolioSummary\(apiBaseUrl,controller.signal\)/);
  assert.match(hook,/isMockMode \? Promise.resolve/);assert.match(hook,/controller.abort\(\)/);
  assert.doesNotMatch(hook,/new Date\(|setInterval|\.submit\(|\.refreshHistorical/);
});

test('native insufficient-data state stays degraded, never ready',async(t)=>{
  t.mock.method(globalThis,'fetch',async()=>new Response(JSON.stringify({...fixture(),data_status:'INSUFFICIENT_DATA'})));
  const r=await readCanonicalPortfolioSummary('http://localhost:8000');
  assert.equal(r.status,'DEGRADED');assert.equal(r.data?.dataStatus,'INSUFFICIENT_DATA');
});

test('unsafe origins and pre-aborted requests make no request',async(t)=>{
  let calls=0;t.mock.method(globalThis,'fetch',async()=>{calls++;throw new Error('must not run');});
  for(const origin of ['http://public.example','https://user:secret@example.com','https://example.com/?token=x',
    'https://example.com/other','file:///private','not-a-url']) {
    assert.equal((await readCanonicalPortfolioSummary(origin)).message,'INVALID_BACKEND_ORIGIN');
  }
  const c=new AbortController();c.abort();
  assert.equal((await readCanonicalPortfolioSummary('http://localhost:8000',c.signal)).message,'REQUEST_CANCELLED');
  assert.equal(calls,0);
});

test('HTTP, malformed payload and transport failures never leak body/exception or fall back',async(t)=>{
  let calls=0;
  for(const response of [new Response('synthetic-private-error',{status:503}),new Response('not json'),
    new Response(JSON.stringify({secret:'synthetic-private-error'}))]) {
    const mock=t.mock.method(globalThis,'fetch',async()=>{calls++;return response;});
    const r=await readCanonicalPortfolioSummary('http://localhost:8000');
    assert.equal(r.status,'UNAVAILABLE');assert.equal(r.data,null);assert.equal(r.timestamp,null);
    assert.ok(!JSON.stringify(r).includes('synthetic-private-error'));mock.mock.restore();
  }
  assert.equal(calls,3);
  t.mock.method(globalThis,'fetch',async()=>{throw new Error('synthetic-private-error');});
  assert.equal((await readCanonicalPortfolioSummary('http://localhost:8000')).message,'PORTFOLIO_TRANSPORT_OR_RESPONSE_UNAVAILABLE');
});

test('abort cleanup and six-second timeout retain distinct safe outcomes',async(t)=>{
  t.mock.timers.enable({apis:['setTimeout']});
  t.mock.method(globalThis,'fetch',async(_url:URL,options:RequestInit)=>new Promise<Response>((_resolve,reject)=>{
    options.signal?.addEventListener('abort',()=>reject(new Error('safe')),{once:true});
  }));
  const c=new AbortController();const pending=readCanonicalPortfolioSummary('http://localhost:8000',c.signal);
  c.abort();assert.equal((await pending).message,'REQUEST_CANCELLED');
  const timed=readCanonicalPortfolioSummary('http://localhost:8000');
  t.mock.timers.tick(6000);assert.equal((await timed).message,'PORTFOLIO_QUERY_TIMEOUT');
});
