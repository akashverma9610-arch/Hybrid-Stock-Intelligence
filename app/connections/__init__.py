"""Provider-neutral, local/private connection configuration boundary."""

from app.connections.models import ConnectionMode, ConnectionProfile, ConnectionStatus, CredentialSensitivity

__all__ = ("ConnectionMode", "ConnectionProfile", "ConnectionStatus", "CredentialSensitivity")
