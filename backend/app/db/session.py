from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Privileged engine — migrations, admin tasks, health checks. In dev this role is a
# superuser and therefore BYPASSES row-level security. Do NOT use it for request handling.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Application engine — a non-superuser role that IS subject to row-level security.
# Every tenant-scoped runtime query MUST go through here inside a tenant context.
app_engine = create_engine(settings.app_database_url, pool_pre_ping=True)
AppSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=app_engine)

# Postgres GUC the RLS policies read to scope rows to the active tenant.
TENANT_GUC = "app.current_tenant"


def set_tenant(session: Session, tenant_id: UUID | str) -> None:
    """Bind the current transaction to a tenant for row-level security.

    Uses ``set_config(..., is_local => true)`` (SET LOCAL semantics): the value lives
    only for the current transaction, so it can never leak across pooled connections.
    Must be called inside an open transaction (the session starts one on first use).
    """
    session.execute(
        text("SELECT set_config(:guc, :tid, true)"),
        {"guc": TENANT_GUC, "tid": str(tenant_id)},
    )


@contextmanager
def tenant_session(tenant_id: UUID | str) -> Iterator[Session]:
    """App-role session scoped to a single tenant for its whole transaction.

    Commits on success, rolls back on error. Reads and writes inside see (and may
    affect) only ``tenant_id``'s rows — enforced by Postgres RLS, not convention.
    """
    session = AppSessionLocal()
    try:
        set_tenant(session, tenant_id)
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
