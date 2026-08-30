# Macro and Sector Transmission

`MacroState` retains independent rates, liquidity, inflation, growth, fiscal, INR, FII-flow, and commodity-specific states. `EconomicRegime` is descriptive, not a numeric compression. Macro revisions are eligible only after their publication/availability time; a historical run cannot consume a later vintage.

`SectorSensitivityProfile` holds driver direction, magnitude category, lag, conditions, confidence, provenance, and evidence. `SectorEconomicImpact` maps the exact macro component through that profile. The same macro state can produce different sector impacts. Existing price/RS sector logic is not overwritten; economic context is additional evidence only.

Credit, rural, power, global, commodity, inventory, capacity, and policy implementation paths remain profile/evidence dependent. A policy announcement is not tender, order, disbursement, project execution, or company revenue.
