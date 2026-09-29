import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.schemas import ExplanationRequest
from agent.rag import ClinicalKnowledgeBase
from agent.reasoning import ClinicalReasoningAgent

def main():
    print("=" * 80)
    print("  AGENTIC REASONING LAYER — VERIFICATION RUN")
    print("=" * 80)
    
    # 1. Initialize RAG Knowledge Base
    kb = ClinicalKnowledgeBase()
    scenario_query = "sepsis deterioration"
    print(f"\n[1] Querying RAG Knowledge Base for: '{scenario_query}'...")
    protocols = kb.retrieve_relevant_protocols(scenario_query)
    print(f"Retrieved Protocol Snippet:\n{protocols[:250]}...\n")
    
    # 2. Simulate an escalated alert request from the pipeline
    request = ExplanationRequest(
        patient_id="P002",
        scenario="gradual_deterioration (Sepsis)",
        alert_state="ESCALATED",
        current_vitals={
            "heart_rate": 128.0,
            "spo2": 91.5,
            "respiratory_rate": 26.0,
            "blood_pressure_systolic": 88.0,
            "blood_pressure_diastolic": 55.0
        },
        risk_score=88.9,
        recent_trend_summary="HR rising (+1.8 bpm/min), BP dropping (-1.2 mmHg/min), persistent for >10 mins"
    )
    
    # 3. Invoke the Reasoning Agent
    agent = ClinicalReasoningAgent()
    has_key = bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "mock-key")
    print(f"[2] Invoking Clinical Reasoning Agent (OpenAI API Key set: {has_key})...")
    explanation = agent.generate_explanation(request, retrieved_protocols=protocols)
    
    print("\n[3] Structured SBAR Output:")
    print("-" * 80)
    print(f"SITUATION:      {explanation.situation}")
    print(f"BACKGROUND:     {explanation.background}")
    print(f"ASSESSMENT:     {explanation.assessment}")
    print(f"RECOMMENDATION: {explanation.recommendation}")
    print(f"PROTOCOLS:      {explanation.retrieved_protocols}")
    print("=" * 80)
    print("  Agent test completed successfully!")
    print("=" * 80)

if __name__ == "__main__":
    main()
