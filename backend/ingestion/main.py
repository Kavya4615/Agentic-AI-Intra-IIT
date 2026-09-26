"""
main.py — FastAPI Ingestion Gateway
=====================================
The central web server that:
1. Accepts WebSocket connections from the simulator (one per patient)
2. Validates incoming vital sign data using Pydantic schemas
3. Forwards validated readings to the Patient State Engine
4. Provides REST endpoints for querying patient data
5. Broadcasts updates to frontend dashboard clients

Architecture:
  Simulator ──WebSocket──▶ Ingestion Gateway ──▶ State Engine ──▶ Risk Engine
                                │
                                ├── REST API ──▶ Frontend
                                └── WS Broadcast ──▶ Dashboard
"""

import asyncio
import json
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from ingestion.schemas import (
    VitalReadingMessage,
    PatientProfileResponse,
    VitalHistoryResponse,
    SystemStatusResponse,
)
from simulator.patients import get_all_patients, get_patient_by_id

# =============================================================================
#  Application Setup
# =============================================================================

app = FastAPI(
    title="Clinical Decision-Support — Ingestion Gateway",
    description="Real-time vital sign ingestion and streaming for patient monitoring.",
    version="1.0.0",
)

# Allow CORS for the React frontend (will run on a different port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
#  In-Memory State (will be replaced by proper State Engine in Phase 3)
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

    async def process_reading(self, patient_id: str, reading: dict):
        """
        Process a validated vital reading:
        1. Store in history
        2. Update latest reading
        3. Broadcast to all dashboard clients
        """
        self.vital_history[patient_id].append(reading)
        self.latest_readings[patient_id] = reading
        self.total_readings += 1

        # Broadcast to all connected dashboards
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
        # Clean up broken connections
        self.dashboard_connections -= disconnected

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
            # Receive JSON message from simulator
            data = await websocket.receive_text()

            try:
                # Parse and validate with Pydantic
                raw = json.loads(data)
                reading = VitalReadingMessage(**raw)

                # Verify the patient_id matches the URL
                if reading.patient_id != patient_id:
                    await websocket.send_text(json.dumps({
                        "error": f"Patient ID mismatch: URL={patient_id}, message={reading.patient_id}"
                    }))
                    continue

                # Process the validated reading
                await manager.process_reading(patient_id, raw)

            except (json.JSONDecodeError, ValidationError) as e:
                # Send error back to simulator but don't disconnect
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

        # Keep the connection alive; receive any commands from dashboard
        while True:
            msg = await websocket.receive_text()
            # Handle dashboard commands (e.g., clinician decisions)
            try:
                command = json.loads(msg)
                cmd_type = command.get("type", "")

                if cmd_type == "clinician_decision":
                    # Log clinician's decision on an alert (Phase 6+)
                    print(f"  📋 Clinician decision: {command.get('data', {})}")
                    # Will be forwarded to audit trail in later phases

                elif cmd_type == "request_history":
                    # Dashboard requesting vital history for a patient
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
#  REST API Endpoints
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
#  Integrated Simulator Runner (for development convenience)
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Start the background simulator task when the server boots."""
    print()
    print("=" * 70)
    print("  CLINICAL DECISION-SUPPORT - INGESTION GATEWAY")
    print("=" * 70)
    print("  WebSocket endpoints:")
    print("    /ws/vitals/{patient_id}  - Simulator -> Server (per patient)")
    print("    /ws/dashboard            - Server -> Dashboard (broadcasts)")
    print("  REST endpoints:")
    print("    GET /api/status           - System status")
    print("    GET /api/patients          - All patient profiles")
    print("    GET /api/patients/{id}     - Single patient + latest vitals")
    print("    GET /api/patients/{id}/vitals - Recent vital history")
    print("    GET /api/vitals/latest     - Latest vitals for all patients")
    print("=" * 70)
    print()

    # Start the embedded simulator that pushes data via internal WebSocket
    asyncio.create_task(_run_embedded_simulator())


async def _run_embedded_simulator():
    """
    Run the simulator embedded in the server process for development.
    Instead of connecting via real WebSocket, it directly feeds the manager.
    This avoids needing to run the simulator as a separate process during dev.
    """
    import websockets as ws_lib

    # Give the server a moment to fully start
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

            # Directly inject into the manager (bypassing WebSocket for embedded mode)
            await manager.process_reading(pid, reading)

        await asyncio.sleep(interval)


# =============================================================================
#  Entry point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ingestion.main:app", host="127.0.0.1", port=8000, reload=True)
