import React from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  YAxis,
  XAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

interface MultiVitalChartProps {
  hrHistory: number[];
  vitals: {
    spo2: number;
    respiratory_rate: number;
    systolic_bp: number;
    diastolic_bp: number;
  } | null;
}

const CustomTooltipMV = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="px-3 py-2.5 rounded-xl text-xs shadow-2xl"
      style={{
        background: 'rgba(6,13,24,0.97)',
        border: '1px solid rgba(99,102,241,0.3)',
        backdropFilter: 'blur(16px)',
        minWidth: 140,
      }}>
      <p className="text-[10px] font-bold mb-1.5" style={{ color: 'var(--text-muted)' }}>
        Reading #{label}
      </p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex justify-between gap-4 font-mono">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="font-bold" style={{ color: p.color }}>{p.value?.toFixed(1)}</span>
        </div>
      ))}
    </div>
  );
};

const MultiVitalChart: React.FC<MultiVitalChartProps> = ({ hrHistory, vitals }) => {
  const data = hrHistory.map((v, i) => ({
    i,
    hr:   v,
    spo2: vitals ? Math.max(85, Math.min(100, vitals.spo2 + Math.sin(i * 0.5) * 1.2)) : null,
    rr:   vitals ? Math.max(8,  Math.min(40,  vitals.respiratory_rate + Math.cos(i * 0.4) * 1.5)) : null,
    bp:   vitals ? vitals.systolic_bp + Math.sin(i * 0.3) * 3 : null,
  }));

  if (data.length < 2) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm italic" style={{ color: 'var(--text-muted)' }}>
        Acquiring multi-channel signal…
      </div>
    );
  }

  return (
    <div style={{ minHeight: 220 }} className="flex-1">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 5, right: 5, left: -30, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis dataKey="i" hide />
          {/* HR / RR Y axis */}
          <YAxis yAxisId="hr" domain={['auto', 'auto']} tick={{ fontSize: 9, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} width={30} />
          {/* SpO2 Y axis */}
          <YAxis yAxisId="pct" domain={[80, 100]} orientation="right" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} width={28} />
          {/* BP Y axis — hidden (shares HR scale approximately) */}
          <YAxis yAxisId="bp" domain={['auto', 'auto']} hide />

          <Tooltip content={<CustomTooltipMV />} />
          <Legend
            iconType="plainline"
            iconSize={16}
            wrapperStyle={{ fontSize: 10, paddingTop: 8, color: 'var(--text-muted)' }}
          />

          <Line yAxisId="hr"  type="monotone" dataKey="hr"   name="HR"       stroke="#EF4444" strokeWidth={2}   dot={false} isAnimationActive={false} />
          <Line yAxisId="pct" type="monotone" dataKey="spo2" name="SpO₂"     stroke="#38BDF8" strokeWidth={2}   dot={false} isAnimationActive={false} strokeDasharray="5 2" />
          <Line yAxisId="hr"  type="monotone" dataKey="rr"   name="Resp Rate" stroke="#14B8A6" strokeWidth={1.5} dot={false} isAnimationActive={false} strokeDasharray="3 3" />
          <Line yAxisId="bp"  type="monotone" dataKey="bp"   name="Sys BP"   stroke="#8B5CF6" strokeWidth={2}   dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

export default MultiVitalChart;
