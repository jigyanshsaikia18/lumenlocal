"""Operator alerting seam (PRD §8 Observability: "alerting on quota exhaustion").

A minimal, injectable sink so subsystems can raise an operator-facing alert without
knowing how it is delivered. P1C-4 uses it for the FT-9 requirement that a metered
job hitting its cap *alerts* the operator (rather than failing silently or
error-storming). Later tickets reuse it for anomaly/token-expiry alerts (D-5, ON-6).

The shape mirrors the rest of the app's seams (cf. ``AuditLogSink``,
``OverrideStore``): a ``Protocol`` plus an in-memory fake for tests and a logging
default for runtime. Real delivery (email / Slack / webhook) is a drop-in
implementation behind the same ``fire`` method.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger("app.alerts")

# Severity levels (kept tiny on purpose).
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"


@dataclass(frozen=True)
class Alert:
    """One operator-facing alert: a stable ``kind``, a human ``summary``, context."""

    kind: str
    severity: str
    summary: str
    context: dict[str, Any] = field(default_factory=dict)


class AlertSink(Protocol):
    """Delivers an :class:`Alert` to operators (mock this in tests)."""

    def fire(self, alert: Alert) -> None: ...


class InMemoryAlertSink:
    """Collects alerts in a list (tests / dry runs)."""

    def __init__(self) -> None:
        self.alerts: list[Alert] = []

    def fire(self, alert: Alert) -> None:
        self.alerts.append(alert)


class LoggingAlertSink:
    """Default runtime sink: emit a structured log line at WARNING/ERROR.

    Good enough to surface on dashboards and trip log-based alerting until a
    richer delivery channel is wired in. Never raises — alerting must not be able
    to take down the path that is trying to warn about a problem.
    """

    def fire(self, alert: Alert) -> None:
        level = logging.ERROR if alert.severity == SEVERITY_CRITICAL else logging.WARNING
        logger.log(
            level,
            "alert kind=%s severity=%s summary=%s context=%s",
            alert.kind, alert.severity, alert.summary, alert.context,
        )


# Process-wide default. Subsystems accept an AlertSink and fall back to this so the
# common path needs no wiring while tests can inject an InMemoryAlertSink.
alert_sink: AlertSink = LoggingAlertSink()
