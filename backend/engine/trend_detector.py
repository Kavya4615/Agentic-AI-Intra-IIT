"""
trend_detector.py — Slope Calculation & Persistence Tracking
=============================================================
Analyses the rolling window of vital signs to detect meaningful deterioration
trajectories. Key outputs per channel:

  slope            — Rate of change (units/minute) via linear regression
  is_trending_bad  — Whether slope is moving in a clinically bad direction
  consecutive_bad  — How many consecutive readings have been abnormal
  persistence_mins — How long (minutes) the abnormality has persisted
  deviation_score  — Normalised distance from personal baseline (0–1)

The "trending bad" direction differs by channel:
  heart_rate      — bad if rising  (tachycardia)
  spo2            — bad if falling (desaturation)
  respiratory_rate— bad if rising  (tachypnea)
  systolic_bp     — bad if falling (hypotension) OR rising (hypertensive crisis)
  diastolic_bp    — bad if falling OR rising
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from scipy import stats as scipy_stats

from state.patient_state import CHANNEL_NAMES, PatientBaseline, PatientState

# ── Configuration ─────────────────────────────────────────────────────────────

# Minimum readings in window before slope calculation is meaningful
MIN_READINGS_FOR_SLOPE = 4

# How many standard deviations from baseline = "abnormal"
ABNORMAL_STD_THRESHOLD = 1.8

# Minimum absolute slope (units/minute) to count as a "trend" vs. noise
MIN_SLOPE_THRESHOLD: Dict[str, float] = {
    "heart_rate":        0.5,   # 0.5 bpm/minute
    "spo2":              0.1,   # 0.1%/minute
    "respiratory_rate":  0.2,   # 0.2 breaths/minute
    "systolic_bp":       0.5,   # 0.5 mmHg/minute
    "diastolic_bp":      0.3,
}

# Channels where a positive slope is "bad" (rising = worse)
RISING_IS_BAD    = {"heart_rate", "respiratory_rate"}
# Channels where a negative slope is "bad" (falling = worse)
FALLING_IS_BAD   = {"spo2", "systolic_bp", "diastolic_bp"}
# BP can be bad in either direction — handled separately


@dataclass
class ChannelTrend:
    """Trend analysis results for one vital sign channel."""
    channel: str
    current_value: Optional[float]     = None
    baseline_mean: Optional[float]     = None
    baseline_std: Optional[float]      = None

    # Slope (units per minute) — positive = rising, negative = falling
    slope: float                       = 0.0
    slope_r_squared: float             = 0.0    # How linear the trend is (0–1)

    # Whether the slope is moving clinically bad
    is_trending_bad: bool              = False

    # Deviation from personal baseline (in standard deviations)
    deviation_stds: float              = 0.0

    # Normalised deviation score 0–1 (0 = at baseline, 1 = very abnormal)
    deviation_score: float             = 0.0

    # Persistence: how long / how many readings have been consistently abnormal
    consecutive_abnormal: int          = 0
    persistence_minutes: float         = 0.0
    persistence_score: float           = 0.0    # Normalised 0–1

    # Rate-of-change score 0–1 (0 = flat, 1 = very steep change)
    slope_score: float                 = 0.0

    def to_dict(self) -> dict:
        return {
            "channel":              self.channel,
            "current_value":        round(self.current_value, 2) if self.current_value is not None else None,
            "baseline_mean":        self.baseline_mean,
            "baseline_std":         self.baseline_std,
            "slope_per_min":        round(self.slope, 3),
            "slope_r_squared":      round(self.slope_r_squared, 3),
            "is_trending_bad":      self.is_trending_bad,
            "deviation_stds":       round(self.deviation_stds, 2),
            "deviation_score":      round(self.deviation_score, 3),
            "consecutive_abnormal": self.consecutive_abnormal,
            "persistence_minutes":  round(self.persistence_minutes, 2),
            "persistence_score":    round(self.persistence_score, 3),
            "slope_score":          round(self.slope_score, 3),
        }


@dataclass
class TrendReport:
    """Complete trend analysis for all channels of one patient."""
    patient_id: str
    channels: Dict[str, ChannelTrend]   = field(default_factory=dict)
    concordant_channels: List[str]       = field(default_factory=list)
    concordance_score: float             = 0.0   # 0–1, fraction of channels trending bad
    window_readings: int                 = 0
    window_duration_seconds: float       = 0.0

    def to_dict(self) -> dict:
        return {
            "patient_id":              self.patient_id,
            "window_readings":         self.window_readings,
            "window_duration_seconds": round(self.window_duration_seconds, 1),
            "concordant_channels":     self.concordant_channels,
            "concordance_score":       round(self.concordance_score, 3),
            "channels":                {ch: t.to_dict() for ch, t in self.channels.items()},
        }


def _compute_slope(
    values: np.ndarray,
    readings_per_minute: float = 12.0,
) -> tuple[float, float]:
    """
    Compute slope in units-per-minute using linear regression.

    Parameters
    ----------
    values : np.ndarray
        Recent channel values in time order.
    readings_per_minute : float
        Frequency of readings (default 12 = every 5 seconds).

    Returns
    -------
    (slope_per_minute, r_squared)
    """
    n = len(values)
    if n < MIN_READINGS_FOR_SLOPE:
        return 0.0, 0.0

    # Time axis in minutes (equally spaced by 1/readings_per_minute)
    x = np.arange(n) / readings_per_minute

    slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, values)
    r_squared = r_value ** 2

    return float(slope), float(r_squared)


def _deviation_score(deviation_stds: float) -> float:
    """
    Convert standard-deviation distance to a normalised 0–1 score.
    Uses a sigmoid-like function:
      0 std → 0.0
      2 std → ~0.5
      4 std → ~0.9
    """
    return float(1.0 / (1.0 + np.exp(-0.8 * (deviation_stds - 2.0))))


def _slope_score(slope: float, channel: str) -> float:
    """
    Convert slope magnitude to a normalised 0–1 score.
    Each channel has a different scale for what counts as "steep".
    """
    # Maximum slopes that map to score ≈ 1.0
    max_slopes = {
        "heart_rate":        3.0,   # 3 bpm/minute is very fast
        "spo2":              1.0,   # 1%/minute drop is serious
        "respiratory_rate":  1.0,
        "systolic_bp":       2.0,
        "diastolic_bp":      1.5,
    }
    maximum = max_slopes.get(channel, 1.0)
    magnitude = abs(slope) / maximum
    return float(min(magnitude, 1.0))


def _persistence_score(persistence_minutes: float) -> float:
    """
    Convert persistence duration to a normalised 0–1 score.
    5+ minutes of sustained abnormality → score ≈ 1.0
    """
    return float(min(persistence_minutes / 5.0, 1.0))


def analyse_channel(
    channel: str,
    values: np.ndarray,
    baseline: PatientBaseline,
    reading_interval_seconds: float = 5.0,
) -> ChannelTrend:
    """
    Full trend analysis for a single vital sign channel.

    Parameters
    ----------
    channel : str
        Channel name (e.g., "heart_rate").
    values : np.ndarray
        Rolling window values for this channel (chronological).
    baseline : PatientBaseline
        Patient's personal baseline.
    reading_interval_seconds : float
        How often readings arrive (default 5 s).

    Returns
    -------
    ChannelTrend
    """
    trend = ChannelTrend(channel=channel)

    if len(values) == 0:
        return trend

    # Current value (most recent)
    trend.current_value = float(values[-1])

    # Baseline
    normal = baseline.get_normal_range(channel)
    trend.baseline_mean = normal.get("mean")
    trend.baseline_std  = normal.get("std", 1.0)

    # ── Deviation from baseline ───────────────────────────────────────────────
    if trend.baseline_mean is not None and trend.baseline_std and trend.baseline_std > 0:
        trend.deviation_stds = abs(trend.current_value - trend.baseline_mean) / trend.baseline_std
        trend.deviation_score = _deviation_score(trend.deviation_stds)

    # ── Slope ─────────────────────────────────────────────────────────────────
    readings_per_minute = 60.0 / reading_interval_seconds
    trend.slope, trend.slope_r_squared = _compute_slope(values, readings_per_minute)
    trend.slope_score = _slope_score(trend.slope, channel)

    # ── Direction — is the slope clinically bad? ──────────────────────────────
    min_slope = MIN_SLOPE_THRESHOLD.get(channel, 0.3)
    if channel in RISING_IS_BAD:
        trend.is_trending_bad = trend.slope > min_slope
    elif channel in FALLING_IS_BAD:
        trend.is_trending_bad = trend.slope < -min_slope
    else:
        # BP: bad in either direction beyond threshold
        trend.is_trending_bad = abs(trend.slope) > min_slope

    # ── Persistence — count consecutive abnormal readings ────────────────────
    normal_low  = normal.get("low",  -np.inf)
    normal_high = normal.get("high",  np.inf)

    consecutive = 0
    for val in reversed(values):
        if val < normal_low or val > normal_high:
            consecutive += 1
        else:
            break  # Stop at first normal reading

    trend.consecutive_abnormal = consecutive
    trend.persistence_minutes  = (consecutive * reading_interval_seconds) / 60.0
    trend.persistence_score    = _persistence_score(trend.persistence_minutes)

    return trend


def analyse_patient_trends(
    state: PatientState,
    reading_interval_seconds: float = 5.0,
) -> TrendReport:
    """
    Generate a complete TrendReport for a patient by analysing all channels.

    Parameters
    ----------
    state : PatientState
        Current patient state (contains rolling window and baseline).
    reading_interval_seconds : float
        Sensor frequency, default 5 s.

    Returns
    -------
    TrendReport
    """
    report = TrendReport(
        patient_id=state.patient_id,
        window_readings=len(state.window),
        window_duration_seconds=state.window_duration_seconds(),
    )

    bad_channels = []

    for ch in CHANNEL_NAMES:
        values = state.get_channel_array(ch)
        trend  = analyse_channel(ch, values, state.baseline, reading_interval_seconds)
        report.channels[ch] = trend

        if trend.is_trending_bad or trend.deviation_score > 0.4:
            bad_channels.append(ch)

    report.concordant_channels = bad_channels
    report.concordance_score   = len(bad_channels) / len(CHANNEL_NAMES)

    return report
