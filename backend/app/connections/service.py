"""Connection service: OAuth connect, token vaulting, location import (P1D-1/P1D-2).

Operations:

* :meth:`ConnectionService.start` — validate client in tenant, mint signed state,
  return Google consent URL (self-serve).
* :meth:`ConnectionService.proxy_connect` — same as start but enforces the
  project-ownership rule before minting the state (agency-proxy, P1D-2).
* :meth:`ConnectionService.handle_callback` — verify state, exchange code, vault
  the raw token; the DB row keeps only the opaque ``token_ref``.
* :meth:`ConnectionService.import_locations` — OAuth-backed bulk import.
* :meth:`ConnectionService.import_from_csv` — CSV/batch import; no GBP API call;
  idempotent on ``google_place_id`` (P1D-2).

Scope is enforced against the caller's tenant on every operation.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import jwt

from app.connections.repository import ConnectionStore
from app.core.config import settings
from app.core.errors import APIError
from app.core.security import create_oauth_state, decode_token
from app.core.vault import TokenVault
from app.gbp.oauth import GbpOAuthClient, OAuthToken
from app.models.connection import GbpConnection
from app.models.location import Location

_VALID_METHODS = ("self_serve", "agency_proxy")


@dataclass(frozen=True)
class CsvRow:
    """Lightweight DTO for one CSV import row (mirrors ``CsvLocationRow``)."""

    google_place_id: str
    name: str = ""
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class StartResult:
    """Output of ``start``: where to send the client and the bound state token."""

    consent_url: str
    state: str


class ConnectionService:
    """Compose the GBP client, the vault, and the DB store into the connect flow."""

    def __init__(
        self, store: ConnectionStore, vault: TokenVault, gbp: GbpOAuthClient
    ) -> None:
        self._store = store
        self._vault = vault
        self._gbp = gbp

    # -- step 1a: self-serve start ----------------------------------------------
    def start(
        self, tenant_id: UUID, client_id: UUID, connect_method: str = "self_serve"
    ) -> StartResult:
        if connect_method not in _VALID_METHODS:
            raise APIError(
                400, "invalid_connect_method",
                f"connect_method must be one of {_VALID_METHODS}",
                {"connect_method": connect_method},
            )
        self._assert_client_in_tenant(tenant_id, client_id)
        state = create_oauth_state(str(tenant_id), str(client_id), connect_method)
        return StartResult(consent_url=self._gbp.consent_url(state), state=state)

    # -- step 1b: agency-proxy start (project-ownership guard) -----------------
    def proxy_connect(
        self,
        tenant_id: UUID,
        client_id: UUID,
        agency_gbp_project_id: str,
    ) -> StartResult:
        """Mint a guided consent link for an agency-on-behalf flow.

        The **project-ownership rule** (PRD §6.3 ON-5, PRD §9.1 rule 5) is
        enforced here: the agency must supply a non-empty project ID that is
        not the platform's own project, proving they hold their own
        Google-approved GBP API project.
        """
        if not agency_gbp_project_id.strip():
            raise APIError(
                400,
                "project_id_required",
                "agency_gbp_project_id is required.  Each agency must operate "
                "under their own Google-approved GBP project (PRD §6.3 ON-5).",
                {"field": "agency_gbp_project_id"},
            )
        if (
            settings.platform_gbp_project_id
            and agency_gbp_project_id == settings.platform_gbp_project_id
        ):
            raise APIError(
                422,
                "project_ownership_violation",
                "The supplied project ID matches the platform's own GBP project. "
                "Agencies may not route client access through the platform's project "
                "(PRD §9.1 rule 5 — Google project-ownership policy).",
                {"field": "agency_gbp_project_id"},
            )

        self._assert_client_in_tenant(tenant_id, client_id)
        state = create_oauth_state(
            str(tenant_id),
            str(client_id),
            "agency_proxy",
            agency_gbp_project_id=agency_gbp_project_id,
        )
        return StartResult(consent_url=self._gbp.consent_url(state), state=state)

    # -- step 2: callback (vault the token, store only a ref) -------------------
    async def handle_callback(self, state: str, code: str) -> GbpConnection:
        claims = self._verify_state(state)
        tenant_id = UUID(claims["tenant_id"])
        client_id = UUID(claims["client_id"])
        connect_method = claims["connect_method"]
        # Carry through the project ID minted at proxy_connect so it is stored
        # as evidence the ownership rule was checked (PRD §6.3 ON-5).
        agency_gbp_project_id: str | None = claims.get("agency_gbp_project_id")

        # Defend the binding even if a state was minted before a client moved tenants.
        self._assert_client_in_tenant(tenant_id, client_id)

        token: OAuthToken = await self._gbp.exchange_code(code)

        # COMPLIANCE: the raw token is written to the vault ONLY; the DB gets a ref.
        token_ref = f"gbp/{client_id}/{uuid4().hex}"
        await self._vault.set_secret(token_ref, token.serialize())

        connection = GbpConnection(
            client_id=client_id,
            connect_method=connect_method,
            token_ref=token_ref,
            scopes=list(token.scopes),
            token_status="healthy",
            expires_at=token.expires_at,
            agency_gbp_project_id=agency_gbp_project_id,
        )
        return self._store.add_connection(connection)

    # -- step 3: import locations ----------------------------------------------
    async def import_locations(
        self, tenant_id: UUID, connection_id: UUID
    ) -> list[Location]:
        connection = self._store.get_connection(connection_id)
        if connection is None:
            raise APIError(404, "connection_not_found", "Connection not found")
        # Cross-tenant access is indistinguishable from "not found".
        if self._store.tenant_id_for_client(connection.client_id) != tenant_id:
            raise APIError(404, "connection_not_found", "Connection not found")

        raw = await self._vault.get_secret(connection.token_ref)
        token = OAuthToken.deserialize(raw)
        remote = await self._gbp.list_locations(token)

        existing = self._store.existing_place_ids(connection.client_id)
        imported: list[Location] = []
        for r in remote:
            if r.google_place_id in existing:
                continue  # idempotent: a re-import does not duplicate locations
            location = self._store.add_location(
                Location(
                    tenant_id=tenant_id,
                    client_id=connection.client_id,
                    google_place_id=r.google_place_id,
                    latitude=r.latitude,
                    longitude=r.longitude,
                    profile_data_live=r.profile_data or {},
                )
            )
            existing.add(r.google_place_id)
            imported.append(location)
        return imported

    # -- step 4: CSV / batch import (P1D-2) ------------------------------------
    def import_from_csv(
        self,
        tenant_id: UUID,
        client_id: UUID,
        rows: list[CsvRow],
    ) -> list[Location]:
        """Insert locations from a CSV/batch payload; no GBP API call required.

        Idempotent on ``google_place_id``: rows whose place-id already exists
        for this client are silently skipped.  Tenant-scoped: a client in
        another tenant is reported as not found (cross-tenant guard).
        """
        if self._store.tenant_id_for_client(client_id) != tenant_id:
            raise APIError(404, "client_not_found", "Client not found")

        existing = self._store.existing_place_ids(client_id)
        imported: list[Location] = []
        for row in rows:
            if row.google_place_id in existing:
                continue
            profile: dict = {"name": row.name} if row.name else {}
            location = self._store.add_location(
                Location(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    google_place_id=row.google_place_id,
                    latitude=row.latitude,
                    longitude=row.longitude,
                    profile_data_live=profile,
                )
            )
            existing.add(row.google_place_id)
            imported.append(location)
        return imported

    # -- helpers ----------------------------------------------------------------
    def _assert_client_in_tenant(self, tenant_id: UUID, client_id: UUID) -> None:
        if self._store.tenant_id_for_client(client_id) != tenant_id:
            # A client outside the caller's tenant is reported as not found.
            raise APIError(404, "client_not_found", "Client not found")

    def _verify_state(self, state: str) -> dict:
        try:
            claims = decode_token(state)
        except jwt.InvalidTokenError as exc:
            raise APIError(400, "invalid_state", "OAuth state is invalid or expired") from exc
        if claims.get("type") != "oauth_state":
            raise APIError(400, "invalid_state", "OAuth state is invalid or expired")
        return claims
