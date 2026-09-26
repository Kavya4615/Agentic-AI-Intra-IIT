"""
generator.py — Synthetic Patient Vital Sign Generator
======================================================
The main entry point for the simulator. It creates a scenario for each patient
and produces a continuous stream of vital sign readings at a configurable interval.

Usage (standalone):
    python -m simulator.generator

This will print JSON-formatted vital readings to stdout every few seconds, 
allowing you to visually verify the data before connecting it to the ingestion gateway.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional

from simulator.patients import PatientProfile, get_all_patients
from simulator.scenarios import BaseScenario, VitalReading, create_scenario


class PatientSimulator:
    """
    Manages the simulation for a single patient.
    
    Holds the patient's profile, their assigned scenario, and tracks elapsed
    time to generate time-appropriate vital readings.
    """

    def __init__(self, patient: PatientProfile):
        self.patient = patient
        self.scenario: BaseScenario = create_scenario(
            patient.scenario, patient.baseline_vitals
        )
        self.start_time: float = time.monotonic()
        self.reading_count: int = 0

    def generate_reading(self) -> Dict:
        """
        Generate the next vital reading for this patient.
        
        Returns a dictionary ready for JSON serialization containing the
        patient ID, timestamp, vital values, and metadata.
        """
        elapsed = time.monotonic() - self.start_time
        vitals: VitalReading = self.scenario.generate(elapsed)
        self.reading_count += 1

        return {
            "patient_id": self.patient.patient_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(elapsed, 1),
            "reading_number": self.reading_count,
            "vitals": vitals.to_dict(),
        }

    def reset(self):
        """Reset the simulation clock (e.g., to restart a scenario)."""
        self.start_time = time.monotonic()
        self.reading_count = 0
        # Re-create scenario to reset any internal state (e.g., crisis onset randomness)
        self.scenario = create_scenario(
            self.patient.scenario, self.patient.baseline_vitals
        )


class CohortSimulator:
    """
    Manages simultaneous simulations for an entire cohort of patients.
    
    Parameters
    ----------
    patients : list of PatientProfile, optional
        Which patients to simulate. Defaults to the full registry.
    interval_seconds : float
        Time between readings per patient. Default 5.0 seconds.
    """

    def __init__(
        self,
        patients: Optional[List[PatientProfile]] = None,
        interval_seconds: float = 5.0,
    ):
        self.patients = patients or get_all_patients()
        self.interval = interval_seconds
        self.simulators: Dict[str, PatientSimulator] = {
            p.patient_id: PatientSimulator(p) for p in self.patients
        }
        self._running = False

    def generate_all_readings(self) -> List[Dict]:
        """Generate one reading for every patient in the cohort (synchronous)."""
        return [sim.generate_reading() for sim in self.simulators.values()]

    async def stream(self) -> AsyncGenerator[Dict, None]:
        """
        Async generator that yields one reading per patient per interval.
        
        Yields
        ------
        dict
            A vital reading dictionary for one patient.
        """
        self._running = True
        while self._running:
            for sim in self.simulators.values():
                reading = sim.generate_reading()
                yield reading
            await asyncio.sleep(self.interval)

    def stop(self):
        """Stop the streaming loop."""
        self._running = False

    def get_patient_profiles(self) -> List[Dict]:
        """Return all patient profiles as serializable dicts."""
        return [p.to_dict() for p in self.patients]


# =============================================================================
#  Standalone runner — for testing and visual verification
# =============================================================================

async def _run_demo():
    """
    Run the simulator standalone, printing colored output to the terminal.
    Press Ctrl+C to stop.
    """
    sim = CohortSimulator(interval_seconds=3.0)

    # Print patient roster
    print("=" * 80)
    print("  SYNTHETIC PATIENT SIMULATOR — COHORT ROSTER")
    print("=" * 80)
    for p in sim.patients:
        print(f"  {p.patient_id} | {p.name:<20s} | Age {p.age} {p.sex} | Scenario: {p.scenario}")
    print("=" * 80)
    print(f"  Streaming vitals every {sim.interval}s  |  Press Ctrl+C to stop")
    print("=" * 80)
    print()

    # Color codes for terminal output
    COLORS = {
        "stable": "\033[92m",                   # Green
        "gradual_deterioration": "\033[91m",     # Red
        "copd_exacerbation": "\033[93m",         # Yellow
        "sudden_crisis": "\033[95m",             # Magenta
        "artifact_noise": "\033[90m",            # Gray
        "recovery": "\033[96m",                  # Cyan
        "hemorrhagic_shock": "\033[91m",         # Red
        "intermittent_arrhythmia": "\033[94m",   # Blue
    }
    RESET = "\033[0m"

    try:
        async for reading in sim.stream():
            pid = reading["patient_id"]
            patient = sim.simulators[pid].patient
            v = reading["vitals"]
            color = COLORS.get(patient.scenario, "")

            # Format vital signs with warning indicators
            hr_warn = " ⚠" if v["heart_rate"] > 110 or v["heart_rate"] < 50 else ""
            spo2_warn = " ⚠" if v["spo2"] < 92 else ""
            rr_warn = " ⚠" if v["respiratory_rate"] > 24 or v["respiratory_rate"] < 8 else ""
            sbp_warn = " ⚠" if v["systolic_bp"] < 90 or v["systolic_bp"] > 180 else ""
            artifact_tag = " [ARTIFACT]" if v.get("is_artifact") else ""

            print(
                f"{color}"
                f"[{reading['timestamp'][:19]}] "
                f"{pid} {patient.name:<18s} | "
                f"HR:{v['heart_rate']:5.1f}{hr_warn:3s} | "
                f"SpO2:{v['spo2']:5.1f}%{spo2_warn:3s} | "
                f"RR:{v['respiratory_rate']:5.1f}{rr_warn:3s} | "
                f"BP:{v['systolic_bp']:5.1f}/{v['diastolic_bp']:4.1f}{sbp_warn:3s}"
                f"{artifact_tag}"
                f"{RESET}"
            )

    except KeyboardInterrupt:
        sim.stop()
        print("\n\n  Simulation stopped.")


def main():
    """Entry point for `python -m simulator.generator`."""
    asyncio.run(_run_demo())


if __name__ == "__main__":
    main()
