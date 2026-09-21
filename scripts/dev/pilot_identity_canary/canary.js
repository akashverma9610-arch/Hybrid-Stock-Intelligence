/* Tokens stay in Auth0 SDK memory; never printed, persisted, or put in a URL. */
"use strict";
(async () => {
  const status = document.getElementById("status");
  const ids = ["login", "recheck", "checks", "revoke", "enable", "logout"];
  const show = value => { status.textContent = JSON.stringify(value, null, 2); };
  let client;
  let config;
  let principal;
  const api = async (path, method = "GET", body = undefined) => {
    // Never refresh silently during proof: expiry must remain observable.
    const token = await client.getTokenSilently({cacheMode: "cache-only"});
    if (!token) throw new Error("REAUTH_REQUIRED");
    const response = await fetch(path, {
      method, cache: "no-store", credentials: "omit", redirect: "error",
      headers: {Authorization: "Bearer " + token, "Content-Type": "application/json"},
      body: body === undefined ? undefined : JSON.stringify(body)
    });
    return {status: response.status, data: await response.json()};
  };
  const refreshIdentity = async () => {
    const result = await api("/api/v1/pilot/me");
    principal = result.status === 200 ? result.data : undefined;
    const label = principal ? config.labels[principal.user_id] : undefined;
    document.getElementById("checks").disabled = !principal;
    document.getElementById("revoke").disabled = principal?.role !== "OWNER";
    document.getElementById("enable").disabled = principal?.role !== "OWNER";
    document.getElementById("logout").disabled = false;
    show({stage: "BACKEND_IDENTITY", http_status: result.status,
      identity: label || "UNAVAILABLE", role: principal?.role || "UNAVAILABLE",
      error_code: result.data?.error?.code || null, data: "SYNTHETIC_CANARY_ONLY"});
  };
  try {
    config = await (await fetch("/canary-config", {cache: "no-store"})).json();
    client = new auth0.Auth0Client({
      domain: config.domain, clientId: config.client_id,
      cacheLocation: "memory", useRefreshTokens: false,
      authorizationParams: {
        audience: config.audience, scope: "openid hsi:access",
        redirect_uri: config.origin + "/callback"
      }
    });
    // The SDK checks OAuth state, nonce, issuer and PKCE transaction. Never
    // decode token claims here to assign a role or canonical HSI identity.
    if (location.pathname === "/callback") {
      const callbackUrl = location.href;
      history.replaceState({}, "", "/");
      await client.handleRedirectCallback(callbackUrl);
      document.getElementById("recheck").disabled = false;
      await refreshIdentity();
    } else {
      show({stage: "READY_FOR_LOGIN", data: "SYNTHETIC_CANARY_ONLY"});
    }
    document.getElementById("login").disabled = false;
    document.getElementById("login").onclick = async () => {
      try { await client.loginWithRedirect({authorizationParams: {prompt: "login", max_age: 0}}); }
      catch { show({stage: "LOGIN_FAILED", classification: "AUTHENTICATION_UNAVAILABLE"}); }
    };
    document.getElementById("recheck").onclick = async () => {
      // Explicit operator retry of the cached token, not a token refresh or
      // validation relaxation. Useful for investigating a future iat/nbf.
      try { await refreshIdentity(); }
      catch { show({stage: "RECHECK_UNAVAILABLE", classification: "REAUTH_OR_NETWORK_REQUIRED"}); }
    };
    document.getElementById("checks").onclick = async () => {
      try {
        const me = await api("/api/v1/pilot/me");
        if (me.status !== 200) {
          show({stage: "ACCESS_DENIED", http_status: me.status, error_code: me.data?.error?.code});
          return;
        }
        const label = config.labels[me.data.user_id];
        const results = [];
        const own = await api("/api/v1/portfolio");
        const expectedId = label === "A" || label === "B" ? "SYNTHETIC-" + label : null;
        results.push({check: "OWN_PRIVATE_VIEW", http_status: own.status,
          passed: expectedId ? own.status === 200 && own.data.portfolio_id === expectedId : own.status === 503});
        // Legacy list endpoints must ignore hostile authority hints, not select
        // another user's private record. IDs below identify synthetic canaries.
        const other = label === "A" ? "B" : "A";
        const hinted = await api("/api/v1/portfolio?owner_id=" + config.users[other] + "&role=OWNER");
        results.push({check: "CROSS_USER_READ_HINT", http_status: hinted.status,
          passed: expectedId ? hinted.status === 200 && hinted.data.portfolio_id === expectedId : hinted.status === 503});
        const cancel = await api("/api/v1/portfolio/import/SYNTHETIC-DRAFT-" + other + "/cancel", "POST", {});
        results.push({check: "CROSS_USER_MUTATION_DENIED", http_status: cancel.status, passed: cancel.status === 404});
        const admin = await api("/api/v1/pilot/admin/status");
        results.push({check: "ADMIN_BOUNDARY", http_status: admin.status,
          passed: admin.status === (me.data.role === "OWNER" ? 200 : 403)});
        if (me.data.role === "TESTER") {
          const mutation = await api("/api/v1/pilot/admin/users/" + config.users[other], "PATCH",
            {enabled: false, reason: "SYNTHETIC_CANARY_DENIED_MUTATION"});
          results.push({check: "ADMIN_MUTATION_DENIED", http_status: mutation.status, passed: mutation.status === 403});
        }
        show({stage: "ISOLATION_CHECKS", identity: label, results,
          passed: results.every(x => x.passed), data: "SYNTHETIC_CANARY_ONLY"});
      } catch { show({stage: "CHECKS_UNAVAILABLE", classification: "REAUTH_OR_NETWORK_REQUIRED"}); }
    };
    for (const [id, enabled] of [["revoke", false], ["enable", true]]) {
      document.getElementById(id).onclick = async () => {
        try {
          const result = await api("/api/v1/pilot/admin/users/" + config.users.B, "PATCH",
            {enabled, reason: "EXPLICIT_OWNER_CANARY_REVOCATION_PROOF"});
          show({stage: enabled ? "TESTER_B_ENABLED" : "TESTER_B_REVOKED", http_status: result.status});
        } catch { show({stage: "ADMIN_CHANGE_UNAVAILABLE"}); }
      };
    }
    document.getElementById("logout").onclick = async () => {
      try { await client.logout({logoutParams: {returnTo: config.origin}}); }
      catch { show({stage: "LOGOUT_UNAVAILABLE"}); }
    };
  } catch {
    history.replaceState({}, "", "/");
    ids.forEach(id => { document.getElementById(id).disabled = true; });
    show({stage: "CANARY_UNAVAILABLE", classification: "CONFIGURATION_OR_LOGIN_FAILED"});
  }
})();
