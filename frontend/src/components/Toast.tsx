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

const LEVEL_COLORS: Record<string, string> = {
  ESCALATED: '#ef4444',
  SUSPECTED: '#f97316',
  WATCH:     '#f59e0b',
};

const Toast: React.FC<ToastProps> = ({ toast, onDismiss, onView }) => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Trigger entrance animation after mount
    requestAnimationFrame(() => setVisible(true));
  }, []);

  const color = LEVEL_COLORS[toast.message.split(' → ')[1]] ?? '#ef4444';

  return (
    <div
      className={`
        pointer-events-auto glass-panel-elevated border p-4 w-80 shadow-2xl
        transition-all duration-300
        ${visible ? 'animate-slide-in opacity-100' : 'opacity-0 translate-x-full'}
      `}
      style={{ borderColor: `${color}40` }}
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center animate-pulse-ring"
          style={{ backgroundColor: `${color}20`, color }}>
          <AlertCircle className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-black uppercase tracking-wider" style={{ color }}>
            Alert: {toast.message}
          </p>
          <p className="text-sm font-semibold text-[var(--text-primary)] mt-0.5 truncate">
            {toast.patientName}
          </p>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Risk score: <span className="font-mono font-bold" style={{ color }}>{toast.riskScore.toFixed(0)}</span>
          </p>
          <button
            id={`toast-view-${toast.id}`}
            onClick={onView}
            className="mt-2.5 text-xs font-bold text-[var(--accent)] hover:underline"
          >
            View SBAR Report →
          </button>
        </div>
        <button
          onClick={() => onDismiss(toast.id)}
          className="flex-shrink-0 text-[var(--text-muted)] hover:text-white transition-colors mt-0.5"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default Toast;
