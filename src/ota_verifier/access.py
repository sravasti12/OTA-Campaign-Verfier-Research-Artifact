"""Server-side authorization for Streamlit-verified OIDC identities."""
from collections.abc import Mapping
from pathlib import Path
from time import time
from typing import Any, Literal, Self
from pydantic import Field, model_validator
from .models import Record
from .llm.evidence import canonical_json
from .persistence.store import StorageError

Role = Literal['reader', 'analyst', 'reviewer', 'admin']
Action = Literal['read', 'analyze', 'review', 'admin']


class AccessDenied(StorageError):
    """The authenticated account is missing, expired, revoked, or lacks a role."""


class Account(Record):
    """An exact issuer/subject allowlist entry, controlled by the host operator."""
    issuer: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    roles: tuple[Role, ...] = Field(min_length=1)
    enabled: bool = True

    @property
    def identity(self) -> str:
        """Return an unambiguous stable audit identity, independent of display names."""
        return canonical_json({'issuer': self.issuer, 'subject': self.subject})


class AccessPolicy(Record):
    """One trusted-host workspace; no browser-selected database or role values."""
    format_version: Literal['access-policy-v1'] = 'access-policy-v1'
    database_path: str = Field(min_length=1)
    max_session_seconds: int = Field(default=3600, ge=60, le=86400)
    accounts: tuple[Account, ...]

    @model_validator(mode='after')
    def unique_accounts(self) -> Self:
        """Reject ambiguous or duplicate grants."""
        identities = [account.identity for account in self.accounts]
        if len(identities) != len(set(identities)):
            raise ValueError('Duplicate issuer/subject allowlist entry')
        return self


def load_access_policy(path: Path) -> AccessPolicy:
    """Read fresh operator grants; no credentials or file contents enter errors."""
    try:
        return AccessPolicy.model_validate_json(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        raise AccessDenied('Shared access configuration is missing or invalid') from None


def authorize(policy: AccessPolicy, claims: Mapping[str, Any], logged_in: bool,
              action: Action, *, now: float | None = None) -> Account:
    """Authorize only claims already verified by Streamlit, never raw browser JSON.

    The caller is the trusted server adapter. This function does not verify JWTs
    or accept identity tokens. OIDC iss/sub and token lifetime are mandatory.
    Role changes are applied by reading the server policy for every operation.
    """
    moment = time() if now is None else now
    issued, expires = claims.get('iat'), claims.get('exp')
    if (not logged_in or type(issued) not in (int, float) or type(expires) not in (int, float)
            or not issued <= moment + 60 or not moment < expires
            or not 0 <= moment - issued <= policy.max_session_seconds):
        raise AccessDenied('Login is missing or expired; sign out and sign in again')
    account = next((account for account in policy.accounts if account.enabled
        and account.issuer == claims.get('iss') and account.subject == claims.get('sub')), None)
    needed = {'read': {'reader', 'analyst', 'reviewer', 'admin'}, 'analyze': {'analyst', 'admin'},
              'review': {'reviewer', 'admin'}, 'admin': {'admin'}}[action]
    if account is None or not needed.intersection(account.roles):
        raise AccessDenied('This account is not authorized for this operation')
    return account
