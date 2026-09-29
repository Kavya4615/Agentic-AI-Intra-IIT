export interface VitalSigns {
  heart_rate: number;
  spo2: number;
  respiratory_rate: number;
  systolic_bp: number;
  diastolic_bp: number;
  is_artifact: boolean;
}

export interface PatientProfile {
  patient_id: string;
  name: string;
  age: number;
  sex: string;
  scenario: string;
}

export interface VitalUpdate {
  patient_id: string;
  timestamp: string;
  vitals: VitalSigns;
  _risk_score?: number;
  _alert_event?: AlertEvent;
}

export interface AlertEvent {
  patient_id: string;
  from_level: string;
  to_level: string;
  risk_score: number;
  timestamp: number;
  message: string;
  correlation_id?: string;
}

export interface SBARExplanation {
  situation: string;
  background: string;
  assessment: string;
  recommendation: string;
  retrieved_protocols: string[];
}

export type DecisionType = 'accept' | 'dismiss' | 'defer' | 'investigate';

export interface AlertDecision {
  id: string;
  alert_id: string;
  patient_id: string;
  decision: DecisionType;
  clinician_id: string;
  reason: string | null;
  decided_at: number;
  decided_at_iso: string;
  previous_state: string;
  resulting_state: string;
  defer_until?: number;
  defer_until_iso?: string;
  defer_remaining_seconds?: number;
}

export interface AlertRecord {
  alert_id: string;
  patient_id: string;
  from_level: string;
  to_level: string;
  risk_score: number;
  fired_at: number;
  fired_at_iso: string;
  message: string;
  needs_review: boolean;
  decision: AlertDecision | null;
  correlation_id: string;
}

export interface AuditEntry {
  id: string;
  patient_id: string;
  timestamp: number;
  timestamp_iso: string;
  event_type: 'observation' | 'retrieval' | 'reasoning' | 'alert' | 'decision';
  payload: Record<string, unknown>;
  correlation_id: string;
}

export interface PatientContext {
  patient_id: string;
  age: number;
  sex: string;
  relevant_history: string[];
  current_medications: string[];
  recent_labs: Record<string, string>;
  baseline_vitals: Record<string, number>;
}

/** Persisted per-patient derived state (not just the latest broadcast) */
export interface PatientLiveState {
  latest: VitalUpdate;
  alertLevel: string;     // persisted across readings that lack _alert_event
  riskScore: number;
  hrHistory: number[];    // last 20 heart rate readings for sparkline
  latestAlertId?: string; // most recent alert_id for decision actions
  latestDecision?: AlertDecision | null; // current decision on latest alert
}
