import React, { useEffect, useState } from 'react';
import { Clock, BrainCircuit, CheckCircle2, XCircle, PauseCircle, Search } from 'lucide-react';
import type { PatientProfile, PatientLiveState } from '../types';
import { SparklineChart } from './SparklineChart';

interface PatientCardProps {
  patient: PatientProfile;
  liveState?: PatientLiveState;
  isSelected: boolean;
  onSelect: () => void;
  onOpenAgent: () => void;
}

const DECISION_BADGE_CONFIG = {
  accept:      { label: 'Accepted',      cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', Icon: CheckCircle2 },
  dismiss:     { label: 'Dismissed',     cls: 'bg-slate-100 text-slate-500 border-slate-200',      Icon: XCircle },
  defer:       { label: 'Deferred',      cls: 'bg-amber-50 text-amber-700 border-amber-200',       Icon: PauseCircle },
  investigate: { label: 'Investigating', cls: 'bg-indigo-50 text-indigo-700 border-indigo-200',    Icon: Search },
} as const;

const SEVERITY_CONFIG: Record<string, {
  dot: string; badge: string; border: string; accent: string;
}> = {
  NORMAL:    { dot: 'bg-teal-500',   badge: 'bg-teal-50 text-teal-700 border-teal-200',     border: 'severity-border-normal',    accent: '#0D9488' },
  WATCH:     { dot: 'bg-amber-500',  badge: 'bg-amber-50 text-amber-700 border-amber-200',  border: 'severity-border-watch',     accent: '#D97706' },
  SUSPECTED: { dot: 'bg-orange-500', badge: 'bg-orange-50 text-orange-700 border-orange-200', border: 'severity-border-suspected', accent: '#EA580C' },
  ESCALATED: { dot: 'bg-red-600',    badge: 'bg-red-50 text-red-700 border-red-300',         border: 'severity-border-escalated', accent: '#DC2626' },
};

const PatientCard: React.FC<PatientCardProps> = ({
  patient, liveState, isSelected, onSelect, onOpenAgent
}) => {
  const [timeAgo, setTimeAgo] = useState('just now');

  const alertLevel = liveState?.alertLevel ?? 'NORMAL';
  const config = SEVERITY_CONFIG[alertLevel] ?? SEVERITY_CONFIG.NORMAL;
  const vitals = liveState?.latest?.vitals;
  const risk = liveState?.riskScore ?? 0;
  const isEscalated = alertLevel === 'ESCALATED';

  useEffect(() => {
    if (!liveState?.latest?.timestamp) return;
    const updateTime = () => {
      const ms = Date.now() - new Date(liveState.latest.timestamp).getTime();
      if (ms < 5000) setTimeAgo('just now');
      else if (ms < 60000) setTimeAgo(`${Math.floor(ms / 1000)}s ago`);
      else setTimeAgo(`${Math.floor(ms / 60000)}m ago`);
    };
    updateTime();
    const interval = setInterval(updateTime, 5000);
    return () => clearInterval(interval);
  }, [liveState?.latest?.timestamp]);

  return (
    <div
      id={`patient-card-${patient.patient_id}`}
      onClick={onSelect}
      className={`
        relative bg-white rounded-xl cursor-pointer
        transition-all duration-200
        ${config.border}
        ${isSelected
          ? 'ring-2 ring-indigo-400 ring-offset-1 shadow-md'
          : 'shadow-sm hover:shadow-md hover:-translate-y-0.5'
        }
        ${isEscalated ? 'animate-escalation' : ''}
        p-4 mb-2
      `}
    >
      {/* Row 1: Avatar + Name + Badge */}
      <div className="flex items-center gap-3 mb-3">
        {/* Initial circle */}
        <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-sm font-bold text-slate-600 flex-shrink-0">
          {patient.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-800 truncate leading-tight">{patient.name}</h3>
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${config.dot}`} />
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            {patient.patient_id} &middot; Bed {patient.patient_id.replace('P00', '10')}
          </p>
        </div>
        <span className={`flex-shrink-0 px-2 py-0.5 rounded-full text-[10px] font-bold border ${config.badge}`}>
          {alertLevel}
        </span>
      </div>

      {/* Row 2: Compact vitals */}
      {vitals ? (
        <div className="grid grid-cols-4 gap-1 mb-3">
          <MiniVital label="HR" value={vitals.heart_rate.toFixed(0)} warn={vitals.heart_rate > 100 || vitals.heart_rate < 50} />
          <MiniVital label="SpO2" value={`${vitals.spo2.toFixed(0)}%`} warn={vitals.spo2 < 92} />
          <MiniVital label="RR" value={vitals.respiratory_rate.toFixed(0)} warn={vitals.respiratory_rate > 24} />
          <MiniVital label="BP" value={`${vitals.systolic_bp.toFixed(0)}/${vitals.diastolic_bp.toFixed(0)}`} warn={vitals.systolic_bp < 90} />
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-1 mb-3">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="flex flex-col items-center gap-1 py-1">
              <div className="h-2 w-6 bg-slate-100 rounded animate-pulse" />
              <div className="h-4 w-8 bg-slate-100 rounded animate-pulse" />
            </div>
          ))}
        </div>
      )}

      {/* Row 3: Risk bar + sparkline + timestamp */}
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <div className="flex justify-between items-center mb-1">
            <span className="label-upper">Risk</span>
            <span className="font-tabular text-xs font-bold" style={{ color: config.accent }}>
              {risk.toFixed(0)}
            </span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-slate-100 overflow-hidden">
            <div
              className="h-full rounded-full risk-bar-fill"
              style={{ width: `${Math.min(100, Math.max(0, risk))}%`, backgroundColor: config.accent }}
            />
          </div>
        </div>

        {liveState && liveState.hrHistory.length > 2 && (
          <div className="w-20 h-7 flex-shrink-0">
            <SparklineChart data={liveState.hrHistory} color={config.accent} />
          </div>
        )}

        {vitals && (
          <div className="flex items-center gap-1 text-[10px] text-slate-400 flex-shrink-0">
            <Clock className="w-3 h-3" />
            <span>{timeAgo}</span>
          </div>
        )}
      </div>

      {/* SBAR button + Decision Badge */}
      {(isEscalated || isSelected || !!liveState?.latestDecision) && (
        <div className="mt-3 flex flex-col gap-2">
          {/* Decision badge if a decision exists */}
          {liveState?.latestDecision && (() => {
            const dec = liveState.latestDecision!.decision as keyof typeof DECISION_BADGE_CONFIG;
            const badge = DECISION_BADGE_CONFIG[dec];
            if (!badge) return null;
            const { Icon } = badge;
            return (
              <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[10px] font-bold ${badge.cls}`}>
                <Icon className="w-3 h-3" />
                {badge.label}
                {liveState.latestDecision!.defer_remaining_seconds && liveState.latestDecision!.defer_remaining_seconds > 0 && (
                  <span className="ml-auto opacity-70">
                    {Math.ceil(liveState.latestDecision!.defer_remaining_seconds / 60)}m
                  </span>
                )}
              </div>
            );
          })()}

          <button
            id={`agent-btn-${patient.patient_id}`}
            onClick={e => { e.stopPropagation(); onOpenAgent(); }}
            className="w-full flex items-center justify-center gap-2 py-2 rounded-lg
              bg-indigo-50 hover:bg-indigo-100 border border-indigo-200
              text-xs font-bold text-indigo-700 transition-colors"
          >
            <BrainCircuit className="w-3.5 h-3.5" />
            {liveState?.latestDecision ? 'View SBAR & Decision' : 'View SBAR Report'}
          </button>
        </div>
      )}
    </div>
  );
};

const MiniVital = ({ label, value, warn }: { label: string; value: string; warn: boolean }) => (
  <div className="flex flex-col items-center text-center">
    <span className="label-upper text-[9px]">{label}</span>
    <span className={`font-tabular text-xs font-bold ${warn ? 'text-red-600' : 'text-slate-700'}`}>{value}</span>
  </div>
);

export default PatientCard;
