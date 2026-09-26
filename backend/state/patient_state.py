"""
patient_state.py — Patient State Engine
=========================================
Maintains an evolving per-patient record that updates incrementally as new
vital readings arrive. Key responsibilities:

  1. Rolling window  — keeps the last N readings for trend calculations
  2. Baseline        — establishes each patient's personal "normal" 
  3. State tracking  — current alert level, transition timestamps
  4. Summary stats   — per-channel mean/std over the window

Design notes:
  - Uses collections.deque with a fixed maxlen for O(1) append + auto-eviction.
  - Baseline is computed from the first BASELINE_READINGS readings, then frozen.
    This lets the system learn each patient's individual normals before alerting.
  - All vitals channels are tracked uniformly via CHANNEL_NAMES.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

from simulator.patients import PatientProfile

# ── Configuration ────────────────────────────────────────────────────────────

WINDOW_SIZE       = 36    # Number of readings in the rolling window (~3 min at 5s interval)
BASELINE_READINGS = 20    # How many initial readings to use to build the baseline
CHANNEL_NAMES     = ["heart_rate", "spo2", "respiratory_rate", "systolic_bp", "diastolic_bp"]

# Population-level normal ranges used before a personal baseline is established
POPULATION_NORMALS: Dict[str, Dict[str, float]] = {
    "heart_rate":       {"low": 60,  "high": 100, "critical_low": 40,  "critical_high": 130},
    "spo2":             {"low": 95,  "high": 100, "critical_low": 88,  "critical_high": 100},
    "respiratory_rate": {"low": 12,  "high": 20,  "critical_low": 8,   "critical_high": 30},
    "systolic_bp":      {"low": 90,  "high": 140, "critical_low": 70,  "critical_high": 180},
    "diastolic_bp":     {"low": 60,  "high": 90,  "critical_low": 40,  "critical_high": 120},
}


class AlertLevel(str, Enum):
    """Alert severity levels — matches the state machine in Phase 6."""
    NORMAL    = "NORMAL"
    WATCH     = "WATCH"
    SUSPECTED = "SUSPECTED"
    ESCALATED = "ESCALATED"


@dataclass
class ChannelStats:
    """Running statistics for a single vital sign channel over the window."""
    channel: str
    values: List[float] = field(default_factory=list)   # Raw values in window

    @property
    def mean(self) -> Optional[float]:
        return float(np.mean(self.values)) if self.values else None

    @property
    def std(self) -> Optional[float]:
        return float(np.std(self.values)) if len(self.values) > 1 else None

    @property
    def latest(self) -> Optional[float]:
        return self.values[-1] if self.values else None

    @property
    def min(self) -> Optional[float]:
        return float(np.min(self.values)) if self.values else None

    @property
    def max(self) -> Optional[float]:
        return float(np.max(self.values)) if self.values else None

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "latest": self.latest,
            "mean": round(self.mean, 2) if self.mean is not None else None,
            "std": round(self.std, 2) if self.std is not None else None,
            "min": self.min,
            "max": self.max,
            "count": len(self.values),
        }


@dataclass
class PatientBaseline:
    """
    Each patient's personal normal ranges, derived from their initial readings.
    Once established (after BASELINE_READINGS readings), the baseline is frozen
    so it doesn't drift due to deterioration.
    """
    established: bool = False
    readings_collected: int = 0
    channels: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Raw accumulator — only used during baseline collection
    _accumulator: Dict[str, List[float]] = field(default_factory=lambda: {ch: [] for ch in CHANNEL_NAMES})

    def add_reading(self, vitals: dict) -> bool:
        """
        Feed a reading into the baseline accumulator.
        Returns True when the baseline becomes established.
        """
        if self.established:
            return True

        for ch in CHANNEL_NAMES:
            val = vitals.get(ch)
            if val is not None:
                self._accumulator[ch].append(val)

        self.readings_collected += 1

        if self.readings_collected >= BASELINE_READINGS:
            self._compute()
            return True
        return False

    def _compute(self):
        """Freeze the baseline from accumulated readings."""
        for ch in CHANNEL_NAMES:
            vals = self._accumulator[ch]
            if vals:
                mean = float(np.mean(vals))
                std  = max(float(np.std(vals)), 1.0)  # Minimum std=1 to avoid division by zero
                # Use 2.5 std dev as the personal "normal" band
                self.channels[ch] = {
                    "mean": round(mean, 2),
                    "std":  round(std,  2),
                    "low":  round(mean - 2.5 * std, 2),
                    "high": round(mean + 2.5 * std, 2),
                }
        self.established = True

    def get_normal_range(self, channel: str) -> Dict[str, float]:
        """
        Return normal range for a channel.
        Falls back to population normals if baseline not yet established.
        """
        if self.established and channel in self.channels:
            return self.channels[channel]
        return POPULATION_NORMALS.get(channel, {"low": 0, "high": 999})

    def to_dict(self) -> dict:
        return {
            "established": self.established,
            "readings_collected": self.readings_collected,
            "channels": self.channels,
        }


class PatientState:
    """
    Authoritative, continuously-updated state for one patient.

    Updated with every incoming vital reading. Provides:
      - Rolling window of recent readings
      - Per-channel statistics over the window
      - Personal baseline (once established)
      - Current alert level and transition history
    """

    def __init__(self, profile: PatientProfile):
        self.patient_id   = profile.patient_id
        self.profile      = profile
        self.baseline     = PatientBaseline()

        # Try to seed baseline from profile's predefined baseline_vitals
        if profile.baseline_vitals:
            for ch in CHANNEL_NAMES:
                if ch in profile.baseline_vitals:
                    bv = profile.baseline_vitals[ch]
                    mean = bv.get("mean", 0)
                    std  = max(bv.get("std", 1), 1.0)
                    self.baseline.channels[ch] = {
                        "mean": mean,
                        "std":  std,
                        "low":  round(mean - 2.5 * std, 2),
                        "high": round(mean + 2.5 * std, 2),
                    }
            self.baseline.established = True
            self.baseline.readings_collected = BASELINE_READINGS

        # Rolling window — raw reading dicts (last WINDOW_SIZE readings)
        self.window: deque = deque(maxlen=WINDOW_SIZE)

        # Per-channel value arrays for numpy operations
        self._channel_windows: Dict[str, deque] = {
            ch: deque(maxlen=WINDOW_SIZE) for ch in CHANNEL_NAMES
        }

        # Alert state
        self.alert_level: AlertLevel   = AlertLevel.NORMAL
        self.alert_level_since: float  = time.monotonic()
        self.last_escalation_time: Optional[float] = None

        # Risk score tracking
        self.current_risk_score: float = 0.0
        self.risk_score_history: deque = deque(maxlen=WINDOW_SIZE)

        # Counts
        self.total_readings: int = 0
        self.artifact_count: int = 0

        # Timestamp of last reading
        self.last_reading_time: Optional[str] = None

    def update(self, reading: dict) -> "PatientState":
        """
        Ingest a new vital reading. This is called by the ingestion gateway
        for every reading that passes validation.

        Parameters
        ----------
        reading : dict
            The raw reading dict from the simulator/WebSocket.

        Returns
        -------
        self — for chaining
        """
        vitals = reading.get("vitals", {})
        is_artifact = vitals.get("is_artifact", False)

        self.total_readings += 1
        self.last_reading_time = reading.get("timestamp")

        if is_artifact:
            self.artifact_count += 1
            # Artifacts are NOT added to the rolling window —
            # they should not influence trends or baselines.
            return self

        # Add to rolling window
        self.window.append(reading)

        # Update per-channel deques
        for ch in CHANNEL_NAMES:
            val = vitals.get(ch)
            if val is not None:
                self._channel_windows[ch].append(float(val))

        # Feed baseline accumulator (no-op once established)
        self.baseline.add_reading(vitals)

        return self

    def get_channel_array(self, channel: str) -> np.ndarray:
        """Return numpy array of recent values for a channel."""
        return np.array(list(self._channel_windows[channel]), dtype=float)

    def get_channel_stats(self, channel: str) -> ChannelStats:
        """Return ChannelStats for a single channel."""
        stats = ChannelStats(channel=channel, values=list(self._channel_windows[channel]))
        return stats

    def get_all_channel_stats(self) -> Dict[str, ChannelStats]:
        """Return ChannelStats for all channels."""
        return {ch: self.get_channel_stats(ch) for ch in CHANNEL_NAMES}

    def get_latest_vitals(self) -> Optional[dict]:
        """Return the most recent non-artifact vital reading."""
        return self.window[-1] if self.window else None

    def window_duration_seconds(self) -> float:
        """Approximate how many seconds of data are in the window."""
        if len(self.window) < 2:
            return 0.0
        try:
            t0 = datetime.fromisoformat(self.window[0]["timestamp"].replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(self.window[-1]["timestamp"].replace("Z", "+00:00"))
            return (t1 - t0).total_seconds()
        except Exception:
            return 0.0

    def set_alert_level(self, level: AlertLevel):
        """Update the alert level and record the transition time."""
        if level != self.alert_level:
            self.alert_level = level
            self.alert_level_since = time.monotonic()
            if level == AlertLevel.ESCALATED:
                self.last_escalation_time = time.monotonic()

    def seconds_at_current_level(self) -> float:
        """How many seconds has the patient been at the current alert level."""
        return time.monotonic() - self.alert_level_since

    def to_summary_dict(self) -> dict:
        """Compact summary suitable for API responses and dashboard."""
        latest = self.get_latest_vitals()
        latest_vitals = latest.get("vitals", {}) if latest else {}

        return {
            "patient_id":          self.patient_id,
            "name":                self.profile.name,
            "age":                 self.profile.age,
            "sex":                 self.profile.sex,
            "alert_level":         self.alert_level.value,
            "risk_score":          round(self.current_risk_score, 2),
            "seconds_at_level":    round(self.seconds_at_current_level(), 1),
            "total_readings":      self.total_readings,
            "artifact_count":      self.artifact_count,
            "window_size":         len(self.window),
            "baseline_established": self.baseline.established,
            "last_reading_time":   self.last_reading_time,
            "latest_vitals":       latest_vitals,
            "channel_stats": {
                ch: self.get_channel_stats(ch).to_dict()
                for ch in CHANNEL_NAMES
            },
        }


class StateManager:
    """
    Holds PatientState objects for all patients in the cohort.
    
    Acts as the single source of truth for current patient state.
    The ingestion gateway calls `update()` on every incoming reading,
    and the risk engine reads state via `get_state()`.
    """

    def __init__(self):
        self._states: Dict[str, PatientState] = {}

    def initialize_patient(self, profile: PatientProfile) -> PatientState:
        """Create and register state for a patient."""
        state = PatientState(profile)
        self._states[profile.patient_id] = state
        return state

    def update(self, reading: dict) -> Optional[PatientState]:
        """
        Update state for the patient named in the reading.
        Returns the updated PatientState (or None if patient unknown).
        """
        pid = reading.get("patient_id")
        state = self._states.get(pid)
        if state:
            state.update(reading)
        return state

    def get_state(self, patient_id: str) -> Optional[PatientState]:
        """Look up a patient's state."""
        return self._states.get(patient_id)

    def all_states(self) -> List[PatientState]:
        """Return all patient states."""
        return list(self._states.values())

    def cohort_summary(self) -> List[dict]:
        """Return summary dicts for all patients, sorted by risk score descending."""
        summaries = [s.to_summary_dict() for s in self._states.values()]
        return sorted(summaries, key=lambda x: x["risk_score"], reverse=True)

    def initialize_all(self):
        """Initialize states for all patients in the registry."""
        from simulator.patients import get_all_patients
        for p in get_all_patients():
            self.initialize_patient(p)
        return self


# Singleton instance shared across the application
state_manager = StateManager()
