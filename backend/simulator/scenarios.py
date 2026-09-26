"""
scenarios.py — Clinical Scenario Engines
=========================================
Each scenario class controls how a patient's vitals evolve over time.
Scenarios are deterministic trajectories with added physiological noise,
designed to test every part of the trend-detection and alerting pipeline.

Scenario catalog:
  - StableScenario:              Vitals hover near baseline with normal noise.
  - GradualDeteriorationScenario: Slow, steady worsening (e.g., developing sepsis).
  - COPDExacerbationScenario:     Respiratory-focused deterioration.
  - SuddenCrisisScenario:         Normal vitals then abrupt crash (cardiac event).
  - ArtifactNoiseScenario:        Normal vitals with intermittent sensor artifacts.
  - RecoveryScenario:             Starts abnormal, gradually normalizes.
  - HemorrhagicShockScenario:     Progressive blood-loss pattern (↑HR, ↓BP, ↓SpO2).
  - IntermittentArrhythmiaScenario: Mostly stable with episodic HR irregularity.
"""

import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict


@dataclass
class VitalReading:
    """A single set of vital signs at a point in time."""
    heart_rate: float
    spo2: float
    respiratory_rate: float
    systolic_bp: float
    diastolic_bp: float
    is_artifact: bool = False   # Flag for intentionally injected artifacts

    def to_dict(self) -> Dict[str, float | bool]:
        return {
            "heart_rate": round(self.heart_rate, 1),
            "spo2": round(self.spo2, 1),
            "respiratory_rate": round(self.respiratory_rate, 1),
            "systolic_bp": round(self.systolic_bp, 1),
            "diastolic_bp": round(self.diastolic_bp, 1),
            "is_artifact": self.is_artifact,
        }


def _clamp(value: float, low: float, high: float) -> float:
    """Constrain a value within physiological bounds."""
    return max(low, min(high, value))


def _noise(std: float) -> float:
    """Gaussian noise with the given standard deviation."""
    return random.gauss(0, std)


# =============================================================================
#  Base class
# =============================================================================

class BaseScenario(ABC):
    """
    Abstract base for all scenario generators.
    
    Parameters
    ----------
    baseline : dict
        Per-vital baseline stats, e.g. {"heart_rate": {"mean": 74, "std": 4}, ...}
    """

    def __init__(self, baseline: Dict[str, Dict[str, float]]):
        self.baseline = baseline

    @abstractmethod
    def generate(self, elapsed_seconds: float) -> VitalReading:
        """
        Produce a vital reading for the given number of seconds since
        the simulation started for this patient.
        """
        ...


# =============================================================================
#  1. Stable — vitals hover around baseline with normal physiological noise
# =============================================================================

class StableScenario(BaseScenario):
    """Patient is hemodynamically stable. Vitals show only random fluctuation."""

    def generate(self, elapsed_seconds: float) -> VitalReading:
        b = self.baseline
        return VitalReading(
            heart_rate=_clamp(b["heart_rate"]["mean"] + _noise(b["heart_rate"]["std"]), 40, 180),
            spo2=_clamp(b["spo2"]["mean"] + _noise(b["spo2"]["std"]), 70, 100),
            respiratory_rate=_clamp(b["respiratory_rate"]["mean"] + _noise(b["respiratory_rate"]["std"]), 6, 40),
            systolic_bp=_clamp(b["systolic_bp"]["mean"] + _noise(b["systolic_bp"]["std"]), 60, 220),
            diastolic_bp=_clamp(b["diastolic_bp"]["mean"] + _noise(b["diastolic_bp"]["std"]), 30, 130),
        )


# =============================================================================
#  2. Gradual Deterioration — slow sepsis-like worsening over ~20-30 minutes
# =============================================================================

class GradualDeteriorationScenario(BaseScenario):
    """
    Vitals slowly worsen over time, mimicking developing sepsis:
    - Heart rate creeps up
    - Blood pressure drifts down
    - SpO2 gradually drops
    - Respiratory rate increases
    
    The deterioration accelerates after ~10 minutes (600 seconds) of simulation.
    """

    def generate(self, elapsed_seconds: float) -> VitalReading:
        b = self.baseline
        # Progress factor: 0 at start, ~1 at 20 minutes, accelerating after 10 min
        t_minutes = elapsed_seconds / 60.0
        # Sigmoid-like ramp: slow start, accelerates, then plateaus
        progress = 1.0 / (1.0 + math.exp(-0.3 * (t_minutes - 12)))

        # Deterioration magnitudes at full progress
        hr_shift     = progress * 35        # +35 bpm at peak
        spo2_shift   = progress * -8        # -8% at peak
        rr_shift     = progress * 12        # +12 breaths/min at peak
        sbp_shift    = progress * -30       # -30 mmHg systolic at peak
        dbp_shift    = progress * -20       # -20 mmHg diastolic at peak

        return VitalReading(
            heart_rate=_clamp(
                b["heart_rate"]["mean"] + hr_shift + _noise(b["heart_rate"]["std"]), 40, 180
            ),
            spo2=_clamp(
                b["spo2"]["mean"] + spo2_shift + _noise(b["spo2"]["std"] * 0.5), 70, 100
            ),
            respiratory_rate=_clamp(
                b["respiratory_rate"]["mean"] + rr_shift + _noise(b["respiratory_rate"]["std"]), 6, 45
            ),
            systolic_bp=_clamp(
                b["systolic_bp"]["mean"] + sbp_shift + _noise(b["systolic_bp"]["std"]), 60, 220
            ),
            diastolic_bp=_clamp(
                b["diastolic_bp"]["mean"] + dbp_shift + _noise(b["diastolic_bp"]["std"]), 30, 130
            ),
        )


# =============================================================================
#  3. COPD Exacerbation — respiratory-focused deterioration
# =============================================================================

class COPDExacerbationScenario(BaseScenario):
    """
    Respiratory parameters worsen prominently:
    - SpO2 drops significantly (from already-low baseline)
    - Respiratory rate climbs
    - Heart rate compensates upward
    - BP changes are modest
    
    The exacerbation develops over ~15 minutes with periodic "episodes" of
    worsening (simulating bronchospasm).
    """

    def generate(self, elapsed_seconds: float) -> VitalReading:
        b = self.baseline
        t_minutes = elapsed_seconds / 60.0
        progress = min(1.0, t_minutes / 18.0)

        # Episodic bronchospasm component — periodic worsening every ~5 minutes
        episodic = 0.3 * math.sin(2 * math.pi * t_minutes / 5.0)
        episodic = max(0, episodic)  # Only the "bad" half of the wave

        total_factor = progress + episodic * progress

        spo2_shift  = total_factor * -10       # SpO2 drops to low 80s from ~93
        rr_shift    = total_factor * 14        # RR can hit 34+
        hr_shift    = total_factor * 25        # Compensatory tachycardia
        sbp_shift   = total_factor * -10       # Mild hypotension
        dbp_shift   = total_factor * -5

        return VitalReading(
            heart_rate=_clamp(
                b["heart_rate"]["mean"] + hr_shift + _noise(b["heart_rate"]["std"]), 40, 180
            ),
            spo2=_clamp(
                b["spo2"]["mean"] + spo2_shift + _noise(b["spo2"]["std"]), 70, 100
            ),
            respiratory_rate=_clamp(
                b["respiratory_rate"]["mean"] + rr_shift + _noise(b["respiratory_rate"]["std"]), 6, 50
            ),
            systolic_bp=_clamp(
                b["systolic_bp"]["mean"] + sbp_shift + _noise(b["systolic_bp"]["std"]), 60, 220
            ),
            diastolic_bp=_clamp(
                b["diastolic_bp"]["mean"] + dbp_shift + _noise(b["diastolic_bp"]["std"]), 30, 130
            ),
        )


# =============================================================================
#  4. Sudden Crisis — normal then abrupt cardiac-event-like crash at ~8 min
# =============================================================================

class SuddenCrisisScenario(BaseScenario):
    """
    Patient appears stable for ~8 minutes (480 seconds), then vitals
    suddenly crash over 60-90 seconds, mimicking an acute MI or PE:
    - Heart rate spikes then may become bradycardic
    - BP crashes
    - SpO2 drops sharply
    - RR spikes initially
    """

    def __init__(self, baseline: Dict[str, Dict[str, float]]):
        super().__init__(baseline)
        # Add some randomness to the crisis onset (±2 minutes)
        self.crisis_onset = 480 + random.uniform(-120, 120)

    def generate(self, elapsed_seconds: float) -> VitalReading:
        b = self.baseline

        if elapsed_seconds < self.crisis_onset:
            # Pre-crisis: completely stable
            return VitalReading(
                heart_rate=_clamp(b["heart_rate"]["mean"] + _noise(b["heart_rate"]["std"]), 40, 180),
                spo2=_clamp(b["spo2"]["mean"] + _noise(b["spo2"]["std"]), 70, 100),
                respiratory_rate=_clamp(b["respiratory_rate"]["mean"] + _noise(b["respiratory_rate"]["std"]), 6, 40),
                systolic_bp=_clamp(b["systolic_bp"]["mean"] + _noise(b["systolic_bp"]["std"]), 60, 220),
                diastolic_bp=_clamp(b["diastolic_bp"]["mean"] + _noise(b["diastolic_bp"]["std"]), 30, 130),
            )
        else:
            # Crisis phase — rapid deterioration
            crisis_duration = elapsed_seconds - self.crisis_onset
            # Fast ramp: 0 → 1 over ~90 seconds
            severity = min(1.0, crisis_duration / 90.0)

            return VitalReading(
                heart_rate=_clamp(
                    b["heart_rate"]["mean"] + severity * 55 + _noise(3), 40, 200
                ),
                spo2=_clamp(
                    b["spo2"]["mean"] - severity * 18 + _noise(1), 60, 100
                ),
                respiratory_rate=_clamp(
                    b["respiratory_rate"]["mean"] + severity * 16 + _noise(2), 6, 50
                ),
                systolic_bp=_clamp(
                    b["systolic_bp"]["mean"] - severity * 50 + _noise(5), 50, 220
                ),
                diastolic_bp=_clamp(
                    b["diastolic_bp"]["mean"] - severity * 30 + _noise(3), 25, 130
                ),
            )


# =============================================================================
#  5. Artifact / Noise — normal vitals with intermittent sensor glitches
# =============================================================================

class ArtifactNoiseScenario(BaseScenario):
    """
    The patient is truly stable, but sensors produce occasional wild readings:
    - ~15% of readings contain an artifact in 1-2 channels
    - Artifacts are physiologically impossible values (SpO2=40, HR=250, etc.)
    - This tests the system's spike-gate / artifact-rejection logic
    """

    def generate(self, elapsed_seconds: float) -> VitalReading:
        b = self.baseline
        is_artifact = random.random() < 0.15

        if not is_artifact:
            return VitalReading(
                heart_rate=_clamp(b["heart_rate"]["mean"] + _noise(b["heart_rate"]["std"]), 40, 180),
                spo2=_clamp(b["spo2"]["mean"] + _noise(b["spo2"]["std"]), 70, 100),
                respiratory_rate=_clamp(b["respiratory_rate"]["mean"] + _noise(b["respiratory_rate"]["std"]), 6, 40),
                systolic_bp=_clamp(b["systolic_bp"]["mean"] + _noise(b["systolic_bp"]["std"]), 60, 220),
                diastolic_bp=_clamp(b["diastolic_bp"]["mean"] + _noise(b["diastolic_bp"]["std"]), 30, 130),
            )
        else:
            # Pick 1-2 channels to corrupt
            channels = ["hr", "spo2", "rr", "sbp", "dbp"]
            num_corrupted = random.choice([1, 2])
            corrupted = set(random.sample(channels, num_corrupted))

            hr = b["heart_rate"]["mean"] + _noise(b["heart_rate"]["std"])
            spo2 = b["spo2"]["mean"] + _noise(b["spo2"]["std"])
            rr = b["respiratory_rate"]["mean"] + _noise(b["respiratory_rate"]["std"])
            sbp = b["systolic_bp"]["mean"] + _noise(b["systolic_bp"]["std"])
            dbp = b["diastolic_bp"]["mean"] + _noise(b["diastolic_bp"]["std"])

            if "hr" in corrupted:
                hr = random.choice([0, 20, 220, 250, 300])
            if "spo2" in corrupted:
                spo2 = random.choice([0, 30, 45, 55])
            if "rr" in corrupted:
                rr = random.choice([0, 2, 55, 60])
            if "sbp" in corrupted:
                sbp = random.choice([0, 30, 250, 280])
            if "dbp" in corrupted:
                dbp = random.choice([0, 15, 160, 180])

            return VitalReading(
                heart_rate=hr,
                spo2=spo2,
                respiratory_rate=rr,
                systolic_bp=sbp,
                diastolic_bp=dbp,
                is_artifact=True,
            )


# =============================================================================
#  6. Recovery — starts abnormal, gradually normalizes over ~15 minutes
# =============================================================================

class RecoveryScenario(BaseScenario):
    """
    Patient starts with elevated vitals (post-op stress response) and
    gradually returns to normal as treatment takes effect.
    - HR comes down from ~100 to ~75
    - SpO2 improves from ~94 to ~97
    - RR normalizes from ~22 to ~16
    - BP stabilizes
    """

    def generate(self, elapsed_seconds: float) -> VitalReading:
        b = self.baseline
        t_minutes = elapsed_seconds / 60.0
        # Exponential decay toward normal baselines
        recovery_factor = math.exp(-0.08 * t_minutes)  # 0 → 1 decaying

        # Initial offsets (how "abnormal" the patient starts)
        hr_offset  = 26 * recovery_factor    # Starts +26 bpm above normal (~75)
        spo2_offset = -4 * recovery_factor   # Starts -4% below normal
        rr_offset  = 8 * recovery_factor     # Starts +8 above normal
        sbp_offset = -15 * recovery_factor   # Starts -15 mmHg (mild hypotension)
        dbp_offset = -10 * recovery_factor

        # Target "recovered" baselines (healthier than initial)
        target_hr = 75
        target_spo2 = 97
        target_rr = 15
        target_sbp = 125
        target_dbp = 75

        return VitalReading(
            heart_rate=_clamp(target_hr + hr_offset + _noise(b["heart_rate"]["std"]), 40, 180),
            spo2=_clamp(target_spo2 + spo2_offset + _noise(b["spo2"]["std"]), 70, 100),
            respiratory_rate=_clamp(target_rr + rr_offset + _noise(b["respiratory_rate"]["std"]), 6, 40),
            systolic_bp=_clamp(target_sbp + sbp_offset + _noise(b["systolic_bp"]["std"]), 60, 220),
            diastolic_bp=_clamp(target_dbp + dbp_offset + _noise(b["diastolic_bp"]["std"]), 30, 130),
        )


# =============================================================================
#  7. Hemorrhagic Shock — progressive blood loss pattern
# =============================================================================

class HemorrhagicShockScenario(BaseScenario):
    """
    Mimics compensated then decompensated hemorrhagic shock:
    Phase 1 (0–10 min): Compensatory — HR rises, BP maintained, SpO2 stable
    Phase 2 (10–20 min): Decompensation — BP crashes, SpO2 drops, HR very high
    
    Key clinical pattern: HR rises BEFORE BP drops (early compensatory tachycardia).
    """

    def generate(self, elapsed_seconds: float) -> VitalReading:
        b = self.baseline
        t_minutes = elapsed_seconds / 60.0

        if t_minutes < 10:
            # Phase 1: Compensatory
            phase_progress = t_minutes / 10.0
            hr_shift = phase_progress * 30        # HR rises to ~120
            spo2_shift = phase_progress * -2      # Minimal SpO2 change
            rr_shift = phase_progress * 6         # Mild tachypnea
            sbp_shift = phase_progress * -5       # BP barely affected
            dbp_shift = phase_progress * -3
        else:
            # Phase 2: Decompensation
            phase_progress = min(1.0, (t_minutes - 10) / 10.0)
            hr_shift = 30 + phase_progress * 25   # HR now 140+
            spo2_shift = -2 + phase_progress * -10 # SpO2 crashes
            rr_shift = 6 + phase_progress * 12    # RR very elevated
            sbp_shift = -5 + phase_progress * -45  # BP crashes
            dbp_shift = -3 + phase_progress * -25

        return VitalReading(
            heart_rate=_clamp(
                b["heart_rate"]["mean"] + hr_shift + _noise(b["heart_rate"]["std"]), 40, 200
            ),
            spo2=_clamp(
                b["spo2"]["mean"] + spo2_shift + _noise(b["spo2"]["std"]), 60, 100
            ),
            respiratory_rate=_clamp(
                b["respiratory_rate"]["mean"] + rr_shift + _noise(b["respiratory_rate"]["std"]), 6, 50
            ),
            systolic_bp=_clamp(
                b["systolic_bp"]["mean"] + sbp_shift + _noise(b["systolic_bp"]["std"]), 40, 220
            ),
            diastolic_bp=_clamp(
                b["diastolic_bp"]["mean"] + dbp_shift + _noise(b["diastolic_bp"]["std"]), 20, 130
            ),
        )


# =============================================================================
#  8. Intermittent Arrhythmia — mostly stable with episodic HR irregularity
# =============================================================================

class IntermittentArrhythmiaScenario(BaseScenario):
    """
    Patient is mostly stable but has periodic AFib episodes lasting ~2 minutes
    every ~7 minutes. During episodes:
    - HR jumps to 120-150 and becomes erratic
    - BP drops slightly
    - Other vitals stay near normal
    
    Tests the system's ability to distinguish transient episodes from sustained
    deterioration (should NOT escalate to crisis).
    """

    def generate(self, elapsed_seconds: float) -> VitalReading:
        b = self.baseline
        t_minutes = elapsed_seconds / 60.0

        # Episode detection: ~2 min episode every ~7 min cycle
        cycle_position = t_minutes % 7.0
        in_episode = cycle_position < 2.0

        if in_episode:
            # During AFib episode
            episode_progress = cycle_position / 2.0
            # Rapid, irregular HR
            hr = random.uniform(115, 155)
            # Slight BP drop during episode
            sbp_shift = -15
            dbp_shift = -8
            # Other vitals mildly affected
            rr_shift = 3
            spo2_shift = -2
        else:
            # Between episodes — normal sinus rhythm
            hr = b["heart_rate"]["mean"] + _noise(b["heart_rate"]["std"])
            sbp_shift = 0
            dbp_shift = 0
            rr_shift = 0
            spo2_shift = 0

        if in_episode:
            return VitalReading(
                heart_rate=_clamp(hr, 40, 200),
                spo2=_clamp(b["spo2"]["mean"] + spo2_shift + _noise(1), 70, 100),
                respiratory_rate=_clamp(b["respiratory_rate"]["mean"] + rr_shift + _noise(2), 6, 40),
                systolic_bp=_clamp(b["systolic_bp"]["mean"] + sbp_shift + _noise(b["systolic_bp"]["std"]), 60, 220),
                diastolic_bp=_clamp(b["diastolic_bp"]["mean"] + dbp_shift + _noise(b["diastolic_bp"]["std"]), 30, 130),
            )
        else:
            return VitalReading(
                heart_rate=_clamp(hr, 40, 200),
                spo2=_clamp(b["spo2"]["mean"] + _noise(b["spo2"]["std"]), 70, 100),
                respiratory_rate=_clamp(b["respiratory_rate"]["mean"] + _noise(b["respiratory_rate"]["std"]), 6, 40),
                systolic_bp=_clamp(b["systolic_bp"]["mean"] + _noise(b["systolic_bp"]["std"]), 60, 220),
                diastolic_bp=_clamp(b["diastolic_bp"]["mean"] + _noise(b["diastolic_bp"]["std"]), 30, 130),
            )


# =============================================================================
#  Scenario Factory — maps scenario names to classes
# =============================================================================

SCENARIO_MAP = {
    "stable":                  StableScenario,
    "gradual_deterioration":   GradualDeteriorationScenario,
    "copd_exacerbation":       COPDExacerbationScenario,
    "sudden_crisis":           SuddenCrisisScenario,
    "artifact_noise":          ArtifactNoiseScenario,
    "recovery":                RecoveryScenario,
    "hemorrhagic_shock":       HemorrhagicShockScenario,
    "intermittent_arrhythmia": IntermittentArrhythmiaScenario,
}


def create_scenario(scenario_name: str, baseline: Dict[str, Dict[str, float]]) -> BaseScenario:
    """
    Factory function: create a scenario instance from its name.
    
    Parameters
    ----------
    scenario_name : str
        One of the keys in SCENARIO_MAP.
    baseline : dict
        Per-vital baseline stats from the patient profile.
    
    Returns
    -------
    BaseScenario
        An instance of the matching scenario class.
    
    Raises
    ------
    ValueError
        If the scenario name is not recognized.
    """
    cls = SCENARIO_MAP.get(scenario_name)
    if cls is None:
        raise ValueError(
            f"Unknown scenario '{scenario_name}'. "
            f"Available: {list(SCENARIO_MAP.keys())}"
        )
    return cls(baseline)
