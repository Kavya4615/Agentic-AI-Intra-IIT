import React from 'react';
import { ResponsiveContainer, AreaChart, Area } from 'recharts';

interface SparklineChartProps {
  data: number[];
  color?: string;
}

export const SparklineChart: React.FC<SparklineChartProps> = ({ data, color = '#818CF8' }) => {
  const chartData = data.map((v, i) => ({ i, v }));
  const gradId = `sparkGrad-${color.replace('#', '')}`;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={chartData} margin={{ top: 1, right: 0, left: 0, bottom: 1 }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor={color} stopOpacity={0.5} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#${gradId})`}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
};
