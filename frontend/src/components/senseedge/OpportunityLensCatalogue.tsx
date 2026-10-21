import React, { useMemo, useState } from 'react';

/**
 * Old HSI 35-lens discovery catalogue.
 *
 * Catalogue-only until the canonical backend exposes verified per-lens fit and
 * readiness assessments. The frontend must not infer matches from Watch tags,
 * mock prices, diagnostic presence or the lens name.
 */
const LENS_FAMILIES = [
  {name: 'Technical & Market Structure', ids: ['PRE_BREAKOUT_ACCUMULATION','CONFIRMED_BREAKOUT','BREAKOUT_RETEST','INSTITUTIONAL_ACCUMULATION','SECTOR_ROTATION_LEADER','MARKET_RED_RESILIENCE']},
  {name: 'Growth, Earnings & Fundamental Change', ids: ['EARNINGS_MOMENTUM','EARNINGS_SURPRISE_POST_RESULT_DRIFT','FUNDAMENTAL_INFLECTION','CASH_FLOW_INFLECTION','MARGIN_EXPANSION','CAPACITY_EXPANSION','NEW_PRODUCT_NEW_CUSTOMER_INFLECTION','MARKET_SHARE_GAINER','EXPORT_SCALING']},
  {name: 'Compounders & Quality', ids: ['LONG_TERM_STRUCTURAL_COMPOUNDER','MID_TERM_COMPOUNDER','EARLY_EMERGING_LEADER_SMALL_MIDCAP','GARP','QARP']},
  {name: 'Valuation, Recovery & Balance Sheet', ids: ['DEEP_VALUE_MEAN_REVERSION','RERATING_CANDIDATE','CYCLICAL_RECOVERY','TURNAROUND_RECOVERY','DELEVERAGING']},
  {name: 'Macro, Industry & Strategic Opportunities', ids: ['COMMODITY_UPCYCLE','DOMESTIC_CAPEX_BENEFICIARY','ORDER_BOOK_CAPEX_CYCLE','IMPORT_SUBSTITUTION','POLICY_REGULATORY_BENEFICIARY']},
  {name: 'Events & Special Situations', ids: ['EVENT_CATALYST','SPECIAL_SITUATION','DEMERGER_VALUE_UNLOCK','ASSET_MONETISATION','PROMOTER_MANAGEMENT_TRANSFORMATION']},
] as const;

export const OPPORTUNITY_LENS_COUNT = LENS_FAMILIES.reduce((total, family) => total + family.ids.length, 0);

const friendly = (id: string) => id.replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase());

export function OpportunityLensCatalogue() {
  const [query, setQuery] = useState('');
  const [family, setFamily] = useState('ALL');
  const [selected, setSelected] = useState<string | null>(null);
  const visible = useMemo(() => LENS_FAMILIES.flatMap(group =>
    (family === 'ALL' || group.name === family ? group.ids : [])
      .filter(id => (id + ' ' + group.name).toLowerCase().includes(query.toLowerCase()))
      .map(id => ({id, family: group.name}))
  ), [query, family]);

  const selectedLens = visible.find(lens => lens.id === selected);
  return <section className="se-panel" aria-labelledby="opportunity-lenses-title">
    <header><h2 id="opportunity-lenses-title">Opportunity Lenses · {OPPORTUNITY_LENS_COUNT}</h2><span className="se-pill amber">Catalogue · Not active</span></header>
    <div className="se-table-tools"><p>Thirty-five research perspectives on one HSI database and Shared Brain. This catalogue shows design scope, not verified stock opportunities.</p></div>
    <div className="se-filters">
      <label>Research family <select aria-label="Filter opportunity lens family" value={family} onChange={event => {setFamily(event.target.value); setSelected(null);}}>
        <option value="ALL">All six families</option>
        {LENS_FAMILIES.map(group => <option key={group.name} value={group.name}>{group.name}</option>)}
      </select></label>
      <label>Find lens <input aria-label="Search opportunity lenses" value={query} onChange={event => {setQuery(event.target.value); setSelected(null);}} placeholder="Earnings, breakout, value…"/></label>
    </div>
    <div className="se-table-wrap" tabIndex={0} aria-label="35 opportunity lens catalogue">
      <table><thead><tr><th>Opportunity Lens</th><th>Family</th><th>Data readiness</th><th>Lens fit</th><th>Research</th></tr></thead>
      <tbody>{visible.map(lens => <tr key={lens.id} className={selectedLens?.id===lens.id?'selected':''}>
        <td><strong>{friendly(lens.id)}</strong><small>{lens.id}</small></td>
        <td>{lens.family}</td>
        <td><span className="se-pill amber">Not verified</span></td>
        <td>Not evaluated</td>
        <td><button type="button" className="se-link" onClick={() => setSelected(selected === lens.id ? null : lens.id)} aria-expanded={selected === lens.id}>Details</button></td>
      </tr>)}</tbody></table>
    </div>
    {visible.length === 0 && <div className="se-empty"><strong>No matching lens</strong><p>Change the family or search filter.</p></div>}
    {selectedLens && <div className="se-selected" role="status">
      <h3>{friendly(selectedLens.id)}</h3>
      <p>Family: {selectedLens.family}. Pending canonical D01–D61 input certification, named source evidence, 1D/1W/1M horizon readiness and approved lens-fit policy.</p>
      <p>Backend has not exposed a verified list of matching stocks for this lens. No return, target, confidence or trade decision is inferred.</p>
      <span className="se-pill amber">Research definition only · No broker execution</span>
    </div>}
    <p className="se-footnote">A stock may eventually match multiple lenses, but appears only once in the canonical candidate pool. Missing or stale evidence must stay visible. Current Watch archetype counts are separate from this catalogue.</p>
  </section>;
}
