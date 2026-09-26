"""
test_pipeline.py — End-to-End Integration Test
================================================
Simulates 200 readings per patient through the full deterministic pipeline
and prints a summary table showing risk scores and alert level transitions.

Run with:
    .\\venv\\Scripts\\python.exe test_pipeline.py
"""

import time
from datetime import datetime, timezone

from alerts.pipeline import create_pipeline
from simulator.patients import get_all_patients
from simulator.scenarios import create_scenario

READINGS_PER_PATIENT = 200
READING_INTERVAL_S   = 5      # Simulate 5-second intervals (16 min of data)


def fake_reading(patient_id: str, vitals_dict: dict, t: int, n: int) -> dict:
    """Build a reading dict in the format the pipeline expects."""
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "patient_id":     patient_id,
        "timestamp":      ts,
        "elapsed_seconds": t,
        "reading_number":  n,
        "vitals":         vitals_dict,
    }


def run():
    print("=" * 100)
    print("  DETERMINISTIC PIPELINE — END-TO-END INTEGRATION TEST")
    print(f"  {READINGS_PER_PATIENT} readings × 8 patients = {READINGS_PER_PATIENT * 8} total")
    print("=" * 100)

    # Initialise pipeline (also initialises StateManager)
    pipeline = create_pipeline()
    patients = get_all_patients()

    # Create a scenario per patient
    scenarios = {
        p.patient_id: create_scenario(p.scenario, p.baseline_vitals)
        for p in patients
    }

    # Per-patient tracking
    results_by_patient = {p.patient_id: {
        "name":        p.name,
        "scenario":    p.scenario,
        "risk_scores": [],
        "alert_transitions": [],
        "artifact_count":    0,
    } for p in patients}

    # Feed readings through pipeline
    for n in range(1, READINGS_PER_PATIENT + 1):
        elapsed_s = (n - 1) * READING_INTERVAL_S

        for p in patients:
            pid      = p.patient_id
            vitals   = scenarios[pid].generate(elapsed_s)
            reading  = fake_reading(pid, vitals.to_dict(), elapsed_s, n)

            result = pipeline.process(reading)

            rec = results_by_patient[pid]

            if result.skipped:
                rec["artifact_count"] += 1
            else:
                if result.risk_score:
                    rec["risk_scores"].append(result.risk_score.risk_score)

                if result.alert_event:
                    rec["alert_transitions"].append({
                        "reading":    n,
                        "elapsed_min": round(elapsed_s / 60, 1),
                        "from":  result.alert_event.from_level.value,
                        "to":    result.alert_event.to_level.value,
                        "score": round(result.alert_event.risk_score, 1),
                    })

    # Print results
    print()
    print(f"  {'Patient':<8} {'Name':<20} {'Scenario':<26} {'Avg Risk':>8} {'Max Risk':>8} {'Artifacts':>9} {'Transitions'}")
    print("  " + "-" * 98)

    for pid, rec in results_by_patient.items():
        scores    = rec["risk_scores"]
        avg_risk  = sum(scores) / len(scores) if scores else 0
        max_risk  = max(scores) if scores else 0
        n_trans   = len(rec["alert_transitions"])

        print(
            f"  {pid:<8} {rec['name']:<20} {rec['scenario']:<26} "
            f"{avg_risk:>8.1f} {max_risk:>8.1f} {rec['artifact_count']:>9}   {n_trans} transition(s)"
        )

    print()
    print("  ALERT TRANSITIONS DETAIL:")
    print("  " + "-" * 98)
    for pid, rec in results_by_patient.items():
        if rec["alert_transitions"]:
            print(f"  {pid} — {rec['name']}:")
            for t in rec["alert_transitions"]:
                print(
                    f"    Reading #{t['reading']:>3} (t={t['elapsed_min']:>4.1f}min) "
                    f"{t['from']:>10} -> {t['to']:<10}  risk={t['score']}"
                )

    print()
    print("=" * 100)
    print("  Pipeline test complete.")
    print("=" * 100)


if __name__ == "__main__":
    run()
