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
  accept:      { label: 'Accepted',      cls: 'text-emerald-400', bg: 'rgba(20,184,166,0.12)', border: 'rgba(20,184,166,0.3)', Icon: CheckCircle2 },
  dismiss:     { label: 'Dismissed',     cls: 'text-slate-400',   bg: 'rgba(100,116,139,0.1)', border: 'rgba(100,116,139,0.25)', Icon: XCircle },
  defer:       { label: 'Deferred',      cls: 'text-amber-400',   bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.3)',  Icon: PauseCircle },
  investigate: { label: 'Investigating', cls: 'text-indigo-400',  bg: 'rgba(99,102,241,0.12)', border: 'rgba(99,102,241,0.3)',  Icon: Search },
} as const;

const SEVERITY_CONFIG: Record<string, {
  dot: string; textColor: string; bg: string; border: string;
  glow: string; leftBorder: string; accent: string;
}> = {
  NORMAL: {
    dot: 'bg-teal-400',
    textColor: '#2DD4BF',
    bg: 'rgba(20,184,166,0.06)',
    border: 'rgba(20,184,166,0.2)',
    glow: 'rgba(20,184,166,0.0)',
    leftBorder: '#14B8A6',
    accent: '#14B8A6',
  },
  WATCH: {
    dot: 'bg-amber-400',
    textColor: '#FCD34D',
    bg: 'rgba(245,158,11,0.07)',
    border: 'rgba(245,158,11,0.25)',
    glow: 'rgba(245,158,11,0.08)',
    leftBorder: '#F59E0B',
    accent: '#F59E0B',
  },
  SUSPECTED: {
    dot: 'bg-orange-400',
    textColor: '#FB923C',
    bg: 'rgba(249,115,22,0.08)',
    border: 'rgba(249,115,22,0.3)',
    glow: 'rgba(249,115,22,0.12)',
    leftBorder: '#F97316',
    accent: '#F97316',
  },
  ESCALATED: {
    dot: 'bg-red-400',
    textColor: '#F87171',
    bg: 'rgba(239,68,68,0.08)',
    border: 'rgba(239,68,68,0.35)',
    glow: 'rgba(239,68,68,0.2)',
    leftBorder: '#EF4444',
    accent: '#EF4444',
  },
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
      className={`relative cursor-pointer rounded-xl transition-all duration-200 scan-shimmer`}
      style={{
        background: isSelected
          ? `linear-gradient(135deg, ${config.bg}, rgba(99,102,241,0.08))`
          : config.bg,
        border: isSelected
          ? `1px solid rgba(99,102,241,0.5)`
          : `1px solid ${config.border}`,
        borderLeft: `3px solid ${config.leftBorder}`,
        boxShadow: isSelected
          ? `0 0 0 1px rgba(99,102,241,0.25), 0 8px 30px rgba(0,0,0,0.4), 0 0 20px ${config.glow}`
          : isEscalated
          ? `0 0 20px rgba(239,68,68,0.15), 0 4px 16px rgba(0,0,0,0.3)`
          : `0 4px 16px rgba(0,0,0,0.3)`,
        padding: '0.85rem',
        animation: isEscalated ? 'escalation-flash 2s ease infinite' : undefined,
      }}
    >
      {/* Row 1: Avatar + Name + Badge */}
      <div className="flex items-center gap-3 mb-3">
        {/* Initials */}
        <div className="relative flex-shrink-0">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-xs font-black"
            style={{
              background: `linear-gradient(135deg, ${config.bg}, rgba(99,102,241,0.1))`,
              border: `1px solid ${config.border}`,
              color: config.textColor,
            }}
          >
            {patient.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
          </div>
          <span className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 ${config.dot}`}
            style={{ borderColor: 'var(--bg-base)' }} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold truncate leading-tight" style={{ color: 'var(--text-bright)' }}>
              {patient.name}
            </h3>
          </div>
          <p className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {patient.patient_id} · Bed {patient.patient_id.replace('P00', '1')}
          </p>
        </div>

        <span
          className="flex-shrink-0 px-2 py-0.5 rounded-lg text-[9px] font-black uppercase tracking-wider"
          style={{ background: config.bg, border: `1px solid ${config.border}`, color: config.textColor }}
        >
          {alertLevel}
        </span>
      </div>

      {/* Row 2: Compact vitals */}
      {vitals ? (
        <div className="grid grid-cols-4 gap-1 mb-3">
          <MiniVital label="HR"   value={vitals.heart_rate.toFixed(0)}      warn={vitals.heart_rate > 100 || vitals.heart_rate < 50} />
          <MiniVital label="SpO₂" value={`${vitals.spo2.toFixed(0)}%`}      warn={vitals.spo2 < 92} />
          <MiniVital label="RR"   value={vitals.respiratory_rate.toFixed(0)} warn={vitals.respiratory_rate > 24} />
          <MiniVital label="BP"   value={`${vitals.systolic_bp.toFixed(0)}/${vitals.diastolic_bp.toFixed(0)}`} warn={vitals.systolic_bp < 90} />
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-1 mb-3">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="flex flex-col items-center gap-1 py-1">
              <div className="h-2 w-6 rounded animate-pulse" style={{ background: 'rgba(255,255,255,0.05)' }} />
              <div className="h-4 w-8 rounded animate-pulse" style={{ background: 'rgba(255,255,255,0.05)' }} />
            </div>
          ))}
        </div>
      )}

      {/* Row 3: Risk bar + sparkline + timestamp */}
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <div className="flex justify-between items-center mb-1.5">
            <span className="label-upper">Risk Score</span>
            <span className="font-mono-val text-xs font-bold" style={{ color: config.textColor }}>
              {risk.toFixed(0)}
            </span>
          </div>
          <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.05)' }}>
            <div
              className="h-full rounded-full risk-bar-fill"
              style={{ width: `${Math.min(100, Math.max(0, risk))}%`, backgroundColor: config.accent }}
            />
          </div>
        </div>

        {liveState && liveState.hrHistory.length > 2 && (
          <div className="w-20 h-7 flex-shrink-0 opacity-80">
            <SparklineChart data={liveState.hrHistory} color={config.accent} />
          </div>
        )}

        {vitals && (
          <div className="flex items-center gap-1 text-[10px] flex-shrink-0" style={{ color: 'var(--text-muted)' }}>
            <Clock className="w-3 h-3" />
            <span>{timeAgo}</span>
          </div>
        )}
      </div>

      {/* SBAR button + Decision Badge */}
      {(isEscalated || isSelected || !!liveState?.latestDecision) && (
        <div className="mt-3 flex flex-col gap-2">
          {liveState?.latestDecision && (() => {
            const dec = liveState.latestDecision!.decision as keyof typeof DECISION_BADGE_CONFIG;
            const badge = DECISION_BADGE_CONFIG[dec];
            if (!badge) return null;
            const { Icon } = badge;
            return (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-bold"
                style={{ background: badge.bg, border: `1px solid ${badge.border}`, color: badge.cls.replace('text-', '') }}>
                <Icon className="w-3 h-3" />
                <span className={badge.cls}>{badge.label}</span>
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
            className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold transition-all"
            style={{
              background: 'rgba(99,102,241,0.12)',
              border: '1px solid rgba(99,102,241,0.3)',
              color: '#A5B4FC',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(99,102,241,0.22)';
              (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 16px rgba(99,102,241,0.3)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(99,102,241,0.12)';
              (e.currentTarget as HTMLButtonElement).style.boxShadow = 'none';
            }}
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
  <div className="flex flex-col items-center text-center py-1 rounded-lg" style={{
    background: warn ? 'rgba(239,68,68,0.06)' : 'rgba(255,255,255,0.02)',
  }}>
    <span className="label-upper text-[9px]">{label}</span>
    <span className="font-mono-val text-xs font-bold mt-0.5" style={{
      color: warn ? '#F87171' : 'var(--text-primary)',
      textShadow: warn ? '0 0 8px rgba(239,68,68,0.5)' : undefined,
    }}>
      {value}
    </span>
  </div>
);

export default PatientCard;
