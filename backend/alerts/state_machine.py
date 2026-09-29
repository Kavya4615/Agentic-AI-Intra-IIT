"""
state_machine.py — Alert State Machine
=======================================
Manages the four-level alert lifecycle for each patient:

    NORMAL ──▶ WATCH ──▶ SUSPECTED ──▶ ESCALATED
                │             │
                ◀────────────◀ (recovery transitions)

Transition rules (must hold for required duration to avoid premature alerts):

  NORMAL → WATCH:      risk > 25 sustained for 60 s
  WATCH → SUSPECTED:   risk > 50 sustained for 90 s
  SUSPECTED → ESCALATED: risk > 72 sustained for 60 s   ← fires LLM + dashboard alert
  SUSPECTED → WATCH:   risk < 35 sustained for 180 s
  WATCH → NORMAL:      risk < 20 sustained for 300 s
  ESCALATED → WATCH:   risk < 30 sustained for 600 s    (auto-downgrade after recovery)
  ESCALATED → NORMAL:  clinician action only            (dismiss / accept)

Suppression rules:
  - Don't re-fire ESCALATED for the same patient within 15 minutes
  - If clinician dismissed same pattern within 30 minutes, stay at SUSPECTED max
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from state.patient_state import AlertLevel


# ── Transition thresholds ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class Transition:
    """Defines a valid state transition with its conditions."""
    from_level: AlertLevel
    to_level:   AlertLevel
    risk_threshold: float      # Risk score required (above or below depending on direction)
    direction: str             # "above" or "below"
    hold_seconds: float        # How long the condition must hold before transitioning


# Hold counts are in number of readings (at 5s/reading: 12 readings = 60s)
TRANSITIONS: List[Transition] = [
    # Deterioration path
    Transition(AlertLevel.NORMAL,    AlertLevel.WATCH,      25,  "above",  12),   # 60s
    Transition(AlertLevel.WATCH,     AlertLevel.SUSPECTED,  50,  "above",  18),   # 90s
    Transition(AlertLevel.SUSPECTED, AlertLevel.ESCALATED,  72,  "above",  12),   # 60s
    # Recovery path
    Transition(AlertLevel.SUSPECTED, AlertLevel.WATCH,      35,  "below",  36),   # 180s
    Transition(AlertLevel.WATCH,     AlertLevel.NORMAL,     20,  "below",  60),   # 300s
    Transition(AlertLevel.ESCALATED, AlertLevel.WATCH,      30,  "below", 120),   # 600s
]

# Suppression (in readings count at 5s/reading)
ESCALATION_COOLDOWN_READINGS = 180    # 15 minutes = 180 readings
DISMISSAL_SUPPRESSION_READINGS = 360  # 30 minutes = 360 readings


class ClinicianDecision(str, Enum):
    """Possible clinician actions on an escalated alert."""
    ACCEPT      = "ACCEPT"       # Acknowledged; will take action
    DISMISS     = "DISMISS"      # Not clinically relevant; suppress
    DEFER       = "DEFER"        # Check again in 10 minutes
    INVESTIGATE = "INVESTIGATE"  # Request more information


@dataclass
class AlertEvent:
    """Represents a meaningful alert state transition."""
    patient_id:     str
    from_level:     AlertLevel
    to_level:       AlertLevel
    risk_score:     float
    timestamp:      float = field(default_factory=time.monotonic)
    message:        str   = ""
    clinician_decision: Optional[ClinicianDecision] = None

    def to_dict(self) -> dict:
        return {
            "patient_id":   self.patient_id,
            "from_level":   self.from_level.value,
            "to_level":     self.to_level.value,
            "risk_score":   round(self.risk_score, 2),
            "timestamp":    self.timestamp,
            "message":      self.message,
            "clinician_decision": self.clinician_decision.value if self.clinician_decision else None,
        }


class AlertStateMachine:
    """
    Manages alert level transitions for one patient.

    On every risk score update, `evaluate()` checks whether any transition
    condition is met and returns an AlertEvent if a transition occurs.
    """

    def __init__(self, patient_id: str):
        self.patient_id  = patient_id
        self.level       = AlertLevel.NORMAL
        self.risk_score  = 0.0
        self._reading_count: int = 0   # Incremented on every evaluate() call

        # Track when (reading number) the threshold condition was first met
        # key = (from_level, to_level), value = reading number when condition started
        self._condition_start: Dict[tuple, Optional[int]] = {}

        # Suppression (reading numbers)
        self._last_escalation_reading: Optional[int] = None
        self._last_dismissal_reading:  Optional[int] = None

        # History of events for audit
        self.event_history: List[AlertEvent] = []

    def evaluate(self, risk_score: float) -> Optional[AlertEvent]:
        """
        Evaluate the current risk score and check for state transitions.

        Parameters
        ----------
        risk_score : float
            Current composite risk score (0–100).

        Returns
        -------
        AlertEvent if a transition occurred, else None.
        """
        self.risk_score = risk_score
        self._reading_count += 1
        now = self._reading_count

        for transition in TRANSITIONS:
            if transition.from_level != self.level:
                continue

            key = (transition.from_level, transition.to_level)

            # Check if the score meets this transition's condition
            condition_met = (
                (transition.direction == "above" and risk_score >= transition.risk_threshold) or
                (transition.direction == "below" and risk_score <  transition.risk_threshold)
            )

            if condition_met:
                # Start or maintain the hold counter
                if self._condition_start.get(key) is None:
                    self._condition_start[key] = now

                held_for = now - self._condition_start[key]

                if held_for >= transition.hold_seconds:
                    # Check suppression before firing ESCALATED
                    if transition.to_level == AlertLevel.ESCALATED:
                        if not self._can_escalate(now):
                            continue

                    # Transition!
                    event = self._do_transition(transition, risk_score)
                    return event
            else:
                # Condition not met — reset hold timer
                self._condition_start[key] = None

        return None

    def _can_escalate(self, now: int) -> bool:
        """Check suppression rules before allowing ESCALATED transition."""
        # Cooldown since last escalation
        if self._last_escalation_reading is not None:
            if now - self._last_escalation_reading < ESCALATION_COOLDOWN_READINGS:
                return False
        # Cooldown since clinician dismissed
        if self._last_dismissal_reading is not None:
            if now - self._last_dismissal_reading < DISMISSAL_SUPPRESSION_READINGS:
                return False
        return True

    def _do_transition(self, transition: Transition, risk_score: float) -> AlertEvent:
        """Execute a transition and record the event."""
        prev_level = self.level
        self.level = transition.to_level

        # Reset hold timers for all transitions from the new level
        keys_to_reset = [k for k in self._condition_start if k[0] != self.level]
        for k in keys_to_reset:
            self._condition_start[k] = None

        if transition.to_level == AlertLevel.ESCALATED:
            self._last_escalation_reading = self._reading_count

        msg = (
            f"Alert level changed: {prev_level.value} → {transition.to_level.value} "
            f"(risk={risk_score:.1f}, held for ≥{transition.hold_seconds}s)"
        )

        event = AlertEvent(
            patient_id=self.patient_id,
            from_level=prev_level,
            to_level=transition.to_level,
            risk_score=risk_score,
            message=msg,
        )
        self.event_history.append(event)
        return event

    def record_clinician_decision(
        self, decision: ClinicianDecision, event: Optional[AlertEvent] = None
    ):
        """
        Record a clinician's action and apply suppression as needed.

        Parameters
        ----------
        decision : ClinicianDecision
        event : AlertEvent, optional
            The event being acted upon. If None, acts on the current state.
        """
        if decision == ClinicianDecision.DISMISS:
            self._last_dismissal_reading = self._reading_count
            # Force back to NORMAL after a dismiss
            self.level = AlertLevel.NORMAL
            # Reset all hold counters
            self._condition_start.clear()

        elif decision == ClinicianDecision.ACCEPT:
            # Acknowledge — de-escalate to WATCH level. The alert is reviewed
            # but the patient remains under observation. Re-escalation requires
            # the condition to re-trigger after a cooldown period.
            if self.level in (AlertLevel.ESCALATED, AlertLevel.SUSPECTED):
                self.level = AlertLevel.WATCH
                self._condition_start.clear()
            self._last_escalation_reading = self._reading_count

        elif decision == ClinicianDecision.DEFER:
            # Snooze escalation for 10 minutes (120 readings)
            self._last_escalation_reading = self._reading_count - (ESCALATION_COOLDOWN_READINGS - 120)

        elif decision == ClinicianDecision.INVESTIGATE:
            # Active investigation — de-escalate urgency to WATCH.
            # Clinician is looking into it; continued urgent alerting unnecessary.
            if self.level in (AlertLevel.ESCALATED, AlertLevel.SUSPECTED):
                self.level = AlertLevel.WATCH
                self._condition_start.clear()
            self._last_escalation_reading = self._reading_count

        if event:
            event.clinician_decision = decision

    def force_level(self, level: AlertLevel):
        """Directly set the alert level (for testing or admin override)."""
        self.level = level
        self._condition_start.clear()

    def to_dict(self) -> dict:
        return {
            "patient_id":               self.patient_id,
            "current_level":            self.level.value,
            "current_risk_score":       round(self.risk_score, 2),
            "reading_count":            self._reading_count,
            "last_escalation_reading":  self._last_escalation_reading,
            "event_count":              len(self.event_history),
            "recent_events": [
                e.to_dict() for e in self.event_history[-5:]
            ],
        }
