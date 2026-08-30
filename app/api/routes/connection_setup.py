"""Tiny server-rendered, local/private Kotak Neo setup page."""

from html import escape

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.dependencies import get_api_settings, get_connection_service
from app.api.errors import APIRequestError
from app.api.settings import APISettings
from app.connections.service import ProviderConnectionService


router = APIRouter(include_in_schema=False)


@router.get("/setup/kotak-neo", response_class=HTMLResponse)
def kotak_setup_page(
    settings: APISettings = Depends(get_api_settings),
    service: ProviderConnectionService = Depends(get_connection_service),
) -> HTMLResponse:
    if not settings.connection_management_available:
        raise APIRequestError(status_code=403, code="CONNECTION_MANAGEMENT_DISABLED", message="Connection management is limited to local/private deployments.")
    profile = service.kotak_profile()
    return HTMLResponse(_page(profile.status.value, dict(profile.credential_fields_configured)))


def _page(status: str, configured: dict[str, bool]) -> str:
    safe_status = escape(status)
    saved = " ".join(f'<span>{escape(field)}: {"SAVED" if present else "NOT SET"}</span>' for field, present in configured.items())
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kotak Neo Connection</title>
<style>body{{font-family:system-ui,sans-serif;max-width:34rem;margin:3rem auto;padding:0 1rem}} label,input,button{{display:block;width:100%;box-sizing:border-box}} input,button{{margin:.5rem 0 1rem;padding:.65rem}} button{{cursor:pointer}} #status{{white-space:pre-wrap;padding:1rem;background:#f4f4f4;border-radius:.25rem}}</style>
</head><body>
<h1>Kotak Neo Connection</h1>
<p>This local/private page stores only the Trade API token and optional session credentials in the operating-system credential store. Saved values are never displayed. A current authenticator TOTP is never stored.</p>
<h2>Market Data</h2>
<label for="tradeapi-access-token">Trade API Access Token:</label>
<input id="tradeapi-access-token" name="tradeapi_access_token" type="password" autocomplete="off" required>
<p>Token generated in Neo → More → Trade API → Your Application.</p>
<label for="test-symbol">Optional NSE test symbol:</label>
<input id="test-symbol" name="test_symbol" type="text" autocomplete="off" placeholder="Uses deterministic local symbol when blank">
<button id="save" type="button">Save Credentials</button>
<button id="test-market-data" type="button">Test Market Data</button>
<h2>Authenticated Session</h2>
<label for="mobile-number">Mobile Number:</label>
<input id="mobile-number" name="mobile_number" type="tel" autocomplete="off" required>
<label for="ucc">UCC / Client Code:</label>
<input id="ucc" name="ucc" type="text" autocomplete="off" required>
<label for="mpin">MPIN:</label>
<input id="mpin" name="mpin" type="password" autocomplete="off" required>
<label for="current-totp">Current Authenticator TOTP:</label>
<input id="current-totp" name="current_totp" type="password" inputmode="numeric" pattern="[0-9]{{6}}" autocomplete="one-time-code">
<p id="configured" aria-label="Saved credential fields">{saved}</p>
<button id="test-session" type="button">Test Session</button>
<button id="clear" type="button">Clear Kotak Credentials</button>
<h2>Connection Status</h2><div id="status" aria-live="polite">{safe_status}</div>
<script>
const statusBox = document.getElementById('status');
const fields = ['tradeapi_access_token', 'mobile_number', 'ucc', 'mpin'];
const input = (field) => document.querySelector(`[name="${{field}}"]`);
const clearInputs = () => fields.forEach((field) => {{ input(field).value = ''; }});
const statusState = {{marketDataStatus: null, sessionStatus: null}};
function render(result) {{
  const displayStatus = result.status === 'CONNECTED' || result.status === 'NOT_CONFIGURED' ? result.status : (result.error_code ? 'ERROR' : (result.status || 'ERROR'));
  const lines = [displayStatus];
  if (result.session_read_access) lines.push('Authentication: ' + (result.session_read_access === 'AVAILABLE' ? 'PASS' : result.session_read_access));
  if (result.quote_access) lines.push('Quote access: ' + (result.quote_access === 'AVAILABLE' ? 'PASS' : result.quote_access));
  if (result.instrument_resolution) lines.push('Instrument resolution: ' + result.instrument_resolution);
  if (result.canonical_normalization) lines.push('Normalization: ' + result.canonical_normalization);
  if (result.test_symbol) lines.push('Symbol: ' + result.test_symbol);
  if (result.freshness) lines.push('Freshness: ' + result.freshness);
  if (result.error_code) lines.push('Error: ' + result.error_code);
  if (result.message) lines.push(result.message);
  statusBox.textContent = lines.join('\\n');
}}
function showMarketData(result) {{
  // A new quote-only result must never display a stale Session error.
  statusState.sessionStatus = null;
  statusState.marketDataStatus = result;
  render(result);
}}
function showSession(result) {{
  statusState.sessionStatus = result;
  render(result);
}}
async function request(url, options) {{
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw body.error || {{code:'CONNECTION_ERROR', message:'Connection request failed.'}};
  return body;
}}
async function saveCredentials(forSession) {{
  const values = Object.fromEntries(fields.map((field) => [field, input(field).value.trim()]));
  // Market Data is quote-only: its sole required secret is the TradeAPI token.
  // Optional session validation has its separate mobile/UCC/MPIN requirement.
  const required = forSession ? fields : ['tradeapi_access_token'];
  if (required.some((field) => !values[field])) {{ statusBox.textContent = 'ERROR\\nRequired Kotak credential fields are missing.'; return false; }}
  const changed = Object.fromEntries(Object.entries(values).filter(([, value]) => value));
  await request('/api/v1/connections/kotak-neo', {{method:'PUT', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(changed)}});
  clearInputs();
  return true;
}}
async function saveMarketTokenIfProvided() {{
  // The saved token is intentionally cleared from the password field after
  // Save. A later quote-only test uses the secure store unless a replacement
  // token was explicitly supplied in this interaction.
  return input('tradeapi_access_token').value.trim() ? saveCredentials(false) : true;
}}
document.getElementById('save').addEventListener('click', async () => {{
  try {{ if (await saveCredentials(false)) statusBox.textContent = 'CONFIGURED'; }}
  catch (error) {{ clearInputs(); showMarketData({{status:'ERROR', error_code:error.code, message:error.message}}); }}
}});
document.getElementById('test-market-data').addEventListener('click', async () => {{
  try {{ if (await saveMarketTokenIfProvided()) {{ const test_symbol = input('test_symbol').value.trim(); showMarketData(await request('/api/v1/connections/kotak-neo/test', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:test_symbol ? JSON.stringify({{test_symbol}}) : undefined}})); }} }}
  catch (error) {{ clearInputs(); showMarketData({{status:'ERROR', error_code:error.code, message:error.message}}); }}
}});
document.getElementById('test-session').addEventListener('click', async () => {{
  const totp = input('current_totp').value.trim();
  if (!/^\\d{{6}}$/.test(totp)) {{ statusBox.textContent = 'ERROR\\nEnter the current six-digit authenticator code.'; return; }}
  try {{
    if (await saveCredentials(true)) showSession(await request('/api/v1/connections/kotak-neo/session/test', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{current_totp: totp}})}}));
  }} catch (error) {{ showSession({{status:'ERROR', error_code:error.code, message:error.message}}); }}
  finally {{ input('current_totp').value = ''; }}
}});
document.getElementById('clear').addEventListener('click', async () => {{
  if (!window.confirm('Clear all securely stored Kotak Neo credentials?')) return;
  try {{ const profile = await request('/api/v1/connections/kotak-neo/credentials', {{method:'DELETE'}}); clearInputs(); showMarketData({{status:profile.status}}); }}
  catch (error) {{ showMarketData({{status:'ERROR', error_code:error.code, message:error.message}}); }}
}});
</script></body></html>"""
