"""
agent_service.py — Agentic Layer Service
==========================================
Singleton service that bridges the deterministic alert pipeline (Phase 6)
to the agentic LLM reasoning layer (Phase 7).

Phase 9 update:
  - Fetches the static PatientContext for the patient before calling RAG.
  - Passes context into rag.retrieve_with_context() → both protocol text and
    context are injected into the LLM prompt.
  - Logs the retrieval event to the audit trail (Phase 11).

On every ESCALATED alert event, this service:
  1. Builds an ExplanationRequest from the pipeline context.
  2. Fetches the patient's static clinical context.
  3. Queries the RAG knowledge base for relevant protocols + context.
  4. Invokes the ClinicalReasoningAgent to generate a structured SBAR.
  5. Caches the last explanation per patient for REST API retrieval.
"""

import asyncio
import time
from typing import Dict, Optional

from alerts.state_machine import AlertEvent
from state.patient_state import AlertLevel, PatientState
from agent.rag import ClinicalKnowledgeBase
from agent.reasoning import ClinicalReasoningAgent
from agent.schemas import ExplanationRequest, SBARResponse
from agent.patient_context import PatientContext


class AgentService:
    """
    Singleton service that wraps the RAG + LLM reasoning pipeline.
    Thread-safe via asyncio (all calls are scheduled on the event loop).
    """

    def __init__(self):
        self._kb = ClinicalKnowledgeBase()
        self._agent = ClinicalReasoningAgent()
        # Cache: patient_id -> (SBARResponse, timestamp)
        self._explanation_cache: Dict[str, tuple] = {}
        # Track which patients are currently being processed (prevents duplicate calls)
        self._in_flight: set = set()

    def _build_trend_summary(self, state: PatientState) -> str:
        """Produce a short human-readable trend summary from patient state."""
        lines = []
        if hasattr(state, "trend_report") and state.trend_report:
            tr = state.trend_report
            for ch, slope in getattr(tr, "slopes", {}).items():
                if abs(slope) > 0.1:
                    direction = "rising" if slope > 0 else "falling"
                    lines.append(f"{ch}: {direction} ({slope:+.2f}/min)")
        if not lines:
            # Fallback: compute simple direction from risk score history
            hist = list(state.risk_score_history)[-10:] if state.risk_score_history else []
            if len(hist) >= 2:
                delta = hist[-1] - hist[0]
                lines.append(
                    f"Risk score {'rising' if delta > 0 else 'falling'} "
                    f"({delta:+.1f} over last {len(hist)} readings)"
                )
            else:
                lines.append("Insufficient trend data.")
        return "; ".join(lines)

    def _build_vitals_snapshot(self, state: PatientState) -> dict:
        """Extract the latest vitals from patient state."""
        snapshot = {}
        for channel in ["heart_rate", "spo2", "respiratory_rate", "systolic_bp", "diastolic_bp"]:
            arr = state.get_channel_array(channel)
            if len(arr) > 0:
                snapshot[channel] = round(float(arr[-1]), 1)
        return snapshot

    def _get_patient_context(self, patient_id: str) -> Optional[PatientContext]:
        """Fetch the static PatientContext for a patient."""
        try:
            from simulator.patient_context_data import get_patient_context
            return get_patient_context(patient_id)
        except Exception as e:
            print(f"  [AgentService] Could not load context for {patient_id}: {e}")
            return None

    async def handle_escalation(
        self,
        alert_event: AlertEvent,
        patient_state: PatientState,
        scenario: str,
        audit_logger=None,        # Phase 11: optional audit logger
        correlation_id: str = "",  # Phase 11: correlation ID for the episode
    ) -> Optional[SBARResponse]:
        """
        Asynchronously generate a clinical SBAR explanation for an ESCALATED alert.
        Returns the SBARResponse, or None if generation fails.

        Parameters
        ----------
        alert_event    : The ESCALATED AlertEvent from the state machine.
        patient_state  : The current PatientState (for vitals and trends).
        scenario       : The patient's clinical scenario string (e.g. 'gradual_deterioration').
        audit_logger   : Optional AuditLogger instance (Phase 11).
        correlation_id : Correlation ID tying this episode together (Phase 11).
        """
        pid = alert_event.patient_id

        # Prevent duplicate in-flight calls for the same patient
        if pid in self._in_flight:
            return self._explanation_cache.get(pid, (None,))[0]

        self._in_flight.add(pid)
        try:
            # Build the explanation request
            vitals = self._build_vitals_snapshot(patient_state)
            trend_summary = self._build_trend_summary(patient_state)

            request = ExplanationRequest(
                patient_id=pid,
                scenario=scenario,
                alert_state=alert_event.to_level.value,
                current_vitals=vitals,
                risk_score=round(alert_event.risk_score, 1),
                recent_trend_summary=trend_summary,
            )

            # ── Phase 9: Retrieve context + protocols ─────────────────────────
            patient_context = self._get_patient_context(pid)
            knowledge_base, protocol_names = self._kb.retrieve_with_context(
                query=scenario,
                patient_context=patient_context,
            )

            # ── Phase 11: Log retrieval event ─────────────────────────────────
            if audit_logger:
                retrieved_snippets = {
                    "protocol_names": protocol_names,
                    "context_available": patient_context is not None,
                    "knowledge_base_length": len(knowledge_base),
                }
                audit_logger.log(
                    patient_id=pid,
                    event_type="retrieval",
                    payload={
                        "query": scenario,
                        "retrieved": retrieved_snippets,
                    },
                    correlation_id=correlation_id,
                )

            # ── Run LLM inference in a thread pool ────────────────────────────
            loop = asyncio.get_event_loop()
            sbar = await loop.run_in_executor(
                None,
                lambda: self._agent.generate_explanation(
                    request=request,
                    knowledge_base=knowledge_base,
                    protocol_names=protocol_names,
                ),
            )

            # ── Phase 11: Log reasoning output ───────────────────────────────
            if audit_logger:
                audit_logger.log(
                    patient_id=pid,
                    event_type="reasoning",
                    payload={"sbar": sbar.model_dump()},
                    correlation_id=correlation_id,
                )

            # Cache the result
            self._explanation_cache[pid] = (sbar, time.monotonic())
            return sbar

        except Exception as e:
            print(f"  [AgentService] ERROR generating explanation for {pid}: {e}")
            return None
        finally:
            self._in_flight.discard(pid)

    def get_cached_explanation(self, patient_id: str) -> Optional[SBARResponse]:
        """Return the last cached explanation for a patient, or None."""
        entry = self._explanation_cache.get(patient_id)
        return entry[0] if entry else None

    def get_cached_explanation_age(self, patient_id: str) -> Optional[float]:
        """Return how many seconds ago the last explanation was generated."""
        entry = self._explanation_cache.get(patient_id)
        return round(time.monotonic() - entry[1], 1) if entry else None


# Global singleton — instantiated once at server startup
agent_service = AgentService()
