"""Enforce two independent authorization dimensions: role and signed scope."""
import pytest
from fastapi import HTTPException

from accessfix_ai.presentation import auth as auth_module


class StubStore:
    def __init__(self, role):
        self.role = role
        self.lookups = []
    def member_role(self, tenant, subject):
        self.lookups.append((tenant, subject))
        return self.role


@pytest.mark.parametrize(("role", "permission", "expected"), [
    ("viewer", "job:read", True),
    ("viewer", "site:verify", False),
    ("viewer", "fix:review", False),
    ("editor", "site:verify", True),
    ("owner", "site:verify", True),
    ("admin", "site:verify", True),
    ("reviewer", "job:read", False),
    ("", "job:read", False),
])
def test_role_permissions(role, permission, expected):
    assert auth_module.role_scope_allowed(role, permission) is expected


def test_scope_denies_viewer_even_with_granted_write_scope(monkeypatch):
    monkeypatch.setattr(auth_module, "verify_session", lambda *_: None)
    store = StubStore("viewer")
    claims = {"tenant_id": "tenant-a", "sub": "subject-a", "scope": "site:verify job:read"}
    with pytest.raises(HTTPException) as error:
        auth_module.scope("site:verify", store)(claims)
    assert error.value.status_code == 403
    assert error.value.detail["code"] == "ROLE_FORBIDDEN"
    assert store.lookups == [("tenant-a", "subject-a")]


def test_viewer_read_allowed_only_with_granted_scope(monkeypatch):
    monkeypatch.setattr(auth_module, "verify_session", lambda *_: None)
    claims = {"tenant_id": "tenant-a", "sub": "subject-a", "scope": "job:read"}
    assert auth_module.scope("job:read", StubStore("viewer"))(claims) == claims
    with pytest.raises(HTTPException) as error:
        auth_module.scope("scan:read", StubStore("viewer"))(claims)
    assert error.value.detail["code"] == "INSUFFICIENT_SCOPE"


def test_missing_membership_and_unknown_roles_fail_closed(monkeypatch):
    monkeypatch.setattr(auth_module, "verify_session", lambda *_: None)
    claims = {"tenant_id": "tenant-a", "sub": "subject-a", "scope": "job:read"}
    for role in (None, "unreviewed_role"):
        with pytest.raises(HTTPException):
            auth_module.scope("job:read", StubStore(role))(claims)
