"""The unit the Policy Compliance Engine evaluates: one external write (P3A-2).

Every outbound write to Google (a review *reply*, a review-request campaign, a
post, a profile/listing edit) is described as an :class:`ExternalWrite` before it
leaves the platform. The engine (``app.compliance.engine``) inspects it; the
gateway (``app.compliance.gateway``) is the only sanctioned path that turns an
evaluated action into an actual write, so nothing reaches Google un-checked
(PRD §9.2, schema §7).

The shape is deliberately tiny and provider-agnostic:

* ``action_type`` — what kind of write this is (``review_reply`` / ``review_request``
  / ``post`` / ``listing_edit`` …). Stored verbatim in ``compliance_events.action_type``.
* ``content``     — the human-authored text being written (the reply body, the
  request message, the post copy). This is what the incentive/staff-name/pressure
  linters read.
* ``metadata``    — structured, non-prose fields of the action (campaign send
  mode, any targeting parameters). This is where a *gating* attempt would have to
  smuggle a sentiment-routing field, so the engine inspects it explicitly.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

# Canonical action types (match ``compliance_events.action_type``, schema §7).
ACTION_REVIEW_REPLY = "review_reply"
ACTION_REVIEW_REQUEST = "review_request"
ACTION_POST = "post"
ACTION_LISTING_EDIT = "listing_edit"

#: Write kinds that would *create / edit / delete* a customer review or rating.
#: The Reviews API forbids these (reply-only — CLAUDE.md, PRD §9.1.4); the engine
#: blocks any action carrying one of these types as a defence-in-depth backstop,
#: even though no endpoint is ever built to emit them.
REVIEW_MUTATION_ACTIONS = (
    "review_create",
    "review_edit",
    "review_update",
    "review_delete",
    "rating_edit",
    "rating_update",
)


@dataclass(frozen=True)
class ExternalWrite:
    """A single outbound write, described for policy evaluation.

    ``content`` defaults to empty (a pure listing edit may carry no prose) and
    ``metadata`` to an empty mapping. Frozen so an action cannot be mutated
    between evaluation and execution.
    """

    action_type: str
    content: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
