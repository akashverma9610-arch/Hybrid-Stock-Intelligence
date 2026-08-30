# Canonical Execution Gate Definitions

Registry version: `execution-gate-registry-v1`. Phase 5B implements an analytical, non-ordering eligibility engine with versioned configuration and immutable records.

1. **Net Friction & Tax Hurdle** — candidate normally exceeds the weakest holding by +0.70 to +1.00 Decision Score points and justifies applicable costs, slippage, taxes, and friction. Tax/statutory costs are not permanently hard-coded facts.
2. **Capital Velocity / Time Stop** — approximately 10–15 trading sessions without meaningful >1 ATR expansion may receive a -0.5 Decision Score penalty and rotation-priority review. Exact values are versioned.
3. **Surveillance & Circuit Filter** — requires fresh authoritative ASM/GSM/surveillance and circuit data. Intended disqualification covers ASM Stage 2+ / GSM and restrictive 5% circuits, subject only to an explicitly approved verified exception.
4. **Tranche Scaling & De-Risking** — intended policy: 50% initial tranche; 33–50% partial profit around T1; remaining stop may move to breakeven subject to structural/liquidity conditions.
5. **Portfolio Heat & Factor Cap** — intended limits: portfolio heat <=6%, single-stock <=25–30%, sector <=35%. Ranges must be resolved before production eligibility.
6. **Five-Trading-Day Pre-Earnings Blackout** — no fresh entries within five trading sessions before scheduled earnings; existing positions may still be risk-managed.

Every gate has explicit required inputs and treats insufficient data as blocking eligibility. Decision Score measures attractiveness; execution gates measure permission and are never combined into a hidden score. No gate creates a portfolio rotation, signal, size, order, broker instruction, or trading action.
