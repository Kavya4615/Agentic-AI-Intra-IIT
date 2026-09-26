"""
patients.py — Static Patient Profiles
======================================
Defines 8 synthetic patients with realistic demographics, medical histories,
current medications, and recent lab results. Each patient is assigned a 
clinical scenario that controls how their vitals evolve over time.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class LabResults:
    """Most recent lab results for a patient."""
    hemoglobin: float          # g/dL  (normal: 12-17)
    white_blood_cells: float   # x10^3/µL  (normal: 4.5-11.0)
    platelets: float           # x10^3/µL  (normal: 150-400)
    creatinine: float          # mg/dL  (normal: 0.6-1.2)
    lactate: float             # mmol/L  (normal: 0.5-2.0)
    sodium: float              # mEq/L  (normal: 136-145)
    potassium: float           # mEq/L  (normal: 3.5-5.0)
    glucose: float             # mg/dL  (normal: 70-100 fasting)


@dataclass
class PatientProfile:
    """Complete static profile for a synthetic patient."""
    patient_id: str
    name: str
    age: int
    sex: str                               # "M" or "F"
    weight_kg: float
    height_cm: float
    medical_history: List[str]             # Diagnoses
    current_medications: List[str]
    allergies: List[str]
    recent_labs: LabResults
    scenario: str                          # Which clinical scenario to run
    notes: str = ""                        # Additional clinical notes

    # Baseline vital ranges specific to this patient (personalized normals)
    baseline_vitals: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        return {
            "patient_id": self.patient_id,
            "name": self.name,
            "age": self.age,
            "sex": self.sex,
            "weight_kg": self.weight_kg,
            "height_cm": self.height_cm,
            "medical_history": self.medical_history,
            "current_medications": self.current_medications,
            "allergies": self.allergies,
            "recent_labs": {
                "hemoglobin": self.recent_labs.hemoglobin,
                "white_blood_cells": self.recent_labs.white_blood_cells,
                "platelets": self.recent_labs.platelets,
                "creatinine": self.recent_labs.creatinine,
                "lactate": self.recent_labs.lactate,
                "sodium": self.recent_labs.sodium,
                "potassium": self.recent_labs.potassium,
                "glucose": self.recent_labs.glucose,
            },
            "scenario": self.scenario,
            "notes": self.notes,
            "baseline_vitals": self.baseline_vitals,
        }


# =============================================================================
#  PATIENT REGISTRY — 8 diverse patients with different clinical scenarios
# =============================================================================

PATIENT_REGISTRY: List[PatientProfile] = [

    # ── Patient 1: Stable elderly male ──────────────────────────────────────
    PatientProfile(
        patient_id="P001",
        name="Rajesh Kumar",
        age=68,
        sex="M",
        weight_kg=72.0,
        height_cm=170.0,
        medical_history=["Hypertension", "Type 2 Diabetes", "Hyperlipidemia"],
        current_medications=["Amlodipine 5mg", "Metformin 500mg BD", "Atorvastatin 20mg"],
        allergies=["Sulfa drugs"],
        recent_labs=LabResults(
            hemoglobin=13.5, white_blood_cells=7.2, platelets=220,
            creatinine=1.0, lactate=1.1, sodium=140, potassium=4.2, glucose=145
        ),
        scenario="stable",
        notes="Routine post-operative monitoring day 2. Uncomplicated cholecystectomy.",
        baseline_vitals={
            "heart_rate":      {"mean": 74, "std": 4},
            "spo2":            {"mean": 97, "std": 1},
            "respiratory_rate": {"mean": 16, "std": 2},
            "systolic_bp":     {"mean": 138, "std": 6},
            "diastolic_bp":    {"mean": 82, "std": 4},
        }
    ),

    # ── Patient 2: Gradual sepsis deterioration ─────────────────────────────
    PatientProfile(
        patient_id="P002",
        name="Priya Sharma",
        age=55,
        sex="F",
        weight_kg=65.0,
        height_cm=160.0,
        medical_history=["Chronic Kidney Disease Stage 3", "Urinary Tract Infections (recurrent)"],
        current_medications=["Lisinopril 10mg", "Sodium Bicarbonate 650mg", "Ferrous Sulfate 325mg"],
        allergies=["Penicillin"],
        recent_labs=LabResults(
            hemoglobin=10.8, white_blood_cells=12.5, platelets=180,
            creatinine=2.1, lactate=1.8, sodium=137, potassium=4.8, glucose=110
        ),
        scenario="gradual_deterioration",
        notes="Admitted for pyelonephritis. On IV antibiotics. WBC trending up.",
        baseline_vitals={
            "heart_rate":      {"mean": 88, "std": 5},
            "spo2":            {"mean": 96, "std": 1},
            "respiratory_rate": {"mean": 18, "std": 2},
            "systolic_bp":     {"mean": 128, "std": 8},
            "diastolic_bp":    {"mean": 76, "std": 5},
        }
    ),

    # ── Patient 3: COPD exacerbation ────────────────────────────────────────
    PatientProfile(
        patient_id="P003",
        name="Maria Fernandes",
        age=72,
        sex="F",
        weight_kg=58.0,
        height_cm=155.0,
        medical_history=["COPD (GOLD Stage III)", "Congestive Heart Failure (NYHA Class II)", "Atrial Fibrillation"],
        current_medications=["Metoprolol 50mg", "Furosemide 40mg", "Tiotropium inhaler", "Salbutamol PRN"],
        allergies=[],
        recent_labs=LabResults(
            hemoglobin=11.2, white_blood_cells=9.8, platelets=195,
            creatinine=1.3, lactate=1.5, sodium=138, potassium=3.8, glucose=95
        ),
        scenario="copd_exacerbation",
        notes="Admitted with worsening dyspnea. On 2L O2 via nasal cannula. History of 2 exacerbations this year.",
        baseline_vitals={
            "heart_rate":      {"mean": 82, "std": 8},   # Irregularly irregular due to AFib
            "spo2":            {"mean": 93, "std": 2},    # Baseline low due to COPD
            "respiratory_rate": {"mean": 20, "std": 3},
            "systolic_bp":     {"mean": 132, "std": 10},
            "diastolic_bp":    {"mean": 75, "std": 6},
        }
    ),

    # ── Patient 4: Sudden cardiac event ─────────────────────────────────────
    PatientProfile(
        patient_id="P004",
        name="Amit Patel",
        age=48,
        sex="M",
        weight_kg=92.0,
        height_cm=178.0,
        medical_history=["Obesity", "Obstructive Sleep Apnea", "Family history of MI"],
        current_medications=["CPAP at night", "Aspirin 81mg"],
        allergies=["Iodine contrast"],
        recent_labs=LabResults(
            hemoglobin=15.1, white_blood_cells=8.0, platelets=250,
            creatinine=0.9, lactate=1.0, sodium=141, potassium=4.0, glucose=105
        ),
        scenario="sudden_crisis",
        notes="Admitted for elective knee arthroscopy. Pre-op holding. Appears well.",
        baseline_vitals={
            "heart_rate":      {"mean": 78, "std": 5},
            "spo2":            {"mean": 96, "std": 1},
            "respiratory_rate": {"mean": 15, "std": 2},
            "systolic_bp":     {"mean": 142, "std": 7},
            "diastolic_bp":    {"mean": 88, "std": 5},
        }
    ),

    # ── Patient 5: Noisy sensor / artifact patient ──────────────────────────
    PatientProfile(
        patient_id="P005",
        name="Sunita Devi",
        age=34,
        sex="F",
        weight_kg=55.0,
        height_cm=162.0,
        medical_history=["Appendectomy (age 20)"],
        current_medications=["None"],
        allergies=[],
        recent_labs=LabResults(
            hemoglobin=13.0, white_blood_cells=6.5, platelets=280,
            creatinine=0.7, lactate=0.8, sodium=139, potassium=4.1, glucose=88
        ),
        scenario="artifact_noise",
        notes="Observation after minor fall. Moving frequently, sensors keep dislodging.",
        baseline_vitals={
            "heart_rate":      {"mean": 70, "std": 4},
            "spo2":            {"mean": 99, "std": 0.5},
            "respiratory_rate": {"mean": 14, "std": 2},
            "systolic_bp":     {"mean": 115, "std": 5},
            "diastolic_bp":    {"mean": 72, "std": 4},
        }
    ),

    # ── Patient 6: Post-surgical recovery ───────────────────────────────────
    PatientProfile(
        patient_id="P006",
        name="Vikram Singh",
        age=60,
        sex="M",
        weight_kg=80.0,
        height_cm=175.0,
        medical_history=["Coronary Artery Disease", "Prior CABG (2023)", "Type 2 Diabetes"],
        current_medications=["Aspirin 81mg", "Clopidogrel 75mg", "Metoprolol 25mg", "Insulin Glargine 20u"],
        allergies=["Morphine (nausea)"],
        recent_labs=LabResults(
            hemoglobin=11.0, white_blood_cells=11.2, platelets=160,
            creatinine=1.4, lactate=2.5, sodium=136, potassium=4.6, glucose=180
        ),
        scenario="recovery",
        notes="Post-op day 1 from emergency bowel resection. Initial instability resolving.",
        baseline_vitals={
            "heart_rate":      {"mean": 100, "std": 6},   # Elevated post-op
            "spo2":            {"mean": 94, "std": 2},
            "respiratory_rate": {"mean": 22, "std": 3},
            "systolic_bp":     {"mean": 110, "std": 8},
            "diastolic_bp":    {"mean": 68, "std": 5},
        }
    ),

    # ── Patient 7: Young trauma — hemorrhagic shock trajectory ──────────────
    PatientProfile(
        patient_id="P007",
        name="Arjun Mehta",
        age=25,
        sex="M",
        weight_kg=75.0,
        height_cm=180.0,
        medical_history=[],
        current_medications=["Normal Saline IV 125mL/hr"],
        allergies=[],
        recent_labs=LabResults(
            hemoglobin=12.0, white_blood_cells=10.5, platelets=200,
            creatinine=0.8, lactate=2.2, sodium=140, potassium=3.9, glucose=130
        ),
        scenario="hemorrhagic_shock",
        notes="MVA victim. Splenic laceration managed conservatively. Serial hemoglobin monitoring.",
        baseline_vitals={
            "heart_rate":      {"mean": 92, "std": 5},
            "spo2":            {"mean": 98, "std": 1},
            "respiratory_rate": {"mean": 18, "std": 2},
            "systolic_bp":     {"mean": 118, "std": 6},
            "diastolic_bp":    {"mean": 72, "std": 4},
        }
    ),

    # ── Patient 8: Stable with intermittent arrhythmia ──────────────────────
    PatientProfile(
        patient_id="P008",
        name="Lakshmi Nair",
        age=78,
        sex="F",
        weight_kg=52.0,
        height_cm=150.0,
        medical_history=["Paroxysmal Atrial Fibrillation", "Hypertension", "Osteoarthritis"],
        current_medications=["Warfarin 5mg", "Diltiazem 120mg", "Acetaminophen 500mg PRN"],
        allergies=["NSAIDs"],
        recent_labs=LabResults(
            hemoglobin=12.5, white_blood_cells=5.8, platelets=210,
            creatinine=1.1, lactate=1.0, sodium=142, potassium=4.3, glucose=92
        ),
        scenario="intermittent_arrhythmia",
        notes="Monitoring for AFib episodes post rate-control medication adjustment.",
        baseline_vitals={
            "heart_rate":      {"mean": 76, "std": 10},   # Variable due to PAF
            "spo2":            {"mean": 96, "std": 1},
            "respiratory_rate": {"mean": 17, "std": 2},
            "systolic_bp":     {"mean": 145, "std": 8},
            "diastolic_bp":    {"mean": 80, "std": 5},
        }
    ),
]


def get_patient_by_id(patient_id: str) -> PatientProfile | None:
    """Look up a patient by their ID."""
    for patient in PATIENT_REGISTRY:
        if patient.patient_id == patient_id:
            return patient
    return None


def get_all_patients() -> List[PatientProfile]:
    """Return the full patient registry."""
    return PATIENT_REGISTRY


def get_patient_ids() -> List[str]:
    """Return all patient IDs."""
    return [p.patient_id for p in PATIENT_REGISTRY]
