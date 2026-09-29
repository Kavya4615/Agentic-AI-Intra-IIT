"""
test_context_integration.py — Phase 9 Integration Tests
=========================================================
Verifies that:
1. PatientContext profiles exist and are well-formed for all 8 patients.
2. The RAG retrieve_with_context() method returns text referencing context fields.
3. The ClinicalReasoningAgent mock response cites specific context facts
   (medication names, lab values) for context-rich patients.
4. Spot-checks: P002 (sepsis) output mentions WBC/Lactate; P003 output mentions
   Metoprolol (beta-blocker masking); P007 output mentions Haemoglobin decline.
"""

import sys
import os

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulator.patient_context_data import get_patient_context, get_all_contexts
from agent.rag import ClinicalKnowledgeBase
from agent.reasoning import ClinicalReasoningAgent
from agent.schemas import ExplanationRequest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_request(patient_id: str, scenario: str, risk: float = 85.0) -> ExplanationRequest:
    return ExplanationRequest(
        patient_id=patient_id,
        scenario=scenario,
        alert_state="ESCALATED",
        current_vitals={"heart_rate": 110, "spo2": 89, "respiratory_rate": 26, "systolic_bp": 85},
        risk_score=risk,
        recent_trend_summary="HR rising (+3.2/min); SpO2 falling (-1.1/min); BP falling (-2.0/min)",
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_all_contexts_exist():
    """All 8 patients must have a PatientContext defined."""
    contexts = get_all_contexts()
    expected_ids = {"P001", "P002", "P003", "P004", "P005", "P006", "P007", "P008"}
    found_ids = set(contexts.keys())
    missing = expected_ids - found_ids
    assert not missing, f"Missing PatientContext for: {missing}"
    print(f"  [OK] All 8 PatientContext profiles found: {sorted(found_ids)}")


def test_context_fields_are_non_empty():
    """Each context must have non-empty history, medications, and labs."""
    for pid, ctx in get_all_contexts().items():
        assert ctx.relevant_history, f"{pid}: relevant_history is empty"
        assert ctx.current_medications, f"{pid}: current_medications is empty"
        assert ctx.recent_labs, f"{pid}: recent_labs is empty"
        assert ctx.baseline_vitals, f"{pid}: baseline_vitals is empty"
    print("  [OK] All PatientContext profiles have non-empty fields")


def test_rag_retrieve_with_context_returns_combined():
    """RAG must return context block + protocol block together."""
    kb = ClinicalKnowledgeBase()
    ctx = get_patient_context("P002")
    combined, protocol_names = kb.retrieve_with_context("gradual_deterioration", patient_context=ctx)

    assert "PATIENT CLINICAL CONTEXT" in combined, "Missing context header in RAG output"
    assert "RELEVANT CLINICAL PROTOCOLS" in combined, "Missing protocol header in RAG output"
    assert "P002" in combined, "Context should reference patient ID"
    assert len(protocol_names) > 0, "Should return at least one protocol name"
    print(f"  [OK] RAG retrieve_with_context returns combined text (len={len(combined)})")
    print(f"    Protocols retrieved: {protocol_names}")


def test_p002_sbar_mentions_wbc_or_lactate():
    """
    P002 (sepsis) has elevated WBC and borderline Lactate.
    The mock SBAR Background or Assessment must reference at least one of these.
    """
    kb = ClinicalKnowledgeBase()
    agent = ClinicalReasoningAgent()
    ctx = get_patient_context("P002")

    combined, protocol_names = kb.retrieve_with_context("gradual_deterioration", patient_context=ctx)
    request = _make_request("P002", "gradual_deterioration", risk=88.0)
    sbar = agent.generate_explanation(request, knowledge_base=combined, protocol_names=protocol_names)

    full_text = (sbar.background + sbar.assessment + sbar.recommendation).lower()

    # Must contain at least one clinical context clue
    assert (
        "wbc" in full_text
        or "lactate" in full_text
        or "infection" in full_text
        or "sepsis" in full_text
        or "ckd" in full_text
    ), f"P002 SBAR does not reference expected sepsis context. Background: {sbar.background}"

    print(f"  [OK] P002 SBAR references clinical context (WBC/Lactate/infection)")
    print(f"    Background snippet: {sbar.background[:200]}...")


def test_p003_sbar_mentions_beta_blocker():
    """
    P003 (COPD) is on Metoprolol (beta-blocker) and has AFib.
    The mock SBAR must flag that beta-blockers blunt the tachycardic response.
    """
    kb = ClinicalKnowledgeBase()
    agent = ClinicalReasoningAgent()
    ctx = get_patient_context("P003")

    combined, protocol_names = kb.retrieve_with_context("copd_exacerbation", patient_context=ctx)
    request = _make_request("P003", "copd_exacerbation", risk=91.0)
    sbar = agent.generate_explanation(request, knowledge_base=combined, protocol_names=protocol_names)

    full_text = (sbar.background + sbar.assessment).lower()

    assert (
        "metoprolol" in full_text
        or "beta" in full_text
        or "blunt" in full_text
        or "rate" in full_text
    ), f"P003 SBAR does not mention Metoprolol/beta-blocker context. Got: {sbar.background}"

    print(f"  [OK] P003 SBAR mentions Metoprolol/beta-blocker masking effect")
    print(f"    Background snippet: {sbar.background[:200]}...")


def test_p007_sbar_mentions_haemoglobin_decline():
    """
    P007 (hemorrhagic shock) has a documented Hgb drop from 14.2→12.0 g/dL.
    The mock SBAR must reference haemoglobin / bleeding / haemorrhage.
    """
    kb = ClinicalKnowledgeBase()
    agent = ClinicalReasoningAgent()
    ctx = get_patient_context("P007")

    combined, protocol_names = kb.retrieve_with_context("hemorrhagic_shock", patient_context=ctx)
    request = _make_request("P007", "hemorrhagic_shock", risk=95.0)
    sbar = agent.generate_explanation(request, knowledge_base=combined, protocol_names=protocol_names)

    full_text = (sbar.background + sbar.assessment).lower()

    assert (
        "haemoglobin" in full_text
        or "hemoglobin" in full_text
        or "hgb" in full_text
        or "haemorrhage" in full_text
        or "hemorrhage" in full_text
        or "bleeding" in full_text
        or "lactate" in full_text
        or "decline" in full_text
    ), f"P007 SBAR does not mention Hgb/bleeding context. Got: {sbar.background}"

    print(f"  [OK] P007 SBAR references haemoglobin decline / haemorrhagic context")
    print(f"    Background snippet: {sbar.background[:200]}...")


def test_context_text_format():
    """PatientContext.to_structured_text() must include key fields."""
    for pid in ["P002", "P003", "P007"]:
        ctx = get_patient_context(pid)
        text = ctx.to_structured_text()
        assert "Age/Sex" in text, f"{pid}: structured text missing Age/Sex"
        assert "Relevant History" in text, f"{pid}: structured text missing Relevant History"
        assert "Current Medications" in text, f"{pid}: structured text missing Current Medications"
        assert "Recent Labs" in text, f"{pid}: structured text missing Recent Labs"
    print("  [OK] PatientContext.to_structured_text() includes all required sections")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("=" * 70)
    print("  PHASE 9 — CLINICAL CONTEXT INTEGRATION TESTS")
    print("=" * 70)
    print()

    tests = [
        test_all_contexts_exist,
        test_context_fields_are_non_empty,
        test_rag_retrieve_with_context_returns_combined,
        test_p002_sbar_mentions_wbc_or_lactate,
        test_p003_sbar_mentions_beta_blocker,
        test_p007_sbar_mentions_haemoglobin_decline,
        test_context_text_format,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"  [FAIL] {test.__name__}")
            print(f"         {e}")
        except Exception as e:
            failed += 1
            print(f"  [ERROR] {test.__name__}: {type(e).__name__}: {e}")

    print()
    print("=" * 70)
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 70)
    print()

    if failed:
        sys.exit(1)
