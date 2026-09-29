import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  Activity, AlertCircle, Wifi, WifiOff, Zap, Menu, X,
  Bell, RefreshCw, AlertTriangle, Filter,
} from 'lucide-react';
import type { PatientProfile, VitalUpdate, PatientLiveState, AlertDecision } from '../types';
import PatientCard from './PatientCard';
import ExplanationModal from './ExplanationModal';
import DetailPanel from './DetailPanel';
import Toast, { type ToastItem } from './Toast';
import { useAutoAnimate } from '@formkit/auto-animate/react';

const MAX_HR_HISTORY = 20;
const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws/dashboard';

type SidebarFilter = 'all' | 'needs-review';
type SystemStatus = 'connecting' | 'connected' | 'reconnecting' | 'offline' | 'stalled';

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

  // ── Fetch pending count from API ──────────────────────────────────────────
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

  // ── Initial data + WebSocket ──────────────────────────────────────────────

  useEffect(() => {
    let isSubscribed = true;

    fetchInitialData();
    refreshPendingCount();

    const connectWs = () => {
      if (!isSubscribed) return;
      console.log(`[WebSocket] Connecting to ${WS_URL}...`);
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isSubscribed) {
          ws.close();
          return;
        }
        console.log('[WebSocket] Connected');
        setSystemStatus('connected');
        setOfflineReason('');
        backoffRef.current = 1000; // reset backoff
        lastMessageTimeRef.current = Date.now();
        fetchInitialData(); // hydrate on reconnect
      };

      ws.onclose = (event) => {
        if (!isSubscribed) return;
        console.log(`[WebSocket] Disconnected (code: ${event.code}, reason: ${event.reason})`);
        setSystemStatus(backoffRef.current > 1000 ? 'reconnecting' : 'offline');
        setOfflineReason(`Code ${event.code}`);
        
        // Exponential backoff capped at 10s
        const backoff = Math.min(backoffRef.current, 10000);
        console.log(`[WebSocket] Reconnecting in ${backoff}ms...`);
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isSubscribed) {
            backoffRef.current = backoff * 2;
            connectWs();
          }
        }, backoff);
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
      };

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
              const newAlertLevel =
                data._alert_event?.to_level ?? existing?.alertLevel ?? 'NORMAL';
              const newRisk =
                data._risk_score ?? existing?.riskScore ?? 0;
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
                  // Preserve alert id and decision if no new alert event
                  latestAlertId: data._alert_event
                    ? `${data.patient_id}-${data._alert_event.timestamp.toFixed(3)}`
                    : existing?.latestAlertId,
                  latestDecision: existing?.latestDecision,
                },
              };
            });

            if (data._alert_event) {
              // Refresh pending count on any alert state change (including de-escalation)
              refreshPendingCount();
              if (data._alert_event.to_level === 'ESCALATED') {
                const name = patientNameMap.current[data.patient_id] ?? data.patient_id;
                addToast(data, name);
              }
            }
          }

          // Phase 10: decision update broadcast
          if (msg.type === 'decision_update') {
            const { patient_id, decision } = msg.data;
            setLiveState(prev => {
              const existing = prev[patient_id];
              if (!existing) return prev;

              // Mirror the same level-downgrade logic for WS-broadcast decisions
              let newLevel = existing.alertLevel;
              const d = (decision?.decision ?? '') as string;
              if (d === 'dismiss') {
                newLevel = 'NORMAL';
              } else if (d === 'accept' || d === 'investigate' || d === 'defer') {
                if (newLevel === 'ESCALATED' || newLevel === 'SUSPECTED') {
                  newLevel = 'WATCH';
                }
              }

              return {
                ...prev,
                [patient_id]: { ...existing, latestDecision: decision, alertLevel: newLevel },
              };
            });
            refreshPendingCount();
          }

          // Phase 10: alert event (capture alert_id for decisions)
          if (msg.type === 'alert_event') {
            const alertData = msg.data;
            const pid = alertData.patient_id;
            const alertId = `${pid}-${alertData.timestamp.toFixed(3)}`;
            setLiveState(prev => {
              const existing = prev[pid];
              if (!existing) return prev;
              return {
                ...prev,
                [pid]: {
                  ...existing,
                  latestAlertId: alertId,
                  latestDecision: null, // new alert, no decision yet
                },
              };
            });
          }
        } catch (e) {
          console.error(e);
        }
      };
    };

    connectWs();

    stallCheckIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        const timeSinceLastMessage = Date.now() - lastMessageTimeRef.current;
        if (timeSinceLastMessage > 15000) {
          console.warn('[WebSocket] No messages received in 15s. Stream stalled.');
          setSystemStatus('stalled');
          setOfflineReason('No messages > 15s');
        }
      }
    }, 5000);

    return () => {
      isSubscribed = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (stallCheckIntervalRef.current) clearInterval(stallCheckIntervalRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [addToast, refreshPendingCount, fetchInitialData]);

  // Sorted and filtered patient list
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
        return (
          (s?.alertLevel === 'ESCALATED' || s?.alertLevel === 'SUSPECTED')
          && !s?.latestDecision
        );
      })
    : sortedPatients;

  const selectedState = selectedPatientId ? liveState[selectedPatientId] : null;
  const selectedProfile = selectedPatientId
    ? patients.find(p => p.patient_id === selectedPatientId) ?? null
    : null;

  const escalatedCount = Object.values(liveState).filter(s => s.alertLevel === 'ESCALATED').length;
  const suspectedCount = Object.values(liveState).filter(s => s.alertLevel === 'SUSPECTED').length;
  const watchCount = Object.values(liveState).filter(s => s.alertLevel === 'WATCH').length;

  const handleDecisionMade = useCallback((pid: string, decision: AlertDecision) => {
    setLiveState(prev => {
      const existing = prev[pid];
      if (!existing) return prev;

      // Downgrade alert level after a clinician action so the patient
      // leaves the ESCALATED banner / Needs Review queue immediately.
      let newLevel = existing.alertLevel;
      const d = decision.decision;
      if (d === 'dismiss') {
        // Dismiss forces all the way back to NORMAL (SM side-effect mirrors this)
        newLevel = 'NORMAL';
      } else if (d === 'accept' || d === 'investigate' || d === 'defer') {
        // Accept / investigate / defer: still monitoring but no longer urgent
        if (newLevel === 'ESCALATED' || newLevel === 'SUSPECTED') {
          newLevel = 'WATCH';
        }
      }

      return {
        ...prev,
        [pid]: { ...existing, latestDecision: decision, alertLevel: newLevel },
      };
    });
    refreshPendingCount();
  }, [refreshPendingCount]);

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[#F5F6FA]">

      {/* ── ESCALATED Banner ─────────────────────────────────────────── */}
      {escalatedCount > 0 && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 flex items-center justify-center gap-2 flex-shrink-0 animate-pulse-soft">
          <AlertCircle className="w-4 h-4 text-red-600" />
          <span className="text-xs font-bold text-red-700 uppercase tracking-wider">
            {escalatedCount} Patient{escalatedCount > 1 ? 's' : ''} in ESCALATED State — Immediate Review Required
          </span>
        </div>
      )}

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-slate-200 px-4 lg:px-6 py-3 flex justify-between items-center flex-shrink-0 z-40 shadow-sm">
        <div className="flex items-center gap-3">
          <button
            className="lg:hidden p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition"
            onClick={() => setIsSidebarOpen(true)}
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-base lg:text-lg font-extrabold text-slate-800 leading-tight">
                SentinelCare
              </h1>
              <p className="text-[10px] font-medium tracking-widest text-slate-400 uppercase">
                Clinical Decision Support
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 lg:gap-3">
          {/* Alert pills */}
          {escalatedCount > 0 && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-50 border border-red-200 text-xs font-bold text-red-700 animate-pulse-ring">
              {escalatedCount} Escalated
            </span>
          )}
          {suspectedCount > 0 && (
            <span className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-orange-50 border border-orange-200 text-xs font-bold text-orange-700">
              {suspectedCount} Suspected
            </span>
          )}
          {watchCount > 0 && (
            <span className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-xs font-bold text-amber-700">
              {watchCount} Watch
            </span>
          )}

          {/* Needs review pill */}
          {pendingCount > 0 && (
            <button
              id="needs-review-btn"
              onClick={() => setSidebarFilter(f => f === 'needs-review' ? 'all' : 'needs-review')}
              className={`hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border transition ${
                sidebarFilter === 'needs-review'
                  ? 'bg-violet-600 text-white border-violet-600 shadow-md'
                  : 'bg-violet-50 border-violet-200 text-violet-700 hover:bg-violet-100'
              }`}
            >
              <AlertTriangle className="w-3 h-3" />
              {pendingCount} Needs Review
            </button>
          )}

          {/* Utility icons */}
          <div className="hidden lg:flex items-center gap-1 ml-2 border-l border-slate-200 pl-3">
            <button className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-lg transition">
              <RefreshCw className="w-4 h-4" />
            </button>
            <button className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-lg transition relative">
              <Bell className="w-4 h-4" />
              {escalatedCount > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
              )}
            </button>
          </div>

          {/* Connection pill */}
          <div
            title={offlineReason || 'Connected'}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border
            ${systemStatus === 'connected'
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : systemStatus === 'connecting' || systemStatus === 'reconnecting'
              ? 'bg-amber-50 text-amber-700 border-amber-200'
              : systemStatus === 'stalled'
              ? 'bg-orange-50 text-orange-700 border-orange-200'
              : 'bg-red-50 text-red-700 border-red-200'
            }`}
          >
            {systemStatus === 'connected' ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            <span className="hidden lg:inline">{systemStatus}</span>
            <span className={`w-1.5 h-1.5 rounded-full ${
              systemStatus === 'connected' ? 'bg-emerald-500 animate-pulse'
              : systemStatus === 'stalled' ? 'bg-orange-500'
              : systemStatus === 'offline' ? 'bg-red-500'
              : 'bg-amber-500 animate-ping'
            }`} />
          </div>
        </div>
      </header>

      {/* ── Main ───────────────────────────────────────────────────────── */}
      <main className="flex-1 flex overflow-hidden relative">

        {/* Sidebar overlay for mobile */}
        {isSidebarOpen && (
          <div
            className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 lg:hidden"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        {/* Left Column: Patient List */}
        <aside
          className={`
            absolute lg:relative w-80 lg:w-[320px] h-full bg-white border-r border-slate-200 z-50 flex flex-col
            transition-transform duration-300 ease-in-out shadow-xl lg:shadow-none
            ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          `}
        >
          <div className="px-4 py-3 border-b border-slate-100 flex justify-between items-center flex-shrink-0">
            <h2 className="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
              <AlertCircle className="w-3.5 h-3.5" />
              Patient Cohort
            </h2>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-slate-400 bg-slate-50 px-2 py-0.5 rounded-full">
                {displayedPatients.length}/{sortedPatients.length}
              </span>
              <button
                className="lg:hidden p-1 text-slate-400 hover:text-slate-700 rounded"
                onClick={() => setIsSidebarOpen(false)}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Filter tabs */}
          <div className="flex border-b border-slate-100 flex-shrink-0">
            <FilterTab
              active={sidebarFilter === 'all'}
              onClick={() => setSidebarFilter('all')}
              label="All Patients"
              count={sortedPatients.length}
            />
            <FilterTab
              active={sidebarFilter === 'needs-review'}
              onClick={() => setSidebarFilter('needs-review')}
              label="Needs Review"
              count={pendingCount}
              highlight
            />
          </div>

          {/* Readings counter */}
          <div className="px-4 py-2 border-b border-slate-100 flex items-center gap-2 text-[10px] font-medium text-slate-400 flex-shrink-0">
            <Zap className="w-3 h-3 text-indigo-400" />
            <span className="font-tabular">{totalReadings.toLocaleString()} readings processed</span>
          </div>

          <div className="flex-1 overflow-y-auto p-3" ref={parentRef}>
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
              <div className="flex-1 flex flex-col items-center justify-center h-48 text-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-emerald-50 flex items-center justify-center">
                  <Filter className="w-6 h-6 text-emerald-400" />
                </div>
                <p className="text-xs font-medium text-slate-400">All alerts reviewed!</p>
                <p className="text-[10px] text-slate-300">No undecided ESCALATED/SUSPECTED alerts.</p>
              </div>
            )}

            {displayedPatients.length === 0 && sidebarFilter === 'all' && (
              <div className="flex-1 flex flex-col items-center justify-center h-48">
                <div className="w-12 h-12 rounded-2xl bg-slate-50 flex items-center justify-center mb-3">
                  <Activity className="w-6 h-6 text-slate-300 animate-pulse" />
                </div>
                <p className="text-xs font-medium text-slate-400">Awaiting patient feed...</p>
              </div>
            )}
          </div>
        </aside>

        {/* Right Panel: Detail View */}
        <div className="flex-1 overflow-hidden bg-[#F5F6FA] flex flex-col relative z-0">
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

      {/* ── Toast Stack ────────────────────────────────────────────────── */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-3 pointer-events-none">
        {toasts.map(t => (
          <Toast
            key={t.id}
            toast={t}
            onDismiss={dismissToast}
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
    className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[10px] font-bold uppercase tracking-wider transition-all border-b-2 ${
      active
        ? highlight
          ? 'text-violet-700 border-violet-500 bg-violet-50'
          : 'text-slate-700 border-slate-700'
        : 'text-slate-400 border-transparent hover:text-slate-600 hover:bg-slate-50'
    }`}
  >
    {label}
    {count > 0 && (
      <span className={`px-1.5 py-0.5 rounded-full text-[9px] font-bold ${
        highlight && count > 0 ? 'bg-violet-200 text-violet-800' : 'bg-slate-100 text-slate-500'
      }`}>
        {count}
      </span>
    )}
  </button>
);

export default Dashboard;
