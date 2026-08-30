# Portfolio Heat

Gate 5 uses the versioned first methodology: position heat is capital at risk to the structural stop divided by portfolio equity; aggregate heat is the sum of existing and proposed risk amounts divided by portfolio equity. Allocation percentage is stored/evaluated separately from heat.

The evaluator accepts a supplied hypothetical projected allocation and risk amount. It calculates no quantity or allocation. Exact maximum heat, stock allocation, sector allocation, and heat-methodology version are required; unresolved values return `INSUFFICIENT_DATA`, never an arbitrary value from a range.

For reconstructed holdings, Phase 6A reuses the same risk concept: quantity multiplied by the absolute difference between eligible current price (or weighted-average reference when price is unavailable) and a persisted structural stop. The engine never invents a stop. Heat coverage records whether every active holding has valid risk inputs; incomplete coverage means total heat is unavailable rather than understated.
