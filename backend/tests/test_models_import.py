"""P1A-1 acceptance: all core models import cleanly and are registered on Base."""
from app.db.base import Base
from app.models import Client, Plan, RolePermission, Tenant, User, UserRole

ALL_MODELS = (Plan, Tenant, Client, User, UserRole, RolePermission)


def test_all_models_registered_on_metadata() -> None:
    """Every model imports without error and is registered on the shared metadata."""
    registered = set(Base.metadata.tables)
    for model in ALL_MODELS:
        assert model.__tablename__ in registered


def test_expected_tables_present() -> None:
    assert {m.__tablename__ for m in ALL_MODELS} == {
        "plans",
        "tenants",
        "clients",
        "users",
        "user_roles",
        "role_permissions",
    }


def test_tenant_id_fk_on_users() -> None:
    col = User.__table__.c["tenant_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "tenants.id" in fk_targets


def test_tenant_id_fk_on_clients() -> None:
    col = Client.__table__.c["tenant_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "tenants.id" in fk_targets


def test_tenant_plan_fk() -> None:
    col = Tenant.__table__.c["plan_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "plans.id" in fk_targets


def test_user_role_user_fk() -> None:
    col = UserRole.__table__.c["user_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "users.id" in fk_targets


def test_role_permissions_composite_pk() -> None:
    pk_cols = {c.name for c in RolePermission.__table__.primary_key}
    assert pk_cols == {"role", "permission"}
