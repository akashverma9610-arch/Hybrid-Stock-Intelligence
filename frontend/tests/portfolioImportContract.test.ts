import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { parseScreenshotDraft, screenshotReviewRows, reviewRowsAreComplete } from '../src/api/portfolioImportContract.ts';

const fixture = () => ({ import_id: 'synthetic-draft', status: 'DRAFT', holdings: [{
  row_id: 'row-1', instrument_id: 'NSE:INE372A01015', symbol: 'SYNTHETIC', instrument_name: 'Synthetic Company',
  quantity: '10.123456789012345678', average_price: '123.456789012345678', current_price: null,
  extraction_confidence: null, resolution_status: 'MATCHED', field_warnings: [],
}] });

test('exact API snake_case maps once; decimal precision and nulls retained', () => {
  const draft = parseScreenshotDraft(fixture())!;
  assert.equal(draft.importId, 'synthetic-draft');
  assert.equal(draft.holdings[0].quantity, '10.123456789012345678');
  assert.equal(draft.holdings[0].averagePrice, '123.456789012345678');
  assert.equal(draft.holdings[0].currentPrice, null);
  assert.equal(draft.holdings[0].extractionConfidence, null);
  assert.equal(reviewRowsAreComplete(screenshotReviewRows(draft)), true);
});

test('ambiguous and unmatched rows are never silently included or resolved', () => {
  for (const resolution_status of ['AMBIGUOUS', 'UNMATCHED']) {
    const input = fixture(); Object.assign(input.holdings[0], { resolution_status, instrument_id: null });
    const rows = screenshotReviewRows(parseScreenshotDraft(input)!);
    assert.equal(rows[0].include, false); assert.equal(rows[0].instrumentId, null);
    assert.equal(reviewRowsAreComplete(rows), false);
  }
});

test('malformed drafts fail closed rather than coerce to a valid holding', () => {
  for (const patch of [{ quantity: 12 }, { average_price: 'NaN' }, { row_id: '' },
    { instrument_id: null }, { resolution_status: 'GUESSED' }, { field_warnings: null },
    { extraction_confidence: undefined }]) {
    const body = fixture(); Object.assign(body.holdings[0], patch);
    assert.equal(parseScreenshotDraft(body), null);
  }
  assert.equal(parseScreenshotDraft({ ...fixture(), status: 'IMPORTED' }), null);
  assert.equal(parseScreenshotDraft({ ...fixture(), import_id: '' }), null);
  assert.equal(parseScreenshotDraft(null), null);
});

test('duplicate source row identity is rejected', () => {
  const body = fixture(); body.holdings.push({ ...body.holdings[0] });
  assert.equal(parseScreenshotDraft(body), null);
});

test('review rows omit extracted price/confidence and extra source material', () => {
  const body = { ...fixture(), token: 'synthetic-do-not-forward' };
  const rows = screenshotReviewRows(parseScreenshotDraft(body)!);
  assert.deepEqual(Object.keys(rows[0]).sort(), ['averagePrice', 'include', 'instrumentId', 'quantity', 'rowId', 'symbol']);
  assert.ok(!JSON.stringify(rows).includes('synthetic-do-not-forward'));
  rows[0].quantity = '20';
  assert.equal(body.holdings[0].quantity, '10.123456789012345678');
});

test('incomplete/non-positive included rows and duplicate canonical holdings block confirmation', () => {
  const rows = screenshotReviewRows(parseScreenshotDraft(fixture())!);
  for (const patch of [{ quantity: null }, { quantity: '0' }, { quantity: '-1' }, { quantity: 'Infinity' },
    { averagePrice: null }, { averagePrice: '0.00' }, { instrumentId: 'SYNTHETIC' }, { rowId: '' }]) {
    assert.equal(reviewRowsAreComplete([{ ...rows[0], ...patch }]), false);
  }
  assert.equal(reviewRowsAreComplete([...rows, { ...rows[0], rowId: 'row-2' }]), false);
  assert.equal(reviewRowsAreComplete([...rows, { ...rows[0], instrumentId: 'NSE:OTHER' }]), false);
  assert.equal(reviewRowsAreComplete([]), false);
});

test('excluded unresolved row does not fabricate fields or block valid included row', () => {
  const rows = screenshotReviewRows(parseScreenshotDraft(fixture())!);
  rows.push({ rowId: 'unresolved', instrumentId: null, symbol: null, quantity: null, averagePrice: null, include: false });
  assert.equal(reviewRowsAreComplete(rows), true);
});

test('pure contract has no transport, storage, credentials or automatic mode selection', () => {
  const source = readFileSync(new URL('../src/api/portfolioImportContract.ts', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /\b(fetch|localStorage|sessionStorage|XMLHttpRequest)\b|https?:\/\/|new Date|REPLACE|MERGE/);
  const modal = readFileSync(new URL('../src/components/portfolio/PortfolioScreenshotImportModal.tsx', import.meta.url), 'utf8');
  assert.match(modal, /const client = isMockMode \? undefined : importClient/);
  assert.match(modal, /if \(!client \|\| !draft \|\| loading \|\| confirmationUncertain\) return/);
  assert.match(modal, /disabled=\{loading \|\| confirmationUncertain/);
  assert.match(modal, /Confirmation outcome is unknown/);
  assert.doesNotMatch(modal, /Number\(event\.target\.value\)|as any|client\.getPortfolio/);
  const composition = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
  assert.ok(!composition.includes('PortfolioScreenshotImportModal'));
});

test('actual modal renders unavailable without an adapter and in demo mode', async () => {
  const require = createRequire(import.meta.url);
  for (const mockMode of [false, true]) {
    const result = await build({
      stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server';
        import {PortfolioScreenshotImportModal} from './src/components/portfolio/PortfolioScreenshotImportModal';
        const forbidden = () => { throw new Error('must not call a client'); };
        module.exports = renderToStaticMarkup(React.createElement(PortfolioScreenshotImportModal,
          {onClose: forbidden, onConfirmed: forbidden, importClient: ${mockMode ? '{uploadPortfolioScreenshots: forbidden, cancelPortfolioImport: forbidden, confirmPortfolioImport: forbidden}' : 'undefined'}}));`,
        resolveDir: fileURLToPath(new URL('..', import.meta.url)), loader: 'tsx' },
      bundle: true, write: false, platform: 'node', format: 'cjs', external: ['react', 'react-dom/server'],
      plugins: [{ name: 'isolated-data-context', setup(builder) {
        builder.onResolve({ filter: /api\/context$/ }, () => ({ path: 'context', namespace: 'test' }));
        builder.onLoad({ filter: /.*/, namespace: 'test' }, () => ({ contents: `export const useDataClient = () => ({isMockMode: ${mockMode}});` }));
      } }],
    });
    const module = { exports: '' };
    new Function('require', 'module', 'exports', result.outputFiles[0].text)(require, module, module.exports);
    assert.match(module.exports, /Import unavailable: approved portfolio-write integration is not connected/);
    assert.match(module.exports, /type="file" disabled=""/);
    assert.match(module.exports, /<button disabled=""[^>]*>Extract holdings for review<\/button>/);
    assert.ok(!module.exports.includes('Confirm reviewed portfolio (Replace)'));
  }
});
