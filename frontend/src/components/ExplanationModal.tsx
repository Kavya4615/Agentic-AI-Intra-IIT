import React, { useEffect, useState, useCallback } from 'react';
import {
  X, Brain, FileText, AlertTriangle, Activity, Zap, RefreshCw,
  ShieldAlert, Clock, CheckCircle2, XCircle, PauseCircle, Search,
  ClipboardList, ChevronDown, ChevronUp, User, Beaker, Pill, History,
  ArrowRight,
} from 'lucide-react';
import type { SBARExplanation, AuditEntry, PatientContext, AlertDecision } from '../types';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

interface ExplanationModalProps {
  patientId: string;
  patientName?: string;
  isOpen: boolean;
  onClose: () => void;
  latestAlertId?: string;
  currentDecision?: AlertDecision | null;
  onDecisionMade?: (decision: AlertDecision) => void;
}

type FetchMode = 'get' | 'trigger';
type ActiveTab = 'sbar' | 'context' | 'audit';

const DECISION_CONFIG = {
  accept: {
    label: 'Accept', icon: CheckCircle2,
    color: '#10B981', bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.35)',
    tooltip: 'Acknowledge alert — keep monitoring, mark as reviewed',
  },
  dismiss: {
    label: 'Dismiss', icon: XCircle,
    color: '#64748B', bg: 'rgba(100,116,139,0.12)', border: 'rgba(100,116,139,0.3)',
    tooltip: 'Suppress re-alerting for 30 minutes. Forces state to NORMAL.',
  },
  defer: {
    label: 'Defer 15m', icon: PauseCircle,
    color: '#F59E0B', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.35)',
    tooltip: 'Snooze alert for 15 minutes then re-evaluate',
  },
  investigate: {
    label: 'Investigate', icon: Search,
    color: '#6366F1', bg: 'rgba(99,102,241,0.15)', border: 'rgba(99,102,241,0.4)',
    tooltip: 'Flag for active investigation — no suppression',
  },
} as const;

const DECISION_BADGE: Record<string, { label: string; color: string; bg: string; border: string }> = {
  accept:      { label: 'Accepted',      color: '#2DD4BF', bg: 'rgba(20,184,166,0.1)',  border: 'rgba(20,184,166,0.3)' },
  dismiss:     { label: 'Dismissed',     color: '#94A3B8', bg: 'rgba(148,163,184,0.1)', border: 'rgba(148,163,184,0.25)' },
  defer:       { label: 'Deferred',      color: '#FCD34D', bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.3)' },
  investigate: { label: 'Investigating', color: '#A5B4FC', bg: 'rgba(99,102,241,0.12)', border: 'rgba(99,102,241,0.3)' },
};

const AUDIT_EVENT_CONFIG: Record<string, { dot: string; label: string; icon: React.FC<{className?: string}> }> = {
  observation: { dot: '#475569', label: 'Observation',   icon: Activity },
  retrieval:   { dot: '#3B82F6', label: 'RAG Retrieval', icon: FileText },
  reasoning:   { dot: '#8B5CF6', label: 'Reasoning',     icon: Brain },
  alert:       { dot: '#EF4444', label: 'Alert Fired',   icon: AlertTriangle },
  decision:    { dot: '#10B981', label: 'Decision',      icon: CheckCircle2 },
};

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

  useEffect(() => { setLocalDecision(currentDecision ?? null); }, [currentDecision]);

  const fetchExplanation = useCallback(async (fetchMode: FetchMode = 'get') => {
    setLoading(true); setError(''); setSbar(null); setMode(fetchMode);
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
    } finally { setLoading(false); }
  }, [patientId]);

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

  const fetchAudit = useCallback(async () => {
    setAuditLoading(true);
    try {
      const url = correlationId
        ? `${API}/api/audit/${correlationId}`
        : `${API}/api/patients/${patientId}/audit?limit=30`;
      const res = await fetch(url);
      const data = await res.json();
      if (res.ok) setAuditEntries(data.entries ?? []);
    } catch (_) { /* ignore */ }
    finally { setAuditLoading(false); }
  }, [patientId, correlationId]);

  useEffect(() => {
    if (isOpen && patientId) {
      fetchExplanation('get');
      setLocalDecision(currentDecision ?? null);
    } else {
      setSbar(null); setError(''); setClinicalCtx(null);
      setAuditEntries([]); setActiveTab('sbar');
    }
  }, [isOpen, patientId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (isOpen && activeTab === 'context') fetchContext();
    if (isOpen && activeTab === 'audit') fetchAudit();
  }, [activeTab, isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  const submitDecision = async (decisionType: string, reason?: string) => {
    if (!latestAlertId) return;
    setDecisionLoading(decisionType);
    try {
      const res = await fetch(`${API}/api/patients/${patientId}/alerts/${encodeURIComponent(latestAlertId)}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: decisionType, clinician_id: 'Dr. Clinician', reason: reason ?? null }),
      });
      const data = await res.json();
      if (res.ok && data.decision) {
        setLocalDecision(data.decision);
        onDecisionMade?.(data.decision);
        setShowReasonInput(false); setReasonInput(''); setPendingDecision(null);
      }
    } catch (_) { /* ignore */ }
    finally { setDecisionLoading(null); }
  };

  const handleDecisionClick = (type: string) => {
    if (type === 'dismiss' || type === 'defer') {
      setPendingDecision(type); setShowReasonInput(true);
    } else { submitDecision(type); }
  };

  if (!isOpen) return null;

  const tabs: { id: ActiveTab; label: string; icon: React.FC<{className?: string}> }[] = [
    { id: 'sbar',    label: 'SBAR Report',     icon: Brain },
    { id: 'context', label: 'Patient Context', icon: User },
    { id: 'audit',   label: 'Audit Trail',     icon: History },
  ];

  return (
    <div
      id="explanation-modal-overlay"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 lg:p-8 animate-fade-in-up"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(12px)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-4xl max-h-[92vh] overflow-hidden flex flex-col rounded-2xl"
        style={{
          background: 'rgba(6,13,24,0.97)',
          border: '1px solid rgba(99,102,241,0.25)',
          boxShadow: '0 40px 80px rgba(0,0,0,0.8), 0 0 60px rgba(99,102,241,0.1)',
          backdropFilter: 'blur(24px)',
        }}>

        {/* ── Header ──────────────────────────────────────────────────────── */}
        <div className="flex justify-between items-start px-6 py-4 flex-shrink-0"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                style={{
                  background: 'linear-gradient(135deg, rgba(99,102,241,0.3), rgba(139,92,246,0.2))',
                  border: '1px solid rgba(99,102,241,0.4)',
                  boxShadow: '0 0 20px rgba(99,102,241,0.3)',
                }}>
                <Brain className="w-5 h-5" style={{ color: '#818CF8' }} />
              </div>
              <div>
                <h2 className="text-lg font-black" style={{ color: 'var(--text-bright)' }}>AI SBAR Analysis</h2>
                {patientName && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{patientName}</p>}
              </div>
            </div>
            <div className="flex items-center gap-3 text-xs mt-1 ml-13"
              style={{ color: 'var(--text-muted)', marginLeft: '3.25rem' }}>
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-mono"
                style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', color: 'var(--text-secondary)' }}>
                MRN: <span className="font-bold" style={{ color: 'var(--text-primary)' }}>{patientId}</span>
              </span>
              {generationTime && (
                <span className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" /> Generated {generationTime}
                </span>
              )}
              {localDecision && (() => {
                const badge = DECISION_BADGE[localDecision.decision];
                return badge ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-black"
                    style={{ background: badge.bg, border: `1px solid ${badge.border}`, color: badge.color }}>
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
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition"
                style={{
                  background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.25)',
                  color: '#A5B4FC',
                }}
              >
                <RefreshCw className="w-3.5 h-3.5" /> Re-run
              </button>
            )}
            <button
              id="close-modal-btn"
              onClick={onClose}
              className="p-2 rounded-xl transition"
              style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--text-muted)' }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.04)')}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* ── Clinician Verification Banner ──────────────────────────────── */}
        <div className="px-6 py-2.5 flex items-start gap-3 flex-shrink-0"
          style={{ background: 'rgba(245,158,11,0.06)', borderBottom: '1px solid rgba(245,158,11,0.15)' }}>
          <ShieldAlert className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: '#F59E0B' }} />
          <p className="text-xs leading-relaxed font-medium" style={{ color: 'rgba(245,158,11,0.9)' }}>
            <span className="font-black uppercase tracking-wider mr-1">Clinician Verification Required:</span>
            AI-generated support tool only. Does not replace clinical judgment.
          </p>
        </div>

        {/* ── Tabs ─────────────────────────────────────────────────────────── */}
        <div className="flex px-6 flex-shrink-0"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(6,13,24,0.5)' }}>
          {tabs.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                id={`modal-tab-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className="flex items-center gap-2 px-4 py-3 text-xs font-bold transition-all border-b-2 mr-1"
                style={activeTab === tab.id
                  ? { borderColor: '#6366F1', color: '#818CF8' }
                  : { borderColor: 'transparent', color: 'var(--text-muted)' }
                }
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* ── Content ──────────────────────────────────────────────────────── */}
        <div className="p-6 flex-1 overflow-y-auto" style={{ background: 'rgba(6,13,24,0.7)' }}>

          {/* ── SBAR Tab ─────────────────────────────────────────────────── */}
          {activeTab === 'sbar' && (
            <>
              {loading ? (
                <div className="flex flex-col items-center justify-center py-20 gap-6">
                  <div className="relative">
                    <div className="w-16 h-16 border-2 rounded-full animate-spin"
                      style={{ borderColor: 'rgba(99,102,241,0.2)', borderTopColor: '#6366F1' }} />
                    <Brain className="w-6 h-6 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
                      style={{ color: '#818CF8' }} />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                      {mode === 'trigger' ? 'Synthesising Clinical Context...' : 'Retrieving Assessment...'}
                    </p>
                    <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                      Running RAG protocol + context analysis
                    </p>
                  </div>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center gap-5 max-w-sm mx-auto text-center py-14">
                  <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
                    style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)' }}>
                    <AlertTriangle className="w-7 h-7" style={{ color: '#EF4444' }} />
                  </div>
                  <div>
                    <p className="text-base font-bold mb-1" style={{ color: 'var(--text-primary)' }}>No Analysis Available</p>
                    <p className="text-sm mb-5" style={{ color: 'var(--text-muted)' }}>{error}</p>
                    <button
                      id="generate-sbar-btn"
                      onClick={() => fetchExplanation('trigger')}
                      className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm transition-all"
                      style={{
                        background: 'linear-gradient(135deg, rgba(99,102,241,0.4), rgba(139,92,246,0.3))',
                        border: '1px solid rgba(99,102,241,0.5)',
                        color: '#E0E7FF',
                        boxShadow: '0 0 20px rgba(99,102,241,0.3)',
                      }}
                    >
                      <Zap className="w-4 h-4" />
                      Generate Report
                    </button>
                  </div>
                </div>
              ) : sbar ? (
                <div className="grid gap-4 animate-fade-in-up">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <SbarSection letter="S" title="Situation"   content={sbar.situation}   color="#EF4444" glow="rgba(239,68,68,0.2)"    bg="rgba(239,68,68,0.05)"   border="rgba(239,68,68,0.15)" />
                    <SbarSection letter="B" title="Background"  content={sbar.background}  color="#3B82F6" glow="rgba(59,130,246,0.2)"   bg="rgba(59,130,246,0.05)"  border="rgba(59,130,246,0.15)" />
                  </div>
                  <SbarSection letter="A" title="Assessment"     content={sbar.assessment}     color="#F97316" glow="rgba(249,115,22,0.2)"  bg="rgba(249,115,22,0.05)"  border="rgba(249,115,22,0.15)" />
                  <SbarSection letter="R" title="Recommendation" content={sbar.recommendation} color="#10B981" glow="rgba(16,185,129,0.2)"  bg="rgba(16,185,129,0.05)"  border="rgba(16,185,129,0.15)" />

                  {sbar.retrieved_protocols?.length > 0 && (
                    <div className="mt-2 pt-4" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                      <h4 className="text-xs font-black uppercase tracking-widest mb-3 flex items-center gap-2"
                        style={{ color: 'var(--text-muted)' }}>
                        <FileText className="w-4 h-4" style={{ color: '#818CF8' }} />
                        Supporting Clinical Guidelines
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {sbar.retrieved_protocols.map((protocol, i) => (
                          <span key={i}
                            className="px-3 py-1.5 rounded-lg text-xs font-mono font-medium flex items-center gap-1.5"
                            style={{
                              background: 'rgba(99,102,241,0.08)',
                              border: '1px solid rgba(99,102,241,0.2)',
                              color: '#A5B4FC',
                            }}>
                            <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#6366F1', boxShadow: '0 0 4px rgba(99,102,241,0.5)' }} />
                            {protocol}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

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

          {activeTab === 'context' && <ContextTab context={clinicalCtx} loading={ctxLoading} />}
          {activeTab === 'audit' && (
            <AuditTab entries={auditEntries} loading={auditLoading} correlationId={correlationId} onRefresh={fetchAudit} />
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
  letter, title, content, color, glow, bg, border,
}: {
  letter: string; title: string; content: string;
  color: string; glow: string; bg: string; border: string;
}) => (
  <div className="rounded-2xl p-5"
    style={{ background: bg, border: `1px solid ${border}`, boxShadow: `0 0 20px ${glow}` }}>
    <div className="flex items-center gap-3 mb-4 pb-3"
      style={{ borderBottom: `1px solid ${border}` }}>
      <div className="w-9 h-9 rounded-xl flex items-center justify-center font-black text-base text-white"
        style={{ background: `linear-gradient(135deg, ${color}, ${color}99)`, boxShadow: `0 0 16px ${glow}` }}>
        {letter}
      </div>
      <h3 className="font-black uppercase tracking-widest text-sm" style={{ color }}>{title}</h3>
    </div>
    <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>{content}</p>
  </div>
);

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
  <div className="mt-2 pt-5" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
    <h4 className="text-xs font-black uppercase tracking-widest mb-4 flex items-center gap-2"
      style={{ color: 'var(--text-muted)' }}>
      <ClipboardList className="w-4 h-4" style={{ color: '#818CF8' }} />
      Clinician Action
    </h4>

    {localDecision ? (
      (() => {
        const badge = DECISION_BADGE[localDecision.decision];
        return (
          <div className="flex items-center gap-3 px-5 py-4 rounded-2xl"
            style={{ background: badge?.bg ?? 'rgba(255,255,255,0.04)', border: `1px solid ${badge?.border ?? 'rgba(255,255,255,0.08)'}` }}>
            <CheckCircle2 className="w-5 h-5 flex-shrink-0" style={{ color: badge?.color }} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-black capitalize" style={{ color: badge?.color }}>
                {localDecision.decision} by {localDecision.clinician_id}
              </p>
              {localDecision.reason && (
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{localDecision.reason}</p>
              )}
              {localDecision.defer_remaining_seconds !== undefined && localDecision.defer_remaining_seconds > 0 && (
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                  Re-evaluates in {Math.ceil(localDecision.defer_remaining_seconds / 60)}m
                </p>
              )}
            </div>
          </div>
        );
      })()
    ) : (
      <>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {(Object.keys(DECISION_CONFIG) as (keyof typeof DECISION_CONFIG)[]).map(type => {
            const cfg = DECISION_CONFIG[type];
            const Icon = cfg.icon;
            const isLoadingThis = decisionLoading === type;
            return (
              <button
                key={type}
                id={`decision-btn-${type}`}
                title={cfg.tooltip}
                disabled={!!decisionLoading}
                onClick={() => onDecisionClick(type)}
                className="flex items-center justify-center gap-2 px-3 py-3 rounded-xl text-xs font-black transition-all"
                style={{ background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.boxShadow = `0 0 16px ${cfg.border}`; }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.boxShadow = 'none'; }}
              >
                {isLoadingThis ? (
                  <span className="w-4 h-4 border-2 rounded-full animate-spin"
                    style={{ borderColor: `${cfg.color}40`, borderTopColor: cfg.color }} />
                ) : (
                  <Icon className="w-4 h-4" />
                )}
                {cfg.label}
              </button>
            );
          })}
        </div>

        {showReasonInput && pendingDecision && (
          <div className="mt-4 p-4 rounded-xl animate-fade-in-up"
            style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.2)' }}>
            <p className="text-xs font-black mb-2 capitalize" style={{ color: '#A5B4FC' }}>
              Confirm {pendingDecision}:
            </p>
            <textarea
              value={reasonInput}
              onChange={e => onReasonChange(e.target.value)}
              placeholder="Optional: add a clinical note or reason..."
              className="w-full text-xs p-3 rounded-lg resize-none h-16 focus:outline-none"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(99,102,241,0.25)',
                color: 'var(--text-primary)',
              }}
            />
            <div className="flex gap-2 mt-2">
              <button onClick={() => onConfirmDecision(reasonInput)}
                className="flex-1 py-2 rounded-lg text-xs font-black transition"
                style={{ background: 'rgba(99,102,241,0.3)', border: '1px solid rgba(99,102,241,0.5)', color: '#E0E7FF' }}>
                Confirm
              </button>
              <button onClick={onCancelDecision}
                className="flex-1 py-2 rounded-lg text-xs font-black transition"
                style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-muted)' }}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </>
    )}
  </div>
);

const ContextTab: React.FC<{ context: PatientContext | null; loading: boolean }> = ({ context, loading }) => {
  if (loading) return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <div className="w-10 h-10 border-2 rounded-full animate-spin"
        style={{ borderColor: 'rgba(99,102,241,0.2)', borderTopColor: '#6366F1' }} />
      <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading patient context...</p>
    </div>
  );
  if (!context) return (
    <div className="flex flex-col items-center justify-center py-16 gap-3" style={{ color: 'var(--text-muted)' }}>
      <User className="w-10 h-10" />
      <p className="text-sm">No clinical context available.</p>
    </div>
  );

  const sections = [
    {
      title: 'Demographics', icon: User, color: '#94A3B8', bg: 'rgba(148,163,184,0.06)', border: 'rgba(148,163,184,0.15)',
      content: <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{context.age} years old · {context.sex}</p>,
    },
    {
      title: 'Medical History', icon: ClipboardList, color: '#3B82F6', bg: 'rgba(59,130,246,0.06)', border: 'rgba(59,130,246,0.15)',
      content: (
        <ul className="space-y-1.5">
          {context.relevant_history.map((h, i) => (
            <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <ArrowRight className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" style={{ color: '#3B82F6' }} /> {h}
            </li>
          ))}
        </ul>
      ),
    },
    {
      title: 'Current Medications', icon: Pill, color: '#8B5CF6', bg: 'rgba(139,92,246,0.06)', border: 'rgba(139,92,246,0.15)',
      content: (
        <ul className="space-y-1.5">
          {context.current_medications.map((m, i) => (
            <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <ArrowRight className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" style={{ color: '#8B5CF6' }} /> {m}
            </li>
          ))}
        </ul>
      ),
    },
    {
      title: 'Recent Labs', icon: Beaker, color: '#F59E0B', bg: 'rgba(245,158,11,0.06)', border: 'rgba(245,158,11,0.15)',
      content: (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2">
          {Object.entries(context.recent_labs).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-2">
              <span className="text-xs font-bold font-mono" style={{ color: 'var(--text-muted)' }}>{k}</span>
              <span className="text-xs font-semibold"
                style={{ color: v.includes('(H') ? '#F87171' : v.includes('(L') ? '#60A5FA' : 'var(--text-primary)' }}>
                {v}
              </span>
            </div>
          ))}
        </div>
      ),
    },
  ];

  return (
    <div className="grid gap-4 animate-fade-in-up">
      {sections.map(s => (
        <div key={s.title} className="rounded-2xl p-5"
          style={{ background: s.bg, border: `1px solid ${s.border}` }}>
          <div className="flex items-center gap-2 mb-4 pb-3" style={{ borderBottom: `1px solid ${s.border}` }}>
            <s.icon className="w-4 h-4" style={{ color: s.color }} />
            <h3 className="text-xs font-black uppercase tracking-wider" style={{ color: s.color }}>{s.title}</h3>
          </div>
          {s.content}
        </div>
      ))}
    </div>
  );
};

const AuditTab: React.FC<{
  entries: AuditEntry[]; loading: boolean; correlationId: string; onRefresh: () => void;
}> = ({ entries, loading, correlationId, onRefresh }) => {
  if (loading) return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <div className="w-10 h-10 border-2 rounded-full animate-spin"
        style={{ borderColor: 'rgba(99,102,241,0.2)', borderTopColor: '#6366F1' }} />
      <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading audit trail...</p>
    </div>
  );
  if (entries.length === 0) return (
    <div className="flex flex-col items-center justify-center py-16 gap-4" style={{ color: 'var(--text-muted)' }}>
      <History className="w-10 h-10" />
      <p className="text-sm">No audit entries yet. Trigger an SBAR to generate a full episode chain.</p>
      <button onClick={onRefresh}
        className="px-4 py-2 rounded-lg text-xs font-bold transition"
        style={{ background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)', color: '#A5B4FC' }}>
        Refresh
      </button>
    </div>
  );

  return (
    <div className="animate-fade-in-up">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Escalation Audit Chain</h3>
          {correlationId && (
            <p className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-muted)' }}>
              Episode: {correlationId.substring(0, 16)}...
            </p>
          )}
        </div>
        <button onClick={onRefresh}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-muted)' }}>
          <RefreshCw className="w-3 h-3" /> Refresh
        </button>
      </div>

      <div className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-px" style={{ background: 'rgba(99,102,241,0.15)' }} />
        <div className="space-y-5">
          {entries.map((entry) => {
            const cfg = AUDIT_EVENT_CONFIG[entry.event_type] ?? { dot: '#475569', label: entry.event_type, icon: Activity };
            const Icon = cfg.icon;
            const time = new Date(entry.timestamp_iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            return (
              <div key={entry.id} className="flex gap-4 relative">
                <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 z-10"
                  style={{
                    background: `${cfg.dot}20`,
                    border: `2px solid ${cfg.dot}`,
                    boxShadow: `0 0 12px ${cfg.dot}50`,
                    color: cfg.dot,
                  }}>
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1 min-w-0 pb-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>{cfg.label}</span>
                    <span className="text-[10px] font-mono flex-shrink-0" style={{ color: 'var(--text-muted)' }}>{time}</span>
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
    if (v) summary = `HR:${v.heart_rate?.toFixed(0)} SpO2:${v.spo2?.toFixed(0)}% Risk:${(payload.risk_score as number)?.toFixed(0)}`;
  } else if (eventType === 'alert') {
    summary = `${payload.from_level} → ${payload.to_level} (risk ${(payload.risk_score as number)?.toFixed(0)})`;
  } else if (eventType === 'retrieval') {
    const protocols = (payload.retrieved as { protocol_names?: string[] })?.protocol_names ?? [];
    summary = `Protocols: ${protocols.join(', ') || 'none'}`;
  } else if (eventType === 'reasoning') {
    const sbar = payload.sbar as { situation?: string } | undefined;
    summary = sbar?.situation ? `${sbar.situation.substring(0, 80)}...` : '';
  } else if (eventType === 'decision') {
    summary = `${payload.decision} by ${payload.clinician_id}`;
  }

  return (
    <div className="mt-1">
      {summary && <p className="text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>{summary}</p>}
      <button onClick={() => setExpanded(e => !e)}
        className="flex items-center gap-1 mt-1 text-[10px] font-medium transition"
        style={{ color: '#818CF8' }}>
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {expanded ? 'Hide' : 'Show'} raw payload
      </button>
      {expanded && (
        <pre className="mt-2 text-[10px] rounded-xl p-3 overflow-x-auto max-h-32 font-mono"
          style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(99,102,241,0.15)', color: '#94A3B8' }}>
          {JSON.stringify(payload, null, 2)}
        </pre>
      )}
    </div>
  );
};

export default ExplanationModal;
