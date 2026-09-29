"""
decisions.py — Clinician-in-the-Loop Decision Workflow (Phase 10)
==================================================================
Manages alert decisions: accept, dismiss, defer, investigate.

Storage: in-memory (dict keyed by alert_id) for the prototype.
All writes are thread-safe at Python's GIL level for single-process FastAPI.

Decision semantics:
  accept     — Acknowledged. Alert stays visible, monitoring continues.
                Removes from "needs review" queue.
  dismiss    — Suppresses re-alerting for DISMISSAL_COOLDOWN seconds.
                Forces state machine cooldown. Keeps visible but muted.
  defer      — Snoozes for DEFER_MINUTES. The system will re-evaluate and
                re-surface the alert after the snooze expires.
  investigate— Flags for follow-up. No suppression — clinician is actively
                looking into it. Distinguishes from accept.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from alerts.state_machine import ClinicianDecision


# ── Constants ─────────────────────────────────────────────────────────────────

DEFER_MINUTES: int = 15     # How long a defer snooze lasts
DISMISSAL_COOLDOWN: int = 1800  # 30 min — minimum seconds before re-alerting after dismiss


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class AlertDecision:
    """
    One clinician action on one alert episode.
    """
    id: str                             # Unique decision ID
    alert_id: str                       # The alert event ID (or composite patient+timestamp)
    patient_id: str
    decision: str                       # accept | dismiss | defer | investigate
    clinician_id: str                   # Placeholder; future: real user auth
    reason: Optional[str]               # Free-text note
    decided_at: float                   # Unix timestamp
    previous_state: str                 # Alert level before decision
    resulting_state: str                # Alert level after decision (may be same)
    defer_until: Optional[float] = None # Unix timestamp when defer expires

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "alert_id": self.alert_id,
            "patient_id": self.patient_id,
            "decision": self.decision,
            "clinician_id": self.clinician_id,
            "reason": self.reason,
            "decided_at": self.decided_at,
            "decided_at_iso": datetime.fromtimestamp(self.decided_at, tz=timezone.utc).isoformat(),
            "previous_state": self.previous_state,
            "resulting_state": self.resulting_state,
            "defer_until": self.defer_until,
        }
        if self.defer_until:
            d["defer_until_iso"] = datetime.fromtimestamp(self.defer_until, tz=timezone.utc).isoformat()
            d["defer_remaining_seconds"] = max(0.0, round(self.defer_until - time.time(), 1))
        return d


@dataclass
class AlertRecord:
    """
    Tracks an alert episode for a patient: the event + optional decision.
    """
    alert_id: str
    patient_id: str
    from_level: str
    to_level: str
    risk_score: float
    fired_at: float               # Unix timestamp
    fired_at_iso: str
    message: str
    decision: Optional[AlertDecision] = None
    correlation_id: str = ""       # Phase 11

    @property
    def needs_review(self) -> bool:
        """True if the alert is ESCALATED/SUSPECTED and has no decision yet."""
        return (
            self.to_level in ("ESCALATED", "SUSPECTED")
            and self.decision is None
        )

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "patient_id": self.patient_id,
            "from_level": self.from_level,
            "to_level": self.to_level,
            "risk_score": round(self.risk_score, 2),
            "fired_at": self.fired_at,
            "fired_at_iso": self.fired_at_iso,
            "message": self.message,
            "needs_review": self.needs_review,
            "decision": self.decision.to_dict() if self.decision else None,
            "correlation_id": self.correlation_id,
        }


# ── Decision Manager ──────────────────────────────────────────────────────────

class DecisionManager:
    """
    In-memory store for alert records and clinician decisions.
    One instance shared as a singleton via `decision_manager`.
    """

    def __init__(self):
        # alert_id -> AlertRecord
        self._alerts: Dict[str, AlertRecord] = {}
        # patient_id -> [alert_id, ...]  (ordered list of alert_ids)
        self._patient_alerts: Dict[str, List[str]] = {}

    # ── Alert Registration ─────────────────────────────────────────────────

    def register_alert(
        self,
        alert_event,                  # alerts.state_machine.AlertEvent
        correlation_id: str = "",
    ) -> AlertRecord:
        """
        Register a new alert event. Called by the pipeline whenever any
        state transition fires (not just ESCALATED ones).
        """
        alert_id = f"{alert_event.patient_id}-{alert_event.timestamp:.3f}"
        fired_at = time.time()
        record = AlertRecord(
            alert_id=alert_id,
            patient_id=alert_event.patient_id,
            from_level=alert_event.from_level.value,
            to_level=alert_event.to_level.value,
            risk_score=alert_event.risk_score,
            fired_at=fired_at,
            fired_at_iso=datetime.fromtimestamp(fired_at, tz=timezone.utc).isoformat(),
            message=alert_event.message,
            correlation_id=correlation_id,
        )
        self._alerts[alert_id] = record
        self._patient_alerts.setdefault(alert_event.patient_id, []).append(alert_id)
        return record

    # ── Decision Recording ─────────────────────────────────────────────────

    def record_decision(
        self,
        alert_id: str,
        decision: str,
        clinician_id: str = "clinician",
        reason: Optional[str] = None,
        pipeline=None,                 # DeterministicPipeline — to apply SM side-effects
    ) -> AlertDecision:
        """
        Record a clinician decision for an alert.

        Parameters
        ----------
        alert_id     : ID of the alert being acted upon.
        decision     : One of 'accept', 'dismiss', 'defer', 'investigate'.
        clinician_id : Placeholder clinician identifier.
        reason       : Optional free-text note.
        pipeline     : If provided, applies state-machine side-effects.

        Returns
        -------
        AlertDecision
        """
        record = self._alerts.get(alert_id)
        if not record:
            raise KeyError(f"Alert {alert_id} not found")

        decision_lower = decision.lower()
        valid = {"accept", "dismiss", "defer", "investigate"}
        if decision_lower not in valid:
            raise ValueError(f"Invalid decision '{decision}'. Must be one of {valid}")

        now = time.time()
        defer_until = None

        # ── Apply state machine side-effects ───────────────────────────────
        if pipeline:
            sm = pipeline.get_alert_machine(record.patient_id)
            current_level = sm.level.value

            if decision_lower == "dismiss":
                sm.record_clinician_decision(ClinicianDecision.DISMISS)
                resulting_state = "NORMAL"  # SM forces back to NORMAL

            elif decision_lower == "accept":
                sm.record_clinician_decision(ClinicianDecision.ACCEPT)
                resulting_state = sm.level.value  # De-escalated by SM

            elif decision_lower == "defer":
                sm.record_clinician_decision(ClinicianDecision.DEFER)
                defer_until = now + (DEFER_MINUTES * 60)
                resulting_state = current_level  # Alert stays active but snoozed

            elif decision_lower == "investigate":
                # Active investigation — de-escalate urgency
                sm.record_clinician_decision(ClinicianDecision.INVESTIGATE)
                resulting_state = sm.level.value  # De-escalated by SM
            else:
                resulting_state = current_level
        else:
            resulting_state = record.to_level

        alert_decision = AlertDecision(
            id=str(uuid.uuid4()),
            alert_id=alert_id,
            patient_id=record.patient_id,
            decision=decision_lower,
            clinician_id=clinician_id,
            reason=reason,
            decided_at=now,
            previous_state=record.to_level,
            resulting_state=resulting_state,
            defer_until=defer_until,
        )

        record.decision = alert_decision

        # Auto-resolve all other pending alerts for this patient.
        # When a clinician acts on one alert, older unresolved alerts
        # for the same patient are no longer actionable.
        for other_aid in self._patient_alerts.get(record.patient_id, []):
            if other_aid != alert_id:
                other_rec = self._alerts.get(other_aid)
                if other_rec and other_rec.needs_review:
                    other_rec.decision = AlertDecision(
                        id=str(uuid.uuid4()),
                        alert_id=other_aid,
                        patient_id=record.patient_id,
                        decision="auto_resolved",
                        clinician_id="system",
                        reason=f"Superseded by {decision_lower} on alert {alert_id}",
                        decided_at=now,
                        previous_state=other_rec.to_level,
                        resulting_state=other_rec.to_level,
                    )

        return alert_decision

    def auto_resolve_patient_pending(
        self,
        patient_id: str,
        reason: str = "auto-resolved",
    ) -> int:
        """
        Mark all pending (needs_review) alerts for a patient as auto-resolved.
        Called when a patient naturally de-escalates, so stale ESCALATED/SUSPECTED
        records don't linger in the 'needs review' queue.

        Returns the number of alerts resolved.
        """
        resolved = 0
        ids = self._patient_alerts.get(patient_id, [])
        now = time.time()
        for aid in ids:
            record = self._alerts.get(aid)
            if record and record.needs_review:
                record.decision = AlertDecision(
                    id=str(uuid.uuid4()),
                    alert_id=aid,
                    patient_id=patient_id,
                    decision="auto_resolved",
                    clinician_id="system",
                    reason=reason,
                    decided_at=now,
                    previous_state=record.to_level,
                    resulting_state=record.to_level,
                )
                resolved += 1
        return resolved

    # ── Queries ────────────────────────────────────────────────────────────

    def get_alerts_for_patient(self, patient_id: str) -> List[AlertRecord]:
        """Return all alert records for a patient, newest first."""
        ids = self._patient_alerts.get(patient_id, [])
        records = [self._alerts[aid] for aid in ids if aid in self._alerts]
        return list(reversed(records))

    def get_pending_alerts(self) -> List[AlertRecord]:
        """
        Return all undecided ESCALATED/SUSPECTED alerts across the cohort,
        sorted by risk score descending.
        """
        pending = [
            r for r in self._alerts.values()
            if r.needs_review
        ]
        return sorted(pending, key=lambda r: r.risk_score, reverse=True)

    def get_alert(self, alert_id: str) -> Optional[AlertRecord]:
        return self._alerts.get(alert_id)

    def get_latest_alert(self, patient_id: str) -> Optional[AlertRecord]:
        """Return the most recent alert record for a patient."""
        ids = self._patient_alerts.get(patient_id, [])
        if not ids:
            return None
        return self._alerts.get(ids[-1])


# ── Singleton ─────────────────────────────────────────────────────────────────

decision_manager = DecisionManager()
