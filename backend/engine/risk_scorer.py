"""
risk_scorer.py — Composite Risk Score Engine
=============================================
Combines per-channel trend analysis into a single 0–100 risk score.

Scoring formula (per channel):
    channel_score = (
        w_dev * deviation_score +
        w_slope * slope_score +
        w_persist * persistence_score
    )

Final composite score:
    raw_score = weighted_mean(channel_scores)
    risk_score = raw_score * concordance_multiplier * 100

The concordance_multiplier rewards situations where MULTIPLE channels
deteriorate together — the clinical hallmark of genuine patient deterioration
vs. isolated noise.

Weights are clinically motivated:
  - SpO2 and BP deviations are weighted higher (life-threatening faster)
  - Persistence is valued: sustained abnormality > transient spike
  - Concordance can amplify the score by up to 2× when all channels agree
"""

from dataclasses import dataclass, field
from typing import Dict, List

from engine.trend_detector import TrendReport, ChannelTrend

# ── Per-channel weights ───────────────────────────────────────────────────────
# Each channel contributes differently to the composite score.
CHANNEL_WEIGHTS: Dict[str, float] = {
    "heart_rate":        1.0,
    "spo2":              1.6,   # SpO2 drops are life-threatening faster
    "respiratory_rate":  1.1,
    "systolic_bp":       1.4,   # Hypotension/crisis is high priority
    "diastolic_bp":      0.9,
}

# ── Component weights within each channel ────────────────────────────────────
W_DEVIATION   = 0.40   # 40% — how far from baseline
W_SLOPE       = 0.30   # 30% — rate of change
W_PERSISTENCE = 0.30   # 30% — how long it's been abnormal

# ── Concordance multiplier ────────────────────────────────────────────────────
# Maps (number of bad channels) → score multiplier
# 0 bad channels → 0.5×  (single-channel noise gets heavily penalised)
# 1 bad channel  → 0.8×
# 2 bad channels → 1.0×
# 3 bad channels → 1.4×
# 4 bad channels → 1.7×
# 5 bad channels → 2.0×  (all systems failing = maximally amplified)
CONCORDANCE_MULTIPLIERS = {0: 0.5, 1: 0.8, 2: 1.0, 3: 1.4, 4: 1.7, 5: 2.0}


@dataclass
class ChannelRiskComponent:
    """Breakdown of how a single channel contributes to the risk score."""
    channel: str
    channel_weight: float
    deviation_score: float
    slope_score: float
    persistence_score: float
    raw_channel_score: float         # Weighted combination of the three components
    weighted_channel_score: float    # raw_channel_score × channel_weight

    def to_dict(self) -> dict:
        return {
            "channel":               self.channel,
            "channel_weight":        self.channel_weight,
            "deviation_score":       round(self.deviation_score, 3),
            "slope_score":           round(self.slope_score, 3),
            "persistence_score":     round(self.persistence_score, 3),
            "raw_channel_score":     round(self.raw_channel_score, 3),
            "weighted_channel_score": round(self.weighted_channel_score, 3),
        }


@dataclass
class RiskScore:
    """
    Complete risk score breakdown for a single assessment cycle.
    Provides full transparency into how the score was computed.
    """
    patient_id: str
    risk_score: float                               # Final 0–100 score
    raw_weighted_score: float                       # Before concordance multiplier
    concordance_multiplier: float
    concordant_channel_count: int
    concordant_channels: List[str]
    channel_components: Dict[str, ChannelRiskComponent] = field(default_factory=dict)

    # Convenience thresholds
    @property
    def is_watch(self) -> bool:
        return self.risk_score >= 25

    @property
    def is_suspected(self) -> bool:
        return self.risk_score >= 50

    @property
    def is_escalated(self) -> bool:
        return self.risk_score >= 72

    def to_dict(self) -> dict:
        return {
            "patient_id":               self.patient_id,
            "risk_score":               round(self.risk_score, 2),
            "raw_weighted_score":       round(self.raw_weighted_score, 4),
            "concordance_multiplier":   round(self.concordance_multiplier, 2),
            "concordant_channel_count": self.concordant_channel_count,
            "concordant_channels":      self.concordant_channels,
            "is_watch":                 self.is_watch,
            "is_suspected":             self.is_suspected,
            "is_escalated":             self.is_escalated,
            "channel_components": {
                ch: comp.to_dict()
                for ch, comp in self.channel_components.items()
            },
        }


def score_channel(trend: ChannelTrend, channel_weight: float) -> ChannelRiskComponent:
    """
    Compute the risk contribution for a single vital sign channel.

    Parameters
    ----------
    trend : ChannelTrend
        Trend analysis for this channel.
    channel_weight : float
        Clinical importance weighting for this channel.

    Returns
    -------
    ChannelRiskComponent
    """
    raw = (
        W_DEVIATION   * trend.deviation_score +
        W_SLOPE       * trend.slope_score +
        W_PERSISTENCE * trend.persistence_score
    )
    return ChannelRiskComponent(
        channel=trend.channel,
        channel_weight=channel_weight,
        deviation_score=trend.deviation_score,
        slope_score=trend.slope_score,
        persistence_score=trend.persistence_score,
        raw_channel_score=raw,
        weighted_channel_score=raw * channel_weight,
    )


def compute_risk_score(trend_report: TrendReport) -> RiskScore:
    """
    Convert a TrendReport into a composite RiskScore.

    Algorithm
    ---------
    1. For each channel, compute:
           channel_score = w_dev*deviation + w_slope*slope + w_persist*persistence
    2. Compute weighted mean across all channels (using CHANNEL_WEIGHTS).
    3. Count how many channels are "concordantly bad".
    4. Multiply by concordance multiplier.
    5. Scale to 0–100.

    Parameters
    ----------
    trend_report : TrendReport

    Returns
    -------
    RiskScore
    """
    total_weight = sum(CHANNEL_WEIGHTS.values())
    weighted_sum = 0.0
    components: Dict[str, ChannelRiskComponent] = {}

    for ch, trend in trend_report.channels.items():
        weight = CHANNEL_WEIGHTS.get(ch, 1.0)
        comp   = score_channel(trend, weight)
        components[ch] = comp
        weighted_sum  += comp.weighted_channel_score

    # Normalise by total weight → value in [0, 1]
    raw_weighted = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Concordance multiplier
    n_bad       = len(trend_report.concordant_channels)
    multiplier  = CONCORDANCE_MULTIPLIERS.get(n_bad, CONCORDANCE_MULTIPLIERS[5])

    # Final score: scaled to [0, 100], capped at 100
    final_score = min(raw_weighted * multiplier * 100, 100.0)

    return RiskScore(
        patient_id=trend_report.patient_id,
        risk_score=round(final_score, 2),
        raw_weighted_score=raw_weighted,
        concordance_multiplier=multiplier,
        concordant_channel_count=n_bad,
        concordant_channels=trend_report.concordant_channels,
        channel_components=components,
    )
