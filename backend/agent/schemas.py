from pydantic import BaseModel, Field
from typing import List, Optional

class SBARResponse(BaseModel):
    situation: str = Field(description="The current situation or primary clinical alert.")
    background: str = Field(description="Relevant patient background, recent trends, and vital signs context.")
    assessment: str = Field(description="Clinical assessment based on the vitals, trends, and retrieved medical protocols.")
    recommendation: str = Field(description="Actionable recommendations or next steps for the clinical team.")
    retrieved_protocols: List[str] = Field(description="The titles or summaries of the protocols referenced.")

class ExplanationRequest(BaseModel):
    patient_id: str
    scenario: str
    alert_state: str
    current_vitals: dict
    risk_score: float
    recent_trend_summary: str
