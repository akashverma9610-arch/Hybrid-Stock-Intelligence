# HSI Agent V1 Lyzr connection and master thesis

Baseline: `d68c4a8f94880711f7597e03f81897b5c47ab149` on `main`.

Status: `CONFIGURATION_READY / PUBLIC_HTTPS_INGRESS_REQUIRED / CREDENTIALS_REQUIRED / NOT_YET_CONNECTED`.
Decision B: `HSI_LYZR_AGENT_CONFIGURATION_READY_INGRESS_OR_CREDENTIAL_BLOCKED`.

HSI is the product and hybrid analyst; its Python backend remains the
deterministic financial-intelligence/tool layer. Lyzr is the initial hosted
agent platform, not another Brain or a source of financial truth. This slice
does not change Core V1, policies, market-data/runtime providers, database,
API routes, UI or broker authority.

## Portable package

| File | Role |
| --- | --- |
| [`config/hsi_agent_v1_master_thesis.md`](../../config/hsi_agent_v1_master_thesis.md) | Canonical concise reasoning, evidence, safety and intent-routing instructions. It is included in the created Agent instructions; no Knowledge Base is required for V1. |
| [`config/hsi_agent_v1_acceptance_prompts.json`](../../config/hsi_agent_v1_acceptance_prompts.json) | Five portable acceptance prompts: deep analysis, market opportunities, setup, portfolio and comparison. They constrain expected and forbidden tool use. |
| [`scripts/lyzr_bootstrap_hsi_agent_v1.py`](../../scripts/lyzr_bootstrap_hsi_agent_v1.py) | Standard-library, explicit `--create` integration helper. It imports no HSI runtime module and contains no secret or configured identifier. |

The master thesis preserves one canonical Brain, `FACT → DATA →
INTERPRETATION → INFERENCE`, partial/missing evidence, cost discipline,
portfolio comparison, stored-only setup limitations, structured output and the
fixed `RESEARCH_READ_ONLY / WATCH_ONLY / NON_EXECUTABLE` boundary. It does not
turn a candidate, score, gate reference or setup field into BUY/SELL/ROTATE
authority.

## Current Lyzr integration contract

The bootstrap downloads the existing tool-only FastAPI document from exactly
`<HSI_PUBLIC_BASE_URL>/hsi/v1/openapi.json`; it does not maintain or accept a
handwritten API definition. Before cloud registration it requires exactly the
eight existing protected operations and their `HSIAgentKey` security scheme:

`hsi_get_capabilities`, `hsi_scan_market`, `hsi_run_diagnostics`,
`hsi_get_stock_intelligence`, `hsi_get_market_context`,
`hsi_get_news_catalysts`, `hsi_get_portfolio_state`, and `hsi_get_setup`.

It replaces only the downloaded schema `servers` value with the validated
public origin plus `/hsi/v1`. The Lyzr OpenAPI Tool request receives that native
schema and one default `Authorization: Bearer …` header sourced exclusively
from `HSI_AGENT_API_KEY`; no other HSI routes are in the imported document.
Description enhancement is disabled, so no extra OpenAI credential is sent.

Current official Lyzr documentation describes `POST /v3/tools/` with an OpenAPI
schema/default headers and `x-api-key` authentication, and returns tool IDs;
it describes `POST /v3/agents/` with an account-configured provider/model and
LLM credential identifier. Agent chat is available as `POST /v3/agent/{id}/chat`.
See [OpenAPI Tool API](https://docs.lyzr.ai/agent-apis/tools/Create%20OpenAPI%20Tool%20Endpoint),
[Agent creation API](https://docs.lyzr.ai/api-docs/agents/Create%20Agent), and
[Agent concepts](https://docs.lyzr.ai/enterprise/get-started/concepts/agents).

The account-specific values are intentionally not guessed. `LYZR_PROVIDER_ID`,
`LYZR_MODEL` and `LYZR_LLM_CREDENTIAL_ID` must name a provider/model/credential
that actually exists in the selected Lyzr workspace. The bootstrap uses a low
temperature (`0.2`), no description enhancement, no Knowledge Base and no
search tool. Knowledge Base ingestion is deferred; if later approved it should
start only with curated thesis/interpretation/funnel/portfolio/setup material,
not the full architecture/audit corpus.

## Required local configuration and ingress

Configure these values in the local secret manager or runtime environment,
never in repository files, prompts, URLs or commands copied into source:

- `LYZR_API_KEY`: Lyzr workspace API key.
- `HSI_AGENT_API_KEY`: existing Agent tool Bearer secret, also configured in
  the served HSI process.
- `HSI_PUBLIC_BASE_URL`: origin only, e.g. `https://agent.example.com`; must be
  public HTTPS and contain no path/query/fragment/user info/loopback/private
  address.
- `LYZR_LLM_CREDENTIAL_ID`, `LYZR_PROVIDER_ID`, `LYZR_MODEL`: already-provisioned
  Lyzr workspace values.

The script rejects missing values, plaintext HTTP, localhost, `.local` and
non-global IP origins. It has no default URL, model or credential ID. `--create`
is required for remote mutation; without it the script only validates local
configuration. It suppresses response bodies and exception details so keys,
authorization headers and credential values are never printed.

Public ingress is not configured on this host. A future approved ingress must
terminate TLS and forward **only** `/hsi/v1` to loopback HSI, rejecting all
other routes. It must not expose SQLite, filesystem, admin/operator APIs,
broker/order paths or a general proxy. No router forwarding, CORS change,
tunnel account, firewall rule or backend public bind was created here.

## Safe activation and acceptance

After an operator configures the six environment values and a restricted public
HTTPS ingress, run from `D:\nse-stock-manager`:

```powershell
python scripts/lyzr_bootstrap_hsi_agent_v1.py --create
```

Store returned agent/tool IDs only in the approved local integration state;
they are not committed. Then run the five acceptance prompts in the Lyzr
playground/API, observing tool traces. The expected discipline is: no market
scan for one-stock/setup/compare requests; one shared scan for opportunities;
no default diagnostics for every portfolio holding; blocked T2/extended/horizon
remain unavailable; no automatic sell/rotation; and no claim of live whole-NSE,
strict historical PIT, fresh unprovided news or broker execution.

This slice does not create the Agent because required environment values and
public ingress are absent. Thus no Agent ID, tool-set ID, provider/model, tool
connection or live workflow proof exists yet. There is no Knowledge Base and no
external search attachment. The local acceptance suite is fixture/contract
proof only.

Exactly one next continuation after live connection evidence is:
`HSI_AGENT_V1_REAL_USER_WORKFLOW_TUNING_AND_FRESH_SEARCH_V1`. It is not started.
