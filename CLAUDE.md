# Claude Code Guidance — NSE Stock Manager

## Authority and scope

Treat repository code, tests, and `docs/architecture/` as authoritative.
Conversation, memory, and checkpoints are working context only; they cannot
approve an architecture, policy, activation, or deployment change.

This is a private, AI-assisted research and paper-trading system—not a trading
or autonomous-execution system. Default to the smallest, reviewable change.
Do not commit, merge, push, delete, migrate data, contact a provider, or change
application behavior unless the user explicitly requests it.

## Non-negotiable engineering constraints

- Preserve the chain `FACT → DATA → INTERPRETATION → INFERENCE` with source,
  timestamp, provenance, validation, freshness, and explicit `as_of` handling.
- Fail closed: missing, stale, invalid, unproven, or partial data is never a
  neutral value, fabricated fact, or passing result. Never use a silent mock or
  latest-record fallback in API/live or historical work.
- Keep Decision Score, confidence, six gates, portfolio rotation, and execution
  separate. Analytical output must never place orders, activate a strategy, or
  promote/deploy a model.
- Retain immutable/versioned records and avoid rewriting history. Do not claim
  a complete or "best NSE" result from partial universe coverage.
- Preserve public/private boundaries: do not expose rule inventories, weights,
  thresholds, gate IDs, or internal evidence IDs. Do not add secrets to files,
  logs, tests, or frontend code.

Read the relevant primary contract before changing its area:

- `docs/architecture/brain_contract.md` — invariants and boundary rules.
- `docs/architecture/brain_architecture.md` and `docs/ARCHITECTURE.md` —
  architecture and package map.
- `docs/architecture/data_flow.md` — failure propagation and time semantics.
- `docs/architecture/model_governance.md` — human-reviewed governance only.
- `docs/architecture/audit_reproducibility.md` — immutable reconstruction.
- `docs/architecture/versioning_and_change_control.md` — required change flow.

## Working conventions

- First inspect `git status --short`; respect existing work by others.
- Keep changes local to the authorized task. Do not refactor unrelated code.
- For architecture or behavior changes, update the relevant contract/mapping and
  focused tests alongside implementation, following the documented change flow.
- Run focused tests first; use `python -m pytest` for the full suite when the
  requested change and environment make that appropriate. Python 3.12+ is
  required; the development install is `python -m pip install -e ".[dev]"`.
- Treat `data/`, runtime databases, `.env*`, provider credentials, and generated
  reports as local operational material. Do not edit or publish them casually.

## Claude working context

Use `.claude/memory/` only for durable, scoped working notes and
`.claude/checkpoints/` only for resumable task handoffs. Their READMEs define
what belongs there. These files are not governing architecture and must never
override the documents above.
