import React from 'react';
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell
} from 'recharts';
import { BrainCircuit, HeartPulse, Wind, Activity, Droplets, AlertCircle, ArrowUpRight, ArrowDownRight, ArrowRight, TrendingUp } from 'lucide-react';
import type { PatientProfile, PatientLiveState } from '../types';

interface DetailPanelProps {
  patient: PatientProfile | null;
  liveState: PatientLiveState | null;
  onOpenAgent: () => void;
}

const LEVEL_COLORS: Record<string, string> = {
  NORMAL: '#0D9488', WATCH: '#D97706', SUSPECTED: '#EA580C', ESCALATED: '#DC2626',
};
const LEVEL_BG: Record<string, string> = {
  NORMAL: 'bg-teal-50 text-teal-700 border-teal-200',
  WATCH: 'bg-amber-50 text-amber-700 border-amber-200',
  SUSPECTED: 'bg-orange-50 text-orange-700 border-orange-200',
  ESCALATED: 'bg-red-50 text-red-700 border-red-300',
};

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-slate-200 px-3 py-2 text-xs shadow-lg rounded-lg font-tabular">
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }} className="font-bold">
          {p.name}: {p.value?.toFixed(1)}
        </p>
      ))}
    </div>
  );
};

// Donut chart data for risk composition
const RISK_COMPONENTS = [
  { name: 'Deviation', weight: 40, color: '#6366F1' },
  { name: 'Slope', weight: 30, color: '#F59E0B' },
  { name: 'Persistence', weight: 30, color: '#0D9488' },
];

// Alert state donut
const ALERT_STATES = [
  { name: 'NORMAL', color: '#0D9488' },
  { name: 'WATCH', color: '#D97706' },
  { name: 'SUSPECTED', color: '#EA580C' },
  { name: 'ESCALATED', color: '#DC2626' },
];

const DetailPanel: React.FC<DetailPanelProps> = ({ patient, liveState, onOpenAgent }) => {
  if (!patient || !liveState) {
    return (
      <div className="h-full flex items-center justify-center bg-[#F5F6FA]">
        <div className="text-center space-y-3">
          <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto">
            <Activity className="w-8 h-8 text-slate-300" />
          </div>
          <p className="text-sm font-medium text-slate-400">Select a patient to view dashboard</p>
        </div>
      </div>
    );
  }

  const vitals = liveState.latest?.vitals;
  const alertLevel = liveState.alertLevel;
  const alertColor = LEVEL_COLORS[alertLevel] ?? '#0D9488';
  const riskScore = liveState.riskScore;

  const chartData = liveState.hrHistory.map((v, i) => ({
    i,
    hr: v,
    spo2: vitals ? Math.max(85, Math.min(100, vitals.spo2 + (Math.sin(i * 0.5) * 1.2))) : 98,
    rr: vitals ? Math.max(10, Math.min(40, vitals.respiratory_rate + (Math.cos(i * 0.4) * 1.5))) : 16,
    bp: vitals ? vitals.systolic_bp + (Math.sin(i * 0.3) * 3) : 120
  }));

  // Active alert state index for the donut
  const activeStateIdx = ALERT_STATES.findIndex(s => s.name === alertLevel);
  const alertDonutData = ALERT_STATES.map((s, i) => ({
    name: s.name,
    value: i === activeStateIdx ? 70 : 10,
    color: s.color,
  }));

  // Risk composition scaled by actual score
  const riskDonutData = RISK_COMPONENTS.map(c => ({
    name: c.name,
    value: (c.weight / 100) * riskScore,
    color: c.color,
  }));

  return (
    <div className="h-full overflow-y-auto p-6 flex flex-col gap-5 animate-fade-in-up bg-[#F5F6FA]">

      {/* ── Patient Header ─────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-indigo-100 flex items-center justify-center text-lg font-bold text-indigo-600">
            {patient.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
          </div>
          <div>
            <h2 className="text-xl font-extrabold text-slate-800">{patient.name}</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {patient.patient_id} &middot; {patient.age}y {patient.sex} &middot; {patient.scenario.replace(/_/g, ' ')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border ${LEVEL_BG[alertLevel]}`}>
            <AlertCircle className="w-3.5 h-3.5" />
            {alertLevel}
          </div>
          <button
            id={`detail-agent-btn-${patient.patient_id}`}
            onClick={onOpenAgent}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold
              bg-indigo-600 hover:bg-indigo-700 text-white
              shadow-sm transition-all active:scale-95"
          >
            <BrainCircuit className="w-4 h-4" />
            SBAR Report
          </button>
        </div>
      </div>

      {/* ── Vitals Stat Cards ──────────────────────────── */}
      {vitals && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <VitalStatCard
            icon={<HeartPulse className="w-5 h-5" />}
            iconColor="text-red-500" iconBg="bg-red-50"
            label="Heart Rate"
            value={vitals.heart_rate.toFixed(0)} unit="bpm"
            trend="up" trendValue="+2.4%"
            warn={vitals.heart_rate > 100 || vitals.heart_rate < 50}
          />
          <VitalStatCard
            icon={<Wind className="w-5 h-5" />}
            iconColor="text-sky-500" iconBg="bg-sky-50"
            label="SpO₂"
            value={vitals.spo2.toFixed(1)} unit="%"
            trend="down" trendValue="-0.8%"
            warn={vitals.spo2 < 92}
          />
          <VitalStatCard
            icon={<Activity className="w-5 h-5" />}
            iconColor="text-emerald-500" iconBg="bg-emerald-50"
            label="Resp Rate"
            value={vitals.respiratory_rate.toFixed(0)} unit="rpm"
            trend="flat" trendValue="0%"
            warn={vitals.respiratory_rate > 24 || vitals.respiratory_rate < 12}
          />
          <VitalStatCard
            icon={<Droplets className="w-5 h-5" />}
            iconColor="text-violet-500" iconBg="bg-violet-50"
            label="Blood Pressure"
            value={`${vitals.systolic_bp.toFixed(0)}/${vitals.diastolic_bp.toFixed(0)}`} unit="mmHg"
            trend="up" trendValue="+3.1%"
            warn={vitals.systolic_bp < 90 || vitals.systolic_bp > 160}
          />
        </div>
      )}

      {/* ── Charts Row ─────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* HR Trend Chart (spans 2 cols) */}
        <div className="lg:col-span-2 widget-card flex flex-col gap-3 min-h-[280px]">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-red-50 flex items-center justify-center">
                <HeartPulse className="w-4 h-4 text-red-500" />
              </div>
              <h3 className="text-sm font-bold text-slate-700">Heart Rate Trend</h3>
            </div>
            <span className="text-xs text-slate-400 font-tabular">Last {liveState.hrHistory.length} readings</span>
          </div>
          {chartData.length > 2 ? (
            <div className="flex-1" style={{ minHeight: 200 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="hrGradLight" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={alertColor} stopOpacity={0.15} />
                      <stop offset="100%" stopColor={alertColor} stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                  <XAxis dataKey="i" hide />
                  <YAxis
                    domain={['auto', 'auto']}
                    tick={{ fontSize: 10, fill: '#94A3B8' }}
                    tickLine={false} axisLine={false}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone" dataKey="hr" name="HR"
                    stroke={alertColor} strokeWidth={2.5}
                    fill="url(#hrGradLight)" dot={false}
                    activeDot={{ r: 4, fill: alertColor, stroke: '#fff', strokeWidth: 2 }}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-sm text-slate-400 italic">
              Acquiring signal…
            </div>
          )}
        </div>

        {/* Risk Composition Donut */}
        <div className="widget-card flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-indigo-50 flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-indigo-500" />
            </div>
            <h3 className="text-sm font-bold text-slate-700">Risk Composition</h3>
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
                    <Cell key={idx} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="donut-center">
              <p className="stat-value text-2xl" style={{ color: alertColor }}>{riskScore.toFixed(0)}</p>
              <p className="text-[10px] text-slate-400 font-bold">/ 100</p>
            </div>
          </div>
          <div className="flex justify-center gap-4">
            {RISK_COMPONENTS.map(c => (
              <div key={c.name} className="flex items-center gap-1.5 text-[10px] text-slate-500 font-medium">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: c.color }} />
                {c.name} ({c.weight}%)
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
            <div className="w-7 h-7 rounded-lg bg-violet-50 flex items-center justify-center">
              <Activity className="w-4 h-4 text-violet-500" />
            </div>
            <h3 className="text-sm font-bold text-slate-700">Cross-Vital Concordance</h3>
          </div>
          {chartData.length > 2 ? (
            <div className="flex-1" style={{ minHeight: 120 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                  <XAxis dataKey="i" hide />
                  <YAxis tick={{ fontSize: 10, fill: '#94A3B8' }} tickLine={false} axisLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line type="monotone" dataKey="hr" name="HR" stroke="#EF4444" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="bp" name="SysBP" stroke="#8B5CF6" strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-sm text-slate-400 italic">Collecting…</div>
          )}
          <div className="flex gap-4 text-[10px] text-slate-400 font-medium">
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-0.5 rounded bg-red-500 inline-block" /> Heart Rate</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-0.5 rounded bg-violet-500 inline-block" /> Systolic BP</span>
          </div>
        </div>

        {/* Alert State Donut */}
        <div className="widget-card flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-red-50 flex items-center justify-center">
              <AlertCircle className="w-4 h-4 text-red-500" />
            </div>
            <h3 className="text-sm font-bold text-slate-700">Alert State</h3>
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
                    <Cell key={idx} fill={entry.color} opacity={idx === activeStateIdx ? 1 : 0.2} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="donut-center">
              <p className="text-sm font-extrabold" style={{ color: alertColor }}>{alertLevel}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {ALERT_STATES.map(s => (
              <div key={s.name} className={`flex items-center gap-1.5 text-[10px] font-medium ${s.name === alertLevel ? 'text-slate-700 font-bold' : 'text-slate-400'}`}>
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color, opacity: s.name === alertLevel ? 1 : 0.3 }} />
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
  icon, iconColor, iconBg, label, value, unit, trend, trendValue, warn
}: {
  icon: React.ReactNode; iconColor: string; iconBg: string;
  label: string; value: string; unit: string;
  trend: 'up'|'down'|'flat'; trendValue: string;
  warn: boolean;
}) => (
  <div className={`widget-card flex flex-col gap-3 ${warn ? 'border-red-200 bg-red-50/50' : ''}`}>
    <div className="flex justify-between items-start">
      <div className={`w-8 h-8 rounded-xl ${iconBg} flex items-center justify-center ${iconColor}`}>
        {icon}
      </div>
      <div className={`flex items-center gap-0.5 text-[11px] font-bold rounded-full px-2 py-0.5
        ${trend === 'up' ? 'text-red-600 bg-red-50' : trend === 'down' ? 'text-amber-600 bg-amber-50' : 'text-slate-400 bg-slate-50'}`}>
        {trend === 'up' && <ArrowUpRight className="w-3 h-3" />}
        {trend === 'down' && <ArrowDownRight className="w-3 h-3" />}
        {trend === 'flat' && <ArrowRight className="w-3 h-3" />}
        {trendValue}
      </div>
    </div>
    <div>
      <p className={`stat-value text-2xl ${warn ? 'text-red-600' : ''}`}>{value}</p>
      <p className="text-[11px] text-slate-400 mt-0.5 font-medium">{label} <span className="text-slate-300">{unit}</span></p>
    </div>
  </div>
);

export default DetailPanel;
