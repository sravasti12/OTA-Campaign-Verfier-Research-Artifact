"""Streamlit OIDC entry gate; local demo remains deliberately unauthenticated."""
import os
import sqlite3
from .persistence.store import StorageError
from pathlib import Path
from typing import Any
import streamlit as st
from .access import AccessDenied, Action, Account, authorize, load_access_policy
from .shared import SharedWorkflowService


def access_mode() -> str:
    """Reject typos instead of falling back to an unauthenticated mode."""
    mode = os.environ.get('OTA_ACCESS_MODE', 'local')
    if mode not in ('local', 'shared'):
        raise AccessDenied('OTA_ACCESS_MODE must be local or shared')
    return mode


def _verified_claims() -> tuple[dict[str, Any], bool]:
    # Streamlit authenticates OIDC; this module never parses raw browser tokens.
    return dict(st.user), bool(st.user.is_logged_in)


def shared_gate() -> bool:
    """Authenticate before any source data, library entries, or clients are loaded."""
    try:
        if access_mode() == 'local':
            if isinstance(st.session_state.get('workflow_service'), SharedWorkflowService):
                raise AccessDenied('Restart the server to change access modes')
            return True
        path_value = os.environ.get('OTA_ACCESS_CONFIG')
        if not path_value:
            raise AccessDenied('Set OTA_ACCESS_CONFIG to a protected server allowlist')
        policy_path = Path(path_value).resolve()
        policy = load_access_policy(policy_path)
        claims, logged_in = _verified_claims()
        if not logged_in:
            st.title('OTA Campaign Verifier — shared simulation review')
            if st.button('Sign in', key='sign_in'):
                st.login()
            return False
        with st.sidebar:
            if st.button('Sign out', key='sign_out'):
                st.logout()
        account = authorize(policy, claims, True, 'read')
        database = Path(policy.database_path)
        if not database.is_absolute():
            database = policy_path.parent / database
        database = database.resolve()
        def check(action: Action) -> Account:
            current_policy = load_access_policy(policy_path)
            current_database = Path(current_policy.database_path)
            if not current_database.is_absolute():
                current_database = policy_path.parent / current_database
            if current_database.resolve() != database:
                raise AccessDenied('Workspace configuration changed; restart the server')
            current_claims, current_login = _verified_claims()
            return authorize(current_policy, current_claims, current_login, action)
        binding = (str(policy_path), str(database), account.identity)
        if st.session_state.get('shared_binding') != binding:
            previous = st.session_state.get('workflow_service')
            if isinstance(previous, SharedWorkflowService):
                previous.close()
            service = SharedWorkflowService(database, check)
            st.session_state.workflow_service = service
            st.session_state.shared_binding = binding
            st.session_state.pop('active_run_id', None)
            st.session_state.pop('previous_workspaces', None)
        else:
            st.session_state.workflow_service._authorize_action = check
        st.sidebar.caption('Authenticated shared workspace / roles: ' + ', '.join(account.roles))
        return True
    except (StorageError, OSError, ValueError, sqlite3.Error):
        st.error('Shared access unavailable or denied. Check your login and ask the host operator to verify configuration.')
        return False
