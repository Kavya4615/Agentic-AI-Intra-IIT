"""
audit.py — Full Audit Trail (Phase 11)
=======================================
In-memory audit log capturing every event in an escalation episode:

  observation → retrieval → reasoning → alert → decision

Each event carries a correlation_id that ties the full chain together,
enabling per-episode reconstruction via GET /api/audit/{correlation_id}.

Design:
  - In-memory for prototype (list of AuditEntry, indexed by correlation_id
    and patient_id). Production would persist to PostgreSQL.
  - Thread-safe at Python GIL level for single-process FastAPI.
  - correlation_id is generated at the first observation event and propagated
    through the entire episode.
"""

import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any


# ── Event Types ───────────────────────────────────────────────────────────────

class EventType:
    OBSERVATION = "observation"   # Raw + processed vital reading
    RETRIEVAL   = "retrieval"     # RAG: what protocols + context were fetched
    REASONING   = "reasoning"     # LLM: full SBAR generation call + output
    ALERT       = "alert"         # State machine transition event
    DECISION    = "decision"      # Clinician action on alert


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class AuditEntry:
    """One event in the audit log."""
    id: str
    patient_id: str
    timestamp: float                  # Unix timestamp
    timestamp_iso: str
    event_type: str                   # EventType constant
    payload: Dict[str, Any]           # JSON-serialisable event data
    correlation_id: str               # Ties all events in one episode together

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "timestamp": self.timestamp,
            "timestamp_iso": self.timestamp_iso,
            "event_type": self.event_type,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
        }


# ── Audit Logger ──────────────────────────────────────────────────────────────

class AuditLogger:
    """
    In-memory audit log store.
    Provides per-patient and per-correlation-id querying.
    """

    def __init__(self):
        # All entries in insertion order
        self._entries: List[AuditEntry] = []
        # patient_id -> list of entry IDs
        self._patient_index: Dict[str, List[str]] = {}
        # correlation_id -> list of entry IDs
        self._correlation_index: Dict[str, List[str]] = {}

    def generate_correlation_id(self) -> str:
        """Generate a new UUID correlation ID for a new episode."""
        return str(uuid.uuid4())

    def log(
        self,
        patient_id: str,
        event_type: str,
        payload: Dict[str, Any],
        correlation_id: str = "",
    ) -> AuditEntry:
        """
        Record one event in the audit trail.

        Parameters
        ----------
        patient_id     : Patient this event pertains to.
        event_type     : One of EventType constants.
        payload        : JSON-serialisable dict of event data.
        correlation_id : Episode correlation ID (blank = no episode context).

        Returns
        -------
        AuditEntry
        """
        now = time.time()
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            timestamp=now,
            timestamp_iso=datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id or "",
        )

        self._entries.append(entry)

        # Update patient index
        self._patient_index.setdefault(patient_id, []).append(entry.id)

        # Update correlation index
        if correlation_id:
            self._correlation_index.setdefault(correlation_id, []).append(entry.id)

        return entry

    # ── Queries ────────────────────────────────────────────────────────────

    def get_by_patient(
        self,
        patient_id: str,
        from_ts: Optional[float] = None,
        to_ts: Optional[float] = None,
        limit: int = 200,
    ) -> List[AuditEntry]:
        """
        Return audit entries for a patient, optionally filtered by time range.
        Results are chronological.
        """
        ids = self._patient_index.get(patient_id, [])
        # Build a quick id→entry lookup
        lookup = {e.id: e for e in self._entries}
        entries = [lookup[eid] for eid in ids if eid in lookup]

        if from_ts is not None:
            entries = [e for e in entries if e.timestamp >= from_ts]
        if to_ts is not None:
            entries = [e for e in entries if e.timestamp <= to_ts]

        return entries[-limit:]

    def get_by_correlation(self, correlation_id: str) -> List[AuditEntry]:
        """
        Return all events belonging to one escalation episode, chronological.
        """
        ids = self._correlation_index.get(correlation_id, [])
        lookup = {e.id: e for e in self._entries}
        entries = [lookup[eid] for eid in ids if eid in lookup]
        return sorted(entries, key=lambda e: e.timestamp)

    def get_all(self, limit: int = 500) -> List[AuditEntry]:
        """Return the most recent `limit` entries across all patients."""
        return self._entries[-limit:]

    def has_complete_chain(self, correlation_id: str) -> dict:
        """
        Check whether a given episode has a complete audit chain.
        Returns a dict indicating which stages are present.
        """
        entries = self.get_by_correlation(correlation_id)
        types_present = {e.event_type for e in entries}
        required = {
            EventType.OBSERVATION,
            EventType.RETRIEVAL,
            EventType.REASONING,
            EventType.ALERT,
        }
        return {
            "correlation_id": correlation_id,
            "stages_present": list(types_present),
            "is_complete": required.issubset(types_present),
            "missing_stages": list(required - types_present),
            "has_decision": EventType.DECISION in types_present,
            "entry_count": len(entries),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

audit_logger = AuditLogger()
