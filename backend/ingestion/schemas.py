"""
schemas.py — Pydantic Data Models
===================================
Defines the data validation schemas for vital sign readings and API responses.
Pydantic ensures that any data entering the system has the correct format
and reasonable values, catching errors at the boundary.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class VitalSignsSchema(BaseModel):
    """
    Schema for a single set of vital signs.
    Validates that values are within physiologically possible ranges
    (not necessarily normal — just physically possible from a sensor).
    """
    heart_rate: float = Field(..., ge=0, le=350, description="Heart rate in bpm")
    spo2: float = Field(..., ge=0, le=100, description="Blood oxygen saturation %")
    respiratory_rate: float = Field(..., ge=0, le=80, description="Breaths per minute")
    systolic_bp: float = Field(..., ge=0, le=350, description="Systolic blood pressure mmHg")
    diastolic_bp: float = Field(..., ge=0, le=250, description="Diastolic blood pressure mmHg")
    is_artifact: bool = Field(default=False, description="Whether this reading is a known artifact")


class VitalReadingMessage(BaseModel):
    """
    Schema for a complete vital reading message received over WebSocket.
    This is what the simulator sends to the ingestion gateway.
    """
    patient_id: str = Field(..., min_length=1, max_length=20, description="Patient identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    elapsed_seconds: float = Field(default=0, ge=0, description="Seconds since simulation start")
    reading_number: int = Field(default=0, ge=0, description="Sequential reading count")
    vitals: VitalSignsSchema

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Ensure the timestamp is a valid ISO 8601 string."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"Invalid ISO 8601 timestamp: {v}")
        return v


class PatientProfileResponse(BaseModel):
    """Schema for patient profile data returned by REST endpoints."""
    patient_id: str
    name: str
    age: int
    sex: str
    weight_kg: float
    height_cm: float
    medical_history: List[str]
    current_medications: List[str]
    allergies: List[str]
    recent_labs: Dict[str, float]
    scenario: str
    notes: str = ""
    baseline_vitals: Dict[str, Dict[str, float]] = {}


class VitalHistoryResponse(BaseModel):
    """Schema for returning recent vital readings for a patient."""
    patient_id: str
    total_readings: int
    readings: List[Dict[str, Any]]


class SystemStatusResponse(BaseModel):
    """Schema for the system health/status endpoint."""
    status: str = "running"
    connected_patients: int
    total_readings_received: int
    uptime_seconds: float
    patients: List[str]


class AlertEventSchema(BaseModel):
    """Schema for alert events pushed to the frontend."""
    patient_id: str
    alert_level: str  # NORMAL, WATCH, SUSPECTED, ESCALATED
    risk_score: float
    timestamp: str
    message: str
    vitals_snapshot: Optional[VitalSignsSchema] = None
    previous_level: Optional[str] = None
