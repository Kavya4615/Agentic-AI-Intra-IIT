"""
patient_context_data.py — Static Clinical Context Profiles
===========================================================
One PatientContext per patient (P001–P008), clinically consistent with each
scenario. Sourced from the PatientProfile registry in simulator/patients.py
but reformatted for direct LLM injection.

These are the facts the agent must reason over that are NOT captured by vitals
alone — comorbidities, medications, and recent labs that significantly change
the interpretation of a deterioration pattern.
"""

from agent.patient_context import PatientContext

# ── P001 · Rajesh Kumar · Stable Recovery ────────────────────────────────────
P001_CONTEXT = PatientContext(
    patient_id="P001",
    age=68,
    sex="Male",
    relevant_history=[
        "Hypertension (well-controlled on Amlodipine)",
        "Type 2 Diabetes Mellitus (HbA1c 7.4%)",
        "Hyperlipidemia",
        "Laparoscopic cholecystectomy (2 days ago — uncomplicated)",
    ],
    current_medications=[
        "Amlodipine 5mg OD",
        "Metformin 500mg BD",
        "Atorvastatin 20mg OD",
    ],
    recent_labs={
        "Hemoglobin": "13.5 g/dL (N)",
        "WBC": "7.2 × 10³/µL (N)",
        "Platelets": "220 × 10³/µL (N)",
        "Creatinine": "1.0 mg/dL (N)",
        "Lactate": "1.1 mmol/L (N)",
        "Na": "140 mEq/L (N)",
        "K": "4.2 mEq/L (N)",
        "Glucose": "145 mg/dL (H — DM)",
    },
    baseline_vitals={
        "heart_rate": 74.0,
        "spo2": 97.0,
        "respiratory_rate": 16.0,
        "systolic_bp": 138.0,
        "diastolic_bp": 82.0,
    },
)

# ── P002 · Priya Sharma · Gradual Sepsis Deterioration ───────────────────────
P002_CONTEXT = PatientContext(
    patient_id="P002",
    age=55,
    sex="Female",
    relevant_history=[
        "Chronic Kidney Disease Stage 3 (eGFR ~35 mL/min/1.73m²)",
        "Recurrent Urinary Tract Infections (3× in past year)",
        "Admitted for acute pyelonephritis — IV antibiotics day 2",
        "Penicillin allergy (rash)",
    ],
    current_medications=[
        "Lisinopril 10mg OD (held due to CKD flare risk)",
        "Sodium Bicarbonate 650mg TID",
        "Ferrous Sulfate 325mg OD",
        "IV Ciprofloxacin 400mg BD (current antibiotic)",
    ],
    recent_labs={
        "Hemoglobin": "10.8 g/dL (L — baseline CKD anaemia)",
        "WBC": "12.5 × 10³/µL (H — active infection)",
        "Platelets": "180 × 10³/µL (N)",
        "Creatinine": "2.1 mg/dL (H — CKD, up from baseline 1.8)",
        "Lactate": "1.8 mmol/L (borderline H — monitor closely)",
        "Na": "137 mEq/L (N)",
        "K": "4.8 mEq/L (N-H — CKD-related)",
        "Glucose": "110 mg/dL (N)",
        "CRP": "142 mg/L (H — active sepsis marker)",
        "Procalcitonin": "2.4 ng/mL (H — bacterial infection)",
    },
    baseline_vitals={
        "heart_rate": 88.0,
        "spo2": 96.0,
        "respiratory_rate": 18.0,
        "systolic_bp": 128.0,
        "diastolic_bp": 76.0,
    },
)

# ── P003 · Maria Fernandes · COPD Exacerbation ───────────────────────────────
P003_CONTEXT = PatientContext(
    patient_id="P003",
    age=72,
    sex="Female",
    relevant_history=[
        "COPD GOLD Stage III (FEV1/FVC < 0.70, FEV1 ~35% predicted)",
        "Congestive Heart Failure NYHA Class II (EF 40%)",
        "Atrial Fibrillation (rate-controlled on Metoprolol)",
        "2× COPD exacerbations requiring hospitalisation in the past 12 months",
        "Admitted with worsening dyspnoea — on 2L O2 nasal cannula",
    ],
    current_medications=[
        "Metoprolol 50mg BD (rate control for AF — NOTE: masks tachycardic response)",
        "Furosemide 40mg OD (diuresis for CHF)",
        "Tiotropium 18mcg inhaler OD (LAMA)",
        "Salbutamol 2.5mg nebuliser PRN (SABA — started this admission)",
        "Prednisolone 40mg OD (systemic steroids for exacerbation)",
    ],
    recent_labs={
        "Hemoglobin": "11.2 g/dL (L — chronic disease anaemia)",
        "WBC": "9.8 × 10³/µL (N-H — steroids effect)",
        "Platelets": "195 × 10³/µL (N)",
        "Creatinine": "1.3 mg/dL (mildly H)",
        "Lactate": "1.5 mmol/L (N)",
        "Na": "138 mEq/L (N)",
        "K": "3.8 mEq/L (N-L — Furosemide risk, monitor)",
        "pCO2 (ABG)": "52 mmHg (H — chronic CO2 retention, type 2 RF)",
        "pO2 (ABG)": "58 mmHg (L — on 2L O2)",
        "pH (ABG)": "7.38 (compensated)",
        "BNP": "380 pg/mL (H — CHF component)",
    },
    baseline_vitals={
        "heart_rate": 82.0,
        "spo2": 93.0,
        "respiratory_rate": 20.0,
        "systolic_bp": 132.0,
        "diastolic_bp": 75.0,
    },
)

# ── P004 · Amit Patel · Sudden Crisis (Pneumothorax) ─────────────────────────
P004_CONTEXT = PatientContext(
    patient_id="P004",
    age=48,
    sex="Male",
    relevant_history=[
        "Obesity (BMI 29 kg/m²)",
        "Obstructive Sleep Apnoea on CPAP",
        "Strong family history of MI (father at 52, brother at 49)",
        "Admitted for elective knee arthroscopy — pre-operative holding",
        "No prior surgeries, appears otherwise well",
    ],
    current_medications=[
        "CPAP at night (prescribed 3 months ago)",
        "Aspirin 81mg OD (peri-operative — held this morning per anaesthesia)",
    ],
    recent_labs={
        "Hemoglobin": "15.1 g/dL (N)",
        "WBC": "8.0 × 10³/µL (N)",
        "Platelets": "250 × 10³/µL (N)",
        "Creatinine": "0.9 mg/dL (N)",
        "Lactate": "1.0 mmol/L (N)",
        "Na": "141 mEq/L (N)",
        "K": "4.0 mEq/L (N)",
        "Glucose": "105 mg/dL (N)",
        "ECG": "Normal sinus rhythm, no ischaemic changes",
        "CXR": "Clear lung fields bilaterally pre-op",
    },
    baseline_vitals={
        "heart_rate": 78.0,
        "spo2": 96.0,
        "respiratory_rate": 15.0,
        "systolic_bp": 142.0,
        "diastolic_bp": 88.0,
    },
)

# ── P005 · Sunita Devi · Sensor Noise / Motion Artifact ──────────────────────
P005_CONTEXT = PatientContext(
    patient_id="P005",
    age=34,
    sex="Female",
    relevant_history=[
        "Appendectomy age 20 (uncomplicated)",
        "Presented after minor fall — awaiting imaging for R wrist pain",
        "Moving frequently; sensor leads repeatedly dislodged",
        "No significant medical history",
    ],
    current_medications=[
        "Ibuprofen 400mg TID PRN (wrist pain — to be discontinued if any GI upset)",
    ],
    recent_labs={
        "Hemoglobin": "13.0 g/dL (N)",
        "WBC": "6.5 × 10³/µL (N)",
        "Platelets": "280 × 10³/µL (N)",
        "Creatinine": "0.7 mg/dL (N)",
        "Lactate": "0.8 mmol/L (N)",
        "Na": "139 mEq/L (N)",
        "K": "4.1 mEq/L (N)",
        "Glucose": "88 mg/dL (N)",
    },
    baseline_vitals={
        "heart_rate": 70.0,
        "spo2": 99.0,
        "respiratory_rate": 14.0,
        "systolic_bp": 115.0,
        "diastolic_bp": 72.0,
    },
)

# ── P006 · Vikram Singh · Post-Op Recovery ───────────────────────────────────
P006_CONTEXT = PatientContext(
    patient_id="P006",
    age=60,
    sex="Male",
    relevant_history=[
        "Coronary Artery Disease — prior CABG (2023) with 3-vessel grafting",
        "Type 2 Diabetes Mellitus (insulin-dependent, HbA1c 8.1%)",
        "Post-op day 1: emergency left hemicolectomy for bowel obstruction",
        "Morphine allergy (nausea/vomiting) — on alternative opioids",
        "Elevated post-op baseline vitals expected; trending toward recovery",
    ],
    current_medications=[
        "Aspirin 81mg OD (antiplatelet — restarted post-op)",
        "Clopidogrel 75mg OD (antiplatelet — dual DAPT post-CABG)",
        "Metoprolol 25mg BD (cardioprotective — NOTE: limits tachycardia response)",
        "Insulin Glargine 20u SC OD at 22:00",
        "IV Fentanyl PCA (morphine-free pain control)",
        "IV Cefazolin 1g Q8H (surgical prophylaxis)",
    ],
    recent_labs={
        "Hemoglobin": "11.0 g/dL (L — post-op blood loss)",
        "WBC": "11.2 × 10³/µL (H — post-surgical stress response)",
        "Platelets": "160 × 10³/µL (N-L)",
        "Creatinine": "1.4 mg/dL (mildly H — pre-renal vs CKD)",
        "Lactate": "2.5 mmol/L (H — post-op, trending down from 3.1 earlier)",
        "Na": "136 mEq/L (N-L)",
        "K": "4.6 mEq/L (N-H)",
        "Glucose": "180 mg/dL (H — diabetic + surgical stress)",
        "Troponin I": "0.04 ng/mL (borderline — serial monitoring ongoing)",
    },
    baseline_vitals={
        "heart_rate": 100.0,
        "spo2": 94.0,
        "respiratory_rate": 22.0,
        "systolic_bp": 110.0,
        "diastolic_bp": 68.0,
    },
)

# ── P007 · Arjun Mehta · Hemorrhagic Shock ───────────────────────────────────
P007_CONTEXT = PatientContext(
    patient_id="P007",
    age=25,
    sex="Male",
    relevant_history=[
        "Motor vehicle accident — splenic laceration (Grade II) managed conservatively",
        "No prior medical history",
        "Admitted 8 hours ago; serial Hgb monitoring protocol",
        "Hgb drop from 14.2 → 12.0 g/dL over 6 hours (2.2 g/dL decline — significant)",
        "Estimated blood loss ~600-800 mL at scene",
    ],
    current_medications=[
        "Normal Saline IV 125 mL/hr (volume resuscitation)",
        "IV Morphine 2mg PRN Q4H (pain control)",
        "IV Ondansetron 4mg PRN (anti-emetic)",
    ],
    recent_labs={
        "Hemoglobin": "12.0 g/dL (L — down from 14.2 on admission; 2.2g decline in 6h)",
        "WBC": "10.5 × 10³/µL (H — stress leucocytosis from trauma)",
        "Platelets": "200 × 10³/µL (N)",
        "Creatinine": "0.8 mg/dL (N)",
        "Lactate": "2.2 mmol/L (H — tissue hypoperfusion marker)",
        "Na": "140 mEq/L (N)",
        "K": "3.9 mEq/L (N)",
        "Glucose": "130 mg/dL (H — stress response)",
        "INR": "1.1 (N)",
        "Type & Screen": "O+, crossmatch 2 units PRBCs available",
    },
    baseline_vitals={
        "heart_rate": 92.0,
        "spo2": 98.0,
        "respiratory_rate": 18.0,
        "systolic_bp": 118.0,
        "diastolic_bp": 72.0,
    },
)

# ── P008 · Lakshmi Nair · Intermittent Arrhythmia ────────────────────────────
P008_CONTEXT = PatientContext(
    patient_id="P008",
    age=78,
    sex="Female",
    relevant_history=[
        "Paroxysmal Atrial Fibrillation — on anticoagulation with Warfarin",
        "Hypertension (multiple agents, currently managed)",
        "Osteoarthritis (bilateral knees)",
        "Admitted for medication adjustment — Diltiazem dose increased yesterday",
        "Last INR 3.2 (supratherapeutic, target 2.0-3.0) — Warfarin held today",
        "NSAID allergy — cannot use for OA pain control",
    ],
    current_medications=[
        "Warfarin 5mg OD (held today — INR 3.2, supratherapeutic)",
        "Diltiazem 120mg OD (CCB — rate control for AF; dose just increased)",
        "Acetaminophen 500mg QID PRN (OA pain)",
        "Perindopril 4mg OD (ACE-I for hypertension)",
    ],
    recent_labs={
        "Hemoglobin": "12.5 g/dL (N for age/sex)",
        "WBC": "5.8 × 10³/µL (N)",
        "Platelets": "210 × 10³/µL (N)",
        "Creatinine": "1.1 mg/dL (mildly H for age)",
        "Lactate": "1.0 mmol/L (N)",
        "Na": "142 mEq/L (N)",
        "K": "4.3 mEq/L (N)",
        "Glucose": "92 mg/dL (N)",
        "INR": "3.2 (H — supratherapeutic; haemorrhage risk elevated)",
        "TSH": "2.1 mIU/L (N — AF not thyroid-driven)",
        "ECG": "Irregular rhythm consistent with paroxysmal AF; QTc 440ms",
    },
    baseline_vitals={
        "heart_rate": 76.0,
        "spo2": 96.0,
        "respiratory_rate": 17.0,
        "systolic_bp": 145.0,
        "diastolic_bp": 80.0,
    },
)


# ── Registry ──────────────────────────────────────────────────────────────────

PATIENT_CONTEXT_REGISTRY = {
    "P001": P001_CONTEXT,
    "P002": P002_CONTEXT,
    "P003": P003_CONTEXT,
    "P004": P004_CONTEXT,
    "P005": P005_CONTEXT,
    "P006": P006_CONTEXT,
    "P007": P007_CONTEXT,
    "P008": P008_CONTEXT,
}


def get_patient_context(patient_id: str) -> PatientContext | None:
    """Return the static clinical context for a patient, or None if not found."""
    return PATIENT_CONTEXT_REGISTRY.get(patient_id)


def get_all_contexts() -> dict:
    """Return all patient contexts as a dict keyed by patient_id."""
    return dict(PATIENT_CONTEXT_REGISTRY)
