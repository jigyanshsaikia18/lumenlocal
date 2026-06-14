"""P1A-1 acceptance: all core models import cleanly and are registered on Base."""
from app.db.base import Base
from app.models import Client, Plan, RolePermission, Tenant, User, UserRole


def test_models_importable() -> None:
    names = {t for t in Base.metadata.tables}
    assert "plans" in names
    assert "tenants" in names
    assert "clients" in names
    assert "users" in names
    assert "user_roles" in names
    assert "role_permissions" in names


def test_tenant_id_fk_on_users() -> None:
    col = User.__table__.c["tenant_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "tenants.id" in fk_targets


def test_tenant_id_fk_on_clients() -> None:
    col = Client.__table__.c["tenant_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "tenants.id" in fk_targets


def test_role_permissions_composite_pk() -> None:
    pk_cols = {c.name for c in RolePermission.__table__.primary_key}
    assert pk_cols == {"role", "permission"}
