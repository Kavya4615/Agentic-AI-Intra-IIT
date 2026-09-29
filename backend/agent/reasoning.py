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
        knowledge_base: str,           # Phase 9: combined context + protocols
        protocol_names: list[str] | None = None,
    ) -> SBARResponse:
        """
        Generate a structured clinical explanation (SBAR) given the alert context,
        patient clinical context, and protocols.

        Parameters
        ----------
        request       : ExplanationRequest from the alert pipeline.
        knowledge_base: Combined context + protocol text (from rag.retrieve_with_context).
        protocol_names: List of protocol names retrieved (for the response field).
        """
        if protocol_names is None:
            protocol_names = []

        # Fallback to structured mock response when no valid API key is available
        if not self._use_live:
            return self._mock_response(request, knowledge_base, protocol_names)

        return self.chain.invoke({
            "patient_id": request.patient_id,
            "scenario": request.scenario,
            "alert_state": request.alert_state,
            "current_vitals": request.current_vitals,
            "risk_score": request.risk_score,
            "recent_trend_summary": request.recent_trend_summary,
            "knowledge_base": knowledge_base,
        })

    def _mock_response(
        self,
        request: ExplanationRequest,
        knowledge_base: str,
        protocol_names: list[str],
    ) -> SBARResponse:
        """
        Structured mock response that parses real context fields from the
        knowledge_base string to simulate grounded reasoning.
        """
        # Extract key context clues from the knowledge_base text
        kb_lower = knowledge_base.lower()
        context_hints = []

        # Medication cross-references
        if "metoprolol" in kb_lower or "beta-blocker" in kb_lower:
            context_hints.append(
                "Note: Patient is on a beta-blocker (Metoprolol) which may blunt "
                "the tachycardic response — HR values may underestimate physiological stress."
            )
        if "warfarin" in kb_lower or "inr" in kb_lower:
            context_hints.append(
                "Coagulation status is relevant — check INR before any invasive procedure."
            )
        if "lisinopril" in kb_lower or "ckd" in kb_lower:
            context_hints.append(
                "Elevated creatinine may reflect baseline CKD rather than acute deterioration — "
                "compare against patient's baseline."
            )
        if "furosemide" in kb_lower:
            context_hints.append(
                "Patient on loop diuretic — monitor potassium closely for hypokalaemia risk."
            )

        # Lab cross-references
        if "lactate" in kb_lower and ("2." in kb_lower or "h —" in kb_lower):
            context_hints.append(
                "Elevated lactate noted in recent labs — consistent with tissue hypoperfusion."
            )
        if "wbc" in kb_lower and "h —" in kb_lower:
            context_hints.append(
                "Elevated WBC in recent labs suggests active infection or inflammatory process."
            )
        if "hemoglobin" in kb_lower and ("decline" in kb_lower or "down from" in kb_lower):
            context_hints.append(
                "Haemoglobin declining — active haemorrhage must be considered."
            )

        context_note = " ".join(context_hints) if context_hints else (
            "Patient context reviewed — no specific medication or lab flags identified."
        )

        prot_display = ", ".join(protocol_names) if protocol_names else "General Deterioration Protocol"

        return SBARResponse(
            situation=(
                f"Patient {request.patient_id} has reached {request.alert_state} status "
                f"with a composite risk score of {request.risk_score}/100."
            ),
            background=(
                f"Scenario: {request.scenario}. "
                f"Current vitals: {request.current_vitals}. "
                f"Trend: {request.recent_trend_summary}. "
                f"Patient-specific context: {context_note}"
            ),
            assessment=(
                "[MOCK — set OPENAI_API_KEY for live LLM reasoning] "
                f"Clinical deterioration pattern consistent with {request.scenario} scenario. "
                "Multiple vital channels showing concordant abnormality. "
                f"Context-grounded notes: {context_note}"
            ),
            recommendation=(
                "Immediate bedside review recommended. "
                "Consider activating rapid response team if not already done. "
                "Review patient-specific medications and labs before intervention."
            ),
            retrieved_protocols=protocol_names if protocol_names else [prot_display],
        )
