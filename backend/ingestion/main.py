"""
main.py — FastAPI Ingestion Gateway
=====================================
The central web server that:
1. Accepts WebSocket connections from the simulator (one per patient)
2. Validates incoming vital sign data using Pydantic schemas
3. Forwards validated readings to the Patient State Engine
4. Provides REST endpoints for querying patient data
5. Broadcasts updates to frontend dashboard clients

Phases 9–11 additions:
  Phase 9:  GET  /api/patients/{id}/context
  Phase 10: POST /api/patients/{id}/alerts/{alert_id}/decision
            GET  /api/patients/{id}/alerts
            GET  /api/alerts/pending
  Phase 11: GET  /api/patients/{id}/audit
            GET  /api/audit/{correlation_id}

Architecture:
  Simulator ──WebSocket──▶ Ingestion Gateway ──▶ State Engine ──▶ Risk Engine
                                │
                                ├── REST API ──▶ Frontend
                                └── WS Broadcast ──▶ Dashboard
"""

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic import ValidationError

from ingestion.schemas import (
    VitalReadingMessage,
    PatientProfileResponse,
    VitalHistoryResponse,
    SystemStatusResponse,
)
from simulator.patients import get_all_patients, get_patient_by_id
from alerts.pipeline import DeterministicPipeline, create_pipeline
from alerts.decisions import decision_manager, DecisionManager
from state.patient_state import AlertLevel, state_manager
from agent.agent_service import agent_service
from database.audit import audit_logger, EventType

load_dotenv()

# Global deterministic pipeline (initialised at startup)
_pipeline: Optional[DeterministicPipeline] = None

# =============================================================================
#  Application Setup
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline
    _pipeline = create_pipeline()

    api_key_set = bool(os.getenv("OPENAI_API_KEY"))
    print()
    print("=" * 70)
    print("  CLINICAL DECISION-SUPPORT - INGESTION GATEWAY v2.0")
    print("=" * 70)
    print("  WebSocket endpoints:")
    print("    /ws/vitals/{patient_id}  - Simulator -> Server (per patient)")
    print("    /ws/dashboard            - Server -> Dashboard (broadcasts)")
    print("  REST endpoints (core):")
    print("    GET  /api/status                           - System status")
    print("    GET  /api/patients                         - All patient profiles")
    print("    GET  /api/patients/{id}                    - Single patient + vitals")
    print("    GET  /api/patients/{id}/vitals             - Recent vital history")
    print("    GET  /api/vitals/latest                    - Latest vitals all patients")
    print("  Phase 7/9:")
    print("    GET  /api/patients/{id}/explanation        - Latest SBAR (with context)")
    print("    POST /api/patients/{id}/explanation/trigger- Manually trigger SBAR")
    print("  Phase 9:")
    print("    GET  /api/patients/{id}/context            - Static clinical context")
    print("  Phase 10:")
    print("    POST /api/patients/{id}/alerts/{aid}/decision - Clinician decision")
    print("    GET  /api/patients/{id}/alerts             - Alert list + decisions")
    print("    GET  /api/alerts/pending                   - Needs-review queue")
    print("  Phase 11:")
    print("    GET  /api/patients/{id}/audit              - Patient audit log")
    print("    GET  /api/audit/{correlation_id}           - Full episode chain")
    print("    GET  /api/audit                            - Recent audit entries")
    print("=" * 70)
    print(f"  AI Agent: {'LIVE (OpenAI)' if api_key_set else 'MOCK (no OPENAI_API_KEY set)'}")
    print("=" * 70)
    print()

    simulator_task = asyncio.create_task(_run_embedded_simulator())
    yield
    simulator_task.cancel()

app = FastAPI(
    title="Clinical Decision-Support — Ingestion Gateway",
    description="Real-time vital sign ingestion and streaming for patient monitoring.",
    version="2.0.0",
    lifespan=lifespan,
)

# Allow CORS for the React frontend (will run on a different port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
#  Pydantic request bodies (Phase 10)
# =============================================================================

class DecisionRequest(BaseModel):
    decision: str = Field(
        ...,
        description="One of: accept | dismiss | defer | investigate"
    )
    clinician_id: Optional[str] = Field(
        default="clinician",
        description="Clinician identifier (placeholder for demo)"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Optional free-text note for the decision"
    )


# =============================================================================
#  In-Memory State
# =============================================================================

class ConnectionManager:
    """
    Manages WebSocket connections and in-memory vital sign storage.
    
    Two types of WebSocket clients:
    1. Simulator connections — send vital data IN (one per patient)
    2. Dashboard connections — receive broadcasts OUT (one per dashboard client)
    """

    def __init__(self):
        # Simulator connections: patient_id → WebSocket
        self.patient_connections: Dict[str, WebSocket] = {}

        # Dashboard broadcast connections
        self.dashboard_connections: Set[WebSocket] = set()

        # In-memory vital history: patient_id → deque of readings (last 200)
        self.vital_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))

        # Statistics
        self.total_readings: int = 0
        self.start_time: float = time.monotonic()

        # Latest reading per patient (for quick access)
        self.latest_readings: Dict[str, dict] = {}

    async def connect_patient(self, patient_id: str, websocket: WebSocket):
        """Accept a simulator WebSocket connection for a patient."""
        await websocket.accept()
        self.patient_connections[patient_id] = websocket
        print(f"  ✓ Patient {patient_id} connected via WebSocket")

    def disconnect_patient(self, patient_id: str):
        """Handle simulator disconnection."""
        self.patient_connections.pop(patient_id, None)
        print(f"  ✗ Patient {patient_id} disconnected")

    async def connect_dashboard(self, websocket: WebSocket):
        """Accept a dashboard WebSocket connection."""
        await websocket.accept()
        self.dashboard_connections.add(websocket)
        print(f"  ✓ Dashboard client connected (total: {len(self.dashboard_connections)})")

    def disconnect_dashboard(self, websocket: WebSocket):
        """Handle dashboard client disconnection."""
        self.dashboard_connections.discard(websocket)
        print(f"  ✗ Dashboard client disconnected (remaining: {len(self.dashboard_connections)})")

    async def process_reading(self, patient_id: str, reading: dict, scenario: str = ""):
        """
        Process a validated vital reading:
        1. Run through the deterministic pipeline (preprocessor -> risk -> alert SM)
        2. Store in history and update latest reading
        3. Broadcast vital update to all dashboard clients
        4. If an ESCALATED transition fires, trigger the agentic reasoning layer
        5. Phase 11: Log observation + alert events to audit trail
        """
        global _pipeline

        alert_event = None
        correlation_id = ""

        # ── Deterministic pipeline ────────────────────────────────────────────
        if _pipeline:
            result = _pipeline.process(reading)
            if result.alert_event:
                alert_event = result.alert_event
                reading["_alert_event"] = result.alert_event.to_dict()
            if result.risk_score:
                reading["_risk_score"] = round(result.risk_score.risk_score, 2)

        self.vital_history[patient_id].append(reading)
        self.latest_readings[patient_id] = reading
        self.total_readings += 1

        # ── Phase 11: Log observation ─────────────────────────────────────────
        vitals_payload = reading.get("vitals", {})
        risk_score_val = reading.get("_risk_score", 0)

        # Only log every 5th observation to avoid flooding (adjust as needed)
        if self.total_readings % 5 == 0 or alert_event:
            audit_logger.log(
                patient_id=patient_id,
                event_type=EventType.OBSERVATION,
                payload={
                    "vitals": vitals_payload,
                    "risk_score": risk_score_val,
                    "reading_number": reading.get("reading_number"),
                    "timestamp": reading.get("timestamp"),
                },
                correlation_id=correlation_id,
            )

        # ── Broadcast vital update ────────────────────────────────────────────
        broadcast_msg = json.dumps({
            "type": "vital_update",
            "data": reading
        })
        disconnected = set()
        for ws in self.dashboard_connections:
            try:
                await ws.send_text(broadcast_msg)
            except Exception:
                disconnected.add(ws)
        self.dashboard_connections -= disconnected

        # ── Phase 10: Register alert in decision manager ──────────────────────
        if alert_event:
            # Generate correlation ID for this episode
            correlation_id = audit_logger.generate_correlation_id()

            # Phase 11: Log alert state transition
            audit_logger.log(
                patient_id=patient_id,
                event_type=EventType.ALERT,
                payload={
                    "from_level": alert_event.from_level.value,
                    "to_level": alert_event.to_level.value,
                    "risk_score": round(alert_event.risk_score, 2),
                    "message": alert_event.message,
                },
                correlation_id=correlation_id,
            )

            decision_manager.register_alert(alert_event, correlation_id=correlation_id)

            # ── Agentic reasoning on ESCALATED transitions ──────────────────
            if alert_event.to_level == AlertLevel.ESCALATED:
                patient_state = state_manager.get_state(patient_id)
                if patient_state:
                    print(f"  [Agent] ESCALATED alert for {patient_id} — generating SBAR...")
                    asyncio.create_task(
                        agent_service.handle_escalation(
                            alert_event=alert_event,
                            patient_state=patient_state,
                            scenario=scenario or "",
                            audit_logger=audit_logger,
                            correlation_id=correlation_id,
                        )
                    )

            # Broadcast alert event to dashboard (include decision context)
            alert_msg = json.dumps({
                "type": "alert_event",
                "data": {
                    **alert_event.to_dict(),
                    "correlation_id": correlation_id,
                }
            })
            stale = set()
            for ws in self.dashboard_connections:
                try:
                    await ws.send_text(alert_msg)
                except Exception:
                    stale.add(ws)
            self.dashboard_connections -= stale

    def get_patient_history(self, patient_id: str, limit: int = 50) -> List[dict]:
        """Get the most recent readings for a patient."""
        history = list(self.vital_history.get(patient_id, []))
        return history[-limit:]

    def get_all_latest(self) -> Dict[str, dict]:
        """Get the latest reading for every connected patient."""
        return dict(self.latest_readings)


# Global connection manager instance
manager = ConnectionManager()


# =============================================================================
#  WebSocket Endpoints
# =============================================================================

@app.websocket("/ws/vitals/{patient_id}")
async def websocket_vitals(websocket: WebSocket, patient_id: str):
    """
    WebSocket endpoint for receiving vital signs from the simulator.
    
    One connection per patient. The simulator sends JSON vital readings
    continuously, and this endpoint validates and processes each one.
    """
    await manager.connect_patient(patient_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()

            try:
                raw = json.loads(data)
                reading = VitalReadingMessage(**raw)

                if reading.patient_id != patient_id:
                    await websocket.send_text(json.dumps({
                        "error": f"Patient ID mismatch: URL={patient_id}, message={reading.patient_id}"
                    }))
                    continue

                patient_profile = get_patient_by_id(patient_id)
                scenario = patient_profile.scenario if patient_profile else ""

                await manager.process_reading(patient_id, raw, scenario=scenario)

            except (json.JSONDecodeError, ValidationError) as e:
                await websocket.send_text(json.dumps({
                    "error": f"Invalid reading: {str(e)}"
                }))

    except WebSocketDisconnect:
        manager.disconnect_patient(patient_id)


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """
    WebSocket endpoint for the clinician dashboard.
    
    Dashboard clients connect here to receive real-time broadcasts
    of vital sign updates and alert events for all patients.
    """
    await manager.connect_dashboard(websocket)
    try:
        # Send initial state: all patient profiles + latest vitals
        initial_state = {
            "type": "initial_state",
            "data": {
                "patients": [p.to_dict() for p in get_all_patients()],
                "latest_vitals": manager.get_all_latest(),
            }
        }
        await websocket.send_text(json.dumps(initial_state))

        while True:
            msg = await websocket.receive_text()
            try:
                command = json.loads(msg)
                cmd_type = command.get("type", "")

                if cmd_type == "clinician_decision":
                    print(f"  📋 Clinician decision: {command.get('data', {})}")

                elif cmd_type == "request_history":
                    pid = command.get("patient_id", "")
                    limit = command.get("limit", 50)
                    history = manager.get_patient_history(pid, limit)
                    await websocket.send_text(json.dumps({
                        "type": "vital_history",
                        "patient_id": pid,
                        "data": history
                    }))

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)


# =============================================================================
#  REST API — Core Endpoints
# =============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Clinical Decision-Support Ingestion Gateway"}


@app.get("/api/status", response_model=SystemStatusResponse, tags=["System"])
async def system_status():
    """Get the current system status and statistics."""
    return SystemStatusResponse(
        status="running",
        connected_patients=len(manager.patient_connections),
        total_readings_received=manager.total_readings,
        uptime_seconds=round(time.monotonic() - manager.start_time, 1),
        patients=list(manager.patient_connections.keys()),
    )


@app.get("/api/patients", tags=["Patients"])
async def list_patients():
    """List all patient profiles in the registry."""
    patients = get_all_patients()
    return {
        "total": len(patients),
        "patients": [p.to_dict() for p in patients]
    }


@app.get("/api/patients/{patient_id}", tags=["Patients"])
async def get_patient(patient_id: str):
    """Get a specific patient's profile and latest vitals."""
    patient = get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    return {
        "profile": patient.to_dict(),
        "latest_vitals": manager.latest_readings.get(patient_id),
        "total_readings": len(manager.vital_history.get(patient_id, [])),
        "is_connected": patient_id in manager.patient_connections,
    }


@app.get("/api/patients/{patient_id}/vitals", tags=["Vitals"])
async def get_patient_vitals(patient_id: str, limit: int = 50):
    """Get recent vital sign readings for a patient."""
    patient = get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    history = manager.get_patient_history(patient_id, limit)
    return VitalHistoryResponse(
        patient_id=patient_id,
        total_readings=len(history),
        readings=history,
    )


@app.get("/api/vitals/latest", tags=["Vitals"])
async def get_all_latest_vitals():
    """Get the latest vital reading for every connected patient."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patients": manager.get_all_latest(),
    }


# =============================================================================
#  Phase 7: Agent / SBAR Explanation Endpoints
# =============================================================================

@app.get("/api/patients/{patient_id}/explanation", tags=["Agent"])
async def get_patient_explanation(patient_id: str):
    """
    [Phase 7/9] Get the latest LLM-generated SBAR clinical explanation for a patient.
    Phase 9: the explanation now incorporates patient-specific context.
    """
    patient = get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    sbar = agent_service.get_cached_explanation(patient_id)
    if not sbar:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No explanation available for {patient_id}. "
                "An ESCALATED alert must fire before an explanation is generated."
            )
        )

    age = agent_service.get_cached_explanation_age(patient_id)
    return {
        "patient_id": patient_id,
        "explanation_age_seconds": age,
        "sbar": sbar.model_dump(),
    }


@app.post("/api/patients/{patient_id}/explanation/trigger", tags=["Agent"])
async def trigger_patient_explanation(patient_id: str):
    """
    [Phase 7/9] Manually trigger an SBAR explanation for a patient (for testing/demo).
    Phase 9: patient clinical context is now injected automatically.
    """
    patient = get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    patient_state = state_manager.get_state(patient_id)
    if not patient_state:
        raise HTTPException(status_code=404, detail=f"No state found for {patient_id}")

    from alerts.state_machine import AlertEvent
    from state.patient_state import AlertLevel

    risk = patient_state.current_risk_score or 75.0
    correlation_id = audit_logger.generate_correlation_id()

    mock_event = AlertEvent(
        patient_id=patient_id,
        from_level=AlertLevel.SUSPECTED,
        to_level=AlertLevel.ESCALATED,
        risk_score=risk,
        message="Manually triggered explanation request",
    )

    # Phase 11: log the trigger as an alert event
    audit_logger.log(
        patient_id=patient_id,
        event_type=EventType.ALERT,
        payload={
            "from_level": "SUSPECTED",
            "to_level": "ESCALATED",
            "risk_score": risk,
            "message": "Manually triggered",
        },
        correlation_id=correlation_id,
    )

    sbar = await agent_service.handle_escalation(
        alert_event=mock_event,
        patient_state=patient_state,
        scenario=patient.scenario,
        audit_logger=audit_logger,
        correlation_id=correlation_id,
    )

    if not sbar:
        raise HTTPException(status_code=500, detail="Agent failed to generate explanation.")

    return {
        "patient_id": patient_id,
        "triggered_manually": True,
        "correlation_id": correlation_id,
        "sbar": sbar.model_dump(),
    }


# =============================================================================
#  Phase 9: Patient Clinical Context
# =============================================================================

@app.get("/api/patients/{patient_id}/context", tags=["Phase 9 — Clinical Context"])
async def get_patient_context(patient_id: str):
    """
    [Phase 9] Return the static clinical context for a patient:
    age, history, medications, recent labs, and baseline vitals.
    """
    from simulator.patient_context_data import get_patient_context as _get_ctx
    patient = get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    ctx = _get_ctx(patient_id)
    if not ctx:
        raise HTTPException(
            status_code=404,
            detail=f"No clinical context found for {patient_id}"
        )

    return {
        "patient_id": patient_id,
        "context": ctx.model_dump(),
        "formatted_text": ctx.to_structured_text(),
    }


# =============================================================================
#  Phase 10: Clinician Decision Endpoints
# =============================================================================

@app.post("/api/patients/{patient_id}/alerts/{alert_id}/decision", tags=["Phase 10 — Decisions"])
async def post_alert_decision(
    patient_id: str,
    alert_id: str,
    body: DecisionRequest,
):
    """
    [Phase 10] Post a clinician decision on an alert:
      - accept: acknowledge, keep monitoring, mark reviewed
      - dismiss: suppress re-alerting (30 min cooldown), force state to NORMAL
      - defer: snooze for 15 minutes, re-evaluate after
      - investigate: flag for follow-up, no suppression

    This endpoint applies state machine side-effects via the pipeline.
    """
    patient = get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    try:
        dec = decision_manager.record_decision(
            alert_id=alert_id,
            decision=body.decision,
            clinician_id=body.clinician_id or "clinician",
            reason=body.reason,
            pipeline=_pipeline,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Phase 11: Log the decision to audit trail
    alert_record = decision_manager.get_alert(alert_id)
    correlation_id = alert_record.correlation_id if alert_record else ""

    audit_logger.log(
        patient_id=patient_id,
        event_type=EventType.DECISION,
        payload={
            "decision": dec.decision,
            "clinician_id": dec.clinician_id,
            "reason": dec.reason,
            "previous_state": dec.previous_state,
            "resulting_state": dec.resulting_state,
            "defer_until": dec.defer_until,
        },
        correlation_id=correlation_id,
    )

    # Broadcast decision update to dashboard
    broadcast_msg = json.dumps({
        "type": "decision_update",
        "data": {
            "patient_id": patient_id,
            "alert_id": alert_id,
            "decision": dec.to_dict(),
        }
    })
    disconnected = set()
    for ws in manager.dashboard_connections:
        try:
            await ws.send_text(broadcast_msg)
        except Exception:
            disconnected.add(ws)
    manager.dashboard_connections -= disconnected

    return {
        "success": True,
        "alert_id": alert_id,
        "patient_id": patient_id,
        "decision": dec.to_dict(),
    }


@app.get("/api/patients/{patient_id}/alerts", tags=["Phase 10 — Decisions"])
async def get_patient_alerts(patient_id: str, limit: int = 20):
    """
    [Phase 10] List all alert records for a patient with their decision status.
    """
    patient = get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    records = decision_manager.get_alerts_for_patient(patient_id)[:limit]
    return {
        "patient_id": patient_id,
        "total": len(records),
        "alerts": [r.to_dict() for r in records],
    }


@app.get("/api/alerts/pending", tags=["Phase 10 — Decisions"])
async def get_pending_alerts():
    """
    [Phase 10] Get all cohort-wide undecided ESCALATED/SUSPECTED alerts
    (the "Needs Review" queue). Sorted by risk score descending.
    """
    pending = decision_manager.get_pending_alerts()
    return {
        "total_pending": len(pending),
        "alerts": [r.to_dict() for r in pending],
    }


# =============================================================================
#  Phase 11: Audit Trail Endpoints
# =============================================================================

@app.get("/api/patients/{patient_id}/audit", tags=["Phase 11 — Audit Trail"])
async def get_patient_audit(
    patient_id: str,
    from_ts: Optional[float] = Query(default=None, description="Unix timestamp lower bound"),
    to_ts: Optional[float] = Query(default=None, description="Unix timestamp upper bound"),
    limit: int = Query(default=100, le=500),
):
    """
    [Phase 11] Return the audit log for a patient, optionally filtered by
    time range. Includes observations, retrievals, reasoning, alerts, and decisions.
    """
    patient = get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    entries = audit_logger.get_by_patient(
        patient_id=patient_id,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
    )
    return {
        "patient_id": patient_id,
        "total_entries": len(entries),
        "entries": [e.to_dict() for e in entries],
    }


@app.get("/api/audit/{correlation_id}", tags=["Phase 11 — Audit Trail"])
async def get_audit_chain(correlation_id: str):
    """
    [Phase 11] Return the full audit chain for one escalation episode,
    ordered chronologically. This is the "explainability trace":
    observation → retrieval → reasoning → alert → decision.
    """
    entries = audit_logger.get_by_correlation(correlation_id)
    if not entries:
        raise HTTPException(
            status_code=404,
            detail=f"No audit entries found for correlation_id={correlation_id}"
        )

    chain_status = audit_logger.has_complete_chain(correlation_id)

    return {
        "correlation_id": correlation_id,
        "chain_status": chain_status,
        "entries": [e.to_dict() for e in entries],
    }


@app.get("/api/audit", tags=["Phase 11 — Audit Trail"])
async def get_recent_audit(limit: int = Query(default=50, le=200)):
    """
    [Phase 11] Return the most recent audit entries across all patients.
    """
    entries = audit_logger.get_all(limit=limit)
    return {
        "total_entries": len(entries),
        "entries": [e.to_dict() for e in reversed(entries)],  # newest first
    }


# =============================================================================
#  Integrated Simulator Runner (for development convenience)
# =============================================================================




async def _run_embedded_simulator():
    """
    Run the simulator embedded in the server process for development.
    Instead of connecting via real WebSocket, it directly feeds the manager.
    This avoids needing to run the simulator as a separate process during dev.
    """
    await asyncio.sleep(2)
    print("  [Simulator] Starting embedded simulator...")

    from simulator.patients import get_all_patients
    from simulator.scenarios import create_scenario

    patients = get_all_patients()
    simulators = {}
    for p in patients:
        simulators[p.patient_id] = {
            "patient": p,
            "scenario": create_scenario(p.scenario, p.baseline_vitals),
            "start_time": time.monotonic(),
            "count": 0,
        }

    interval = 5.0  # seconds between readings

    print(f"  [Simulator] Running - {len(patients)} patients, {interval}s interval")
    print()

    while True:
        for pid, sim in simulators.items():
            elapsed = time.monotonic() - sim["start_time"]
            vitals = sim["scenario"].generate(elapsed)
            sim["count"] += 1

            reading = {
                "patient_id": pid,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": round(elapsed, 1),
                "reading_number": sim["count"],
                "vitals": vitals.to_dict(),
            }

            scenario = sim["patient"].scenario
            await manager.process_reading(pid, reading, scenario=scenario)

        await asyncio.sleep(interval)


# =============================================================================
#  Entry point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    import sys
    reload = "--reload" in sys.argv
    uvicorn.run(
        "ingestion.main:app",
        host="127.0.0.1",
        port=8000,
        reload=reload,
        reload_dirs=["ingestion", "engine", "alerts", "agent", "state", "simulator"] if reload else None,
    )
