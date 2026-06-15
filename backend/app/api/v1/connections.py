"""GBP connection endpoints (API spec §5, PRD §6, P1D-1/P1D-2).

* ``POST /connections/oauth/start``  — client self-connect; returns consent URL
  (RBAC ``connections.start``).
* ``POST /connections/oauth/callback`` — exchanges code, vaults raw token,
  persists only ``token_ref`` (unauthenticated; state JWT is the binding).
* ``POST /connections/proxy`` — agency-on-behalf connect; enforces the
  Google project-ownership rule before minting the consent URL
  (RBAC ``connections.proxy``, P1D-2).
* ``POST /locations/import`` — OAuth-backed bulk location import
  (RBAC ``locations.import``).
* ``POST /locations/import/csv`` — CSV/batch location import without a GBP
  API call; idempotent on google_place_id (RBAC ``locations.import``, P1D-2).

The ``get_connection_service`` seam is overridden in tests so the chain runs
without Postgres, the vault, or Google.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.connections.repository import SqlAlchemyConnectionStore
from app.connections.service import ConnectionService, CsvRow
from app.core.config import settings
from app.core.vault import get_vault
from app.db.session import get_db
from app.gbp.oauth import get_gbp_client
from app.schemas.connections import (
    ConnectionHealthOut,
    ConnectionOut,
    ConnectionStartRequest,
    ConnectionStartResponse,
    CsvImportRequest,
    CsvImportResponse,
    ImportedLocationOut,
    ImportLocationsRequest,
    ImportLocationsResponse,
    OAuthCallbackRequest,
    ProxyConnectRequest,
    ProxyConnectResponse,
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


@router.post("/connections/proxy", response_model=ProxyConnectResponse)
def proxy_connect(
    body: ProxyConnectRequest,
    ctx: RequestContext = Depends(require("connections.proxy")),
    service: ConnectionService = Depends(get_connection_service),
) -> ProxyConnectResponse:
    """Agency-on-behalf connect: mint a guided link to send to the client.

    The project-ownership rule is enforced before the state is minted — a blank
    or platform-matching ``agency_gbp_project_id`` is rejected (PRD §6.3 ON-5).
    The client follows the returned ``guided_link`` and completes normal OAuth
    consent; the callback at ``/connections/oauth/callback`` handles the rest.
    """
    result = service.proxy_connect(
        ctx.tenant_id, body.client_id, body.agency_gbp_project_id
    )
    return ProxyConnectResponse(guided_link=result.consent_url, state=result.state)


@router.get("/connections/{connection_id}/health", response_model=ConnectionHealthOut)
def get_connection_health(
    connection_id: UUID,
    ctx: RequestContext = Depends(require("connections.read")),
    service: ConnectionService = Depends(get_connection_service),
) -> ConnectionHealthOut:
    """Return token status, expiry, scopes and a re-auth URL for a connection.

    Tenant-scoped: a connection owned by another tenant is indistinguishable
    from a non-existent one (returns 404).
    """
    conn = service.get_health(ctx.tenant_id, connection_id)
    reauth_url = f"{settings.frontend_url}/connections/{connection_id}/reauth"
    return ConnectionHealthOut(
        connection_id=conn.id,
        token_status=conn.token_status,
        expires_at=conn.expires_at,
        scopes=list(conn.scopes),
        reauth_url=reauth_url,
    )


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


@router.post("/locations/import/csv", response_model=CsvImportResponse)
def import_locations_csv(
    body: CsvImportRequest,
    ctx: RequestContext = Depends(require("locations.import")),
    service: ConnectionService = Depends(get_connection_service),
    db: Session = Depends(get_db),
) -> CsvImportResponse:
    """CSV/batch location import — no GBP API call; idempotent on google_place_id.

    Accepts up to 500 rows per request.  Rows whose ``google_place_id`` already
    exists for the client are skipped without error (idempotent).
    """
    rows = [
        CsvRow(
            google_place_id=r.google_place_id,
            name=r.name,
            latitude=r.latitude,
            longitude=r.longitude,
        )
        for r in body.rows
    ]
    created = service.import_from_csv(ctx.tenant_id, body.client_id, rows)
    db.commit()
    return CsvImportResponse(
        client_id=body.client_id,
        imported_count=len(created),
        locations=[ImportedLocationOut.model_validate(loc) for loc in created],
    )
