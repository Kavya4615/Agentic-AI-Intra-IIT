"""
pipeline.py — Deterministic Core Pipeline
==========================================
Wires together Phases 3-6 into a single processing pipeline:

  Incoming reading
      │
      ▼
  [Preprocessor]    ← artifact / spike filter
      │
      ▼
  [State Engine]    ← update rolling window & baseline
      │
      ▼
  [Trend Detector]  ← compute slopes, deviation, persistence
      │
      ▼
  [Risk Scorer]     ← composite 0-100 score
      │
      ▼
  [Alert SM]        ← state transitions + suppression
      │
      ▼
  AlertEvent (if transition occurred) → upstream (LLM agent / dashboard)

This module is imported by the FastAPI ingestion gateway so every
incoming WebSocket reading flows through the full pipeline automatically.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from alerts.state_machine import AlertEvent, AlertStateMachine, ClinicianDecision
from engine.preprocessor import FilterResult, filter_reading
from engine.risk_scorer import RiskScore, compute_risk_score
from engine.trend_detector import TrendReport, analyse_patient_trends
from simulator.patients import get_all_patients
from state.patient_state import PatientState, StateManager, state_manager


@dataclass
class PipelineResult:
    """Full output of one pipeline cycle for one patient."""
    patient_id:    str
    filter_result: FilterResult
    risk_score:    Optional[RiskScore]  = None
    trend_report:  Optional[TrendReport] = None
    alert_event:   Optional[AlertEvent] = None
    skipped:       bool = False     # True when reading was an artifact

    def to_dict(self) -> dict:
        return {
            "patient_id":    self.patient_id,
            "skipped":       self.skipped,
            "is_artifact":   self.filter_result.is_artifact,
            "risk_score":    self.risk_score.to_dict() if self.risk_score else None,
            "alert_event":   self.alert_event.to_dict() if self.alert_event else None,
        }


class DeterministicPipeline:
    """
    Singleton pipeline that processes every incoming vital reading
    through the full deterministic core.
    """

    def __init__(self, sm: StateManager):
        self.state_manager = sm
        # One state machine per patient
        self._alert_machines: Dict[str, AlertStateMachine] = {}

    def _get_alert_machine(self, patient_id: str) -> AlertStateMachine:
        if patient_id not in self._alert_machines:
            self._alert_machines[patient_id] = AlertStateMachine(patient_id)
        return self._alert_machines[patient_id]

    def process(self, reading: dict) -> PipelineResult:
        """
        Run one reading through the full pipeline.

        Parameters
        ----------
        reading : dict
            Raw reading from the WebSocket / embedded simulator.

        Returns
        -------
        PipelineResult
        """
        pid = reading.get("patient_id", "")

        # ── Step 1: Pre-processing / artifact filter ──────────────────────────
        state = self.state_manager.get_state(pid)
        channel_history = {}
        if state:
            channel_history = {
                ch: state.get_channel_array(ch)
                for ch in ["heart_rate", "spo2", "respiratory_rate", "systolic_bp", "diastolic_bp"]
            }

        filter_result = filter_reading(reading, channel_history)

        # Artifacts go no further — don't pollute trends or scores
        if filter_result.is_artifact:
            # Still update state so artifact count is tracked
            if state:
                state.update(reading)
            return PipelineResult(
                patient_id=pid,
                filter_result=filter_result,
                skipped=True,
            )

        # ── Step 2: Update patient state ──────────────────────────────────────
        updated_state = self.state_manager.update(reading)
        if updated_state is None:
            # Unknown patient — ignore
            return PipelineResult(patient_id=pid, filter_result=filter_result, skipped=True)

        # ── Step 3: Trend detection ───────────────────────────────────────────
        trend_report = analyse_patient_trends(updated_state)

        # ── Step 4: Risk scoring ──────────────────────────────────────────────
        risk_score = compute_risk_score(trend_report)

        # Update state with the latest risk score
        updated_state.current_risk_score = risk_score.risk_score
        updated_state.risk_score_history.append(risk_score.risk_score)

        # ── Step 5: Alert state machine ───────────────────────────────────────
        alert_machine = self._get_alert_machine(pid)
        alert_event   = alert_machine.evaluate(risk_score.risk_score)

        # Sync alert level back to patient state
        updated_state.set_alert_level(alert_machine.level)

        return PipelineResult(
            patient_id=pid,
            filter_result=filter_result,
            risk_score=risk_score,
            trend_report=trend_report,
            alert_event=alert_event,
        )

    def record_clinician_decision(
        self, patient_id: str, decision: str
    ):
        """Forward a clinician's decision to the relevant alert state machine."""
        machine = self._get_alert_machine(patient_id)
        try:
            dec = ClinicianDecision(decision.upper())
            machine.record_clinician_decision(dec)
        except ValueError:
            pass

    def get_alert_machine(self, patient_id: str) -> AlertStateMachine:
        return self._get_alert_machine(patient_id)


# Global singleton — initialised once at startup
def create_pipeline() -> DeterministicPipeline:
    """Create and return the pipeline, initialising all patient states."""
    state_manager.initialize_all()
    return DeterministicPipeline(state_manager)
