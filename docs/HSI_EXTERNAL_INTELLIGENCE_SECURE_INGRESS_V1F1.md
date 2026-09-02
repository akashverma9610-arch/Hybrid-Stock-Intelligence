# HSI External Intelligence secure ingress V1F1

This document is an infrastructure handoff, not an application deployment
instruction. The local HSI FastAPI process and its SQLite file stay private.
The only public ingress route is the existing authenticated intake endpoint.

## Connector configuration

The External Intelligence Desk process must have these two secret/configuration
entries supplied by its approved runtime secret manager:

- `HSI_EXTERNAL_INTELLIGENCE_HSI_ORIGIN`: the public HTTPS origin only, for
  example `https://intelligence.example.com`. It must not contain a path,
  query, fragment, loopback hostname, or plaintext Internet HTTP URL.
- `HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN`: the same bearer secret configured
  only in the HSI backend runtime. It grants only `intelligence:ingest` at the
  application boundary and is never placed in source control, a URL, or a
  browser configuration.

The connector constructs exactly:

`https://intelligence.example.com/api/v1/intelligence/events`

It does not accept an arbitrary route. A missing/invalid origin or token fails
closed before delivery; an unavailable ingress remains `PENDING_DELIVERY`.

## Reverse-proxy example

Obtain a public HTTPS origin from an approved reverse proxy, managed tunnel, or
load balancer. Do not expose the local HSI process directly. The following
Nginx shape is an example after TLS certificate provisioning; adapt only host
and certificate paths in the approved infrastructure environment.

```nginx
limit_req_zone $binary_remote_addr zone=hsi_intelligence:10m rate=4r/m;

server {
    listen 443 ssl http2;
    server_name intelligence.example.com;
    ssl_certificate     /managed/certificate/fullchain.pem;
    ssl_certificate_key /managed/certificate/privatekey.pem;
    client_max_body_size 256k;

    location = /api/v1/intelligence/events {
        limit_except POST { deny all; }
        limit_req zone=hsi_intelligence burst=2 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Request-ID $request_id;
        proxy_connect_timeout 5s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        proxy_request_buffering off;
        proxy_buffering off;
    }

    location / { return 404; }
}

server {
    listen 80;
    server_name intelligence.example.com;
    return 444;
}
```

The `4r/m` rate with a burst of two is intentionally narrow for an hourly
producer and bounded retry. The reverse proxy is not an authorization boundary:
HSI still requires the bearer credential on every event. Do not add unrelated
HSI routes, SQLite, files, internal ports, broker functions, or an arbitrary
proxy route to this ingress.

## Canary and revocation

After the origin and secret are configured, the Desk performs one current,
primary-source-verified canary through its existing structured-event path by
calling `connector.ingest_intelligence_event(event)`. It may enable hourly
delivery only after the result is `DELIVERED` and one exact retry returns the
HSI `ACCEPTED_EXISTING` disposition.

To revoke, remove or rotate `HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN` in both
the backend and Desk secret managers, then reload their runtime configuration.
New delivery fails closed; unrelated HSI functionality is unaffected.
