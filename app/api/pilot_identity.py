"""Managed human authentication. HSI authorization never comes from JWT roles."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

import jwt

from app.api.errors import APIRequestError


def denied(code: str = "PILOT_ACCESS_DENIED", status: int = 403) -> APIRequestError:
    return APIRequestError(status_code=status, code=code, message="Pilot access is unavailable or not authorized.")


class PilotRole(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    TESTER = "TESTER"


@dataclass(frozen=True, slots=True)
class PilotPrincipal:
    user_id: str
    role: PilotRole


@dataclass(frozen=True, slots=True)
class PilotIdentitySettings:
    issuer: str
    audience: str
    client_ids: tuple[str, ...]
    store_path: str

    def __post_init__(self):
        url = urlsplit(self.issuer)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path != "/" or url.port not in (None, 443)):
            raise ValueError("PILOT_ISSUER_INVALID")
        if (not self.audience or self.audience == self.issuer or not self.client_ids
                or any(not x or x.strip() != x for x in self.client_ids)
                or self.audience in self.client_ids or not self.store_path):
            raise ValueError("PILOT_IDENTITY_CONFIGURATION_INVALID")


class ManagedTokenVerifier:
    """Auth0 RS256 API access tokens; pinned issuer/audience/SPA clients.

    ID tokens, M2M credentials, token-provided key URLs and JWT role metadata
    confer no authority. Network key refresh is bounded and TLS stays verified.
    No token or exception contents are logged, stored or returned.
    """

    def __init__(self, settings: PilotIdentitySettings):
        self.settings = settings
        self._keys = jwt.PyJWKClient(settings.issuer + ".well-known/jwks.json",
                                   timeout=5, lifespan=300, cache_keys=False)
        self._refresh_lock = Lock()
        self._last_refresh = float("-inf")

    def _signing_key(self, kid: str):
        # PyJWKClient refreshes for every unknown kid by default. Bound that
        # path too, so untrusted tokens cannot cause unbounded provider calls.
        with self._refresh_lock:
            data = self._keys.jwk_set_cache.get()
            keys = () if data is None else self._keys.get_signing_keys()
            matching = tuple(k for k in keys if k.key_id == kid)
            if not matching and monotonic() - self._last_refresh >= 30:
                self._last_refresh = monotonic()
                keys = self._keys.get_signing_keys(refresh=True)
                matching = tuple(k for k in keys if k.key_id == kid)
            if len(matching) != 1 or matching[0].algorithm_name != "RS256":
                raise denied("PILOT_TOKEN_INVALID", 401)
            return matching[0].key

    def verify(self, token: str) -> tuple[str, str]:
        try:
            if not token or len(token) > 16384:
                raise ValueError("invalid")
            header = jwt.get_unverified_header(token)
            if (header.get("alg") != "RS256" or not isinstance(header.get("kid"), str)
                    or not header["kid"] or len(header["kid"]) > 200
                    or any(k in header for k in ("jku", "x5u", "jwk", "crit"))):
                raise ValueError("invalid")
            claims = jwt.decode(token, self._signing_key(header["kid"]), algorithms=["RS256"],
                                audience=self.settings.audience, issuer=self.settings.issuer,
                                options={"require": ["iss", "sub", "aud", "exp", "iat", "azp"]})
            subject = claims["sub"]
            if (not isinstance(subject, str) or not subject or len(subject) > 255
                    or subject.strip() != subject or any(ord(c) < 32 for c in subject)
                    or subject.endswith("@clients") or claims.get("gty") == "client-credentials"
                    or claims["azp"] not in self.settings.client_ids
                    or not isinstance(claims.get("scope"), str)
                    or "hsi:access" not in claims["scope"].split()
                    or type(claims["iat"]) is not int or type(claims["exp"]) is not int
                    or not 0 < claims["exp"] - claims["iat"] <= 600):
                raise ValueError("invalid")
            return self.settings.issuer, subject
        except APIRequestError:
            raise
        except jwt.PyJWKClientConnectionError:
            raise denied("PILOT_IDENTITY_PROVIDER_UNAVAILABLE", 503) from None
        except Exception:
            raise denied("PILOT_TOKEN_INVALID", 401) from None
