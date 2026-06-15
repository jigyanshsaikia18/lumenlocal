"""Capability catalog + built-in role map (RBAC-4).

Access is **capability-based**: every privileged action maps to a granular,
stable capability key (e.g. ``reviews.reply``, ``posts.publish``). Roles are
just named bundles of capabilities. Higher built-in roles inherit the lower
tiers' capabilities (RBAC-1), and ``super_admin`` is a wildcard.

Custom roles (RBAC-3) carry no entry here — their capabilities come from the
``role_permissions`` table and are merged in at request time
(see ``app.security.context.RequestContext``).

Keep this catalog aligned with the "Min role" column of
``05_API_Specification.md``; do not invent capabilities for endpoints that don't
exist yet.
"""
from __future__ import annotations

# --- Read tier (the "analyst+" rows in the API spec) ----------------------------
_READ: frozenset[str] = frozenset(
    {
        "clients.read",
        "users.read",
        "features.read",
        "entitlements.resolve",
        "usage.read",
        "connections.read",
        "locations.read",
        "geogrid.read",
        "geo_ai.read",
        "geo_prompts.read",
        "ai_readiness.read",
        "reviews.read",
        "review_sentiment.read",
        "posts.read",
        "protection.read",
        "suspension_risk.read",
        "compliance.read",
        "competitors.read",
        "reports.read",
        "copilot.ask",
        "audit_log.read",
    }
)

# --- Approval tier (client_owner: approves/rejects pending actions on own data) --
_APPROVE: frozenset[str] = frozenset(
    {
        "approvals.act",
        "protection.reject_edit",
    }
)

# --- Operator tier (account_manager: day-to-day execution) ----------------------
_OPERATE: frozenset[str] = frozenset(
    {
        "connections.start",
        "locations.import",
        "locations.write",
        "geogrid.run",
        "geo_ai.run",
        "geo_prompts.write",
        "reviews.reply",
        "reviews.draft_ai",
        "review_campaigns.create",
        "posts.write",
        "posts.generate_ai",
        "posts.publish",
        "media.upload",
        "qa.manage",
        "services.manage",
        "changes.revert",
        "competitors.manage",
        "reports.build",
        "reports.generate",
        "reports.schedule",
    }
)

# --- Admin tier (agency_admin: org-level configuration within a tenant) ---------
_ADMIN: frozenset[str] = frozenset(
    {
        "tenants.update_own",
        "clients.write",
        "clients.delete",
        "users.invite",
        "users.assign_role",
        "connections.proxy",
        "entitlements.override",
        "entitlements.preview",
        "protection.configure",
        "automation.configure",
        "webhooks.manage",
    }
)

# --- Platform tier (super_admin only: cross-tenant + policy guardrails) ----------
_PLATFORM: frozenset[str] = frozenset(
    {
        "tenants.read",
        "tenants.create",
        "quotas.read",
        "quotas.write",
        "policy.read",
        "policy.publish",
        "roles.define",
    }
)

# Wildcard sentinel: a role mapped to this grants every capability.
WILDCARD = "*"

# Built-in roles, lowest to highest. Each inherits the tiers below it (RBAC-1).
BUILTIN_ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    "analyst": _READ,
    "client_owner": _READ | _APPROVE,
    "account_manager": _READ | _APPROVE | _OPERATE,
    "agency_admin": _READ | _APPROVE | _OPERATE | _ADMIN,
    "super_admin": frozenset({WILDCARD}),
}

# The full, validated registry of known capability keys (everything except the
# wildcard). Used to reject typos when seeding custom-role permission rows.
CAPABILITY_CATALOG: frozenset[str] = (
    _READ | _APPROVE | _OPERATE | _ADMIN | _PLATFORM
)


def role_has_capability(role: str, capability: str) -> bool:
    """True if a *built-in* ``role`` grants ``capability``.

    Custom roles always return False here (they have no built-in bundle); their
    grants are resolved from ``role_permissions`` by the request context.
    """
    granted = BUILTIN_ROLE_CAPABILITIES.get(role)
    if granted is None:
        return False
    return WILDCARD in granted or capability in granted


def is_known_capability(capability: str) -> bool:
    """True if ``capability`` is a registered key (guards custom-role seeding)."""
    return capability in CAPABILITY_CATALOG
