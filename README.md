# Real-Time Agentic Clinical Decision-Support System (CDSS)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat&logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An intelligent, real-time clinical monitoring and early deterioration detection system. Built on a **two-layer architecture**:
1. **Deterministic Core Engine**: High-throughput statistical pre-processing, artifact filtering, multi-vital trend regression, cross-channel concordance scoring, and a 4-tier state machine to eliminate alert fatigue.
2. **Agentic Reasoning Layer**: Clinical context synthesis, retrieval-augmented protocol checks, and clinician-facing explanations.

---

## Architecture Overview

```
 ┌───────────────────────────┐
 │ Synthetic Patient Cohort  │ (8 Scenarios: Sepsis, COPD, Shock, Arrhythmia, etc.)
 └─────────────┬─────────────┘
               │ (5-sec streaming intervals)
               ▼
 ┌───────────────────────────┐
 │ FastAPI Ingestion Gateway │ WebSocket (/ws/vitals/{id}) + REST APIs
 └─────────────┬─────────────┘
               ▼
 ┌───────────────────────────┐
 │   Patient State Engine    │ Rolling-window buffer & per-patient baseline memory
 └─────────────┬─────────────┘
               ▼
 ┌───────────────────────────┐
 │ Preprocessor & Trend Det. │ MAD spike gate + Scipy linear regression slope
 └─────────────┬─────────────┘
               ▼
 ┌───────────────────────────┐
 │   Composite Risk Scorer   │ Deviation (40%) + Slope (30%) + Persistence (30%)
 └─────────────┬─────────────┘ * Cross-vital concordance multiplier (0.5x - 2.0x)
               ▼
 ┌───────────────────────────┐
 │    Alert State Machine    │ NORMAL ──▶ WATCH ──▶ SUSPECTED ──▶ ESCALATED
 └───────────────────────────┘ (Hold timers, hysteresis & alert fatigue suppression)
```

---

## Key Features

- **Physiologically Grounded Patient Simulator:**
  - 8 realistic patient scenarios: Stable recovery, Sepsis deterioration, COPD exacerbation, Sudden hemorrhagic shock, Sensor motion artifacts, Arrhythmia, etc.
  - Monitors 4 vital channels simultaneously: **Heart Rate (HR)**, **Oxygen Saturation (SpO2)**, **Respiratory Rate (RR)**, and **Blood Pressure (Systolic/Diastolic)**.
- **Two-Stage Artifact Gate:**
  - Hard physiological limit checking combined with **Median Absolute Deviation (MAD)** spike rejection to prevent false alarms from sensor disconnects or patient movement.
- **Multi-Parameter Trend & Risk Engine:**
  - Computes rates of change via linear regression.
  - Evaluates cross-channel concordance (e.g. rising HR + dropping BP = acute shock signature).
- **Fatigue-Resistant Alert Lifecycle:**
  - 4-level finite state machine (`NORMAL` → `WATCH` → `SUSPECTED` → `ESCALATED`).
  - Configurable hold durations require sustained risk before escalating.
  - Cooldown and dismissal suppression to protect clinicians from alarm fatigue.
- **Embedded & Standalone Streaming:**
  - Supports both direct WebSocket streaming from external simulators and an embedded background simulator mode for single-command development.

---

## Project Structure

```
Agentic-AI-Intra-IIT/
├── backend/
│   ├── agent/                 # AI Agent layer & clinical knowledge base (Phase 7)
│   ├── alerts/
│   │   ├── pipeline.py        # End-to-end deterministic processing pipeline
│   │   └── state_machine.py   # 4-tier alert state machine & suppression rules
│   ├── database/              # PostgreSQL & audit trail schemas
│   ├── engine/
│   │   ├── preprocessor.py    # Bounds verification & MAD spike filtering
│   │   ├── risk_scorer.py     # Composite risk scoring with concordance multipliers
│   │   └── trend_detector.py  # Linear regression slope & persistence detection
│   ├── ingestion/
│   │   ├── main.py            # FastAPI gateway (WebSockets + REST endpoints)
│   │   └── schemas.py         # Pydantic data contracts
│   ├── simulator/
│   │   ├── generator.py       # Cohort streaming engine
│   │   ├── patients.py        # 8 clinical patient profiles and baseline definitions
│   │   └── scenarios.py       # Trajectory mathematical formulas
│   ├── state/
│   │   └── patient_state.py   # In-memory rolling state actor
│   ├── test_pipeline.py       # End-to-end deterministic pipeline integration test
│   ├── test_simulator.py      # Simulator vital generation validation test
│   └── requirements.txt       # Python backend dependencies
└── README.md
```

---

## Getting Started

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Setup Virtual Environment

```powershell
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Running the Application

### Option A: Run the Live FastAPI Server
Starts the ingestion server with embedded simulator auto-running:

```powershell
.\venv\Scripts\python.exe -m uvicorn ingestion.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Interactive API Documentation (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **All Patient Profiles:** [http://127.0.0.1:8000/api/patients](http://127.0.0.1:8000/api/patients)
- **Latest Cohort Vitals:** [http://127.0.0.1:8000/api/vitals/latest](http://127.0.0.1:8000/api/vitals/latest)

---

### Option B: Run End-to-End Pipeline Integration Test
Executes 1,600 readings across all 8 patient scenarios to verify risk scores and alert state transitions:

```powershell
.\venv\Scripts\python.exe test_pipeline.py
```

Expected output snapshot:
```
====================================================================================================
  DETERMINISTIC PIPELINE - END-TO-END INTEGRATION TEST
  200 readings x 8 patients = 1600 total
====================================================================================================
  Patient  Name                 Scenario                   Avg Risk Max Risk Artifacts Transitions
  --------------------------------------------------------------------------------------------------
  P001     Rajesh Kumar         stable                         23.1     69.1        21   1 transition(s)
  P002     Priya Sharma         gradual_deterioration          62.9    100.0        22   3 transition(s)
  P003     Maria Fernandes      copd_exacerbation              64.2    100.0        26   3 transition(s)
  P004     Amit Patel           sudden_crisis                  62.9    100.0        31   3 transition(s)
  P005     Sunita Devi          artifact_noise                 19.8     61.4        44   0 transition(s)
  P006     Vikram Singh         recovery                       35.4     88.0        26   1 transition(s)
  P007     Arjun Mehta          hemorrhagic_shock              68.5    100.0        32   3 transition(s)
  P008     Lakshmi Nair         intermittent_arrhythmia        43.0    100.0        54   1 transition(s)
```

---

### Option C: Run Synthetic Patient Simulator Standalone
Streams vitals continuously directly into your terminal:

```powershell
.\venv\Scripts\python.exe -m simulator --speed 2.0
```

---

## Simulated Patient Cohort

| ID | Name | Age / Bed | Scenario | Expected Outcome |
|:---|:---|:---|:---|:---|
| **P001** | Rajesh Kumar | 58 / Bed 101 | Stable Recovery | Baseline fluctuations; stays `NORMAL` |
| **P002** | Priya Sharma | 45 / Bed 102 | Gradual Deterioration (Sepsis) | Progressive fever, tachycardia, tachypnea; escalates to `ESCALATED` |
| **P003** | Maria Fernandes | 71 / Bed 103 | COPD Exacerbation | Hypoxemia + tachypnea; rapid escalation |
| **P004** | Amit Patel | 34 / Bed 104 | Sudden Crisis (Pneumothorax) | Acute desaturation & severe tachycardia |
| **P005** | Sunita Devi | 62 / Bed 105 | Sensor Noise / Motion Artifact | High noise; filtered out by MAD gate with 0 false escalations |
| **P006** | Vikram Singh | 50 / Bed 106 | Post-Op Recovery | Mild initial elevation resolving to normal |
| **P007** | Arjun Mehta | 28 / Bed 107 | Hemorrhagic Shock | Falling BP + rising HR; cross-channel concordance alert |
| **P008** | Lakshmi Nair | 67 / Bed 108 | Intermittent Arrhythmia | Episodic tachycardia bursts |

---

## Upcoming Roadmap

- [x] **Phase 1:** Synthetic Patient Simulator
- [x] **Phase 2:** FastAPI WebSocket & Ingestion Gateway
- [x] **Phase 3:** Real-time Patient State Engine
- [x] **Phase 4:** MAD Preprocessing & Trend Detection Engine
- [x] **Phase 5:** Composite Risk Scorer & Multi-Channel Concordance
- [x] **Phase 6:** Alert State Machine & Suppression Logic
- [ ] **Phase 7:** Agentic LLM Reasoning Layer (Clinical RAG + Structured Explanations)
- [ ] **Phase 8:** Real-time Clinician Dashboard UI (React + TypeScript + Tailwind)
