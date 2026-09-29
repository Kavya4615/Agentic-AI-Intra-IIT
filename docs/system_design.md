# System Design Rationale

This document outlines the design decisions and architectural trade-offs made during the development of the Clinical Decision-Support System (CDSS).

## 1. Hybrid Architecture (Deterministic + Agentic)

The core challenge in clinical decision-support is balancing the need for absolute reliability and explainability with the desire for intelligent, context-aware reasoning. 

To solve this, the CDSS employs a **hybrid architecture**:
- **Deterministic Pipeline (Safety & Speed):** A strict, rules-based pipeline handles the high-volume incoming vital signs. It performs signal smoothing, calculates an Early Warning Score (EWS), and manages alert state transitions (Normal → Watch → Suspected → Escalated). This ensures that critical alerts are fired instantly and reliably, without the latency or unpredictability of an LLM.
- **Agentic Layer (Context & Synthesis):** Once the deterministic pipeline fires an `ESCALATED` alert, the Agentic Layer is invoked. An LLM (acting as the clinical reasoning agent) synthesises the vital sign trends with patient-specific static context (medical history, recent labs) and retrieves relevant clinical protocols via RAG. It produces a structured SBAR (Situation, Background, Assessment, Recommendation) report.

**Rationale:** LLMs are powerful synthesisers but prone to hallucination and latency. By decoupling the *trigger* (deterministic) from the *explanation* (agentic), the system guarantees that no critical alert is missed due to API failure, while still providing rich, clinician-friendly context when an alert does occur.

## 2. In-Memory State & Event-Driven Processing

The system processes real-time WebSocket streams from a patient simulator.
- **State Management:** The `patient_state.py` module maintains an in-memory buffer of the last 300 readings (1 hour) per patient. This allows for fast trend calculation (e.g., linear regression slopes over a rolling window) without hammering a database.
- **Event-Driven:** The `state_machine.py` acts as a dampener. It requires sustained threshold breaches to escalate an alert, preventing alarm fatigue from transient spikes (e.g., a patient moving, causing a brief HR spike).

**Rationale:** For the prototype, in-memory processing provides the lowest latency for stream data. In a production environment, this would be backed by a time-series database (e.g., InfluxDB) and a stream processor (e.g., Apache Kafka), but the internal logical flow (buffer → score → state machine) remains identical.

## 3. Context-Aware RAG (Phase 9)

In Phase 9, the Retrieval-Augmented Generation (RAG) system was upgraded to inject a `PatientContext` block into the LLM prompt alongside the retrieved clinical protocols.
- **Patient Context:** Contains age, sex, relevant medical history, current medications, recent labs, and baseline vitals.

**Rationale:** Generic protocol retrieval is insufficient for complex patients. For example, a heart rate of 95 bpm might be "normal" for a healthy adult, but highly concerning for a patient on beta-blockers (which blunt heart rate response). By passing explicit context to the LLM and instructing it to cross-reference medications and labs (e.g., rising WBC, elevated lactate), the SBAR report becomes highly personalised and clinically relevant.

## 4. Clinician-in-the-Loop Workflow (Phase 10)

The system does not act autonomously; it supports human clinicians.
- **Decisions:** Clinicians can Accept, Dismiss, Defer (snooze), or Investigate an alert.
- **Side Effects:** A "Dismiss" decision actively feeds back into the deterministic state machine, forcing the patient state back to `NORMAL` and enforcing a cooldown period to suppress immediate re-alerting.

**Rationale:** Alarm fatigue is the primary reason clinical AI systems fail in practice. Providing explicit tools to dismiss or snooze alerts, and tying those decisions back to the alert generator, is critical for usability.

## 5. Explainability and Audit Trail (Phase 11)

Every action in an escalation episode is logged with a shared `correlation_id`.
- **Chain:** Observation (vitals) → Retrieval (RAG context/protocols) → Reasoning (LLM SBAR) → Alert Transition → Clinician Decision.

**Rationale:** In healthcare, "black box" AI is unacceptable. If an adverse event occurs, administrators must be able to reconstruct exactly what data the system saw, what protocols it retrieved, what explanation it generated, and how the clinician responded. The correlation ID groups these asynchronous events into a single, cohesive explainability trace.
