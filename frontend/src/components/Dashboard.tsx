import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  Activity, AlertCircle, Wifi, WifiOff, Zap, Menu, X,
  Bell, RefreshCw, AlertTriangle, Filter, Cpu, Shield,
} from 'lucide-react';
import type { PatientProfile, VitalUpdate, PatientLiveState, AlertDecision } from '../types';
import PatientCard from './PatientCard';
import ExplanationModal from './ExplanationModal';
import DetailPanel from './DetailPanel';
import Toast, { type ToastItem } from './Toast';
import CohortStatsBar from './CohortStatsBar';
import { useAutoAnimate } from '@formkit/auto-animate/react';

const MAX_HR_HISTORY = 20;
const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws/dashboard';

type SidebarFilter = 'all' | 'needs-review';
type SystemStatus = 'connecting' | 'connected' | 'reconnecting' | 'offline' | 'stalled';

const STATUS_CONFIG: Record<SystemStatus, { color: string; bg: string; border: string; dot: string }> = {
  connected:    { color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', dot: 'bg-emerald-400' },
  connecting:   { color: 'text-amber-400',   bg: 'bg-amber-500/10',   border: 'border-amber-500/30',   dot: 'bg-amber-400' },
  reconnecting: { color: 'text-amber-400',   bg: 'bg-amber-500/10',   border: 'border-amber-500/30',   dot: 'bg-amber-400' },
  stalled:      { color: 'text-orange-400',  bg: 'bg-orange-500/10',  border: 'border-orange-500/30',  dot: 'bg-orange-400' },
  offline:      { color: 'text-red-400',     bg: 'bg-red-500/10',     border: 'border-red-500/30',     dot: 'bg-red-400' },
};

const Dashboard: React.FC = () => {
  const [patients, setPatients]                 = useState<PatientProfile[]>([]);
  const [liveState, setLiveState]               = useState<Record<string, PatientLiveState>>({});
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen]           = useState(false);
  const [systemStatus, setSystemStatus]         = useState<SystemStatus>('connecting');
  const [offlineReason, setOfflineReason]       = useState<string>('');
  const [totalReadings, setTotalReadings]       = useState(0);
  const [toasts, setToasts]                     = useState<ToastItem[]>([]);
  const [isSidebarOpen, setIsSidebarOpen]       = useState(false);
  const [sidebarFilter, setSidebarFilter]       = useState<SidebarFilter>('all');
  const [pendingCount, setPendingCount]         = useState(0);
  const [parentRef] = useAutoAnimate<HTMLDivElement>({ duration: 300 });

  const wsRef = useRef<WebSocket | null>(null);
  const patientNameMap = useRef<Record<string, string>>({});
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(1000);
  const lastMessageTimeRef = useRef<number>(Date.now());
  const stallCheckIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const addToast = useCallback((update: VitalUpdate, name: string) => {
    const evt = update._alert_event!;
    const toast: ToastItem = {
      id: `${evt.patient_id}-${evt.timestamp}`,
      patientId: evt.patient_id,
      patientName: name,
      riskScore: evt.risk_score,
      message: `${evt.from_level} → ${evt.to_level}`,
    };
    setToasts(prev => [toast, ...prev].slice(0, 5));
    setTimeout(() => dismissToast(toast.id), 8000);
  }, [dismissToast]);

  const refreshPendingCount = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/alerts/pending`);
      const data = await res.json();
      setPendingCount(data.total_pending ?? 0);
    } catch (_) { /* ignore */ }
  }, []);

  const fetchInitialData = useCallback(async () => {
    try {
      const [patientsRes, vitalsRes] = await Promise.all([
        fetch(`${API}/api/patients`),
        fetch(`${API}/api/vitals/latest`),
      ]);
      const patientsData = await patientsRes.json();
      const vitalsData = await vitalsRes.json();

      const ps: PatientProfile[] = patientsData.patients;
      setPatients(ps);
      ps.forEach(p => { patientNameMap.current[p.patient_id] = p.name; });

      setLiveState(prev => {
        const initialLive: Record<string, PatientLiveState> = { ...prev };
        for (const [pid, reading] of Object.entries(vitalsData.patients as Record<string, VitalUpdate>)) {
          const existing = initialLive[pid];
          initialLive[pid] = {
            latest: reading,
            alertLevel: reading._alert_event?.to_level ?? existing?.alertLevel ?? 'NORMAL',
            riskScore: reading._risk_score ?? existing?.riskScore ?? 0,
            hrHistory: reading.vitals ? [...(existing?.hrHistory ?? []), reading.vitals.heart_rate].slice(-MAX_HR_HISTORY) : (existing?.hrHistory ?? []),
            latestAlertId: existing?.latestAlertId,
            latestDecision: existing?.latestDecision,
          };
        }
        return initialLive;
      });
    } catch (err) {
      console.error('Failed to fetch initial data:', err);
    }
  }, []);

  useEffect(() => {
    let isSubscribed = true;

    fetchInitialData();
    refreshPendingCount();

    const connectWs = () => {
      if (!isSubscribed) return;
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isSubscribed) { ws.close(); return; }
        setSystemStatus('connected');
        setOfflineReason('');
        backoffRef.current = 1000;
        lastMessageTimeRef.current = Date.now();
        fetchInitialData();
      };

      ws.onclose = (event) => {
        if (!isSubscribed) return;
        setSystemStatus(backoffRef.current > 1000 ? 'reconnecting' : 'offline');
        setOfflineReason(`Code ${event.code}`);
        const backoff = Math.min(backoffRef.current, 10000);
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isSubscribed) { backoffRef.current = backoff * 2; connectWs(); }
        }, backoff);
      };

      ws.onerror = (error) => { console.error('[WebSocket] Error:', error); };

      ws.onmessage = (event) => {
        if (!isSubscribed) return;
        lastMessageTimeRef.current = Date.now();
        setSystemStatus(prev => (prev === 'stalled' ? 'connected' : prev));
        try {
          const msg = JSON.parse(event.data);

          if (msg.type === 'vital_update') {
            const data: VitalUpdate = msg.data;
            setTotalReadings(n => n + 1);
            setLiveState(prev => {
              const existing = prev[data.patient_id];
              const newAlertLevel = data._alert_event?.to_level ?? existing?.alertLevel ?? 'NORMAL';
              const newRisk = data._risk_score ?? existing?.riskScore ?? 0;
              const prevHistory = existing?.hrHistory ?? [];
              const newHistory = data.vitals
                ? [...prevHistory, data.vitals.heart_rate].slice(-MAX_HR_HISTORY)
                : prevHistory;

              return {
                ...prev,
                [data.patient_id]: {
                  latest: data,
                  alertLevel: newAlertLevel,
                  riskScore: newRisk,
                  hrHistory: newHistory,
                  latestAlertId: data._alert_event
                    ? `${data.patient_id}-${data._alert_event.timestamp.toFixed(3)}`
                    : existing?.latestAlertId,
                  latestDecision: existing?.latestDecision,
                },
              };
            });

            if (data._alert_event) {
              refreshPendingCount();
              if (data._alert_event.to_level === 'ESCALATED') {
                const name = patientNameMap.current[data.patient_id] ?? data.patient_id;
                addToast(data, name);
              }
            }
          }

          if (msg.type === 'decision_update') {
            const { patient_id, decision } = msg.data;
            setLiveState(prev => {
              const existing = prev[patient_id];
              if (!existing) return prev;
              let newLevel = existing.alertLevel;
              const d = (decision?.decision ?? '') as string;
              if (d === 'dismiss') { newLevel = 'NORMAL'; }
              else if (d === 'accept' || d === 'investigate' || d === 'defer') {
                if (newLevel === 'ESCALATED' || newLevel === 'SUSPECTED') newLevel = 'WATCH';
              }
              return { ...prev, [patient_id]: { ...existing, latestDecision: decision, alertLevel: newLevel } };
            });
            refreshPendingCount();
          }

          if (msg.type === 'alert_event') {
            const alertData = msg.data;
            const pid = alertData.patient_id;
            const alertId = `${pid}-${alertData.timestamp.toFixed(3)}`;
            setLiveState(prev => {
              const existing = prev[pid];
              if (!existing) return prev;
              return { ...prev, [pid]: { ...existing, latestAlertId: alertId, latestDecision: null } };
            });
          }
        } catch (e) { console.error(e); }
      };
    };

    connectWs();

    stallCheckIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        const timeSinceLastMessage = Date.now() - lastMessageTimeRef.current;
        if (timeSinceLastMessage > 15000) {
          setSystemStatus('stalled');
          setOfflineReason('No messages >15s');
        }
      }
    }, 5000);

    return () => {
      isSubscribed = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (stallCheckIntervalRef.current) clearInterval(stallCheckIntervalRef.current);
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    };
  }, [addToast, refreshPendingCount, fetchInitialData]);

  const sortedPatients = [...patients].sort((a, b) => {
    const aState = liveState[a.patient_id];
    const bState = liveState[b.patient_id];
    const levelOrder: Record<string, number> = { ESCALATED: 0, SUSPECTED: 1, WATCH: 2, NORMAL: 3 };
    const aLevel = levelOrder[aState?.alertLevel ?? 'NORMAL'] ?? 3;
    const bLevel = levelOrder[bState?.alertLevel ?? 'NORMAL'] ?? 3;
    if (aLevel !== bLevel) return aLevel - bLevel;
    return (bState?.riskScore ?? 0) - (aState?.riskScore ?? 0);
  });

  const displayedPatients = sidebarFilter === 'needs-review'
    ? sortedPatients.filter(p => {
        const s = liveState[p.patient_id];
        return (s?.alertLevel === 'ESCALATED' || s?.alertLevel === 'SUSPECTED') && !s?.latestDecision;
      })
    : sortedPatients;

  const selectedState = selectedPatientId ? liveState[selectedPatientId] : null;
  const selectedProfile = selectedPatientId
    ? patients.find(p => p.patient_id === selectedPatientId) ?? null
    : null;

  const escalatedCount = Object.values(liveState).filter(s => s.alertLevel === 'ESCALATED').length;
  const suspectedCount = Object.values(liveState).filter(s => s.alertLevel === 'SUSPECTED').length;
  const watchCount     = Object.values(liveState).filter(s => s.alertLevel === 'WATCH').length;
  const normalCount    = Object.values(liveState).filter(s => s.alertLevel === 'NORMAL').length;

  const handleDecisionMade = useCallback((pid: string, decision: AlertDecision) => {
    setLiveState(prev => {
      const existing = prev[pid];
      if (!existing) return prev;
      let newLevel = existing.alertLevel;
      const d = decision.decision;
      if (d === 'dismiss') { newLevel = 'NORMAL'; }
      else if (d === 'accept' || d === 'investigate' || d === 'defer') {
        if (newLevel === 'ESCALATED' || newLevel === 'SUSPECTED') newLevel = 'WATCH';
      }
      return { ...prev, [pid]: { ...existing, latestDecision: decision, alertLevel: newLevel } };
    });
    refreshPendingCount();
  }, [refreshPendingCount]);

  const statusCfg = STATUS_CONFIG[systemStatus];

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: 'var(--bg-base)' }}>

      {/* ── Cohort Stats Bar ─────────────────────────────────────────── */}
      <CohortStatsBar
        totalReadings={totalReadings}
        escalatedCount={escalatedCount}
        suspectedCount={suspectedCount}
        watchCount={watchCount}
        normalCount={normalCount}
        totalPatients={patients.length}
      />

      {/* ── ESCALATED Banner ─────────────────────────────────────────── */}
      {escalatedCount > 0 && (
        <div
          className="flex items-center justify-center gap-3 px-4 py-2 flex-shrink-0 animate-pulse-soft"
          style={{
            background: 'linear-gradient(90deg, rgba(239,68,68,0.12) 0%, rgba(239,68,68,0.18) 50%, rgba(239,68,68,0.12) 100%)',
            borderBottom: '1px solid rgba(239,68,68,0.3)',
            boxShadow: '0 0 30px rgba(239,68,68,0.1)',
          }}
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
          </span>
          <AlertCircle className="w-3.5 h-3.5 text-red-400" />
          <span className="text-[11px] font-black uppercase tracking-widest text-red-300">
            ⚠ {escalatedCount} Patient{escalatedCount > 1 ? 's' : ''} Require Immediate Escalation
          </span>
        </div>
      )}

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header
        className="px-4 lg:px-6 py-3 flex justify-between items-center flex-shrink-0 z-40"
        style={{
          background: 'var(--bg-header)',
          borderBottom: '1px solid var(--border-dim)',
          backdropFilter: 'blur(20px)',
          boxShadow: '0 4px 30px rgba(0,0,0,0.3)',
        }}
      >
        <div className="flex items-center gap-3">
          <button
            className="lg:hidden p-2 rounded-xl transition"
            style={{ color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.04)' }}
            onClick={() => setIsSidebarOpen(true)}
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3">
            {/* Logo */}
            <div className="relative w-10 h-10 flex items-center justify-center rounded-xl"
              style={{
                background: 'linear-gradient(135deg, rgba(99,102,241,0.3) 0%, rgba(139,92,246,0.2) 100%)',
                border: '1px solid rgba(99,102,241,0.4)',
                boxShadow: '0 0 20px rgba(99,102,241,0.3)',
              }}
            >
              <Shield className="w-5 h-5" style={{ color: '#818CF8' }} />
              <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-emerald-400 border-2 border-[var(--bg-base)]" />
            </div>
            <div>
              <h1 className="text-lg font-black leading-tight gradient-text">SentinelCare</h1>
              <p className="text-[9px] font-bold tracking-[0.2em] uppercase" style={{ color: 'var(--text-muted)' }}>
                Clinical AI Copilot
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 lg:gap-3">
          {/* Alert severity pills */}
          {escalatedCount > 0 && (
            <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-black animate-pulse-ring"
              style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.4)', color: '#F87171' }}>
              <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-blink-dot" />
              {escalatedCount} Escalated
            </span>
          )}
          {suspectedCount > 0 && (
            <span className="hidden lg:flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold"
              style={{ background: 'rgba(249,115,22,0.12)', border: '1px solid rgba(249,115,22,0.3)', color: '#FB923C' }}>
              {suspectedCount} Suspected
            </span>
          )}
          {watchCount > 0 && (
            <span className="hidden lg:flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold"
              style={{ background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.3)', color: '#FCD34D' }}>
              {watchCount} Watch
            </span>
          )}

          {pendingCount > 0 && (
            <button
              id="needs-review-btn"
              onClick={() => setSidebarFilter(f => f === 'needs-review' ? 'all' : 'needs-review')}
              className="hidden lg:flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold transition-all"
              style={sidebarFilter === 'needs-review'
                ? { background: 'rgba(99,102,241,0.4)', border: '1px solid rgba(99,102,241,0.6)', color: '#E0E7FF', boxShadow: '0 0 16px rgba(99,102,241,0.4)' }
                : { background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.25)', color: '#A5B4FC' }}
            >
              <AlertTriangle className="w-3 h-3" />
              {pendingCount} Review
            </button>
          )}

          {/* Utility icons */}
          <div className="hidden lg:flex items-center gap-1 ml-1 pl-3" style={{ borderLeft: '1px solid var(--border-dim)' }}>
            <button className="p-2 rounded-lg transition" style={{ color: 'var(--text-muted)' }}
              onClick={fetchInitialData}>
              <RefreshCw className="w-4 h-4" />
            </button>
            <button className="p-2 rounded-lg transition relative" style={{ color: 'var(--text-muted)' }}>
              <Bell className="w-4 h-4" />
              {escalatedCount > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full animate-pulse" />
              )}
            </button>
            <button className="p-2 rounded-lg transition" style={{ color: 'var(--text-muted)' }}>
              <Cpu className="w-4 h-4" />
            </button>
          </div>

          {/* Connection pill */}
          <div
            title={offlineReason || 'Connected'}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${statusCfg.bg} ${statusCfg.color}`}
            style={{ border: `1px solid ${statusCfg.border.replace('border-', '')}` }}
          >
            {systemStatus === 'connected' ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            <span className="hidden lg:inline">{systemStatus}</span>
            <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.dot} ${
              systemStatus === 'connected' ? 'animate-pulse' : 
              systemStatus === 'connecting' || systemStatus === 'reconnecting' ? 'animate-ping' : ''
            }`} />
          </div>
        </div>
      </header>

      {/* ── Main ───────────────────────────────────────────────────────── */}
      <main className="flex-1 flex overflow-hidden relative">

        {/* Sidebar overlay for mobile */}
        {isSidebarOpen && (
          <div
            className="fixed inset-0 z-40 lg:hidden"
            style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        {/* Left Column: Patient List */}
        <aside
          className={`
            absolute lg:relative w-80 lg:w-[300px] h-full z-50 flex flex-col
            transition-transform duration-300 ease-in-out
            ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          `}
          style={{
            background: 'var(--bg-sidebar)',
            borderRight: '1px solid var(--border-dim)',
            backdropFilter: 'blur(20px)',
            boxShadow: isSidebarOpen ? '4px 0 30px rgba(0,0,0,0.5)' : undefined,
          }}
        >
          {/* Sidebar header */}
          <div className="px-4 py-3 flex justify-between items-center flex-shrink-0"
            style={{ borderBottom: '1px solid var(--border-dim)' }}>
            <h2 className="text-[10px] font-black uppercase tracking-[0.2em] flex items-center gap-2"
              style={{ color: 'var(--text-muted)' }}>
              <Activity className="w-3.5 h-3.5" style={{ color: 'var(--accent-bright)' }} />
              Patient Cohort
            </h2>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full"
                style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--text-muted)', border: '1px solid var(--border-dim)' }}>
                {displayedPatients.length}/{sortedPatients.length}
              </span>
              <button className="lg:hidden p-1 rounded" style={{ color: 'var(--text-muted)' }}
                onClick={() => setIsSidebarOpen(false)}>
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Filter tabs */}
          <div className="flex flex-shrink-0" style={{ borderBottom: '1px solid var(--border-dim)' }}>
            <FilterTab active={sidebarFilter === 'all'} onClick={() => setSidebarFilter('all')}
              label="All Patients" count={sortedPatients.length} />
            <FilterTab active={sidebarFilter === 'needs-review'} onClick={() => setSidebarFilter('needs-review')}
              label="Needs Review" count={pendingCount} highlight />
          </div>

          {/* Readings counter */}
          <div className="px-4 py-2.5 flex items-center gap-2 flex-shrink-0"
            style={{ borderBottom: '1px solid var(--border-dim)' }}>
            <Zap className="w-3 h-3" style={{ color: 'var(--accent-bright)' }} />
            <span className="font-tabular text-[10px] font-medium" style={{ color: 'var(--text-muted)' }}>
              {totalReadings.toLocaleString()} readings processed
            </span>
            <span className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-400 animate-blink-dot" />
          </div>

          {/* Patient list */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2" ref={parentRef}>
            {displayedPatients.map(p => (
              <PatientCard
                key={p.patient_id}
                patient={p}
                liveState={liveState[p.patient_id]}
                isSelected={selectedPatientId === p.patient_id}
                onSelect={() => {
                  setSelectedPatientId(p.patient_id);
                  if (window.innerWidth < 1024) setIsSidebarOpen(false);
                }}
                onOpenAgent={() => { setSelectedPatientId(p.patient_id); setIsModalOpen(true); }}
              />
            ))}

            {displayedPatients.length === 0 && sidebarFilter === 'needs-review' && (
              <div className="flex flex-col items-center justify-center h-48 text-center gap-3 py-8">
                <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
                  style={{ background: 'rgba(20,184,166,0.1)', border: '1px solid rgba(20,184,166,0.2)' }}>
                  <Filter className="w-6 h-6" style={{ color: 'var(--severity-normal)' }} />
                </div>
                <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>All alerts reviewed!</p>
                <p className="text-[10px]" style={{ color: 'var(--text-muted)', opacity: 0.6 }}>No pending decisions.</p>
              </div>
            )}

            {displayedPatients.length === 0 && sidebarFilter === 'all' && (
              <div className="flex flex-col items-center justify-center h-48">
                <div className="w-12 h-12 rounded-2xl flex items-center justify-center mb-3"
                  style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid var(--border-dim)' }}>
                  <Activity className="w-6 h-6 animate-pulse" style={{ color: 'var(--text-muted)' }} />
                </div>
                <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Awaiting patient feed...</p>
              </div>
            )}
          </div>
        </aside>

        {/* Right Panel: Detail View */}
        <div className="flex-1 overflow-hidden flex flex-col relative z-0"
          style={{ background: 'var(--bg-base)' }}>
          <DetailPanel
            patient={selectedProfile}
            liveState={selectedState}
            onOpenAgent={() => setIsModalOpen(true)}
          />
        </div>
      </main>

      {/* ── Modals ─────────────────────────────────────────────────────── */}
      {selectedPatientId && (
        <ExplanationModal
          patientId={selectedPatientId}
          patientName={selectedProfile?.name}
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          latestAlertId={selectedState?.latestAlertId}
          currentDecision={selectedState?.latestDecision}
          onDecisionMade={(dec) => handleDecisionMade(selectedPatientId, dec)}
        />
      )}

      {/* ── Toast Stack ─────────────────────────────────────────────────── */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-3 pointer-events-none">
        {toasts.map(t => (
          <Toast key={t.id} toast={t} onDismiss={dismissToast}
            onView={() => {
              setSelectedPatientId(t.patientId);
              setIsModalOpen(true);
              dismissToast(t.id);
            }}
          />
        ))}
      </div>
    </div>
  );
};

// ── Filter Tab ─────────────────────────────────────────────────────────────────

const FilterTab: React.FC<{
  active: boolean; onClick: () => void; label: string; count: number; highlight?: boolean;
}> = ({ active, onClick, label, count, highlight }) => (
  <button
    onClick={onClick}
    className="flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[10px] font-bold uppercase tracking-wider transition-all border-b-2"
    style={active
      ? highlight
        ? { color: '#A5B4FC', borderColor: '#6366F1', background: 'rgba(99,102,241,0.08)' }
        : { color: 'var(--text-primary)', borderColor: 'var(--accent)', background: 'rgba(99,102,241,0.05)' }
      : { color: 'var(--text-muted)', borderColor: 'transparent' }
    }
  >
    {label}
    {count > 0 && (
      <span className="px-1.5 py-0.5 rounded-full text-[9px] font-black"
        style={highlight && count > 0
          ? { background: 'rgba(99,102,241,0.2)', color: '#A5B4FC' }
          : { background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)' }
        }>
        {count}
      </span>
    )}
  </button>
);

export default Dashboard;
