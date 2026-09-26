"""
preprocessor.py — Spike Gate & Artifact Filter
================================================
Detects and removes physiologically impossible or transient sensor artifacts
BEFORE the values reach trend detection and risk scoring.

Two-stage filtering:
  Stage 1 — Hard physiological limits: values outside the possible range
             for any living human are immediately flagged as artifacts.
  Stage 2 — Statistical spike gate: values that deviate more than
             SPIKE_THRESHOLD * MAD from the recent rolling median are
             flagged as transient spikes (e.g., a sensor shifting).

The filter outputs a cleaned reading with an `is_artifact` flag and a
reason string explaining why a reading was filtered.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from state.patient_state import CHANNEL_NAMES

# ── Hard physiological limits ─────────────────────────────────────────────────
# Values outside these ranges are impossible in any living patient.
HARD_LIMITS: Dict[str, Tuple[float, float]] = {
    "heart_rate":       (20,  300),
    "spo2":             (50,  100),
    "respiratory_rate": (4,   70),
    "systolic_bp":      (50,  300),
    "diastolic_bp":     (20,  200),
}

# Statistical spike gate threshold (multiples of MAD)
# Higher = more permissive (fewer false artifact detections)
SPIKE_THRESHOLD = 4.0

# Minimum window length before statistical filtering activates
MIN_WINDOW_FOR_SPIKE_GATE = 5


@dataclass
class FilterResult:
    """Result of running a reading through the artifact filter."""
    patient_id: str
    original_vitals: dict
    cleaned_vitals: dict
    is_artifact: bool = False
    artifact_reason: str = ""
    channels_flagged: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "patient_id":      self.patient_id,
            "original_vitals": self.original_vitals,
            "cleaned_vitals":  self.cleaned_vitals,
            "is_artifact":     self.is_artifact,
            "artifact_reason": self.artifact_reason,
            "channels_flagged": self.channels_flagged,
        }


def _median_absolute_deviation(values: np.ndarray) -> float:
    """
    Compute the Median Absolute Deviation (MAD) — a robust measure of spread.
    More outlier-resistant than standard deviation.
    """
    if len(values) == 0:
        return 0.0
    median = np.median(values)
    return float(np.median(np.abs(values - median)))


def check_hard_limits(vitals: dict) -> Tuple[bool, str, List[str]]:
    """
    Stage 1: Check if any vital is outside hard physiological limits.

    Returns
    -------
    (is_artifact, reason_string, list_of_flagged_channels)
    """
    flagged = []
    reasons = []
    for ch, (low, high) in HARD_LIMITS.items():
        val = vitals.get(ch)
        if val is None:
            continue
        if val < low or val > high:
            flagged.append(ch)
            reasons.append(f"{ch}={val:.1f} outside [{low}, {high}]")

    if flagged:
        return True, "Hard limit breach: " + "; ".join(reasons), flagged
    return False, "", []


def check_spike_gate(
    vitals: dict,
    channel_history: Dict[str, np.ndarray],
    threshold: float = SPIKE_THRESHOLD,
) -> Tuple[bool, str, List[str]]:
    """
    Stage 2: Statistical spike gate using MAD.
    Flags a reading if any channel deviates too far from the rolling median.

    Parameters
    ----------
    vitals : dict
        The current vital signs.
    channel_history : dict
        {channel_name: np.array of recent values} from the rolling window.
    threshold : float
        Number of MADs away from median to flag as spike.

    Returns
    -------
    (is_spike, reason_string, list_of_flagged_channels)
    """
    flagged = []
    reasons = []

    for ch in CHANNEL_NAMES:
        val = vitals.get(ch)
        history = channel_history.get(ch, np.array([]))

        if val is None or len(history) < MIN_WINDOW_FOR_SPIKE_GATE:
            continue  # Not enough history to judge

        median = np.median(history)
        mad    = _median_absolute_deviation(history)

        # Avoid division by zero — if MAD is very small, use a floor value
        mad = max(mad, 0.5)

        deviation = abs(val - median) / mad
        if deviation > threshold:
            flagged.append(ch)
            reasons.append(
                f"{ch}={val:.1f} (median={median:.1f}, MAD={mad:.1f}, "
                f"deviation={deviation:.1f}σ > {threshold}σ)"
            )

    if flagged:
        return True, "Spike gate: " + "; ".join(reasons), flagged
    return False, "", []


def filter_reading(
    reading: dict,
    channel_history: Dict[str, np.ndarray],
) -> FilterResult:
    """
    Main entry point for the pre-processor.

    Runs a reading through both filtering stages.
    If flagged, marks the reading as artifact (does NOT modify values).
    The caller decides whether to discard the reading or use cleaned_vitals.

    Parameters
    ----------
    reading : dict
        Full reading dict from the simulator/WebSocket.
    channel_history : dict
        {channel: np.array} of recent window values for this patient.

    Returns
    -------
    FilterResult
    """
    pid    = reading.get("patient_id", "")
    vitals = reading.get("vitals", {})

    # If simulator already flagged it as artifact, trust that
    if vitals.get("is_artifact", False):
        return FilterResult(
            patient_id=pid,
            original_vitals=vitals,
            cleaned_vitals=vitals,
            is_artifact=True,
            artifact_reason="Simulator-flagged artifact",
            channels_flagged=list(CHANNEL_NAMES),
        )

    # Stage 1: Hard physiological limits
    is_hard, hard_reason, hard_flagged = check_hard_limits(vitals)
    if is_hard:
        return FilterResult(
            patient_id=pid,
            original_vitals=vitals,
            cleaned_vitals={**vitals, "is_artifact": True},
            is_artifact=True,
            artifact_reason=hard_reason,
            channels_flagged=hard_flagged,
        )

    # Stage 2: Statistical spike gate
    is_spike, spike_reason, spike_flagged = check_spike_gate(vitals, channel_history)
    if is_spike:
        return FilterResult(
            patient_id=pid,
            original_vitals=vitals,
            cleaned_vitals={**vitals, "is_artifact": True},
            is_artifact=True,
            artifact_reason=spike_reason,
            channels_flagged=spike_flagged,
        )

    # Clean reading — passes all checks
    return FilterResult(
        patient_id=pid,
        original_vitals=vitals,
        cleaned_vitals=vitals,
        is_artifact=False,
    )
