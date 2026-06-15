"""DB-free test doubles + app wiring for the connection flow (P1D-1).

A :class:`FakeConnectionStore` (in-memory, simulates the server-side id default),
the real :class:`LocalDevVault` and :class:`MockGbpOAuthClient`, and a helper that
builds a TestClient with the chain overridden so no Postgres / Google / real vault
is touched. The store and vault are returned so a test can assert what was persisted
vs what was vaulted (the core acceptance: raw token in vault, only ``token_ref`` in
the DB).
"""
from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.connections import get_connection_service, router
from app.connections.service import ConnectionService
from app.core.errors import install_error_handlers
from app.core.vault import LocalDevVault
from app.db.session import get_db
from app.gbp.oauth import MockGbpOAuthClient
from app.models.connection import GbpConnection
from app.models.location import Location
from app.security.context import RequestContext
from app.security.deps import get_request_context


class FakeConnectionStore:
    """In-memory ``ConnectionStore``; assigns ids the way a DB flush would."""

    def __init__(self, client_tenants: dict[UUID, UUID]) -> None:
        self._client_tenants = client_tenants
        self.connections: dict[UUID, GbpConnection] = {}
        self.locations: list[Location] = []

    def add_connection(self, connection: GbpConnection) -> GbpConnection:
        if connection.id is None:
            connection.id = uuid4()
        self.connections[connection.id] = connection
        return connection

    def get_connection(self, connection_id: UUID) -> GbpConnection | None:
        return self.connections.get(connection_id)

    def tenant_id_for_client(self, client_id: UUID) -> UUID | None:
        return self._client_tenants.get(client_id)

    def existing_place_ids(self, client_id: UUID) -> set[str]:
        return {
            loc.google_place_id
            for loc in self.locations
            if loc.client_id == client_id and loc.google_place_id
        }

    def add_location(self, location: Location) -> Location:
        if location.id is None:
            location.id = uuid4()
        self.locations.append(location)
        return location


class DummySession:
    """Stands in for the request DB session; commit is a no-op (no real DB)."""

    def commit(self) -> None:  # pragma: no cover - trivial
        pass


def build_env(client_tenants: dict[UUID, UUID], principal: RequestContext | None):
    """Wire a test app over a shared fake store + real local vault + mock Google.

    ``principal`` of None leaves authentication unconfigured, so RBAC-gated routes
    return 401 (the callback is unauthenticated by design and works regardless).
    """
    store = FakeConnectionStore(client_tenants)
    vault = LocalDevVault()
    service = ConnectionService(store, vault, MockGbpOAuthClient())

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_connection_service] = lambda: service
    app.dependency_overrides[get_db] = lambda: DummySession()
    if principal is not None:
        app.dependency_overrides[get_request_context] = lambda: principal

    return {"client": TestClient(app), "store": store, "vault": vault, "service": service}
