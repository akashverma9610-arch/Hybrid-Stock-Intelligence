import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {runInNewContext} from 'node:vm';
import {build} from 'esbuild';
import {cashLabel, csvCell, display, filterWatch, sectorCounts} from '../src/components/senseedge/presentation.ts';

const source = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
test('absence is not zero, cash requires explicit known state',()=>{
  assert.equal(display(null),'—'); assert.equal(display(0),'0');
  for(const status of [null,undefined,'UNKNOWN']) assert.equal(cashLabel(status,123),'UNKNOWN');
  assert.equal(cashLabel('KNOWN',null),'UNKNOWN'); assert.equal(cashLabel('KNOWN',0),'0');
});
test('Watch filtering is a non-mutating view, never fuzzy identity resolution or ranking',()=>{
  const rows = [{symbol:'SYNTHETIC',companyName:'Synthetic A',canonicalInstrumentId:'NSE:EXACT_A',archetypes:['PRE_BREAKOUT']},
    {symbol:'SYNTHETIC_B',companyName:'Synthetic B',canonicalInstrumentId:'NSE:EXACT_B',archetypes:['OTHER']}];
  const before=JSON.stringify(rows);
  assert.deepEqual(filterWatch(rows as never,'exact_a','ALL'),[rows[0]]);
  assert.deepEqual(filterWatch(rows as never,'','PRE_BREAKOUT'),[rows[0]]);
  assert.deepEqual(filterWatch(rows as never,'missing','ALL'),[]);
  assert.equal(JSON.stringify(rows),before);
});
test('sector coverage is counts, retaining unclassified; not portfolio value allocation',()=>{
  const rows=[{sector:'Industrials'},{sector:null},{sector:'Industrials'},{sector:'Financials'}];
  assert.deepEqual(sectorCounts(rows as never),[['Industrials',2],['Financials',1],['Unclassified',1]]);
});
test('explicit CSV export escapes quotes, line breaks and spreadsheet formulas',()=>{
  assert.equal(csvCell('a,"b"'),'"a,""b"""'); assert.equal(csvCell(null),'""');
  for(const value of ['=HYPERLINK("bad")','+123','@formula','-formula',' \t=bad']) assert.ok(csvCell(value).startsWith('"\''));
});

async function render(page: string, data: object) {
  const result=await build({stdin:{contents:`import React from 'react';import {renderToStaticMarkup} from 'react-dom/server';
    import {SenseEdgePages} from './src/components/senseedge/SenseEdgePages';
    module.exports=renderToStaticMarkup(React.createElement(SenseEdgePages,{page:${JSON.stringify(page)}}));`,
    resolveDir:fileURLToPath(new URL('..',import.meta.url)),loader:'tsx'},bundle:true,write:false,platform:'node',format:'cjs',external:['react','react-dom/server'],
    plugins:[{name:'isolated-evidence-readers',setup(builder){
      builder.onResolve({filter:/useSenseEdgeEvidence$/},()=>({path:'evidence',namespace:'fixture'}));
      builder.onResolve({filter:/api\/context$/},()=>({path:'context',namespace:'fixture'}));
      builder.onResolve({filter:/context\/NavigationContext$/},()=>({path:'navigation',namespace:'fixture'}));
      builder.onLoad({filter:/.*/,namespace:'fixture'},args=>({contents:args.path==='evidence'?
        `export const useSenseEdgeEvidence=()=>({loading:false,data:${JSON.stringify(data)}});`:
        args.path==='context'?`export const useDataClient=()=>({triggerRefresh:()=>{},isMockMode:false});`:
        `export const useNavigation=()=>({navigate:()=>{}});`}));
    }}]});
  const module={exports:''};new Function('require','module','exports',result.outputFiles[0].text)(createRequire(import.meta.url),module,module.exports);
  return module.exports;
}
const empty={watch:null,holdings:null,portfolio:null,news:null,market:null};
test('actual pages render unavailable states, no reference-image fabricated numbers or user',async()=>{
  for(const page of ['home','opportunities','portfolio','signals']) {
    const html=await render(page,empty);
    assert.doesNotMatch(html,/Rohan Mehta|42 opportunities|76%|\+40%|Buy Signal Triggered/);
    assert.match(html,/unavailable|Unavailable|UNKNOWN/);
    if(page==='portfolio') {assert.match(html,/UNKNOWN/);assert.doesNotMatch(html,/Good.*78\/100/);}
    if(page==='signals') {assert.match(html,/WATCH_ONLY \/ NON_EXECUTABLE/);assert.match(html,/No bulk live-signal list/);}
    if(page==='opportunities') assert.match(html,/disabled=""[^>]*>.*?Export view/);
  }
});
test('retained stale envelope is visible; missing cash is not replaced with provider fallback amount',async()=>{
  const html=await render('portfolio',{...empty,portfolio:{status:'PARTIAL',freshness:'STALE',timestamp:'2026-01-01T00:00:00Z',
    warnings:['SYNTHETIC_INCOMPLETE_EVIDENCE'],data:{currentValue:null,investedValue:null,totalPnL:null,cashStatus:'UNKNOWN',cashAvailable:987654}}});
  assert.match(html,/STALE/);assert.match(html,/SYNTHETIC_INCOMPLETE_EVIDENCE/);assert.match(html,/UNKNOWN/);assert.doesNotMatch(html,/987654/);
});
test('canonical Watch row renders exact state, blockers and fingerprint without adding prices or ratings',async()=>{
  const row={watchId:'synthetic-watch',canonicalInstrumentId:'NSE:SYNTHETIC',symbol:'SYNTHETIC',companyName:'Synthetic Test Company',
    archetypes:['PRE_BREAKOUT'],sector:'Industrials',evidenceSufficiency:'INSUFFICIENT_DATA',setupState:'UNAVAILABLE',watchAsOf:'2026-01-01T00:00:00Z',
    status:'BLOCKED',policyIdentity:'synthetic-policy-v1',decisionScoreStatus:'UNSCORED',sixGatesState:'NOT_EVALUATED',blockerCodes:['SYNTHETIC_SOURCE_BLOCKER'],fingerprint:'synthetic-fingerprint'};
  const html=await render('opportunities',{...empty,watch:{status:'PARTIAL',freshness:'STALE',timestamp:null,data:{watchAsOf:row.watchAsOf,
    watchCandidateCount:1,evidenceReadyCount:0,validSetupCount:0,sixGatesEvaluatedCount:0,archetypeCounts:[['PRE_BREAKOUT',1]],records:[row]}}});
  for(const value of ['SYNTHETIC','NSE:SYNTHETIC','UNSCORED','NOT EVALUATED','SYNTHETIC_SOURCE_BLOCKER','synthetic-fingerprint']) assert.ok(html.includes(value));
  assert.doesNotMatch(html,/Entry Zone|Potential Return|HSI Confidence|Buy Signal/);
  assert.match(html,/Response metadata:/); assert.match(html,/not evidence as-of/);
});
test('new pages consume existing read clients and never legacy actionable signal feed',()=>{
  const hook=source('src/components/senseedge/useSenseEdgeEvidence.ts');
  assert.deepEqual([...hook.matchAll(/client\.(\w+)\(/g)].map(m=>m[1]),['getMarketWideWatch','getPortfolioRuntimeHoldings','getPortfolioSummary','getNews','getMarketState']);
  const pages=source('src/components/senseedge/SenseEdgePages.tsx');
  assert.doesNotMatch(hook+pages,/getSignals\(|confirmPortfolio|uploadPortfolio|new Date\(|localStorage|sessionStorage|fetch\(/);
  assert.match(pages,/<P1LifecyclePanel key=\{instrument\}/);
  assert.match(source('src/App.tsx'),/if \(isDev\) return <AppShell>/);
  assert.match(source('src/context/NavigationContext.tsx'),/currentRoute: 'signals'/);
});

function worker() {
  const handlers:Record<string,(e:object)=>void>={};const fetched:string[]=[];const cached:string[]=[];let fail=false;
  const cache={addAll:async(paths:string[])=>{cached.push(...paths);},match:async(path:string)=>`public:${path}`};
  runInNewContext(source('public/senseedge-sw.js'),{URL,self:{location:{origin:'https://synthetic.invalid'},addEventListener:(name:string,handler:(e:object)=>void)=>{handlers[name]=handler;}},
    caches:{open:async()=>cache,keys:async()=>['unrelated-cache','senseedge-public-offline-v1'],delete:async()=>true},
    fetch:async(request:{url:string})=>{fetched.push(request.url);if(fail)throw new Error('offline');return 'network';}});
  return {handlers,fetched,cached,setOffline:()=>{fail=true;}};
}
test('PWA installation caches only two public fallback assets',async()=>{
  const w=worker();let task:Promise<unknown>;w.handlers.install({waitUntil:(p:Promise<unknown>)=>{task=p;}});await task!;
  assert.deepEqual(w.cached,['/offline.html','/senseedge-icon.svg']);
});
test('service worker never intercepts API, cross-origin, POST or credential query requests',()=>{
  const w=worker();
  for(const [url,method,mode] of [['https://synthetic.invalid/api/v1/portfolio','GET','cors'],['http://127.0.0.1:8000/api/v1/p1-signals/lifecycle','GET','cors'],['https://synthetic.invalid/','POST','navigate'],['https://synthetic.invalid/?private=value','GET','navigate']]) {
    w.handlers.fetch({request:{url,method,mode},respondWith:()=>assert.fail('private request intercepted')});
  }
  assert.deepEqual(w.fetched,[]);assert.deepEqual(w.cached,[]);
});
test('offline navigation yields public fallback, not last private page or financial snapshot',async()=>{
  const w=worker();w.setOffline();let response:Promise<string>;
  w.handlers.fetch({request:{url:'https://synthetic.invalid/',method:'GET',mode:'navigate'},respondWith:(p:Promise<string>)=>{response=p;}});
  assert.equal(await response!,'public:/offline.html');assert.deepEqual(w.cached,[]);
  assert.doesNotMatch(source('public/senseedge-sw.js'),/cache\.put|indexedDB|localStorage|Authorization|token=/);
});
test('manifest assets exist and secure production-only registration is independent of credentials',()=>{
  const manifest=JSON.parse(source('public/manifest.webmanifest'));
  assert.equal(manifest.display,'standalone'); assert.equal(manifest.scope,'/');
  for(const icon of manifest.icons) assert.ok(source(`public${icon.src}`).length);
  assert.match(source('src/pwa.ts'),/!production \|\| !window.isSecureContext/);
  assert.match(source('src/pwa.ts'),/updateViaCache: 'none'/);
  assert.match(source('public/offline.html'),/not cached for offline use/);
});
