import React from 'react';
import {
  HeartPulse, Wind, Activity, Droplets,
  TrendingUp, TrendingDown, Minus
} from 'lucide-react';

interface CohortStatsBarProps {
  totalReadings: number;
  escalatedCount: number;
  suspectedCount: number;
  watchCount: number;
  normalCount: number;
  totalPatients: number;
}

const StatPill: React.FC<{
  label: string;
  value: number | string;
  total?: number;
  color: string;
  glow: string;
  border: string;
  trend?: 'up' | 'down' | 'flat';
}> = ({ label, value, total, color, glow, border, trend }) => (
  <div
    className="flex flex-col gap-1 px-4 py-2.5 rounded-xl flex-1 min-w-[90px] text-center"
    style={{
      background: `${glow}08`,
      border: `1px solid ${border}`,
    }}
  >
    <div className="flex items-center justify-center gap-1">
      <span className="font-black text-xl font-mono" style={{ color, textShadow: `0 0 12px ${glow}` }}>
        {value}
      </span>
      {total && (
        <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>/{total}</span>
      )}
      {trend === 'up'   && <TrendingUp   className="w-3 h-3 ml-0.5" style={{ color }} />}
      {trend === 'down' && <TrendingDown className="w-3 h-3 ml-0.5" style={{ color }} />}
      {trend === 'flat' && <Minus        className="w-3 h-3 ml-0.5" style={{ color }} />}
    </div>
    <span className="text-[9px] font-black uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
      {label}
    </span>
  </div>
);

const CohortStatsBar: React.FC<CohortStatsBarProps> = ({
  totalReadings,
  escalatedCount,
  suspectedCount,
  watchCount,
  normalCount,
  totalPatients,
}) => {
  return (
    <div
      className="flex items-center gap-3 px-5 py-3 flex-shrink-0"
      style={{
        background: 'rgba(6,13,24,0.85)',
        borderBottom: '1px solid rgba(99,102,241,0.08)',
        backdropFilter: 'blur(16px)',
        overflowX: 'auto',
      }}
    >
      {/* Cohort title */}
      <div className="flex-shrink-0 flex items-center gap-2 mr-2">
        <div className="w-px h-8" style={{ background: 'rgba(255,255,255,0.06)' }} />
        <span className="text-[10px] font-black uppercase tracking-[0.15em]" style={{ color: 'var(--text-muted)' }}>
          Cohort
        </span>
        <div className="w-px h-8" style={{ background: 'rgba(255,255,255,0.06)' }} />
      </div>

      {/* Stats pills */}
      <div className="flex items-center gap-2 flex-1">
        <StatPill
          label="Escalated"
          value={escalatedCount}
          color="#F87171"
          glow="rgba(239,68,68,0.4)"
          border="rgba(239,68,68,0.2)"
          trend={escalatedCount > 0 ? 'up' : 'flat'}
        />
        <StatPill
          label="Suspected"
          value={suspectedCount}
          color="#FB923C"
          glow="rgba(249,115,22,0.4)"
          border="rgba(249,115,22,0.15)"
        />
        <StatPill
          label="Watch"
          value={watchCount}
          color="#FCD34D"
          glow="rgba(245,158,11,0.4)"
          border="rgba(245,158,11,0.12)"
        />
        <StatPill
          label="Normal"
          value={normalCount}
          color="#2DD4BF"
          glow="rgba(20,184,166,0.4)"
          border="rgba(20,184,166,0.12)"
          trend="flat"
        />
        <div className="w-px h-8 flex-shrink-0" style={{ background: 'rgba(255,255,255,0.06)' }} />
        <StatPill
          label="Patients"
          value={totalPatients}
          color="#818CF8"
          glow="rgba(99,102,241,0.4)"
          border="rgba(99,102,241,0.15)"
        />
        <StatPill
          label="Readings"
          value={totalReadings.toLocaleString()}
          color="#94A3B8"
          glow="rgba(148,163,184,0.3)"
          border="rgba(148,163,184,0.1)"
        />
      </div>

      {/* Vital channel icons */}
      <div className="hidden lg:flex items-center gap-3 flex-shrink-0 ml-2 pl-3"
        style={{ borderLeft: '1px solid rgba(255,255,255,0.06)' }}>
        {[
          { icon: HeartPulse, color: '#EF4444', label: 'HR' },
          { icon: Wind,       color: '#38BDF8', label: 'SpO₂' },
          { icon: Activity,   color: '#14B8A6', label: 'RR' },
          { icon: Droplets,   color: '#8B5CF6', label: 'BP' },
        ].map(({ icon: Icon, color, label }) => (
          <div key={label} className="flex flex-col items-center gap-0.5">
            <Icon className="w-3.5 h-3.5" style={{ color }} />
            <span className="text-[8px] font-bold uppercase" style={{ color: 'var(--text-muted)' }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CohortStatsBar;
