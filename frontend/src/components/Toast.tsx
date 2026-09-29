import React, { useEffect, useState } from 'react';
import { AlertCircle, X } from 'lucide-react';

export interface ToastItem {
  id: string;
  patientId: string;
  patientName: string;
  riskScore: number;
  message: string;
}

interface ToastProps {
  toast: ToastItem;
  onDismiss: (id: string) => void;
  onView: () => void;
}

const Toast: React.FC<ToastProps> = ({ toast, onDismiss, onView }) => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
  }, []);

  const toLevel = toast.message.split(' → ')[1] ?? 'ESCALATED';
  const colorMap: Record<string, string> = {
    ESCALATED: '#EF4444',
    SUSPECTED: '#F97316',
    WATCH:     '#F59E0B',
  };
  const color = colorMap[toLevel] ?? '#EF4444';

  return (
    <div
      id={`toast-${toast.id}`}
      className={`pointer-events-auto rounded-2xl p-4 w-80 transition-all duration-300 ${
        visible ? 'animate-slide-in opacity-100' : 'opacity-0 translate-x-full'
      }`}
      style={{
        background: 'rgba(6,13,24,0.95)',
        border: `1px solid ${color}40`,
        boxShadow: `0 20px 50px rgba(0,0,0,0.7), 0 0 30px ${color}20`,
        backdropFilter: 'blur(20px)',
      }}
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center animate-pulse-ring"
          style={{ background: `${color}15`, border: `1px solid ${color}40`, color }}>
          <AlertCircle className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-black uppercase tracking-widest" style={{ color }}>
            ⚡ Alert: {toast.message}
          </p>
          <p className="text-sm font-bold mt-0.5 truncate" style={{ color: 'var(--text-bright)' }}>
            {toast.patientName}
          </p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
            Risk: <span className="font-mono font-black" style={{ color }}>{toast.riskScore.toFixed(0)}</span>
          </p>
          <button
            id={`toast-view-${toast.id}`}
            onClick={onView}
            className="mt-2.5 text-xs font-black transition"
            style={{ color: '#818CF8' }}
            onMouseEnter={e => (e.currentTarget.style.textShadow = '0 0 10px rgba(99,102,241,0.6)')}
            onMouseLeave={e => (e.currentTarget.style.textShadow = 'none')}
          >
            View SBAR Report →
          </button>
        </div>
        <button
          onClick={() => onDismiss(toast.id)}
          className="flex-shrink-0 rounded-lg p-1 transition mt-0.5"
          style={{ color: 'var(--text-muted)', background: 'rgba(255,255,255,0.04)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};

export default Toast;
