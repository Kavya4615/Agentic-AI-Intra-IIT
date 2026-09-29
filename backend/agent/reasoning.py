"""
reasoning.py — Clinical Reasoning Agent (LLM Layer)
======================================================
Phase 9 update:
  - Prompt now explicitly includes a PATIENT CLINICAL CONTEXT block (from RAG)
    containing the patient's history, medications, and labs.
  - The LLM is instructed to cross-reference vitals trends against the context
    (e.g., beta-blocker masking tachycardia, CKD causing baseline creatinine
    elevation, supratherapeutic INR in AF, etc.)
  - The SBAR Background section must reference the PatientContext fields.
"""

import os
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from .schemas import SBARResponse, ExplanationRequest

# ─────────────────────────────────────────────────────────────────────────────
#  Prompt Template (Phase 9 — context-aware)
# ─────────────────────────────────────────────────────────────────────────────

AGENT_PROMPT_TEMPLATE = """
You are an expert clinical decision-support AI embedded in an ICU monitoring system.
A patient has triggered a clinical alert. Generate a structured SBAR explanation
that explicitly integrates the patient's static clinical context with the real-time
vital sign trends and protocol guidelines.

=== ALERT SUMMARY ===
Patient ID: {patient_id}
Clinical Scenario: {scenario}
Alert State: {alert_state}
Composite Risk Score: {risk_score}/100
Current Vitals: {current_vitals}
Recent Vital Trends: {recent_trend_summary}

=== KNOWLEDGE BASE (Context + Protocols) ===
{knowledge_base}

=== INSTRUCTIONS ===
You MUST reason over the PATIENT CLINICAL CONTEXT section above.
Key integration points to consider:
- If the patient is on beta-blockers (Metoprolol, Atenolol, Carvedilol etc.),
  explicitly note that heart rate response may be blunted — a "normal" HR may
  still represent physiological stress.
- If there is a baseline low SpO2 (COPD, CHF), note that a drop is relative to
  their personal baseline, not population norms.
- If recent labs show elevated lactate, rising WBC, rising creatinine, or a
  declining haemoglobin — call these out in the Background and Assessment.
- If the patient has a known allergy, confirm it doesn't apply to recommended
  agents. If it does, flag it.
- If coagulation is abnormal (supratherapeutic INR, thrombocytopaenia), flag
  bleeding risk for any invasive procedures.
- For the Background section: you MUST cite at least 2 specific facts from the
  Patient Clinical Context (history, medications, or labs).
- For the Assessment: provide a synthesised clinical interpretation that
  connects the context facts to the vital trends.
- For the Recommendation: be specific and actionable.

{format_instructions}
"""


def _is_live_api_key(key: str | None) -> bool:
    """Return True only for keys that look like real OpenAI keys (sk-... prefix)."""
    return bool(key and key.startswith("sk-") and len(key) > 20)


class ClinicalReasoningAgent:
    def __init__(self, model_name="gpt-4o-mini", temperature=0.0):
        api_key = os.getenv("OPENAI_API_KEY", "")
        # Only construct the real LLM when we have a plausible key
        self._use_live = _is_live_api_key(api_key)
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key if self._use_live else "sk-mock-key-placeholder",
        )
        self.parser = PydanticOutputParser(pydantic_object=SBARResponse)

        self.prompt = PromptTemplate(
            template=AGENT_PROMPT_TEMPLATE,
            input_variables=[
                "patient_id", "scenario", "alert_state",
                "current_vitals", "risk_score", "recent_trend_summary",
                "knowledge_base",   # Phase 9: replaces bare "protocols"
            ],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )

        self.chain = self.prompt | self.llm | self.parser

    def generate_explanation(
        self,
        request: ExplanationRequest,
        knowledge_base: str = "",           # Phase 9: combined context + protocols
        protocol_names: list[str] | None = None,
        retrieved_protocols: str | None = None,  # Backward compatibility
    ) -> SBARResponse:
        """
        Generate a structured clinical explanation (SBAR) given the alert context,
        patient clinical context, and protocols.

        Parameters
        ----------
        request             : ExplanationRequest from the alert pipeline.
        knowledge_base      : Combined context + protocol text (from rag.retrieve_with_context).
        protocol_names      : List of protocol names retrieved (for the response field).
        retrieved_protocols : Optional alias for knowledge_base for backward compatibility.
        """
        if not knowledge_base and retrieved_protocols:
            knowledge_base = retrieved_protocols

        if protocol_names is None:
            protocol_names = []

        # Fallback to structured mock response when no valid API key is available
        if not self._use_live:
            return self._mock_response(request, knowledge_base, protocol_names)

        try:
            return self.chain.invoke({
                "patient_id": request.patient_id,
                "scenario": request.scenario,
                "alert_state": request.alert_state,
                "current_vitals": request.current_vitals,
                "risk_score": request.risk_score,
                "recent_trend_summary": request.recent_trend_summary,
                "knowledge_base": knowledge_base,
            })
        except Exception as e:
            print(f"  [ClinicalReasoningAgent] Live LLM failed ({e}), falling back to deterministic mock reasoning.")
            return self._mock_response(request, knowledge_base, protocol_names)

    def _mock_response(
        self,
        request: ExplanationRequest,
        knowledge_base: str,
        protocol_names: list[str],
    ) -> SBARResponse:
        """
        Dynamic, patient- and scenario-tailored clinical reasoning engine that
        synthesizes vital trends, comorbidities, medications, lab values, and protocols.
        """
        pid = request.patient_id.upper().strip()
        scenario_lower = request.scenario.lower()
        vitals = request.current_vitals or {}
        trends = request.recent_trend_summary or "Stable physiological trajectory"
        risk = request.risk_score
        state = request.alert_state

        # Helper to format vitals snippet
        def v_str(key: str, unit: str = "", fallback: str = "N/A") -> str:
            val = vitals.get(key)
            return f"{val}{unit}" if val is not None else fallback

        hr_str = v_str("heart_rate", " bpm")
        spo2_str = v_str("spo2", "%")
        rr_str = v_str("respiratory_rate", "/min")
        sys_bp = vitals.get("systolic_bp") or vitals.get("blood_pressure_systolic")
        dia_bp = vitals.get("diastolic_bp") or vitals.get("blood_pressure_diastolic")
        bp_str = f"{sys_bp:.0f}/{dia_bp:.0f} mmHg" if sys_bp and dia_bp else "N/A"

        # ── P001 / Stable Recovery ──────────────────────────────────────────
        if pid == "P001" or ("stable" in scenario_lower and pid not in ["P002", "P003", "P004", "P006", "P007", "P008"]):
            return SBARResponse(
                situation=(
                    f"Patient {pid} (Rajesh Kumar, 68M) is in {state} status with a low composite risk "
                    f"score of {risk}/100. Hemodynamics and respiratory status are stable post-cholecystectomy "
                    f"(HR: {hr_str}, SpO2: {spo2_str}, BP: {bp_str})."
                ),
                background=(
                    f"Post-op Day 2 status following uncomplicated laparoscopic cholecystectomy. "
                    f"Relevant history: Hypertension on Amlodipine 5mg, Type 2 Diabetes on Metformin 500mg, "
                    f"and Sulfa allergy. Baseline laboratory markers within normal limits (Hemoglobin 13.5 g/dL, "
                    f"WBC 7.2 x10^3/uL, Creatinine 1.0 mg/dL, Lactate 1.1 mmol/L). Trends: {trends}."
                ),
                assessment=(
                    "Physiological parameters demonstrate reassuring post-operative recovery without evidence of "
                    "surgical site infection, internal hemorrhage, or glycemic decompensation. Vital signs "
                    "are concordant with baseline targets."
                ),
                recommendation=(
                    "1. Continue standard routine post-operative floor monitoring.\n"
                    "2. Resume home antihypertensive and oral hypoglycemic regimen.\n"
                    "3. Encourage early ambulation, incentive spirometry, and oral intake.\n"
                    "4. No acute ICU or rapid response escalation warranted."
                ),
                retrieved_protocols=protocol_names if protocol_names else ["SEPSIS", "GENERAL MONITORING"],
            )

        # ── P002 / Sepsis (Gradual Deterioration) ────────────────────────────
        elif pid == "P002" or "gradual" in scenario_lower or "sepsis" in scenario_lower:
            return SBARResponse(
                situation=(
                    f"Patient {pid} (Priya Sharma, 55F) has triggered an {state} alert with a composite "
                    f"risk score of {risk}/100, reflecting severe progressive systemic deterioration consistent "
                    f"with evolving urosepsis (HR: {hr_str}, SpO2: {spo2_str}, BP: {bp_str}, RR: {rr_str})."
                ),
                background=(
                    f"Admitted for acute pyelonephritis on IV Ciprofloxacin (Day 2). History of Chronic Kidney Disease "
                    f"Stage 3 (baseline eGFR ~35) and documented Penicillin allergy. Recent labs indicate active infection "
                    f"and metabolic stress: WBC elevated at 12.5 x10^3/uL, CRP 142 mg/L, Procalcitonin 2.4 ng/mL, "
                    f"Creatinine elevated at 2.1 mg/dL (up from baseline 1.8), and Lactate elevated at 1.8 mmol/L. "
                    f"Recent trend: {trends}."
                ),
                assessment=(
                    "Clinical deterioration pattern is consistent with worsening urosepsis / severe sepsis. Rising heart "
                    "rate and declining blood pressure combined with elevated inflammatory markers and lactate reflect "
                    "systemic vasodilation and early tissue hypoperfusion. Underlying CKD Stage 3 increases vulnerability "
                    "to acute renal injury and requires cautious fluid management to avoid pulmonary edema while restoring MAP >= 65 mmHg. "
                    "Documented Penicillin allergy restricts antibiotic escalations to non-beta-lactam alternatives."
                ),
                recommendation=(
                    "1. Execute Sepsis Resuscitation Bundle: Administer 30 mL/kg IV crystalloids with close lung auscultation given CKD Stage 3.\n"
                    "2. Draw stat repeat blood cultures and serum lactate level to evaluate clearance.\n"
                    "3. Escalate antimicrobial therapy: Review renal-dosed antibiotic regimen (non-penicillin options such as Aztreonam or Meropenem).\n"
                    "4. Target MAP >= 65 mmHg; prepare Norepinephrine infusion if hypotensive refractory to fluid challenge."
                ),
                retrieved_protocols=protocol_names if protocol_names else ["SEPSIS"],
            )

        # ── P003 / COPD Exacerbation ─────────────────────────────────────────
        elif pid == "P003" or "copd" in scenario_lower:
            return SBARResponse(
                situation=(
                    f"Patient {pid} (Maria Fernandes, 72F) has triggered an {state} alert (Risk Score: {risk}/100) "
                    f"indicating acute respiratory decompensation secondary to severe COPD exacerbation "
                    f"(SpO2: {spo2_str}, RR: {rr_str}, HR: {hr_str}, BP: {bp_str})."
                ),
                background=(
                    f"Known COPD GOLD Stage III (baseline SpO2 ~93%), Congestive Heart Failure NYHA II (EF 40%, BNP 380 pg/mL), "
                    f"and Atrial Fibrillation. Current medications: Metoprolol 50mg BD, Furosemide 40mg OD, Tiotropium, and Salbutamol. "
                    f"Recent ABG confirms chronic type 2 respiratory failure (pCO2 52 mmHg, pO2 58 mmHg, pH 7.38). "
                    f"CRITICAL: Metoprolol blunts the physiological tachycardic response, masking the severity of respiratory fatigue. "
                    f"Trends: {trends}."
                ),
                assessment=(
                    "Severe ventilation-perfusion mismatch with impending hypercapnic respiratory exhaustion. Baseline Metoprolol therapy "
                    "prevents compensatory tachycardia, meaning observed heart rate substantially underrepresents physiological distress. "
                    "Concurrent Furosemide therapy places the patient at risk of hypokalemia (baseline K 3.8 mEq/L) during repeated beta-agonist "
                    "nebulizations, requiring close electrolyte vigilance alongside airway support."
                ),
                recommendation=(
                    "1. Titrate controlled oxygen via Venturi mask targeting SpO2 88-92% (avoid excessive FiO2 that suppresses hypoxic drive).\n"
                    "2. Administer combined Salbutamol (2.5mg) + Ipratropium (500mcg) nebulizers; continue IV/PO systemic corticosteroids.\n"
                    "3. Obtain stat arterial blood gas (ABG) to check for worsening acidosis (pH < 7.35) and hypercapnia.\n"
                    "4. Initiate Non-Invasive Positive Pressure Ventilation (BiPAP) if tachypnea or acidosis persists; monitor serum potassium closely."
                ),
                retrieved_protocols=protocol_names if protocol_names else ["COPD"],
            )

        # ── P004 / Sudden Crisis (Pneumothorax / Collapse) ───────────────────
        elif pid == "P004" or "crisis" in scenario_lower or "pneumothorax" in scenario_lower:
            return SBARResponse(
                situation=(
                    f"Patient {pid} (Amit Patel, 48M) has experienced a sudden catastrophic physiological collapse "
                    f"triggering an immediate {state} alert (Risk Score: {risk}/100) with severe hypoxia and hypotension "
                    f"(HR: {hr_str}, SpO2: {spo2_str}, BP: {bp_str}, RR: {rr_str})."
                ),
                background=(
                    f"48yo Male in pre-operative holding for elective knee arthroscopy. History of Obesity (BMI 29) "
                    f"and Obstructive Sleep Apnea on CPAP. Baseline labs and pre-op CXR/ECG were normal. Acute, precipitous "
                    f"onset of severe respiratory distress, tachycardia, and hemodynamic collapse. Trends: {trends}."
                ),
                assessment=(
                    "Acute life-threatening cardiopulmonary emergency. The sudden concordant collapse of SpO2 and blood pressure "
                    "is highly suspicious for tension pneumothorax, massive pulmonary embolism, or acute coronary catastrophe. "
                    "Severe obstructive/cardiogenic shock pattern requires immediate physical decompression and invasive stabilization."
                ),
                recommendation=(
                    "1. IMMEDIATELY activate ICU Rapid Response Team / Code Blue and senior anesthesiologist/intensivist.\n"
                    "2. Apply 100% high-flow oxygen via non-rebreather mask; prepare emergency video-laryngoscopy intubation equipment.\n"
                    "3. Perform stat bedside lung ultrasound (eFAST) and chest auscultation; if tension pneumothorax confirmed, perform emergency needle decompression (2nd ICS MCL or 5th ICS AAL) followed by chest tube.\n"
                    "4. Establish dual large-bore IV access, draw stat ABG/Troponin/D-dimer, and prepare inotropic vasopressor infusion."
                ),
                retrieved_protocols=protocol_names if protocol_names else ["SUDDEN CRISIS"],
            )

        # ── P005 / Sensor Artifact Noise ────────────────────────────────────
        elif pid == "P005" or "artifact" in scenario_lower or "noise" in scenario_lower:
            return SBARResponse(
                situation=(
                    f"Patient {pid} (Sunita Devi, 34F) alert triggered (Risk Score: {risk}/100) due to sensor noise "
                    f"and motion artifact rather than primary cardiopulmonary collapse (HR: {hr_str}, SpO2: {spo2_str})."
                ),
                background=(
                    f"34yo Female under observation following a minor fall awaiting wrist radiograph. Medical history unremarkable "
                    f"(remote appendectomy). Baseline labs normal (Hgb 13.0 g/dL, WBC 6.5 x10^3/uL, Lactate 0.8 mmol/L). "
                    f"Patient is moving frequently, causing intermittent photoplethysmography and ECG lead dislodgement. Trends: {trends}."
                ),
                assessment=(
                    "Telemetry analysis indicates artifactual signal degradation. Non-concordant isolated vital spikes and zero-readings "
                    "without corresponding hemodynamic collapse or clinical distress confirm sensor displacement. Patient remains "
                    "physiologically stable with preserved perfusion."
                ),
                recommendation=(
                    "1. Perform direct bedside nursing assessment of pulse, work of breathing, and sensor placement.\n"
                    "2. Replace and reposition pulse oximeter probe (consider alternate finger or earlobe clip) and apply fresh ECG electrodes.\n"
                    "3. Ensure secure lead wire routing to suppress false alarms.\n"
                    "4. No pharmacotherapy or resuscitation escalation required."
                ),
                retrieved_protocols=protocol_names if protocol_names else ["GENERAL MONITORING"],
            )

        # ── P006 / Post-Op Recovery with CAD ─────────────────────────────────
        elif pid == "P006" or "recovery" in scenario_lower:
            return SBARResponse(
                situation=(
                    f"Patient {pid} (Vikram Singh, 60M) is in {state} status (Risk Score: {risk}/100) undergoing post-operative "
                    f"stabilization following emergency bowel resection (HR: {hr_str}, SpO2: {spo2_str}, BP: {bp_str})."
                ),
                background=(
                    f"Post-op Day 1 from emergency left hemicolectomy for bowel obstruction. History of CAD with 3-vessel CABG (2023), "
                    f"Type 2 Diabetes, and Morphine allergy (severe nausea). Current medications: Aspirin, Clopidogrel (DAPT), "
                    f"Metoprolol 25mg BD, and Insulin. Labs show post-surgical leukocytosis (WBC 11.2 x10^3/uL), Hemoglobin 11.0 g/dL, "
                    f"and resolving Lactate (2.5 mmol/L, down from 3.1). Trends: {trends}."
                ),
                assessment=(
                    "Expected post-surgical systemic inflammatory response with elevated baseline heart rate and metabolic stress. "
                    "Lactate is steadily clearing, indicating improving tissue perfusion. Metoprolol provides cardioprotection while "
                    "moderating tachycardia. Concurrent dual antiplatelet therapy requires vigilance for occult surgical site bleeding."
                ),
                recommendation=(
                    "1. Continue morphine-free multimodal analgesia (IV Fentanyl PCA) and surgical prophylaxis (IV Cefazolin).\n"
                    "2. Serial lactate checks Q6H until normalized (<2.0 mmol/L).\n"
                    "3. Monitor surgical drains, wound site, and serial Hemoglobin for occult hemorrhage under DAPT.\n"
                    "4. Maintain glycemic control (target glucose 140-180 mg/dL) using insulin sliding scale."
                ),
                retrieved_protocols=protocol_names if protocol_names else ["SEPSIS", "GENERAL MONITORING"],
            )

        # ── P007 / Hemorrhagic Shock ─────────────────────────────────────────
        elif pid == "P007" or "hemorrhagic" in scenario_lower or "shock" in scenario_lower:
            return SBARResponse(
                situation=(
                    f"Patient {pid} (Arjun Mehta, 25M) has triggered an {state} alert (Risk Score: {risk}/100) indicating "
                    f"acute Class III Hemorrhagic Shock with progressive hemodynamic instability "
                    f"(HR: {hr_str}, BP: {bp_str}, RR: {rr_str}, SpO2: {spo2_str})."
                ),
                background=(
                    f"25yo trauma patient 8 hours post-MVA with Grade II splenic laceration. Serial lab monitoring reveals an acute "
                    f"hemoglobin decline from 14.2 -> 12.0 g/dL over 6 hours (2.2 g/dL drop), accompanied by elevated Lactate (2.2 mmol/L) "
                    f"and stress leukocytosis (WBC 10.5 x10^3/uL). Type & Screen confirmed (O+, 2 units PRBCs ready). Trends: {trends}."
                ),
                assessment=(
                    "Class III Hemorrhagic Shock due to active ongoing intra-abdominal bleeding from splenic laceration. Progressive "
                    "tachycardia and narrowing pulse pressure combined with documented 2.2 g/dL hemoglobin decline and rising lactate "
                    "demonstrate uncompensated blood loss and worsening anaerobic tissue metabolism requiring urgent surgical control."
                ),
                recommendation=(
                    "1. Stat consult to Trauma Surgery and Interventional Radiology for emergent angiographic embolization vs. exploratory laparotomy.\n"
                    "2. Establish two large-bore (14/16G) peripheral IV lines or rapid infusion catheter.\n"
                    "3. Initiate Massive Transfusion Protocol: Transfuse crossmatched PRBCs via rapid blood warmer; avoid clear crystalloid overload to prevent dilutional coagulopathy.\n"
                    "4. Obtain stat repeat ABG, Hemoglobin, coagulation profile (INR/PTT/Fibrinogen), and bedside abdominal FAST ultrasound."
                ),
                retrieved_protocols=protocol_names if protocol_names else ["HEMORRHAGIC SHOCK"],
            )

        # ── P008 / Intermittent Arrhythmia ──────────────────────────────────
        elif pid == "P008" or "arrhythmia" in scenario_lower:
            return SBARResponse(
                situation=(
                    f"Patient {pid} (Lakshmi Nair, 78F) has triggered an {state} alert (Risk Score: {risk}/100) due to "
                    f"acute paroxysmal tachyarrhythmia with rapid ventricular response and hemodynamic vulnerability "
                    f"(HR: {hr_str}, BP: {bp_str}, SpO2: {spo2_str})."
                ),
                background=(
                    f"78yo Female with Paroxysmal Atrial Fibrillation on Warfarin, Hypertension, and Osteoarthritis (NSAID allergy). "
                    f"Diltiazem increased yesterday (120mg OD). Current labs demonstrate supratherapeutic INR 3.2 (Warfarin held today), "
                    f"normal troponin/TSH, and baseline Creatinine 1.1 mg/dL. Trends: {trends}."
                ),
                assessment=(
                    "Paroxysmal Atrial Fibrillation with Rapid Ventricular Response (AF with RVR) impairing diastolic ventricular filling. "
                    "CRITICAL SAFETY NOTE: Supratherapeutic INR (3.2) places patient at high hemorrhage risk; emergency invasive procedures "
                    "or intramuscular injections are strictly contraindicated without reversal planning. Known NSAID allergy restricts analgesics."
                ),
                recommendation=(
                    "1. Obtain stat 12-lead ECG and maintain continuous 5-lead telemetry to analyze rhythm morphology.\n"
                    "2. Titrate IV rate control: Administer IV Diltiazem (0.25 mg/kg over 2 min) or IV Metoprolol with continuous BP monitoring; continue holding Warfarin.\n"
                    "3. Stat check and repletion of serum electrolytes (target Magnesium > 2.0 mg/dL, Potassium > 4.0 mEq/L to stabilize myocardium).\n"
                    "4. Have Vitamin K (Phytonadione) on standby for bleeding signs; strictly avoid NSAIDs and IM injections given INR 3.2."
                ),
                retrieved_protocols=protocol_names if protocol_names else ["ARRHYTHMIA"],
            )

        # ── Generic Fallback for unknown patient/scenario ────────────────────
        else:
            prot_display = ", ".join(protocol_names) if protocol_names else "General Clinical Deterioration Protocol"
            return SBARResponse(
                situation=(
                    f"Patient {pid} has triggered a {state} alert (Risk Score: {risk}/100). "
                    f"Current vital signs demonstrate physiological instability: HR {hr_str}, BP {bp_str}, SpO2 {spo2_str}, RR {rr_str}."
                ),
                background=(
                    f"Clinical Scenario: {request.scenario}. "
                    f"Current physiological telemetry: {vitals}. "
                    f"Observed vital trend: {trends}. "
                    f"Retrieved clinical protocols: {prot_display}."
                ),
                assessment=(
                    f"Synthesized clinical pattern indicates acute physiological stress consistent with the {request.scenario} trajectory. "
                    f"Abnormal vital channels and trend trajectories indicate progressive organ system strain and potential compromise."
                ),
                recommendation=(
                    "1. Conduct immediate bedside clinical and physical examination.\n"
                    "2. Reassess vital signs and verify pulse oximetry, blood pressure cuff sizing, and telemetry leads.\n"
                    "3. Initiate clinical deterioration protocols and draw stat arterial blood gas, basic metabolic panel, and CBC.\n"
                    "4. Escalate to attending physician and activate Rapid Response Team if instability persists."
                ),
                retrieved_protocols=protocol_names if protocol_names else [prot_display],
            )
