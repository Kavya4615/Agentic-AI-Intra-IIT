# Midterm Report: Clinical Decision-Support System

## 1. Project Overview

The objective of this project is to build an Agentic Clinical Decision-Support System (CDSS) capable of real-time patient monitoring, deterministic risk evaluation, and context-aware LLM reasoning. The system aims to assist clinicians in Intensive Care Unit (ICU) or general ward settings by identifying early signs of clinical deterioration and providing structured, actionable insights.

## 2. Progress to Date

The project has been executed in distinct phases. We have successfully completed all planned implementation phases (1 through 12):

### Core Infrastructure (Phases 1-5)
- **Simulator & Ingestion:** Built a high-frequency WebSocket simulator streaming vital signs (HR, SpO2, RR, BP) for 8 distinct patient profiles. Implemented a FastAPI gateway for ingestion.
- **Deterministic Pipeline:** Implemented a signal preprocessor (smoothing, artifact rejection), a risk scoring engine, and an alert state machine (Normal → Watch → Suspected → Escalated). This guarantees sub-second alert triggering.

### Agentic Layer (Phases 6-8)
- **Agent Service & RAG:** Built an LLM agent that triggers on `ESCALATED` alerts. It uses Retrieval-Augmented Generation (RAG) to fetch relevant clinical protocols (e.g., Sepsis, COPD exacerbation) based on the patient's scenario.
- **Frontend Dashboard:** Developed a React/Tailwind frontend to visualize live vitals (sparklines), risk scores, and the generated SBAR (Situation, Background, Assessment, Recommendation) reports.

### Advanced Integration (Phases 9-11)
- **Phase 9 - Patient Clinical Context:** Integrated static patient profiles (history, current medications, recent labs) into the RAG pipeline. The LLM now actively cross-references real-time vitals against facts like beta-blocker usage or baseline CKD, significantly reducing false positive context errors.
- **Phase 10 - Clinician Decision Workflow:** Implemented a "human-in-the-loop" feedback mechanism. Clinicians can Accept, Dismiss, Defer, or Investigate alerts. Dismissals feed back into the state machine to enforce cooldown periods and prevent alarm fatigue.
- **Phase 11 - Full Audit Trail:** Built an in-memory audit logger that tags every event in an escalation episode (Observation → Retrieval → Reasoning → Alert → Decision) with a unique correlation ID, enabling full explainability traces.

## 3. Key Findings & Challenges

- **Deterministic vs. Agentic:** Initial attempts to have the LLM evaluate every single reading were too slow and costly. We learned that the LLM is best used as a *synthesiser of context* after a fast, deterministic engine has triggered the alert.
- **Context Grounding:** Standard RAG was insufficient. Injecting explicit patient facts (like "Patient is on Metoprolol") alongside the protocol text drastically improved the accuracy of the LLM's assessment, allowing it to recognize blunted physiological responses.
- **Alarm Fatigue Mitigation:** The addition of the Phase 10 decision workflow proved essential. A CDSS is only usable if it allows clinicians to snooze or dismiss alerts that they have already clinically evaluated.

## 4. Next Steps (Future Work)

While the core objectives are complete, future enhancements could include:
- **Database Integration:** Moving the in-memory state, decision registry, and audit log to PostgreSQL and Redis for persistence and scalability.
- **Live EHR Integration:** Replacing the static `patient_context_data.py` with dynamic HL7/FHIR integrations to pull real-time lab results and medication administration records.
- **Advanced Embeddings:** Upgrading the keyword-based RAG retriever to use semantic vector embeddings (e.g., `pgvector`) for more nuanced protocol matching.
- **Authentication:** Implementing role-based access control (RBAC) to securely track which clinician made which decision.

## 5. Conclusion

The CDSS successfully demonstrates a viable hybrid architecture for clinical AI. By combining the speed and safety of deterministic rules with the contextual reasoning power of Large Language Models, the system provides timely, explainable, and personalized clinical decision support while mitigating the risks of autonomous AI.
