from typing import List, Dict
from pydantic import BaseModel

class PatientContext(BaseModel):
    patient_id: str
    age: int
    sex: str
    relevant_history: List[str]
    current_medications: List[str]
    recent_labs: Dict[str, str]
    baseline_vitals: Dict[str, float]

    def to_structured_text(self) -> str:
        """Format the context nicely for the LLM prompt."""
        history = ", ".join(self.relevant_history) if self.relevant_history else "None"
        meds = ", ".join(self.current_medications) if self.current_medications else "None"
        labs = "\n  ".join([f"- {k}: {v}" for k, v in self.recent_labs.items()]) if self.recent_labs else "None available"
        
        return (
            f"Patient Context for {self.patient_id}:\n"
            f"- Age/Sex: {self.age}yo {self.sex}\n"
            f"- Relevant History: {history}\n"
            f"- Current Medications: {meds}\n"
            f"- Recent Labs:\n  {labs}"
        )
