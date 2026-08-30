"""Credential-store abstractions.  No normal database table stores secrets."""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Protocol

from app.connections.models import KOTAK_NEO_CREDENTIAL_DEFINITIONS, GLOBAL_DATAFEEDS_CREDENTIAL_DEFINITIONS, UPSTOX_CREDENTIAL_DEFINITIONS, GNEWS_CREDENTIAL_DEFINITIONS


_ALL_CREDENTIAL_DEFINITIONS = (*KOTAK_NEO_CREDENTIAL_DEFINITIONS, *GLOBAL_DATAFEEDS_CREDENTIAL_DEFINITIONS, *UPSTOX_CREDENTIAL_DEFINITIONS, *GNEWS_CREDENTIAL_DEFINITIONS)
from app.market_data.kotak_neo import KotakNeoCredentials


class CredentialStore(Protocol):
    def load(self, connection_id: str) -> Mapping[str, str]: ...
    def save(self, connection_id: str, values: Mapping[str, str]) -> None: ...
    def clear(self, connection_id: str) -> None: ...


class CredentialStoreUnavailableError(RuntimeError):
    """Fixed safe error used instead of a backend/keyring exception."""

    def __init__(self, message: str, *, dpapi_fallback_eligible: bool = False) -> None:
        super().__init__(message)
        self.dpapi_fallback_eligible = dpapi_fallback_eligible


@dataclass(frozen=True, slots=True)
class CredentialStoreBackendStatus:
    available: bool
    backend: str
    code: str | None = None
    message: str | None = None


class KeyringCredentialStore:
    """OS credential-manager backed local store; values are never returned by APIs."""

    def __init__(self, service_name: str = "nse-stock-manager.connection") -> None:
        self._service_name = service_name

    def backend_status(self) -> CredentialStoreBackendStatus:
        """Lazy safe capability report; it never opens, reads, or writes a secret."""
        try:
            import keyring
            backend = keyring.get_keyring()
            module = backend.__class__.__module__.lower()
            name = backend.__class__.__name__
            if "fail" in module or "null" in module or "fail" in name.lower() or "null" in name.lower():
                return CredentialStoreBackendStatus(False, "UNAVAILABLE", "CREDENTIAL_STORE_UNAVAILABLE", "No secure OS credential backend is available.")
            if sys.platform == "win32" and "windows" in module:
                return CredentialStoreBackendStatus(True, "WINDOWS_CREDENTIAL_MANAGER")
            return CredentialStoreBackendStatus(True, "OS_KEYRING")
        except Exception:
            return CredentialStoreBackendStatus(False, "UNAVAILABLE", "CREDENTIAL_STORE_UNAVAILABLE", "No secure OS credential backend is available.")

    def load(self, connection_id: str) -> Mapping[str, str]:
        try:
            import keyring
            return {
                definition.field: value
                for definition in _ALL_CREDENTIAL_DEFINITIONS
                if (value := keyring.get_password(self._service_name, f"{connection_id}:{definition.field}")) is not None
            }
        except Exception as error:
            _raise_keyring_error(error)

    def save(self, connection_id: str, values: Mapping[str, str]) -> None:
        try:
            import keyring
            for name, value in values.items():
                keyring.set_password(self._service_name, f"{connection_id}:{name}", value)
        except Exception as error:
            _raise_keyring_error(error)

    def clear(self, connection_id: str) -> None:
        try:
            import keyring
            from keyring.errors import PasswordDeleteError
            fields = [definition.field for definition in _ALL_CREDENTIAL_DEFINITIONS]
            if connection_id == "kotak-neo":
                # Legacy names are never loaded or migrated.  They are removed
                # only by an explicit clear operation so an exposed old token
                # cannot silently become the active TradeAPI credential.
                fields.extend(("consumer_key", "access_token", "api_key", "trade_api_token", "totp_secret"))
            for field in fields:
                try:
                    keyring.delete_password(self._service_name, f"{connection_id}:{field}")
                except PasswordDeleteError:
                    continue
        except CredentialStoreUnavailableError:
            raise
        except Exception as error:
            _raise_keyring_error(error)


class WindowsDPAPICredentialStore:
    """Current-user Windows DPAPI store containing encrypted credential blobs only."""

    _SCHEMA_VERSION = 1

    def __init__(
        self,
        service_name: str = "nse-stock-manager.connection",
        base_directory: Path | None = None,
    ) -> None:
        self._service_name = service_name
        self._base_directory = base_directory or _windows_credentials_directory()

    def backend_status(self) -> CredentialStoreBackendStatus:
        if sys.platform != "win32":
            return CredentialStoreBackendStatus(False, "UNAVAILABLE", "CREDENTIAL_STORE_UNAVAILABLE", "Windows DPAPI is unavailable on this platform.")
        try:
            import win32crypt  # noqa: F401
        except (ImportError, OSError):
            return CredentialStoreBackendStatus(False, "UNAVAILABLE", "CREDENTIAL_STORE_UNAVAILABLE", "Windows DPAPI is unavailable to this process.")
        return CredentialStoreBackendStatus(True, "WINDOWS_DPAPI")

    def has_secret(self, connection_id: str, field: str) -> bool:
        return self._credential_path(connection_id, field).is_file()

    def get_secret(self, connection_id: str, field: str) -> str | None:
        path = self._credential_path(connection_id, field)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            expected = {
                "schema_version": self._SCHEMA_VERSION,
                "connection_id": connection_id,
                "field": field,
                "provider": payload.get("provider") if isinstance(payload, dict) else None,
                "protected_blob": payload.get("protected_blob") if isinstance(payload, dict) else None,
            }
            # Existing Kotak-only DPAPI blobs remain readable; the generic
            # marker supports non-Kotak connection profiles without moving a
            # secret through SQLite or any application response.
            if not isinstance(payload, dict) or payload != expected or payload["provider"] not in {"KOTAK_NEO", "CONNECTION_SECRET"}:
                raise ValueError("invalid encrypted credential metadata")
            protected = base64.b64decode(payload["protected_blob"], validate=True)
            return self._win32crypt().CryptUnprotectData(protected, None, None, None, 0)[1].decode("utf-8")
        except (OSError, UnicodeDecodeError, ValueError, TypeError, KeyError):
            raise _dpapi_store_error() from None
        except Exception as error:
            if _is_windows_runtime_error(error):
                raise _dpapi_store_error() from None
            raise

    def save_secret(self, connection_id: str, field: str, value: str) -> None:
        try:
            protected = self._win32crypt().CryptProtectData(
                value.encode("utf-8"),
                f"{self._service_name}:{connection_id}:{field}",
                None,
                None,
                None,
                0,
            )[1]
            payload = {
                "schema_version": self._SCHEMA_VERSION,
                "connection_id": connection_id,
                "field": field,
                "provider": "CONNECTION_SECRET",
                "protected_blob": base64.b64encode(protected).decode("ascii"),
            }
            self._atomic_write_json(self._credential_path(connection_id, field), payload)
        except CredentialStoreUnavailableError:
            raise
        except Exception as error:
            if _is_windows_runtime_error(error) or isinstance(error, OSError):
                raise _dpapi_store_error() from None
            raise

    def delete_secret(self, connection_id: str, field: str) -> None:
        try:
            self._credential_path(connection_id, field).unlink(missing_ok=True)
        except OSError:
            raise _dpapi_store_error() from None

    def load(self, connection_id: str) -> Mapping[str, str]:
        return {
            definition.field: value
            for definition in _ALL_CREDENTIAL_DEFINITIONS
            if (value := self.get_secret(connection_id, definition.field)) is not None
        }

    def save(self, connection_id: str, values: Mapping[str, str]) -> None:
        for field, value in values.items():
            self.save_secret(connection_id, field, value)

    def clear(self, connection_id: str) -> None:
        for definition in _ALL_CREDENTIAL_DEFINITIONS:
            self.delete_secret(connection_id, definition.field)
        if connection_id == "kotak-neo":
            for legacy_field in ("consumer_key", "access_token", "api_key", "trade_api_token", "totp_secret"):
                self.delete_secret(connection_id, legacy_field)

    def activate(self) -> None:
        """Persist the non-secret backend selector; no keyring value is copied."""
        self._atomic_write_json(self._selector_path(), {"schema_version": self._SCHEMA_VERSION, "backend": "WINDOWS_DPAPI"})

    def is_activated(self) -> bool:
        path = self._selector_path()
        if not path.is_file():
            return False
        try:
            return json.loads(path.read_text(encoding="utf-8")) == {"schema_version": self._SCHEMA_VERSION, "backend": "WINDOWS_DPAPI"}
        except (OSError, ValueError):
            return False

    def _credential_path(self, connection_id: str, field: str) -> Path:
        if not connection_id.replace("-", "").replace("_", "").isalnum() or not field.replace("_", "").isalnum():
            raise ValueError("invalid credential identifier")
        return self._base_directory / f"{connection_id}.{field}.dpapi"

    def _selector_path(self) -> Path:
        return self._base_directory / ".backend.json"

    def _atomic_write_json(self, path: Path, payload: Mapping[str, object]) -> None:
        temporary_name: str | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _restrict_permissions(path.parent, directory=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
                temporary_name = temporary.name
                json.dump(payload, temporary, sort_keys=True, separators=(",", ":"))
                temporary.flush()
                os.fsync(temporary.fileno())
            _restrict_permissions(Path(temporary_name), directory=False)
            os.replace(temporary_name, path)
            temporary_name = None
            _restrict_permissions(path, directory=False)
        finally:
            if temporary_name:
                Path(temporary_name).unlink(missing_ok=True)

    @staticmethod
    def _win32crypt():
        if sys.platform != "win32":
            raise _dpapi_store_error()
        try:
            import win32crypt
        except (ImportError, OSError):
            raise _dpapi_store_error() from None
        return win32crypt


class WindowsCredentialStore:
    """Native WinVault first, with a deterministic encrypted DPAPI fallback."""

    def __init__(
        self,
        native: CredentialStore | None = None,
        dpapi: WindowsDPAPICredentialStore | None = None,
    ) -> None:
        self._native = native or KeyringCredentialStore()
        self._dpapi = dpapi or WindowsDPAPICredentialStore()

    def backend_status(self) -> CredentialStoreBackendStatus:
        if self._dpapi.is_activated():
            return self._dpapi.backend_status()
        native_status = _backend_status(self._native)
        if native_status.available:
            return native_status
        return self._dpapi.backend_status()

    def load(self, connection_id: str) -> Mapping[str, str]:
        return self._use_selected("load", connection_id)

    def save(self, connection_id: str, values: Mapping[str, str]) -> None:
        self._use_selected("save", connection_id, values)

    def clear(self, connection_id: str) -> None:
        self._use_selected("clear", connection_id)

    def _use_selected(self, operation: str, connection_id: str, values: Mapping[str, str] | None = None):
        if self._dpapi.is_activated():
            return self._call(self._dpapi, operation, connection_id, values)
        try:
            return self._call(self._native, operation, connection_id, values)
        except CredentialStoreUnavailableError as error:
            if not error.dpapi_fallback_eligible:
                raise
            return self._activate_and_call(operation, connection_id, values)

    def _activate_and_call(self, operation: str, connection_id: str, values: Mapping[str, str] | None):
        if not self._dpapi.backend_status().available:
            raise CredentialStoreUnavailableError("Secure credential storage is unavailable.")
        self._dpapi.activate()
        return self._call(self._dpapi, operation, connection_id, values)

    @staticmethod
    def _call(store: CredentialStore, operation: str, connection_id: str, values: Mapping[str, str] | None):
        method = getattr(store, operation)
        return method(connection_id) if values is None else method(connection_id, values)


@dataclass
class InMemoryCredentialStore:
    """Explicit test-only substitute for the OS keyring."""

    values: dict[str, dict[str, str]] = field(default_factory=dict)

    def load(self, connection_id: str) -> Mapping[str, str]:
        return dict(self.values.get(connection_id, {}))

    def save(self, connection_id: str, values: Mapping[str, str]) -> None:
        self.values.setdefault(connection_id, {}).update(values)

    def clear(self, connection_id: str) -> None:
        self.values.pop(connection_id, None)

    def backend_status(self) -> CredentialStoreBackendStatus:
        return CredentialStoreBackendStatus(True, "TEST_IN_MEMORY")


def kotak_credentials_from_values(values: Mapping[str, str]) -> KotakNeoCredentials:
    return KotakNeoCredentials(
        tradeapi_access_token=values.get("tradeapi_access_token"), mobile_number=values.get("mobile_number"),
        ucc=values.get("ucc"), mpin=values.get("mpin"),
    )


def resolve_kotak_credentials(store: CredentialStore, connection_id: str, environment: Mapping[str, str] | None = None) -> tuple[KotakNeoCredentials, str]:
    """Use a complete source only: secure-store values never mix with environment values."""
    try:
        stored = store.load(connection_id)
    except Exception:
        raise CredentialStoreUnavailableError("Secure credential storage is unavailable.") from None
    if stored:
        return kotak_credentials_from_values(stored), "SECURE_STORE"
    return KotakNeoCredentials.from_environment(environment), "ENVIRONMENT"


def create_credential_store() -> CredentialStore:
    """Use the platform's native secure store, with Windows-only DPAPI recovery."""
    return WindowsCredentialStore() if sys.platform == "win32" else KeyringCredentialStore()


def _backend_status(store: CredentialStore) -> CredentialStoreBackendStatus:
    status = getattr(store, "backend_status", None)
    return status() if callable(status) else CredentialStoreBackendStatus(True, "SECURE_STORE")


def _windows_credentials_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        # This path is never created if DPAPI is unavailable; it avoids source/SQLite fallbacks.
        return Path(".") / ".unavailable-windows-credentials"
    return Path(local_app_data) / "NSEStockManager" / "credentials"


def _restrict_permissions(path: Path, *, directory: bool) -> None:
    """Best-effort ACL analogue; Windows DPAPI remains the primary protection."""
    try:
        path.chmod(0o700 if directory else 0o600)
    except OSError:
        pass


def _is_windows_runtime_error(error: Exception) -> bool:
    return isinstance(error, (OSError, ImportError)) or error.__class__.__module__.startswith(("win32", "win32ctypes", "pywintypes"))


def _raise_keyring_error(error: Exception) -> None:
    """Only known keyring/runtime failures qualify for a DPAPI fallback."""
    try:
        from keyring.errors import KeyringError
    except ImportError:
        KeyringError = ()  # type: ignore[assignment,misc]
    if isinstance(error, (OSError, ImportError, KeyringError)) or _is_windows_runtime_error(error):
        raise _secure_store_error(dpapi_fallback_eligible=sys.platform == "win32") from None
    raise error


def _secure_store_error(*, dpapi_fallback_eligible: bool = False) -> CredentialStoreUnavailableError:
    if sys.platform == "win32":
        return CredentialStoreUnavailableError(
            "Windows Credential Manager is unavailable to this process.",
            dpapi_fallback_eligible=dpapi_fallback_eligible,
        )
    return CredentialStoreUnavailableError("Secure credential storage is unavailable.")


def _dpapi_store_error() -> CredentialStoreUnavailableError:
    return CredentialStoreUnavailableError("Windows DPAPI secure credential storage is unavailable.")
