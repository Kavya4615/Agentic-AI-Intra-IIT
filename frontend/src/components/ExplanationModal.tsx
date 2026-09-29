import React, { useEffect, useState, useCallback } from 'react';
import {
  X, Brain, FileText, AlertTriangle, Activity, Zap, RefreshCw,
  ShieldAlert, Clock, CheckCircle2, XCircle, PauseCircle, Search,
  ClipboardList, ChevronDown, ChevronUp, User, Beaker, Pill, History,
  ArrowRight,
} from 'lucide-react';
import type { SBARExplanation, AlertRecord, AuditEntry, PatientContext, AlertDecision } from '../types';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

interface ExplanationModalProps {
  patientId: string;
  patientName?: string;
  isOpen: boolean;
  onClose: () => void;
  /** Latest alert_id so decision buttons know which alert to act on */
  latestAlertId?: string;
  /** Current decision so badge shows correct state */
  currentDecision?: AlertDecision | null;
  onDecisionMade?: (decision: AlertDecision) => void;
}

type FetchMode = 'get' | 'trigger';
type ActiveTab = 'sbar' | 'context' | 'audit';

// ── Decision config ───────────────────────────────────────────────────────────

const DECISION_CONFIG = {
  accept: {
    label: 'Accept',
    icon: CheckCircle2,
    color: 'bg-emerald-600 hover:bg-emerald-700 text-white',
    tooltip: 'Acknowledge alert — keep monitoring, mark as reviewed',
  },
  dismiss: {
    label: 'Dismiss',
    icon: XCircle,
    color: 'bg-slate-500 hover:bg-slate-600 text-white',
    tooltip: 'Suppress re-alerting for 30 minutes. Forces state to NORMAL.',
  },
  defer: {
    label: 'Defer 15m',
    icon: PauseCircle,
    color: 'bg-amber-500 hover:bg-amber-600 text-white',
    tooltip: 'Snooze alert for 15 minutes then re-evaluate',
  },
  investigate: {
    label: 'Investigate',
    icon: Search,
    color: 'bg-indigo-600 hover:bg-indigo-700 text-white',
    tooltip: 'Flag for active investigation — no suppression',
  },
} as const;

const DECISION_BADGE: Record<string, { label: string; cls: string }> = {
  accept:      { label: 'Accepted',      cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  dismiss:     { label: 'Dismissed',     cls: 'bg-slate-100 text-slate-600 border-slate-300' },
  defer:       { label: 'Deferred',      cls: 'bg-amber-50 text-amber-700 border-amber-200' },
  investigate: { label: 'Investigating', cls: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
};

// ── Audit event styles ────────────────────────────────────────────────────────

const AUDIT_EVENT_CONFIG: Record<string, { dot: string; label: string; icon: React.FC<{className?: string}> }> = {
  observation: { dot: 'bg-slate-400', label: 'Observation',  icon: Activity },
  retrieval:   { dot: 'bg-blue-500',  label: 'RAG Retrieval', icon: FileText },
  reasoning:   { dot: 'bg-purple-500',label: 'Reasoning',    icon: Brain },
  alert:       { dot: 'bg-red-500',   label: 'Alert Fired',  icon: AlertTriangle },
  decision:    { dot: 'bg-emerald-500',label: 'Decision',    icon: CheckCircle2 },
};

// =============================================================================
//  Main Modal
// =============================================================================

const ExplanationModal: React.FC<ExplanationModalProps> = ({
  patientId, patientName, isOpen, onClose, latestAlertId, currentDecision, onDecisionMade,
}) => {
  const [sbar, setSbar]                         = useState<SBARExplanation | null>(null);
  const [loading, setLoading]                   = useState(false);
  const [error, setError]                       = useState('');
  const [mode, setMode]                         = useState<FetchMode>('get');
  const [generationTime, setGenerationTime]     = useState<string>('');
  const [activeTab, setActiveTab]               = useState<ActiveTab>('sbar');
  const [clinicalCtx, setClinicalCtx]           = useState<PatientContext | null>(null);
  const [ctxLoading, setCtxLoading]             = useState(false);
  const [auditEntries, setAuditEntries]         = useState<AuditEntry[]>([]);
  const [auditLoading, setAuditLoading]         = useState(false);
  const [decisionLoading, setDecisionLoading]   = useState<string | null>(null);
  const [localDecision, setLocalDecision]       = useState<AlertDecision | null>(currentDecision ?? null);
  const [reasonInput, setReasonInput]           = useState('');
  const [showReasonInput, setShowReasonInput]   = useState(false);
  const [pendingDecision, setPendingDecision]   = useState<string | null>(null);
  const [correlationId, setCorrelationId]       = useState<string>('');

  // Sync external decision into local state
  useEffect(() => { setLocalDecision(currentDecision ?? null); }, [currentDecision]);

  // ── SBAR Fetch ──────────────────────────────────────────────────────────────

  const fetchExplanation = useCallback(async (fetchMode: FetchMode = 'get') => {
    setLoading(true);
    setError('');
    setSbar(null);
    setMode(fetchMode);
    try {
      const isTrigger = fetchMode === 'trigger';
      const url = isTrigger
        ? `${API}/api/patients/${patientId}/explanation/trigger`
        : `${API}/api/patients/${patientId}/explanation`;

      const res = await fetch(url, { method: isTrigger ? 'POST' : 'GET' });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail ?? 'Failed to fetch explanation');
      setSbar(data.sbar);
      if (data.correlation_id) setCorrelationId(data.correlation_id);
      setGenerationTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    } catch (err: unknown) {
      setError((err as Error).message ?? 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  // ── Clinical Context Fetch ──────────────────────────────────────────────────

  const fetchContext = useCallback(async () => {
    if (clinicalCtx) return;
    setCtxLoading(true);
    try {
      const res = await fetch(`${API}/api/patients/${patientId}/context`);
      const data = await res.json();
      if (res.ok) setClinicalCtx(data.context);
    } catch (_) { /* ignore */ }
    finally { setCtxLoading(false); }
  }, [patientId, clinicalCtx]);

  // ── Audit Trail Fetch ───────────────────────────────────────────────────────

  const fetchAudit = useCallback(async () => {
    setAuditLoading(true);
    try {
      // If we have a correlation_id, fetch the episode chain; else per-patient
      const url = correlationId
        ? `${API}/api/audit/${correlationId}`
        : `${API}/api/patients/${patientId}/audit?limit=30`;
      const res = await fetch(url);
      const data = await res.json();
      if (res.ok) {
        setAuditEntries(data.entries ?? []);
      }
    } catch (_) { /* ignore */ }
    finally { setAuditLoading(false); }
  }, [patientId, correlationId]);

  useEffect(() => {
    if (isOpen && patientId) {
      fetchExplanation('get');
      setLocalDecision(currentDecision ?? null);
    } else {
      setSbar(null);
      setError('');
      setClinicalCtx(null);
      setAuditEntries([]);
      setActiveTab('sbar');
    }
  }, [isOpen, patientId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (isOpen && activeTab === 'context') fetchContext();
    if (isOpen && activeTab === 'audit') fetchAudit();
  }, [activeTab, isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Clinician Decision ──────────────────────────────────────────────────────

  const submitDecision = async (decisionType: string, reason?: string) => {
    if (!latestAlertId) return;
    setDecisionLoading(decisionType);
    try {
      const res = await fetch(`${API}/api/patients/${patientId}/alerts/${encodeURIComponent(latestAlertId)}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision: decisionType,
          clinician_id: 'Dr. Clinician',
          reason: reason ?? null,
        }),
      });
      const data = await res.json();
      if (res.ok && data.decision) {
        setLocalDecision(data.decision);
        onDecisionMade?.(data.decision);
        setShowReasonInput(false);
        setReasonInput('');
        setPendingDecision(null);
      }
    } catch (_) { /* ignore */ }
    finally { setDecisionLoading(null); }
  };

  const handleDecisionClick = (type: string) => {
    if (type === 'dismiss' || type === 'defer') {
      setPendingDecision(type);
      setShowReasonInput(true);
    } else {
      submitDecision(type);
    }
  };

  if (!isOpen) return null;

  const tabs: { id: ActiveTab; label: string; icon: React.FC<{className?: string}> }[] = [
    { id: 'sbar', label: 'SBAR Report', icon: Brain },
    { id: 'context', label: 'Patient Context', icon: User },
    { id: 'audit', label: 'Audit Trail', icon: History },
  ];

  return (
    <div
      id="explanation-modal-overlay"
      className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4 lg:p-8 animate-fade-in-up"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white w-full max-w-4xl max-h-[92vh] overflow-hidden shadow-2xl flex flex-col rounded-2xl border border-slate-200">

        {/* ── Header ──────────────────────────────────────────────────────── */}
        <div className="flex justify-between items-start px-6 py-4 border-b border-slate-100 flex-shrink-0">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="w-9 h-9 rounded-xl bg-indigo-100 flex items-center justify-center">
                <Brain className="w-5 h-5 text-indigo-600" />
              </div>
              <div>
                <h2 className="text-lg font-extrabold text-slate-800">AI SBAR Analysis</h2>
                {patientName && <p className="text-xs text-slate-400">{patientName}</p>}
              </div>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-400 mt-1 ml-12">
              <span className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-50 rounded-lg border border-slate-100 text-slate-500 font-mono">
                MRN: <span className="font-bold text-slate-700">{patientId}</span>
              </span>
              {generationTime && (
                <span className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" /> Generated at {generationTime}
                </span>
              )}
              {/* Current decision badge */}
              {localDecision && (() => {
                const badge = DECISION_BADGE[localDecision.decision];
                return badge ? (
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${badge.cls}`}>
                    {badge.label}
                  </span>
                ) : null;
              })()}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {sbar && (
              <button
                id="refresh-explanation-btn"
                title="Re-generate"
                onClick={() => fetchExplanation('trigger')}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl text-xs font-bold text-slate-600 transition"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Re-run
              </button>
            )}
            <button
              id="close-modal-btn"
              onClick={onClose}
              className="p-2 hover:bg-slate-100 rounded-xl text-slate-400 hover:text-slate-700 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* ── Clinician Verification Banner ────────────────────────────────── */}
        <div className="bg-amber-50 border-b border-amber-200 px-6 py-2 flex items-start gap-3 flex-shrink-0">
          <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-800 leading-relaxed font-medium">
            <span className="font-bold uppercase tracking-wider mr-1">Clinician Verification Required:</span>
            AI-generated support tool only. Does not replace clinical judgment.
          </p>
        </div>

        {/* ── Tabs ─────────────────────────────────────────────────────────── */}
        <div className="flex border-b border-slate-100 px-6 flex-shrink-0 bg-white">
          {tabs.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                id={`modal-tab-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-xs font-bold transition-all border-b-2 mr-1 ${
                  activeTab === tab.id
                    ? 'border-indigo-500 text-indigo-700'
                    : 'border-transparent text-slate-400 hover:text-slate-600 hover:border-slate-200'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* ── Content ──────────────────────────────────────────────────────── */}
        <div className="p-6 flex-1 overflow-y-auto bg-slate-50/50">

          {/* ── Tab: SBAR Report ─────────────────────────────────────────── */}
          {activeTab === 'sbar' && (
            <>
              {loading ? (
                <div className="flex flex-col items-center justify-center py-20 gap-5">
                  <div className="relative">
                    <div className="w-14 h-14 border-4 border-slate-200 border-t-indigo-500 rounded-full animate-spin" />
                    <Brain className="w-5 h-5 text-slate-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                  </div>
                  <p className="text-sm font-bold text-slate-600">
                    {mode === 'trigger' ? 'Synthesising Clinical Context...' : 'Retrieving Assessment...'}
                  </p>
                  <p className="text-xs text-slate-400">Running RAG protocol + context checks</p>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center gap-5 max-w-sm mx-auto text-center py-14">
                  <div className="w-14 h-14 rounded-2xl bg-red-50 border border-red-200 flex items-center justify-center">
                    <AlertTriangle className="w-7 h-7 text-red-500" />
                  </div>
                  <div>
                    <p className="text-base font-bold text-slate-700 mb-1">No Analysis Available</p>
                    <p className="text-sm text-slate-400 mb-5">{error}</p>
                    <button
                      id="generate-sbar-btn"
                      onClick={() => fetchExplanation('trigger')}
                      className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold text-sm shadow-sm transition-all active:scale-95"
                    >
                      <Zap className="w-4 h-4" />
                      Generate Report
                    </button>
                  </div>
                </div>
              ) : sbar ? (
                <div className="grid gap-4 animate-fade-in-up">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <SbarSection letter="S" title="Situation" content={sbar.situation} color="#EF4444" bg="bg-red-50" />
                    <SbarSection letter="B" title="Background" content={sbar.background} color="#3B82F6" bg="bg-blue-50" />
                  </div>
                  <SbarSection letter="A" title="Assessment" content={sbar.assessment} color="#F97316" bg="bg-orange-50" />
                  <SbarSection letter="R" title="Recommendation" content={sbar.recommendation} color="#10B981" bg="bg-emerald-50" />

                  {sbar.retrieved_protocols?.length > 0 && (
                    <div className="mt-2 pt-4 border-t border-slate-200">
                      <h4 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3 flex items-center gap-2">
                        <FileText className="w-4 h-4" /> Supporting Clinical Guidelines
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {sbar.retrieved_protocols.map((protocol, i) => (
                          <span
                            key={i}
                            className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-600 font-mono font-medium flex items-center gap-1.5 shadow-sm"
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
                            {protocol}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* ── Phase 10: Decision Actions ─────────────────────────── */}
                  {latestAlertId && (
                    <DecisionPanel
                      localDecision={localDecision}
                      decisionLoading={decisionLoading}
                      showReasonInput={showReasonInput}
                      pendingDecision={pendingDecision}
                      reasonInput={reasonInput}
                      onDecisionClick={handleDecisionClick}
                      onConfirmDecision={(reason) => pendingDecision && submitDecision(pendingDecision, reason)}
                      onCancelDecision={() => { setShowReasonInput(false); setPendingDecision(null); }}
                      onReasonChange={setReasonInput}
                    />
                  )}
                </div>
              ) : null}
            </>
          )}

          {/* ── Tab: Patient Context ──────────────────────────────────────── */}
          {activeTab === 'context' && (
            <ContextTab context={clinicalCtx} loading={ctxLoading} />
          )}

          {/* ── Tab: Audit Trail ─────────────────────────────────────────── */}
          {activeTab === 'audit' && (
            <AuditTab
              entries={auditEntries}
              loading={auditLoading}
              correlationId={correlationId}
              onRefresh={fetchAudit}
            />
          )}
        </div>
      </div>
    </div>
  );
};

// =============================================================================
//  Sub-components
// =============================================================================

const SbarSection = ({
  letter, title, content, color, bg,
}: {
  letter: string; title: string; content: string; color: string; bg: string;
}) => (
  <div className={`widget-card ${bg} border-none`}>
    <div className="flex items-center gap-3 mb-3 pb-3 border-b border-slate-200/50">
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center font-extrabold text-base text-white"
        style={{ backgroundColor: color }}
      >
        {letter}
      </div>
      <h3 className="font-bold text-slate-700 uppercase tracking-widest text-sm">{title}</h3>
    </div>
    <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">{content}</p>
  </div>
);

// ── Decision Panel (Phase 10) ─────────────────────────────────────────────────

const DecisionPanel: React.FC<{
  localDecision: AlertDecision | null;
  decisionLoading: string | null;
  showReasonInput: boolean;
  pendingDecision: string | null;
  reasonInput: string;
  onDecisionClick: (type: string) => void;
  onConfirmDecision: (reason: string) => void;
  onCancelDecision: () => void;
  onReasonChange: (val: string) => void;
}> = ({
  localDecision, decisionLoading, showReasonInput, pendingDecision, reasonInput,
  onDecisionClick, onConfirmDecision, onCancelDecision, onReasonChange,
}) => (
  <div className="mt-2 pt-4 border-t border-slate-200">
    <h4 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3 flex items-center gap-2">
      <ClipboardList className="w-4 h-4" /> Clinician Action
    </h4>

    {localDecision ? (
      <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${DECISION_BADGE[localDecision.decision]?.cls ?? 'bg-slate-50 border-slate-200'}`}>
        <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-bold capitalize">{localDecision.decision} by {localDecision.clinician_id}</p>
          {localDecision.reason && <p className="text-xs mt-0.5 opacity-75">{localDecision.reason}</p>}
          {localDecision.defer_remaining_seconds !== undefined && localDecision.defer_remaining_seconds > 0 && (
            <p className="text-xs mt-0.5 opacity-75">
              Re-evaluates in {Math.ceil(localDecision.defer_remaining_seconds / 60)}m
            </p>
          )}
        </div>
      </div>
    ) : (
      <>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {(Object.keys(DECISION_CONFIG) as (keyof typeof DECISION_CONFIG)[]).map(type => {
            const cfg = DECISION_CONFIG[type];
            const Icon = cfg.icon;
            const isLoading = decisionLoading === type;
            return (
              <button
                key={type}
                id={`decision-btn-${type}`}
                title={cfg.tooltip}
                disabled={!!decisionLoading}
                onClick={() => onDecisionClick(type)}
                className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-xs font-bold transition-all active:scale-95 disabled:opacity-50 ${cfg.color}`}
              >
                {isLoading ? (
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <Icon className="w-4 h-4" />
                )}
                {cfg.label}
              </button>
            );
          })}
        </div>

        {showReasonInput && pendingDecision && (
          <div className="mt-3 p-4 bg-slate-50 rounded-xl border border-slate-200 animate-fade-in-up">
            <p className="text-xs font-bold text-slate-600 mb-2 capitalize">
              Confirm {pendingDecision}:
            </p>
            <textarea
              value={reasonInput}
              onChange={e => onReasonChange(e.target.value)}
              placeholder="Optional: add a clinical note or reason..."
              className="w-full text-xs p-2.5 border border-slate-200 rounded-lg resize-none h-16 focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white"
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={() => onConfirmDecision(reasonInput)}
                className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg transition"
              >
                Confirm
              </button>
              <button
                onClick={onCancelDecision}
                className="flex-1 py-2 bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-bold rounded-lg transition"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </>
    )}
  </div>
);

// ── Context Tab (Phase 9) ─────────────────────────────────────────────────────

const ContextTab: React.FC<{ context: PatientContext | null; loading: boolean }> = ({ context, loading }) => {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="w-10 h-10 border-4 border-slate-200 border-t-indigo-500 rounded-full animate-spin" />
        <p className="text-sm text-slate-400">Loading patient context...</p>
      </div>
    );
  }
  if (!context) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3 text-slate-400">
        <User className="w-10 h-10" />
        <p className="text-sm">No clinical context available.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 animate-fade-in-up">
      {/* Demographics */}
      <div className="widget-card bg-slate-50 border-none">
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-200/50">
          <User className="w-4 h-4 text-slate-500" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Demographics</h3>
        </div>
        <p className="text-sm text-slate-700 font-medium">{context.age} years old · {context.sex}</p>
      </div>

      {/* History */}
      <div className="widget-card bg-blue-50 border-none">
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-blue-200/50">
          <ClipboardList className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-blue-600">Medical History</h3>
        </div>
        <ul className="space-y-1">
          {context.relevant_history.map((h, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
              <ArrowRight className="w-3.5 h-3.5 text-blue-400 mt-0.5 flex-shrink-0" />
              {h}
            </li>
          ))}
        </ul>
      </div>

      {/* Medications */}
      <div className="widget-card bg-purple-50 border-none">
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-purple-200/50">
          <Pill className="w-4 h-4 text-purple-600" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-purple-600">Current Medications</h3>
        </div>
        <ul className="space-y-1">
          {context.current_medications.map((m, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
              <ArrowRight className="w-3.5 h-3.5 text-purple-400 mt-0.5 flex-shrink-0" />
              {m}
            </li>
          ))}
        </ul>
      </div>

      {/* Labs */}
      <div className="widget-card bg-amber-50 border-none">
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-amber-200/50">
          <Beaker className="w-4 h-4 text-amber-600" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-amber-600">Recent Labs</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1.5">
          {Object.entries(context.recent_labs).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-2">
              <span className="text-xs font-bold text-slate-500 font-mono">{k}</span>
              <span className={`text-xs font-medium ${v.includes('(H') ? 'text-red-600 font-bold' : v.includes('(L') ? 'text-blue-600 font-bold' : 'text-slate-700'}`}>
                {v}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ── Audit Trail Tab (Phase 11) ────────────────────────────────────────────────

const AuditTab: React.FC<{
  entries: AuditEntry[];
  loading: boolean;
  correlationId: string;
  onRefresh: () => void;
}> = ({ entries, loading, correlationId, onRefresh }) => {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="w-10 h-10 border-4 border-slate-200 border-t-indigo-500 rounded-full animate-spin" />
        <p className="text-sm text-slate-400">Loading audit trail...</p>
      </div>
    );
  }
  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4 text-slate-400">
        <History className="w-10 h-10" />
        <p className="text-sm">No audit entries yet. Trigger an SBAR to generate a full episode chain.</p>
        <button
          onClick={onRefresh}
          className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-bold rounded-lg transition"
        >
          Refresh
        </button>
      </div>
    );
  }

  return (
    <div className="animate-fade-in-up">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-700">Escalation Audit Chain</h3>
          {correlationId && (
            <p className="text-[10px] font-mono text-slate-400 mt-0.5">
              Episode: {correlationId.substring(0, 12)}...
            </p>
          )}
        </div>
        <button
          onClick={onRefresh}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-bold text-slate-500 transition"
        >
          <RefreshCw className="w-3 h-3" /> Refresh
        </button>
      </div>

      {/* Timeline */}
      <div className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-slate-100" />
        <div className="space-y-4">
          {entries.map((entry, idx) => {
            const cfg = AUDIT_EVENT_CONFIG[entry.event_type] ?? { dot: 'bg-slate-300', label: entry.event_type, icon: Activity };
            const Icon = cfg.icon;
            const time = new Date(entry.timestamp_iso).toLocaleTimeString([], {
              hour: '2-digit', minute: '2-digit', second: '2-digit'
            });
            return (
              <div key={entry.id} className="flex gap-4 relative">
                <div className={`w-8 h-8 rounded-full ${cfg.dot} flex items-center justify-center flex-shrink-0 z-10 ring-4 ring-white shadow-sm`}>
                  <Icon className="w-3.5 h-3.5 text-white" />
                </div>
                <div className="flex-1 min-w-0 pb-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-700">{cfg.label}</span>
                    <span className="text-[10px] font-mono text-slate-400 flex-shrink-0">{time}</span>
                  </div>
                  <AuditPayload payload={entry.payload} eventType={entry.event_type} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

const AuditPayload: React.FC<{ payload: Record<string, unknown>; eventType: string }> = ({ payload, eventType }) => {
  const [expanded, setExpanded] = useState(false);

  let summary = '';
  if (eventType === 'observation') {
    const v = payload.vitals as Record<string, number> | undefined;
    if (v) {
      summary = `HR:${v.heart_rate?.toFixed(0)} SpO2:${v.spo2?.toFixed(0)}% Risk:${(payload.risk_score as number)?.toFixed(0)}`;
    }
  } else if (eventType === 'alert') {
    summary = `${payload.from_level} → ${payload.to_level} (risk ${(payload.risk_score as number)?.toFixed(0)})`;
  } else if (eventType === 'retrieval') {
    const protocols = (payload.retrieved as { protocol_names?: string[] })?.protocol_names ?? [];
    summary = `Protocols: ${protocols.join(', ') || 'none'}`;
  } else if (eventType === 'reasoning') {
    const sbar = payload.sbar as { situation?: string } | undefined;
    summary = sbar?.situation?.substring(0, 80) + '...' ?? '';
  } else if (eventType === 'decision') {
    summary = `${payload.decision} by ${payload.clinician_id}`;
  }

  return (
    <div className="mt-1">
      {summary && (
        <p className="text-xs text-slate-500 leading-relaxed">{summary}</p>
      )}
      <button
        onClick={() => setExpanded(e => !e)}
        className="flex items-center gap-1 mt-1 text-[10px] text-indigo-400 hover:text-indigo-600 font-medium"
      >
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {expanded ? 'Hide' : 'Show'} raw payload
      </button>
      {expanded && (
        <pre className="mt-2 text-[10px] bg-slate-800 text-slate-200 rounded-lg p-3 overflow-x-auto max-h-32">
          {JSON.stringify(payload, null, 2)}
        </pre>
      )}
    </div>
  );
};

export default ExplanationModal;
