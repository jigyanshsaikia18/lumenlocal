"""The DB seam for the connection flow.

``ConnectionStore`` is the narrow persistence interface the service needs: write a
connection, read one back, map a client to its tenant (scope enforcement), and the
existing place-ids + insert for the location import. Splitting it out keeps the
service pure and lets unit tests inject an in-memory fake instead of Postgres
(mirrors ``app.entitlements.repository``).
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.connection import GbpConnection
from app.models.location import Location


class ConnectionStore(Protocol):
    """What the connection service needs from persistence (mock this in tests)."""

    def add_connection(self, connection: GbpConnection) -> GbpConnection: ...

    def get_connection(self, connection_id: UUID) -> GbpConnection | None: ...

    def tenant_id_for_client(self, client_id: UUID) -> UUID | None: ...

    def existing_place_ids(self, client_id: UUID) -> set[str]: ...

    def add_location(self, location: Location) -> Location: ...


class SqlAlchemyConnectionStore:
    """Production ``ConnectionStore`` over ``gbp_connections`` + ``locations``.

    Runs as the RLS-scoped ``lumen_app`` role at runtime; the caller owns the
    surrounding transaction/commit (as elsewhere in the app). ``flush`` populates
    server-side defaults (id) before the row is returned.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_connection(self, connection: GbpConnection) -> GbpConnection:
        self._session.add(connection)
        self._session.flush()
        return connection

    def get_connection(self, connection_id: UUID) -> GbpConnection | None:
        return self._session.get(GbpConnection, connection_id)

    def tenant_id_for_client(self, client_id: UUID) -> UUID | None:
        return self._session.execute(
            text("SELECT tenant_id FROM clients WHERE id = :cid"),
            {"cid": client_id},
        ).scalar_one_or_none()

    def existing_place_ids(self, client_id: UUID) -> set[str]:
        rows = self._session.execute(
            text(
                "SELECT google_place_id FROM locations "
                "WHERE client_id = :cid AND google_place_id IS NOT NULL"
            ),
            {"cid": client_id},
        )
        return {r.google_place_id for r in rows}

    def add_location(self, location: Location) -> Location:
        self._session.add(location)
        self._session.flush()
        return location


# Help static checkers confirm the concrete store satisfies the Protocol.
_STORE_CHECK: type[ConnectionStore] = SqlAlchemyConnectionStore
