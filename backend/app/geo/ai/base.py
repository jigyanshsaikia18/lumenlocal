"""The provider-abstraction interface for AI-search visibility (P2C-1).

Every AI surface gets one adapter implementing :class:`AiSearchProvider`. An
adapter has a single real responsibility: turn that provider's native answer
payload into the common :class:`~app.geo.ai.records.AiVisibilityRecord`. The
network call that *obtains* that payload is deliberately deferred to P2C-2 — this
ticket builds the interface and the normalization, and ships one mock provider
(:mod:`app.geo.ai.mock`) so the pipeline has something to run against.

Two methods, split so the testable part needs no I/O:

* :meth:`normalize` — pure: raw payload -> record. This is the contract each
  provider implements and the part P2C-1's tests exercise directly.
* :meth:`fetch` — the (future) network call. The base raises ``NotImplementedError``
  so no adapter can accidentally reach the live provider before P2C-2 wires up
  real calls under the Policy Compliance Engine and the scanning-ToS caveat
  (``/docs/01_PRD.md §11.1`` — we do **not** claim "fully compliant" for GEO
  scanning yet). :meth:`query` is the template tying the two together.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from app.geo.ai.records import AiVisibilityRecord, Provider


class AiSearchProvider(ABC):
    """Adapter contract: normalize one provider's answer into a common record.

    Subclasses set :attr:`provider` (class- or instance-level) and implement
    :meth:`normalize`. They get :meth:`query` for free.
    """

    #: Which AI surface this adapter speaks for. Set by each concrete adapter.
    provider: Provider

    @abstractmethod
    def normalize(
        self,
        raw: Mapping[str, Any],
        *,
        business_name: str,
    ) -> AiVisibilityRecord:
        """Collapse this provider's native ``raw`` answer into a record.

        Args:
            raw: The provider's native response payload (decoded JSON/dict).
            business_name: The tracked business to look for in the answer.

        Returns:
            An :class:`AiVisibilityRecord` tagged with :attr:`provider`.
        """

    def query(self, prompt: str, *, business_name: str) -> AiVisibilityRecord:
        """Fetch ``prompt`` from the provider and normalize the answer.

        Template method: :meth:`fetch` (I/O) then :meth:`normalize` (pure). The
        business is *not* sent to the provider — we ask the public prompt and
        look for the business in whatever the AI returns, exactly as a user would.
        """
        return self.normalize(self.fetch(prompt), business_name=business_name)

    def fetch(self, prompt: str) -> Mapping[str, Any]:
        """Return the provider's raw answer for ``prompt`` (network call).

        Not implemented in P2C-1: real provider calls land in P2C-2, where they
        must respect rate limits and the scanning ToS (``/docs/01_PRD.md §11.1``).
        The mock provider overrides this with an offline, deterministic payload.
        """
        raise NotImplementedError(
            f"{type(self).__name__} cannot reach {getattr(self.provider, 'value', '?')} "
            "yet — live provider calls arrive in P2C-2; use a mock until then."
        )
