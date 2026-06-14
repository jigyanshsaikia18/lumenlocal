"""P1B-2: capability resolution per role, custom-role scaffold, and scope.

These are pure-Python unit tests (no DB, no HTTP) over the RBAC core. The HTTP
side — that a missing capability yields 403 — is covered in
``test_rbac_middleware.py``.
"""
from uuid import uuid4

import pytest

from app.security.capabilities import (
    BUILTIN_ROLE_CAPABILITIES,
    role_has_capability,
)
from app.security.context import RequestContext, RoleAssignment

ROLES = ["super_admin", "agency_admin", "account_manager", "client_owner", "analyst"]


def ctx_for(role: str, **kw) -> RequestContext:
    return RequestContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        roles=(RoleAssignment(role=role, **kw),),
    )


# Representative capability → the exact set of roles that should hold it.
# One capability per tier, so every role's boundary is asserted.
CAPABILITY_MATRIX = {
    "reviews.read": {"super_admin", "agency_admin", "account_manager", "client_owner", "analyst"},
    "approvals.act": {"super_admin", "agency_admin", "account_manager", "client_owner"},
    "reviews.reply": {"super_admin", "agency_admin", "account_manager"},
    "posts.publish": {"super_admin", "agency_admin", "account_manager"},
    "reports.schedule": {"super_admin", "agency_admin", "account_manager"},
    "clients.write": {"super_admin", "agency_admin"},
    "entitlements.override": {"super_admin", "agency_admin"},
    "policy.publish": {"super_admin"},
    "tenants.create": {"super_admin"},
    "quotas.write": {"super_admin"},
}


@pytest.mark.parametrize("capability,allowed_roles", CAPABILITY_MATRIX.items())
@pytest.mark.parametrize("role", ROLES)
def test_capability_matrix_per_role(role, capability, allowed_roles):
    """Each of the five roles holds exactly the capabilities it should."""
    expected = role in allowed_roles
    assert ctx_for(role).has_capability(capability) is expected


def test_super_admin_is_wildcard():
    """super_admin holds every catalogued capability, including unenumerated ones."""
    ctx = ctx_for("super_admin")
    for capability in BUILTIN_ROLE_CAPABILITIES["account_manager"]:
        assert ctx.has_capability(capability)
    assert ctx.has_capability("some.future.capability")  # wildcard, not just the catalog
    assert ctx.effective_capabilities() == frozenset({"*"})


def test_role_hierarchy_is_inclusive():
    """Higher built-in roles inherit the lower tiers' capabilities (RBAC-1)."""
    caps = {r: ctx_for(r).effective_capabilities() for r in ROLES if r != "super_admin"}
    assert caps["analyst"] < caps["client_owner"]
    assert caps["client_owner"] < caps["account_manager"]
    assert caps["account_manager"] < caps["agency_admin"]


def test_unknown_role_grants_nothing():
    assert role_has_capability("not_a_role", "reviews.read") is False
    assert ctx_for("not_a_role").has_capability("reviews.read") is False


# --- Custom-role scaffold (RBAC-3) ---------------------------------------------
def test_custom_role_capabilities_come_from_granted_permissions():
    """A custom role has no built-in bundle; its grants drive access entirely."""
    ctx = RequestContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        roles=(
            RoleAssignment(
                role="compliance_reviewer",  # not a built-in role
                permissions=frozenset({"compliance.read", "reviews.reply"}),
            ),
        ),
    )
    assert role_has_capability("compliance_reviewer", "reviews.reply") is False  # no bundle
    assert ctx.has_capability("reviews.reply") is True  # granted explicitly
    assert ctx.has_capability("compliance.read") is True
    assert ctx.has_capability("posts.publish") is False  # not granted


def test_granted_permissions_extend_a_builtin_role():
    """role_permissions rows are additive on top of a built-in bundle."""
    ctx = ctx_for("analyst", permissions=frozenset({"posts.publish"}))
    assert ctx.has_capability("reviews.read") is True  # from analyst bundle
    assert ctx.has_capability("posts.publish") is True  # from explicit grant
    assert ctx.has_capability("clients.write") is False


# --- Scope enforcement (RBAC-2) ------------------------------------------------
def test_scoped_assignment_only_covers_its_own_scope():
    client_a, client_b = uuid4(), uuid4()
    ctx = ctx_for("account_manager", scope_type="client", scope_id=client_a)
    assert ctx.has_capability("reviews.reply", scope_id=client_a) is True
    assert ctx.has_capability("reviews.reply", scope_id=client_b) is False
    # No specific target → capability check passes regardless of scope.
    assert ctx.has_capability("reviews.reply") is True


def test_tenant_wide_assignment_covers_every_scope():
    ctx = ctx_for("account_manager")  # scope_id=None → tenant-wide
    assert ctx.has_capability("reviews.reply", scope_id=uuid4()) is True
