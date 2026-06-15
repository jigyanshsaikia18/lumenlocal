"""GBP connection endpoints (API spec §5, PRD §6, P1D-1).

* ``POST /connections/oauth/start`` — operator begins a client self-connect; returns
  the Google consent URL (RBAC ``connections.start``).
* ``POST /connections/oauth/callback`` — handles Google's redirect. There is **no**
  bearer auth here (min role ``system`` in the spec): the request arrives from
  Google's redirect, and the signed ``state`` minted at ``start`` is the CSRF/identity
  binding. The handler vaults the raw token and persists only ``token_ref``.
* ``POST /locations/import`` — pulls the connection's GBP locations into the
  ``locations`` table (RBAC ``locations.import``).

The ``get_connection_service`` seam is overridden in tests so the chain runs without
Postgres, the vault, or Google.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.connections.repository import SqlAlchemyConnectionStore
from app.connections.service import ConnectionService
from app.core.vault import get_vault
from app.db.session import get_db
from app.gbp.oauth import get_gbp_client
from app.schemas.connections import (
    ConnectionOut,
    ConnectionStartRequest,
    ConnectionStartResponse,
    ImportedLocationOut,
    ImportLocationsRequest,
    ImportLocationsResponse,
    OAuthCallbackRequest,
)
from app.security.context import RequestContext
from app.security.deps import require

router = APIRouter(tags=["connections"])


def get_connection_service(db: Session = Depends(get_db)) -> ConnectionService:
    """Provide a request-scoped connection service (overridden in tests)."""
    return ConnectionService(SqlAlchemyConnectionStore(db), get_vault(), get_gbp_client())


@router.post("/connections/oauth/start", response_model=ConnectionStartResponse)
def start_oauth(
    body: ConnectionStartRequest,
    ctx: RequestContext = Depends(require("connections.start")),
    service: ConnectionService = Depends(get_connection_service),
) -> ConnectionStartResponse:
    """Begin a client self-connect: return the Google consent URL + signed state."""
    result = service.start(ctx.tenant_id, body.client_id, body.connect_method)
    return ConnectionStartResponse(consent_url=result.consent_url, state=result.state)


@router.post("/connections/oauth/callback", response_model=ConnectionOut)
async def oauth_callback(
    body: OAuthCallbackRequest,
    service: ConnectionService = Depends(get_connection_service),
    db: Session = Depends(get_db),
) -> ConnectionOut:
    """Exchange the code, vault the raw token, persist only ``token_ref``."""
    connection = await service.handle_callback(body.state, body.code)
    db.commit()
    return ConnectionOut.model_validate(connection)


@router.post("/locations/import", response_model=ImportLocationsResponse)
async def import_locations(
    body: ImportLocationsRequest,
    ctx: RequestContext = Depends(require("locations.import")),
    service: ConnectionService = Depends(get_connection_service),
    db: Session = Depends(get_db),
) -> ImportLocationsResponse:
    """Import the connection's GBP locations (idempotent on google_place_id)."""
    created = await service.import_locations(ctx.tenant_id, body.connection_id)
    db.commit()
    return ImportLocationsResponse(
        connection_id=body.connection_id,
        imported_count=len(created),
        locations=[ImportedLocationOut.model_validate(loc) for loc in created],
    )
