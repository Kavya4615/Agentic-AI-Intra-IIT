import React from 'react';
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell
} from 'recharts';
import {
  BrainCircuit, HeartPulse, Wind, Activity, Droplets,
  AlertCircle, ArrowUpRight, ArrowDownRight, ArrowRight, TrendingUp,
  User, Stethoscope
} from 'lucide-react';
import type { PatientProfile, PatientLiveState } from '../types';

interface DetailPanelProps {
  patient: PatientProfile | null;
  liveState: PatientLiveState | null;
  onOpenAgent: () => void;
}

const LEVEL_COLORS: Record<string, string> = {
  NORMAL: '#14B8A6', WATCH: '#F59E0B', SUSPECTED: '#F97316', ESCALATED: '#EF4444',
};
const LEVEL_GLOW: Record<string, string> = {
  NORMAL: 'rgba(20,184,166,0.3)', WATCH: 'rgba(245,158,11,0.3)',
  SUSPECTED: 'rgba(249,115,22,0.3)', ESCALATED: 'rgba(239,68,68,0.4)',
};
const LEVEL_BG: Record<string, { bg: string; border: string; text: string }> = {
  NORMAL:   { bg: 'rgba(20,184,166,0.1)',  border: 'rgba(20,184,166,0.3)',  text: '#2DD4BF' },
  WATCH:    { bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.3)',  text: '#FCD34D' },
  SUSPECTED:{ bg: 'rgba(249,115,22,0.1)',  border: 'rgba(249,115,22,0.3)',  text: '#FB923C' },
  ESCALATED:{ bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.4)',   text: '#F87171' },
};

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="px-3 py-2 text-xs shadow-xl rounded-xl font-tabular"
      style={{
        background: 'rgba(10,22,40,0.95)',
        border: '1px solid rgba(99,102,241,0.3)',
        backdropFilter: 'blur(16px)',
        color: 'var(--text-primary)',
      }}>
      {payload.map((p: any) => (
        <p key={p.dataKey} className="font-bold" style={{ color: p.color }}>
          {p.name}: {p.value?.toFixed(1)}
        </p>
      ))}
    </div>
  );
};

const RISK_COMPONENTS = [
  { name: 'Deviation',   weight: 40, color: '#6366F1' },
  { name: 'Slope',       weight: 30, color: '#F59E0B' },
  { name: 'Persistence', weight: 30, color: '#14B8A6' },
];

const ALERT_STATES = [
  { name: 'NORMAL',    color: '#14B8A6' },
  { name: 'WATCH',     color: '#F59E0B' },
  { name: 'SUSPECTED', color: '#F97316' },
  { name: 'ESCALATED', color: '#EF4444' },
];

const DetailPanel: React.FC<DetailPanelProps> = ({ patient, liveState, onOpenAgent }) => {
  if (!patient || !liveState) {
    return (
      <div className="h-full flex items-center justify-center" style={{ background: 'var(--bg-base)' }}>
        <div className="text-center space-y-4">
          <div className="w-20 h-20 rounded-3xl flex items-center justify-center mx-auto animate-glow"
            style={{
              background: 'rgba(99,102,241,0.08)',
              border: '1px solid rgba(99,102,241,0.2)',
              boxShadow: '0 0 40px rgba(99,102,241,0.1)',
            }}>
            <Stethoscope className="w-9 h-9" style={{ color: 'rgba(99,102,241,0.5)' }} />
          </div>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-muted)' }}>
            Select a patient to view clinical dashboard
          </p>
          <p className="text-xs" style={{ color: 'var(--text-muted)', opacity: 0.5 }}>
            Real-time vitals, risk analysis &amp; AI-powered SBAR
          </p>
        </div>
      </div>
    );
  }

  const vitals = liveState.latest?.vitals;
  const alertLevel = liveState.alertLevel;
  const alertColor = LEVEL_COLORS[alertLevel] ?? '#14B8A6';
  const alertGlow = LEVEL_GLOW[alertLevel] ?? 'rgba(20,184,166,0.3)';
  const alertLevelBg = LEVEL_BG[alertLevel] ?? LEVEL_BG.NORMAL;
  const riskScore = liveState.riskScore;

  const chartData = liveState.hrHistory.map((v, i) => ({
    i, hr: v,
    spo2: vitals ? Math.max(85, Math.min(100, vitals.spo2 + (Math.sin(i * 0.5) * 1.2))) : 98,
    rr:   vitals ? Math.max(10, Math.min(40, vitals.respiratory_rate + (Math.cos(i * 0.4) * 1.5))) : 16,
    bp:   vitals ? vitals.systolic_bp + (Math.sin(i * 0.3) * 3) : 120,
  }));

  const activeStateIdx = ALERT_STATES.findIndex(s => s.name === alertLevel);
  const alertDonutData = ALERT_STATES.map((s, i) => ({
    name: s.name, value: i === activeStateIdx ? 70 : 10, color: s.color,
  }));
  const riskDonutData = RISK_COMPONENTS.map(c => ({
    name: c.name, value: (c.weight / 100) * riskScore, color: c.color,
  }));

  return (
    <div className="h-full overflow-y-auto p-5 flex flex-col gap-5 animate-fade-in-up"
      style={{ background: 'var(--bg-base)' }}>

      {/* ── Patient Header ─────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3 p-5 rounded-2xl"
        style={{
          background: 'var(--bg-glass)',
          border: `1px solid ${alertLevelBg.border}`,
          boxShadow: `0 0 30px ${alertGlow}, 0 8px 30px rgba(0,0,0,0.4)`,
          backdropFilter: 'blur(20px)',
        }}>
        <div className="flex items-center gap-4">
          <div className="relative w-14 h-14 rounded-2xl flex items-center justify-center text-xl font-black"
            style={{
              background: `linear-gradient(135deg, ${alertLevelBg.bg}, rgba(99,102,241,0.1))`,
              border: `1px solid ${alertLevelBg.border}`,
              color: alertLevelBg.text,
              boxShadow: `0 0 20px ${alertGlow}`,
            }}>
            {patient.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
          </div>
          <div>
            <h2 className="text-2xl font-black" style={{ color: 'var(--text-bright)' }}>{patient.name}</h2>
            <p className="text-xs mt-0.5 font-mono" style={{ color: 'var(--text-muted)' }}>
              {patient.patient_id} · {patient.age}y {patient.sex} · {patient.scenario.replace(/_/g, ' ')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-black uppercase tracking-widest"
            style={{
              background: alertLevelBg.bg,
              border: `1px solid ${alertLevelBg.border}`,
              color: alertLevelBg.text,
              boxShadow: `0 0 12px ${alertGlow}`,
            }}>
            <AlertCircle className="w-3.5 h-3.5" />
            {alertLevel}
          </div>
          <button
            id={`detail-agent-btn-${patient.patient_id}`}
            onClick={onOpenAgent}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-black transition-all"
            style={{
              background: 'linear-gradient(135deg, rgba(99,102,241,0.4) 0%, rgba(139,92,246,0.3) 100%)',
              border: '1px solid rgba(99,102,241,0.5)',
              color: '#E0E7FF',
              boxShadow: '0 0 20px rgba(99,102,241,0.3)',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 30px rgba(99,102,241,0.5)';
              (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-1px)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 20px rgba(99,102,241,0.3)';
              (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0)';
            }}
          >
            <BrainCircuit className="w-4 h-4" />
            AI SBAR Report
          </button>
        </div>
      </div>

      {/* ── Vitals Stat Cards ──────────────────────────────── */}
      {vitals && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <VitalStatCard
            icon={<HeartPulse className="w-5 h-5" />}
            iconColor="#EF4444" glowColor="rgba(239,68,68,0.3)"
            label="Heart Rate" value={vitals.heart_rate.toFixed(0)} unit="bpm"
            trend="up" trendValue="+2.4%"
            warn={vitals.heart_rate > 100 || vitals.heart_rate < 50}
          />
          <VitalStatCard
            icon={<Wind className="w-5 h-5" />}
            iconColor="#38BDF8" glowColor="rgba(56,189,248,0.3)"
            label="SpO₂" value={vitals.spo2.toFixed(1)} unit="%"
            trend="down" trendValue="-0.8%"
            warn={vitals.spo2 < 92}
          />
          <VitalStatCard
            icon={<Activity className="w-5 h-5" />}
            iconColor="#14B8A6" glowColor="rgba(20,184,166,0.3)"
            label="Resp Rate" value={vitals.respiratory_rate.toFixed(0)} unit="rpm"
            trend="flat" trendValue="±0%"
            warn={vitals.respiratory_rate > 24 || vitals.respiratory_rate < 12}
          />
          <VitalStatCard
            icon={<Droplets className="w-5 h-5" />}
            iconColor="#8B5CF6" glowColor="rgba(139,92,246,0.3)"
            label="Blood Pressure" value={`${vitals.systolic_bp.toFixed(0)}/${vitals.diastolic_bp.toFixed(0)}`} unit="mmHg"
            trend="up" trendValue="+3.1%"
            warn={vitals.systolic_bp < 90 || vitals.systolic_bp > 160}
          />
        </div>
      )}

      {/* ── Charts Row ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* HR Trend (spans 2 cols) */}
        <div className="lg:col-span-2 widget-card scan-shimmer flex flex-col gap-3" style={{ minHeight: 260 }}>
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)' }}>
                <HeartPulse className="w-4 h-4" style={{ color: '#EF4444' }} />
              </div>
              <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Heart Rate Trend</h3>
            </div>
            <span className="text-xs font-tabular" style={{ color: 'var(--text-muted)' }}>
              Last {liveState.hrHistory.length} readings
            </span>
          </div>
          {chartData.length > 2 ? (
            <div className="flex-1" style={{ minHeight: 200 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="hrGradDark" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%"   stopColor={alertColor} stopOpacity={0.3} />
                      <stop offset="100%" stopColor={alertColor} stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="i" hide />
                  <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone" dataKey="hr" name="HR"
                    stroke={alertColor} strokeWidth={2.5}
                    fill="url(#hrGradDark)" dot={false}
                    activeDot={{ r: 5, fill: alertColor, stroke: '#0a1628', strokeWidth: 2 }}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-sm italic" style={{ color: 'var(--text-muted)' }}>
              Acquiring signal…
            </div>
          )}
        </div>

        {/* Risk Composition Donut */}
        <div className="widget-card flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)' }}>
              <TrendingUp className="w-4 h-4" style={{ color: '#818CF8' }} />
            </div>
            <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Risk Composition</h3>
          </div>
          <div className="relative flex-1 flex items-center justify-center" style={{ minHeight: 160 }}>
            <ResponsiveContainer width="100%" height={160}>
              <PieChart>
                <Pie
                  data={riskDonutData} dataKey="value" cx="50%" cy="50%"
                  innerRadius={50} outerRadius={70}
                  startAngle={90} endAngle={-270}
                  paddingAngle={3} stroke="none"
                >
                  {riskDonutData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} opacity={0.9} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="donut-center">
              <p className="font-black text-2xl" style={{ color: alertColor, textShadow: `0 0 20px ${alertGlow}` }}>
                {riskScore.toFixed(0)}
              </p>
              <p className="text-[10px] font-bold" style={{ color: 'var(--text-muted)' }}>/ 100</p>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            {RISK_COMPONENTS.map(c => (
              <div key={c.name} className="flex items-center justify-between text-[10px]" style={{ color: 'var(--text-muted)' }}>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: c.color, boxShadow: `0 0 6px ${c.color}` }} />
                  {c.name}
                </div>
                <span className="font-mono font-bold" style={{ color: c.color }}>{c.weight}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Bottom Row: Cross-vital + Alert State ────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Cross-vital concordance */}
        <div className="lg:col-span-2 widget-card flex flex-col gap-3" style={{ minHeight: 180 }}>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.2)' }}>
              <Activity className="w-4 h-4" style={{ color: '#8B5CF6' }} />
            </div>
            <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Cross-Vital Concordance</h3>
          </div>
          {chartData.length > 2 ? (
            <div className="flex-1" style={{ minHeight: 120 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="i" hide />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line type="monotone" dataKey="hr"  name="HR"     stroke="#EF4444" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="bp"  name="SysBP"  stroke="#8B5CF6" strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-sm italic" style={{ color: 'var(--text-muted)' }}>
              Collecting…
            </div>
          )}
          <div className="flex gap-5 text-[10px]" style={{ color: 'var(--text-muted)' }}>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 rounded inline-block" style={{ background: '#EF4444', boxShadow: '0 0 4px rgba(239,68,68,0.5)' }} />
              Heart Rate
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 rounded inline-block" style={{ background: '#8B5CF6', boxShadow: '0 0 4px rgba(139,92,246,0.5)' }} />
              Systolic BP
            </span>
          </div>
        </div>

        {/* Alert State Donut */}
        <div className="widget-card flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.15)' }}>
              <AlertCircle className="w-4 h-4" style={{ color: '#EF4444' }} />
            </div>
            <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Alert State</h3>
          </div>
          <div className="relative flex-1 flex items-center justify-center" style={{ minHeight: 140 }}>
            <ResponsiveContainer width="100%" height={140}>
              <PieChart>
                <Pie
                  data={alertDonutData} dataKey="value" cx="50%" cy="50%"
                  innerRadius={42} outerRadius={60}
                  startAngle={90} endAngle={-270}
                  paddingAngle={2} stroke="none"
                >
                  {alertDonutData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color}
                      opacity={idx === activeStateIdx ? 1 : 0.15}
                    />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="donut-center">
              <p className="text-sm font-black" style={{
                color: alertColor,
                textShadow: `0 0 16px ${alertGlow}`,
              }}>
                {alertLevel}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {ALERT_STATES.map(s => (
              <div key={s.name} className="flex items-center gap-1.5 text-[10px] font-medium"
                style={{ color: s.name === alertLevel ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                <span className="w-2 h-2 rounded-full" style={{
                  backgroundColor: s.color,
                  opacity: s.name === alertLevel ? 1 : 0.25,
                  boxShadow: s.name === alertLevel ? `0 0 6px ${s.color}` : undefined,
                }} />
                {s.name}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

/* ── Vital Stat Card ──────────────────────────── */
const VitalStatCard = ({
  icon, iconColor, glowColor, label, value, unit, trend, trendValue, warn
}: {
  icon: React.ReactNode; iconColor: string; glowColor: string;
  label: string; value: string; unit: string;
  trend: 'up'|'down'|'flat'; trendValue: string;
  warn: boolean;
}) => (
  <div className="widget-card scan-shimmer flex flex-col gap-3"
    style={warn ? {
      border: '1px solid rgba(239,68,68,0.3)',
      boxShadow: '0 0 20px rgba(239,68,68,0.1), 0 4px 16px rgba(0,0,0,0.4)',
    } : undefined}
  >
    <div className="flex justify-between items-start">
      <div className="w-9 h-9 rounded-xl flex items-center justify-center"
        style={{
          background: `${iconColor}15`,
          border: `1px solid ${iconColor}30`,
          color: iconColor,
          boxShadow: `0 0 12px ${glowColor}`,
        }}>
        {icon}
      </div>
      <div className={`flex items-center gap-0.5 text-[11px] font-bold rounded-lg px-2 py-0.5 ${
        trend === 'up' ? 'text-red-400 bg-red-500/10' :
        trend === 'down' ? 'text-amber-400 bg-amber-500/10' :
        'text-slate-400 bg-slate-500/10'
      }`}>
        {trend === 'up'   && <ArrowUpRight className="w-3 h-3" />}
        {trend === 'down' && <ArrowDownRight className="w-3 h-3" />}
        {trend === 'flat' && <ArrowRight className="w-3 h-3" />}
        {trendValue}
      </div>
    </div>
    <div>
      <p className="stat-value text-2xl" style={{
        color: warn ? '#F87171' : 'var(--text-bright)',
        textShadow: warn ? '0 0 12px rgba(239,68,68,0.4)' : undefined,
      }}>
        {value}
      </p>
      <p className="text-[11px] mt-0.5 font-medium" style={{ color: 'var(--text-muted)' }}>
        {label} <span style={{ color: 'var(--text-muted)', opacity: 0.5 }}>{unit}</span>
      </p>
    </div>
  </div>
);

export default DetailPanel;
