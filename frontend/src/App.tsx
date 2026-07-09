import { useCallback, useEffect, useMemo, useState, type ChangeEvent, type Dispatch, type ReactNode, type SetStateAction } from 'react';
import { BrowserRouter, Link, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ArrowRight, Ban, CheckCircle2, Flag, Hand, ShieldAlert, ThumbsUp } from 'lucide-react';
import { api } from './api/client';
import { AppShell } from './components/Layout/AppShell';
import { Pagination } from './components/Pagination';
import { RecordsPagination } from './components/RecordsPagination';
import { ConfirmDialog } from './components/ui/ConfirmDialog';
import { ToastProvider, useToast } from './contexts/ToastContext';
import type { CaseDetail, CaseSummary, FeedbackRecord, Metrics, RecordsPage, ReturnRequestPayload, Rule, ScoreResponse } from './types';

const badgeTone = (risk: string) =>
  risk === 'HIGH'
    ? 'bg-red-background text-red-primary ring-1 ring-red-border'
    : risk === 'MEDIUM'
      ? 'bg-blue-96 text-blue-58 ring-1 ring-blue-96'
      : 'bg-green-background text-green-primary ring-1 ring-green-border';

function MetricCard({ label, value, subtext, accent }: { label: string; value: string | number; subtext?: string; accent?: string }) {
  return (
    <div className="border border-slate-200 bg-white rounded-[22px] p-4 sm:p-5 shadow-sm">
      <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500 sm:text-xs">{label}</div>
      <div className={`mt-2 text-2xl font-semibold sm:mt-3 sm:text-3xl ${accent ?? ''}`}>{value}</div>
      {subtext ? <div className="mt-2 text-xs text-slate-600 sm:text-sm">{subtext}</div> : null}
    </div>
  );
}

function PageHeader({ eyebrow, title, subtitle, action }: { eyebrow?: string; title: string; subtitle: string; action?: ReactNode }) {
  return (
    <div className="mb-4 rounded-[24px] border border-slate-200 bg-white/90 px-5 py-4 shadow-sm backdrop-blur-sm sm:px-6 sm:py-5">
      {eyebrow ? <div className="text-[11px] uppercase tracking-[0.28em] text-slate-500">{eyebrow}</div> : null}
      <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-slate-600 sm:text-base">{subtitle}</p>
        </div>
        {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
      </div>
    </div>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="border border-slate-200 bg-white relative overflow-hidden rounded-[22px] p-4 sm:rounded-[24px] sm:p-5 shadow-sm">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-blue-300/60 to-transparent" />
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900 sm:text-lg">{title}</h2>
          {subtitle ? <p className="mt-1 text-xs text-slate-600 sm:text-sm">{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

function SparkBar({ value, max, tone = 'bg-blue-300' }: { value: number; max: number; tone?: string }) {
  const pct = Math.max(6, (value / Math.max(max, 1)) * 100);
  return <div className={`h-full rounded-full ${tone}`} style={{ width: `${pct}%` }} />;
}

function SimpleChart({ data, tone }: { data: Array<{ label: string; value: number }>; tone?: string }) {
  const max = Math.max(...data.map((item) => item.value), 1);
  return (
    <div className="space-y-3">
      {data.map((item) => (
        <div key={item.label} className="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)_4.5rem] items-center gap-3">
          <div className="truncate text-sm text-slate-600">{item.label}</div>
          <div className="h-2 rounded-full bg-slate-50">
            <SparkBar value={item.value} max={max} tone={tone} />
          </div>
          <div className="flex justify-end">
            <span className="rounded-full bg-slate-100 px-2.5 py-1 font-mono text-xs text-slate-700">{item.value}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function buildSampleReturnRequest(kind: 'low' | 'high'): ReturnRequestPayload {
  const now = new Date();
  const deliveryDate = new Date(now.getTime() - (kind === 'high' ? 12 : 72) * 60 * 60 * 1000);
  return {
    customer: {
      name: kind === 'high' ? 'Mia Patel' : 'Jordan Lee',
      email: kind === 'high' ? 'mia.patel@example.com' : 'jordan.lee@example.com',
      phone: '+1-202-555-0199',
      account_age_days: kind === 'high' ? 21 : 408,
      address: kind === 'high' ? '88 Fraud Lane' : '14 Cedar Street',
      device_id: kind === 'high' ? 'device-fraud' : 'device-1042',
      lifetime_orders: kind === 'high' ? 9 : 42,
      lifetime_returns: kind === 'high' ? 6 : 2,
    },
    order: {
      sku: kind === 'high' ? 'SKU-1002' : 'SKU-2008',
      product_name: kind === 'high' ? 'Designer Jacket' : 'Compact Camera',
      category: kind === 'high' ? 'apparel' : 'electronics',
      product_value: kind === 'high' ? 420 : 189,
      expected_weight: kind === 'high' ? 0.8 : 0.7,
      payment_method: 'card',
      payment_method_risk_score: kind === 'high' ? 82 : 12,
      delivery_date: deliveryDate.toISOString(),
      delivery_status: 'delivered',
    },
    return_data: {
      return_reason: kind === 'high' ? 'I want a refund immediately, or I will open a chargeback.' : 'Purchased wrong color, would like to return it.',
      chat_transcript: kind === 'high' ? 'Customer demanded immediate refund and mentioned chargeback.' : 'Customer asked for a standard return with no issues.',
      email_text: kind === 'high' ? 'Please refund now or I will dispute this charge.' : 'Hello support, I would like to return this item.',
      returned_weight: kind === 'high' ? 0.12 : 0.69,
      condition_reported: kind === 'high' ? 'empty_box' : 'unused',
      delivery_photo_url: kind === 'high' ? 'https://images.example.com/delivery-photo-1.jpg' : '',
      return_photo_url: kind === 'high' ? 'https://images.example.com/return-photo-9.jpg' : '',
      shipping_label_text: kind === 'high' ? 'Ship to 88 Fraud Lane, Mia Patel, SKU-1002' : 'Ship to 14 Cedar Street, Jordan Lee, SKU-2008',
      ocr_text: kind === 'high' ? 'Return label: 88 Fraud Lane, SKU-1002, empty box' : 'Return label: 14 Cedar Street, SKU-2008, unused',

    },
  };
}

function ReturnIntakePanel({ onCreated }: { onCreated: (result: ScoreResponse) => Promise<void> }) {
  const [draft, setDraft] = useState(() => JSON.stringify(buildSampleReturnRequest('low'), null, 2));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [result, setResult] = useState<ScoreResponse>();

  const loadSample = (kind: 'low' | 'high') => setDraft(JSON.stringify(buildSampleReturnRequest(kind), null, 2));

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setDraft(await file.text());
  };

  const submit = async () => {
    setLoading(true);
    setError(undefined);
    try {
      const payload = JSON.parse(draft) as ReturnRequestPayload;
      const scored = await api.createReturn(payload);
      setResult(scored);
      await onCreated(scored);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Invalid return request JSON');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel title="Return intake" subtitle="Paste JSON or upload a file, then submit the request for scoring and case creation.">
      <div className="grid gap-3 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <button onClick={() => loadSample('low')} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">Load normal sample</button>
            <button onClick={() => loadSample('high')} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">Load suspicious sample</button>
            <label className="cursor-pointer rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
              Upload JSON
              <input type="file" accept="application/json" className="hidden" onChange={handleUpload} />
            </label>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            The intake API accepts the same customer, order, and return payloads used by the scoring engine.
          </div>
        </div>
        <div>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            className="min-h-[320px] w-full rounded-2xl border border-slate-200 bg-white p-4 font-mono text-xs text-slate-700 outline-none"
          />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button onClick={submit} disabled={loading} className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white disabled:opacity-60">
              {loading ? 'Scoring...' : 'Submit return'}
            </button>
            {result ? <span className={`rounded-full px-3 py-1 text-xs ${badgeTone(result.risk_level)}`}>{result.decision} {result.risk_score.toFixed(1)}</span> : null}
          </div>
          {error ? <div className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}
        </div>
      </div>
    </Panel>
  );
}

function OverviewPage({ metrics, onReturnCreated }: { metrics?: Metrics; onReturnCreated: (result: ScoreResponse) => Promise<void> }) {
  const totals = metrics?.totals;
  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="ReturnShield AI"
        title="Overview"
        subtitle="Score incoming return requests, track operational risk, and review the active fraud queue."
        action={<Link to="/investigations" className="rounded-2xl bg-slate-950 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-slate-800">Open investigations</Link>}
      />
      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.85fr]">
        <section className="glass-strong rounded-[32px] p-5 soft-ring sm:p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-2xl">
              <div className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Today's signal</div>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">
                Return intake is scored by rules and supervised ML, with NLP, anomaly detection, and fraud-ring signals available for explainability and investigation.
              </h2>
              <p className="mt-3 text-sm leading-6 text-slate-600 sm:text-base">
                Submit a return request to generate a risk score, decision, explanation, and analyst case record.
              </p>
            </div>
            <div className="rounded-[22px] border border-slate-200 bg-slate-950 px-4 py-4 text-white shadow-sm">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-400">Decision chain</div>
              <div className="mt-2 text-lg font-semibold">Rule-led supervised scorer</div>
              <div className="mt-3 space-y-2 text-sm text-slate-300">
                <div className="flex items-center justify-between gap-6">
                  <span>Rules</span>
                  <span className="font-mono text-slate-100">35%</span>
                </div>
                <div className="flex items-center justify-between gap-6">
                  <span>Supervised ML</span>
                  <span className="font-mono text-slate-100">65%</span>
                </div>
                <div className="flex items-center justify-between gap-6 text-slate-400">
                  <span>Fallback</span>
                  <span className="font-mono text-slate-100">Heuristic</span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-[22px] border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Today</div>
              <div className="mt-2 text-2xl font-semibold text-slate-950">{totals?.total_returns_today ?? '—'}</div>
              <div className="mt-2 text-xs text-slate-600">Returns scored since midnight</div>
            </div>
            <div className="rounded-[24px] border border-red-100 bg-red-50 p-4 shadow-sm">
              <div className="text-[11px] uppercase tracking-[0.24em] text-red-600">High risk</div>
              <div className="mt-2 text-2xl font-semibold text-red-700">{totals?.high_risk_cases ?? '—'}</div>
              <div className="mt-2 text-xs text-red-700/80">Cases routed to senior review</div>
            </div>
            <div className="rounded-[24px] border border-blue-100 bg-blue-50 p-4 shadow-sm">
              <div className="text-[11px] uppercase tracking-[0.24em] text-blue-700">Manual review</div>
              <div className="mt-2 text-2xl font-semibold text-blue-800">{totals?.manual_review_cases ?? '—'}</div>
              <div className="mt-2 text-xs text-blue-800/80">Analyst queue waiting</div>
            </div>
            <div className="rounded-[24px] border border-emerald-100 bg-emerald-50 p-4 shadow-sm">
              <div className="text-[11px] uppercase tracking-[0.24em] text-emerald-700">Auto approve</div>
              <div className="mt-2 text-2xl font-semibold text-emerald-700">{totals?.auto_approved_returns ?? '—'}</div>
              <div className="mt-2 text-xs text-emerald-700/80">Low-risk returns released</div>
            </div>
          </div>
        </section>

        <Panel title="Queue posture" subtitle="Current operating signals from the return intake stream">
          <div className="space-y-4">
            <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Estimated fraud prevented</div>
                  <div className="mt-2 text-2xl font-semibold text-slate-950">${(totals?.estimated_fraud_prevented ?? 0).toLocaleString()}</div>
                </div>
                <div className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                  Weighted by decision path
                </div>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-[22px] border border-slate-200 bg-white p-4">
                <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Average risk</div>
                <div className="mt-2 text-2xl font-semibold text-slate-950">{totals?.average_risk_score ?? '—'}</div>
                <div className="mt-2 text-xs text-slate-600">Across all scored returns</div>
              </div>
              <div className="rounded-[22px] border border-slate-200 bg-white p-4">
                <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Decision spread</div>
                <div className="mt-2 text-2xl font-semibold text-slate-950">{totals ? totals.total_returns_today : '—'}</div>
                <div className="mt-2 text-xs text-slate-600">Total cases currently visible</div>
              </div>
            </div>
            <div className="rounded-[22px] border border-slate-200 bg-white p-4">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Signal mix</div>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                <div className="flex items-center justify-between"><span>Rules</span><span className="font-mono">35%</span></div>
                <div className="flex items-center justify-between"><span>Supervised ML</span><span className="font-mono">65%</span></div>
                <div className="flex items-center justify-between text-slate-500"><span>Fallback</span><span className="font-mono">Heuristic</span></div>
              </div>
            </div>
          </div>
        </Panel>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <MetricCard label="Total returns today" value={totals?.total_returns_today ?? '—'} />
        <MetricCard label="High-risk cases" value={totals?.high_risk_cases ?? '—'} accent="text-red-700" />
        <MetricCard label="Manual review" value={totals?.manual_review_cases ?? '—'} accent="text-blue-700" />
        <MetricCard label="Auto-approved" value={totals?.auto_approved_returns ?? '—'} accent="text-emerald-700" />
        <MetricCard label="Fraud prevented" value={`$${(totals?.estimated_fraud_prevented ?? 0).toLocaleString()}`} />
        <MetricCard label="Avg. risk score" value={totals?.average_risk_score ?? '—'} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <ReturnIntakePanel onCreated={onReturnCreated} />
        <Panel title="Detection posture" subtitle="How the scoring pipeline behaves before an analyst opens the case">
          <div className="space-y-3">
            <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-slate-600">Structured features</span>
                <span className="font-mono text-sm text-slate-800">Behavior + device + payment</span>
              </div>
            </div>
            <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-slate-600">Text analysis</span>
                <span className="font-mono text-sm text-slate-800">Reason, chat, email</span>
              </div>
            </div>
            <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-slate-600">Graph features</span>
                <span className="font-mono text-sm text-slate-800">Shared address, device, refund account</span>
              </div>
            </div>
          </div>
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Risk distribution" subtitle="How the current queue is distributed across score bands">
          <SimpleChart data={metrics?.charts?.risk_distribution ?? []} tone="bg-blue-300" />
        </Panel>
        <Panel title="Cases by status" subtitle="Operational state of the current queue">
          <SimpleChart data={metrics?.charts?.cases_by_status ?? []} tone="bg-teal-300" />
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Fraud types" subtitle="Dominant fraud patterns detected in the data">
          <SimpleChart data={metrics?.charts?.fraud_types ?? []} tone="bg-red-300" />
        </Panel>
        <Panel title="Return value at risk" subtitle="Value at risk by decision path">
          <SimpleChart data={metrics?.charts?.return_value_at_risk ?? []} tone="bg-sky-300" />
        </Panel>
      </div>
    </div>
  );
}


function CasesPage({ cases = [], filters, setFilters }: { cases?: CaseSummary[]; filters: { q: string; decision: string; risk: string }; setFilters: Dispatch<SetStateAction<{ q: string; decision: string; risk: string }>> }) {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const filtered = useMemo(() => {
    return cases
      .filter((item) => !filters.decision || item.decision === filters.decision)
      .filter((item) => !filters.risk || item.risk_level === filters.risk)
      .filter((item) => {
        const haystack = `${item.customer_name} ${item.product_name} ${item.return_reason}`.toLowerCase();
        return !filters.q || haystack.includes(filters.q.toLowerCase());
      })
      .sort((a, b) => b.risk_score - a.risk_score);
  }, [cases, filters]);

  const totalFiltered = filtered.length;
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

  const highRisk = paginated.filter((item) => item.risk_level === 'HIGH').length;
  const avgRisk = paginated.length ? (paginated.reduce((sum, item) => sum + item.risk_score, 0) / paginated.length).toFixed(1) : '0.0';

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Operations"
        title="Case queue"
        subtitle="Review returns, sort by score, and filter the active queue."
      />

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel title="Queue controls" subtitle="Search, filter, and monitor the active queue without leaving the page.">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <input
              value={filters.q}
              onChange={(event) => setFilters((value) => ({ ...value, q: event.target.value }))}
              placeholder="Search customer, order, return reason"
              className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none placeholder:text-slate-500"
            />
            <select
              value={filters.risk}
              onChange={(event) => setFilters((value) => ({ ...value, risk: event.target.value }))}
              className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none"
            >
              <option value="">All risk levels</option>
              <option value="LOW">Low</option>
              <option value="MEDIUM">Medium</option>
              <option value="HIGH">High</option>
            </select>
            <select
              value={filters.decision}
              onChange={(event) => setFilters((value) => ({ ...value, decision: event.target.value }))}
              className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none"
            >
              <option value="">All decisions</option>
              <option value="AUTO_APPROVE">Auto approve</option>
              <option value="MANUAL_REVIEW">Manual review</option>
              <option value="HOLD_REFUND_HIGH_RISK">Hold refund</option>
            </select>
            <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              <span>{totalFiltered} visible cases</span>
              <span className="mono">sorted by score</span>
            </div>
          </div>
        </Panel>

        <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-3">
          <MetricCard label="Visible cases" value={totalFiltered} />
          <MetricCard label="High risk" value={highRisk} accent="text-red-700" />
          <MetricCard label="Avg. score" value={avgRisk} accent="text-blue-700" />
        </div>
      </div>

      <Panel title="Case queue" subtitle="Cases are ordered by risk score, with the highest-risk items first.">
        <div className="space-y-3 md:hidden">
          {paginated.map((item) => (
            <div key={item.id} className="rounded-[22px] border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-900">{item.customer_name}</div>
                  <div className="mt-1 text-xs text-slate-500">{item.product_name} · Case {item.id.slice(0, 8)}</div>
                </div>
                <div className="text-right">
                  <div className={`inline-flex rounded-full px-2.5 py-1 text-xs ${badgeTone(item.risk_level)}`}>{item.risk_level}</div>
                  <div className="mt-2 font-mono text-sm text-slate-700">{item.risk_score.toFixed(1)}</div>
                </div>
              </div>
              <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">{item.return_reason}</div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
                  <span className="text-slate-400">Decision</span>
                  <div className="mt-1 font-medium text-slate-800">{item.decision}</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
                  <span className="text-slate-400">Status</span>
                  <div className="mt-1 font-medium text-slate-800">{item.status}</div>
                </div>
              </div>
              <button
                onClick={() => navigate(`/investigations/${item.id}`)}
                className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-950/10 px-3 py-3 text-sm text-slate-800 ring-1 ring-slate-300"
              >
                Investigate
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>

        <div className="hidden overflow-auto rounded-[28px] border border-slate-200 md:block">
          <table className="min-w-full text-left text-sm">
            <thead className="sticky top-0 bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3">Case ID</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Return Reason</th>
                <th className="px-4 py-3">Cust. Risk</th>
                <th className="px-4 py-3">Risk Score</th>
                <th className="px-4 py-3">Risk Level</th>
                <th className="px-4 py-3">Decision</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {paginated.map((item) => (
                <tr key={item.id} className="border-t border-white/6 bg-white hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs text-slate-700">{item.id.slice(0, 8)}</td>
                  <td className="px-4 py-3 font-medium text-slate-900">{item.customer_name}</td>
                  <td className="px-4 py-3 text-slate-700">{item.product_name}</td>
                  <td className="px-4 py-3 text-slate-700">{item.return_reason}</td>
                  <td className="px-4 py-3 font-mono text-slate-700">{item.customer_risk_score.toFixed(1)}</td>
                  <td className="px-4 py-3 font-mono text-slate-800">{item.risk_score.toFixed(1)}</td>
                  <td className="px-4 py-3"><span className={`rounded-full px-2.5 py-1 text-xs ${badgeTone(item.risk_level)}`}>{item.risk_level}</span></td>
                  <td className="px-4 py-3 text-slate-700">{item.decision}</td>
                  <td className="px-4 py-3 text-slate-600">{item.status}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => navigate(`/investigations/${item.id}`)} className="inline-flex items-center gap-2 rounded-2xl bg-slate-950/10 px-3 py-2 text-xs text-slate-800 ring-1 ring-slate-300">
                      Investigate
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <Pagination
          currentPage={page}
          totalItems={totalFiltered}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
        />
      </Panel>
    </div>
  );
}

function TimelinePanel({ timeline }: { timeline: Array<{ label: string; time: string }> }) {
  const steps = timeline.map((step, index) => ({ ...step, index }));
  return (
    <Panel title="Timeline" subtitle="A compact view of how the return moved through the fraud workflow.">
      <div className="relative">
        <div className="absolute left-3 top-3 h-[calc(100%-1.5rem)] w-px bg-gradient-to-b from-blue-300 via-slate-200 to-transparent" />
        <div className="space-y-3">
          {steps.map((step) => (
            <div key={step.label} className="relative pl-11">
              <span className="absolute left-0 top-3 flex h-7 w-7 items-center justify-center rounded-full bg-white text-[11px] font-semibold text-blue-700 ring-1 ring-blue-200">
                {step.index + 1}
              </span>
              <div className="rounded-[24px] border border-slate-200 bg-slate-50 px-4 py-3 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-slate-900">{step.label}</div>
                    <div className="mt-1 text-xs text-slate-500">Decision checkpoint</div>
                  </div>
                  <div className="rounded-full bg-white px-2.5 py-1 font-mono text-[11px] text-slate-600 ring-1 ring-slate-200">
                    {new Date(step.time).toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function ExplainabilityPanelView({ explainability }: { explainability: CaseDetail["explainability"] }) {
  const sortedSignals = [...explainability.signal_contributions].sort((a, b) => b.impact - a.impact);
  const strongestSignal = sortedSignals[0];
  const strongestPositive = explainability.top_positive_drivers[0];
  const strongestMitigation = explainability.top_negative_drivers[0];
  const totalImpact = sortedSignals.reduce((sum, signal) => sum + signal.impact, 0) || 1;

  return (
    <div className="space-y-4">
      <div className="rounded-3xl border border-blue-200 bg-gradient-to-br from-blue-50 to-white p-4">
        <div className="text-xs uppercase tracking-[0.22em] text-blue-700">Why flagged</div>
        <p className="mt-2 text-sm leading-6 text-slate-700">{explainability.why_flagged_summary}</p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Dominant signal</div>
          <div className="mt-2 text-sm font-medium text-slate-900">{strongestSignal?.label ?? "No signal"}</div>
          <div className="mt-1 text-xs text-slate-500">{strongestSignal?.detail ?? "No dominant contributor was detected."}</div>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Strongest driver</div>
          <div className="mt-2 text-sm font-medium text-slate-900">{strongestPositive?.label ?? "No positive driver"}</div>
          <div className="mt-1 text-xs text-slate-500">{strongestPositive?.detail ?? "No additional risk driver stood out."}</div>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Mitigation</div>
          <div className="mt-2 text-sm font-medium text-slate-900">{strongestMitigation?.label ?? "No mitigation"}</div>
          <div className="mt-1 text-xs text-slate-500">{strongestMitigation?.detail ?? "No clear mitigating factors were present."}</div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="space-y-3">
          {sortedSignals.map((signal) => (
            <div key={signal.label} className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3 text-sm">
                <div>
                  <div className="font-medium text-slate-900">{signal.label}</div>
                  <div className="mt-1 text-xs text-slate-500">{signal.detail}</div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-sm text-slate-800">{signal.impact.toFixed(1)}</div>
                  <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">{Math.round((signal.impact / totalImpact) * 100)}%</div>
                </div>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                <div className={`h-full rounded-full ${signal.label === strongestSignal?.label ? "bg-rose-400" : "bg-blue-300"}`} style={{ width: `${Math.max(10, (signal.impact / totalImpact) * 100)}%` }} />
              </div>
            </div>
          ))}
        </div>

        <div className="space-y-4">
          <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Top positive drivers</div>
            <div className="mt-3 space-y-3">
              {explainability.top_positive_drivers.length ? explainability.top_positive_drivers.map((driver) => (
                <div key={driver.label} className="rounded-2xl border border-blue-200 bg-white px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-slate-800">{driver.label}</div>
                    <div className="font-mono text-sm text-blue-700">+{driver.impact.toFixed(1)}</div>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">{driver.detail}</div>
                </div>
              )) : (
                <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">No additional risk drivers surfaced.</div>
              )}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Top negative drivers</div>
            <div className="mt-3 space-y-3">
              {explainability.top_negative_drivers.length ? explainability.top_negative_drivers.map((driver) => (
                <div key={driver.label} className="rounded-2xl border border-emerald-200 bg-white px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-slate-800">{driver.label}</div>
                    <div className="font-mono text-sm text-emerald-700">-{driver.impact.toFixed(1)}</div>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">{driver.detail}</div>
                </div>
              )) : (
                <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">No clear mitigating factors were detected.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FraudRingPanelView({ graph }: { graph?: Record<string, unknown> }) {
  const ringRisk = Number(graph?.ring_risk_score ?? graph?.score ?? 0);
  const componentSize = Number(graph?.component_size ?? graph?.ring_size ?? 0);
  const connectedCustomers = Number(graph?.connected_customers_count ?? 0);
  const sharedAddress = Number(graph?.shared_address_count ?? graph?.shared_address_accounts ?? 0);
  const sharedDevice = Number(graph?.shared_device_count ?? graph?.shared_device_accounts ?? 0);
  const sharedPayment = Number(graph?.shared_payment_count ?? graph?.shared_payment_orders ?? 0);
  const sharedRefund = Number(graph?.shared_refund_account_count ?? 0);
  const textCluster = Number(graph?.text_similarity_cluster_size ?? 0);
  const fraudNeighbors = Number(graph?.fraud_neighbor_count ?? 0);
  const shortestPath = Number(graph?.shortest_path_to_fraud ?? 0);
  const highRiskRatio = Number(graph?.high_risk_neighbor_ratio ?? 0);
  const sameSku = Number(graph?.same_sku_return_cluster_count ?? 0);
  const samePickup = Number(graph?.same_pickup_location_count ?? 0);
  const velocity = Number(graph?.return_velocity_in_component ?? 0);
  const signals = (graph?.signals ?? []) as string[];
  const reasons = (graph?.reason_codes ?? []) as string[];

  return (
    <div className="grid gap-4 xl:grid-cols-[1.08fr_0.92fr]">
      <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Fraud ring graph</div>
            <div className="mt-2 text-sm font-medium text-slate-900">Connected identities, payment proxies, and repeated return stories.</div>
          </div>
          <div className="rounded-2xl bg-rose-50 px-4 py-3 text-right ring-1 ring-rose-100">
            <div className="text-[10px] uppercase tracking-[0.22em] text-rose-600">Ring risk</div>
            <div className="mt-1 text-2xl font-semibold text-rose-700">{ringRisk.toFixed(0)}</div>
          </div>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[
            ["Ring size", componentSize],
            ["Connected customers", connectedCustomers],
            ["Fraud neighbors", fraudNeighbors],
            ["Shared address", sharedAddress],
            ["Shared device", sharedDevice],
            ["Shared payment", sharedPayment],
          ].map(([label, value]) => (
            <div key={label as string} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{label as string}</div>
              <div className="mt-2 text-lg font-semibold text-slate-900">{Number(value).toFixed(0)}</div>
            </div>
          ))}
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Graph paths</div>
            <div className="mt-3 space-y-2 text-sm text-slate-700">
              <div className="rounded-2xl bg-white px-3 py-2 ring-1 ring-slate-200">Customer → Address → Other customers</div>
              <div className="rounded-2xl bg-white px-3 py-2 ring-1 ring-slate-200">Customer → Device → Other customers</div>
              <div className="rounded-2xl bg-white px-3 py-2 ring-1 ring-slate-200">Customer → Refund proxy → Other customers</div>
              <div className="rounded-2xl bg-white px-3 py-2 ring-1 ring-slate-200">Customer → Text pattern → Other customers</div>
            </div>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Cluster metrics</div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-slate-700">
              <div className="rounded-2xl bg-white px-3 py-2 ring-1 ring-slate-200"><div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Text cluster</div><div className="mt-1 font-semibold text-slate-900">{textCluster}</div></div>
              <div className="rounded-2xl bg-white px-3 py-2 ring-1 ring-slate-200"><div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Same SKU cluster</div><div className="mt-1 font-semibold text-slate-900">{sameSku}</div></div>
              <div className="rounded-2xl bg-white px-3 py-2 ring-1 ring-slate-200"><div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Same pickup</div><div className="mt-1 font-semibold text-slate-900">{samePickup}</div></div>
              <div className="rounded-2xl bg-white px-3 py-2 ring-1 ring-slate-200"><div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Shortest path</div><div className="mt-1 font-semibold text-slate-900">{shortestPath}</div></div>
            </div>
            <div className="mt-3 rounded-2xl bg-white px-3 py-2 text-sm text-slate-700 ring-1 ring-slate-200">High-risk neighbor ratio: {highRiskRatio.toFixed(2)}</div>
            <div className="mt-2 rounded-2xl bg-white px-3 py-2 text-sm text-slate-700 ring-1 ring-slate-200">Return velocity in component: {velocity.toFixed(2)}</div>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Ring evidence</div>
          <div className="mt-3 flex flex-wrap gap-2">
            {[`Ring risk ${ringRisk.toFixed(0)}`, `Component ${componentSize}`, `Neighbors ${connectedCustomers}`, `Fraud neighbors ${fraudNeighbors}`].map((chip) => (
              <span key={chip} className="rounded-full bg-rose-50 px-3 py-1 text-xs text-rose-700 ring-1 ring-rose-100">{chip}</span>
            ))}
          </div>
          <div className="mt-4 space-y-2 text-sm text-slate-700">
            {reasons.length ? reasons.map((reason) => <div key={reason} className="rounded-2xl bg-slate-50 px-3 py-2">{reason}</div>) : <div className="rounded-2xl bg-slate-50 px-3 py-2 text-slate-500">No ring-specific reasons were emitted.</div>}
          </div>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Signals</div>
          <div className="mt-3 flex flex-wrap gap-2">
            {signals.length ? signals.map((signal) => <span key={signal} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{signal}</span>) : <span className="text-sm text-slate-500">No additional graph signals.</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

function AdvancedSignalsPanelView({ advancedSignals }: { advancedSignals: CaseDetail["advanced_signals"] }) {
  const behavioral = (advancedSignals.behavioral_ml ?? {}) as Record<string, unknown>;
  const nlp = (advancedSignals.nlp_detection ?? {}) as Record<string, unknown>;
  const image = (advancedSignals.image_verification ?? {}) as Record<string, unknown>;
  const graph = (advancedSignals.graph_fraud ?? {}) as Record<string, unknown>;
  const investigator = (advancedSignals.llm_investigator ?? {}) as Record<string, unknown>;
  const familyScores = (behavioral.family_scores ?? {}) as Record<string, number>;
  const modelMode = String(nlp.model_mode ?? "heuristic");
  const nlpSignals = (nlp.signals ?? {}) as Record<string, number>;
  const behavioralReasons = (behavioral.reason_codes ?? []) as string[];
  const flaggedPhrases = (nlp.flagged_phrases ?? []) as string[];
  const imageSignals = (image.signals ?? []) as string[];
  const graphSignals = (graph.signals ?? []) as string[];
  const investigatorEvidence = (investigator.evidence ?? []) as string[];

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <div className="space-y-4">
        <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Behavioral ML ensemble</div>
          <div className="mt-2 text-sm font-medium text-slate-900">{String(behavioral.summary ?? "Behavioral models combined for return-risk scoring.")}</div>
          <div className="mt-3 space-y-2">
            {Object.entries(familyScores).map(([name, value]) => (
              <div key={name} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-slate-600">{name}</span>
                <span className="font-mono text-slate-800">{Number(value).toFixed(1)}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {behavioralReasons.slice(0, 4).map((reason) => (
              <span key={reason} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{reason}</span>
            ))}
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-500">NLP fraud detection</div>
          <div className="mt-2 text-sm font-medium text-slate-900">{String(nlp.summary ?? "Semantic fraud analysis across return text and support messages.")}</div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
            {Object.entries(nlpSignals).map(([key, value]) => (
              <div key={key} className="rounded-2xl bg-slate-50 px-3 py-2">
                <div className="uppercase tracking-[0.18em] text-slate-400">{key}</div>
                <div className="mt-1 font-mono text-slate-800">{Number(value).toFixed(1)}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {flaggedPhrases.slice(0, 4).map((phrase) => (
              <span key={phrase} className="rounded-full bg-blue-50 px-3 py-1 text-xs text-blue-700">{phrase}</span>
            ))}
          </div>
          <div className="mt-3 text-xs text-slate-500">Mode: {modelMode}</div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Image and OCR verification</div>
          <div className="mt-2 text-sm font-medium text-slate-900">{String(image.summary ?? "No image evidence supplied.")}</div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
            <div className="rounded-2xl bg-slate-50 px-3 py-2">
              <div className="uppercase tracking-[0.18em] text-slate-400">OCR match</div>
              <div className="mt-1 font-mono text-slate-800">{Number(image.ocr_match ?? 0).toFixed(1)}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 px-3 py-2">
              <div className="uppercase tracking-[0.18em] text-slate-400">Photo similarity</div>
              <div className="mt-1 font-mono text-slate-800">{Number(image.photo_similarity ?? 0).toFixed(1)}</div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {imageSignals.slice(0, 4).map((signal) => (
              <span key={signal} className="rounded-full bg-sky-50 px-3 py-1 text-xs text-sky-700">{signal}</span>
            ))}
          </div>
        </div>

        <FraudRingPanelView graph={graph} />

        <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Investigation summary</div>
          <div className="mt-2 text-sm leading-6 text-slate-700">{String(investigator.summary ?? "No investigator summary available.")}</div>
          <div className="mt-3 text-xs uppercase tracking-[0.22em] text-slate-500">Recommendation</div>
          <div className="mt-1 text-sm font-medium text-slate-900">{String(investigator.recommendation ?? "Review manually")}</div>
          <div className="mt-3 space-y-2">
            {investigatorEvidence.slice(0, 4).map((item) => (
              <div key={item} className="rounded-2xl bg-slate-50 px-3 py-2 text-xs text-slate-600">{item}</div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function EnhancementsPage({ latest, cases = [] }: { latest?: ScoreResponse; cases?: CaseSummary[] }) {
  const flaggedCases = cases.filter((item) => item.risk_level !== 'LOW').slice(0, 6);
  const signalCards = [
    {
      title: 'Behavioral ML',
      description: 'RandomForest, GradientBoosting, and HistGradientBoosting blend structured return behavior into one fraud signal.',
      accent: 'from-sky-50 to-slate-50',
      metric: latest?.score_breakdown.structured_ml_score?.toFixed(1) ?? '—',
      details: latest?.advanced_signals?.behavioral_ml as Record<string, unknown> | undefined,
    },
    {
      title: 'NLP fraud detection',
      description: 'Text analysis flags urgency, manipulation, refund pressure, repeated scripts, and empty-box claims.',
      accent: 'from-blue-50 to-white',
      metric: latest?.score_breakdown.nlp_score?.toFixed(1) ?? '—',
      details: latest?.advanced_signals?.nlp_detection as Record<string, unknown> | undefined,
    },
    {
      title: 'Image / OCR verification',
      description: 'Optional photo and label evidence are compared against the shipment record for mismatch signals.',
      accent: 'from-emerald-50 to-white',
      metric: String((latest?.advanced_signals?.image_verification as Record<string, unknown> | undefined)?.score ?? '—'),
      details: latest?.advanced_signals?.image_verification as Record<string, unknown> | undefined,
    },
    {
      title: 'Fraud ring graph',
      description: 'Shared address, device, payment, and phone patterns surface coordinated fraud rings.',
      accent: 'from-rose-50 to-white',
      metric: String((latest?.advanced_signals?.graph_fraud as Record<string, unknown> | undefined)?.score ?? '—'),
      details: latest?.advanced_signals?.graph_fraud as Record<string, unknown> | undefined,
    },
    {
      title: 'Investigation summary',
      description: 'A compact evidence summary turns signals into analyst-ready next actions.',
      accent: 'from-slate-50 to-white',
      metric: String((latest?.advanced_signals?.llm_investigator as Record<string, unknown> | undefined)?.risk_level ?? '—'),
      details: latest?.advanced_signals?.llm_investigator as Record<string, unknown> | undefined,
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Decision intelligence"
        title="Decision engine"
        subtitle="See how rules and supervised ML drive the current decision path, with NLP, graph, and anomaly signals used for explanation."
      />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Latest final score" value={latest?.risk_score?.toFixed(1) ?? '—'} accent="text-blue-700" />
        <MetricCard label="Decision" value={latest?.decision ?? '—'} />
        <MetricCard label="Risk level" value={latest?.risk_level ?? '—'} />
        <MetricCard label="Cases with elevated risk" value={flaggedCases.length} accent="text-sky-700" />
      </div>

      <Panel title="Fraud intelligence signals" subtitle="Supporting signals that enrich the rule-led supervised decision path.">
        <div className="grid gap-4 xl:grid-cols-2">
          {signalCards.map((card) => (
            <div key={card.title} className={`rounded-[24px] border border-slate-200 bg-gradient-to-br ${card.accent} p-4 shadow-sm`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Module</div>
                  <div className="mt-1 text-base font-semibold text-slate-900">{card.title}</div>
                </div>
                <div className="rounded-2xl bg-white px-3 py-2 text-right shadow-sm ring-1 ring-slate-200">
                  <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Score</div>
                  <div className="mt-1 text-lg font-semibold text-slate-900">{card.metric}</div>
                </div>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-600">{card.description}</p>
              <div className="mt-4 rounded-2xl border border-white/70 bg-white/80 p-3 backdrop-blur-sm">
                <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Evidence snapshot</div>
                <div className="mt-2 grid gap-2 md:grid-cols-2">
                  {card.details ? Object.entries(card.details).slice(0, 4).map(([key, value]) => (
                    <div key={key} className="rounded-2xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
                      <div className="uppercase tracking-[0.18em] text-slate-400">{key.replace(/_/g, ' ')}</div>
                      <div className="mt-1 font-medium text-slate-800">{Array.isArray(value) ? `${value.length} items` : typeof value === 'object' ? 'available' : String(value)}</div>
                    </div>
                  )) : (
                    <div className="rounded-2xl bg-slate-50 px-3 py-2 text-xs text-slate-500">No detail payload on the latest case yet.</div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel title="Recent elevated cases" subtitle="Quick access to the cases most likely to need analyst attention.">
          <div className="space-y-3">
            {flaggedCases.length ? flaggedCases.map((item) => (
              <Link key={item.id} to={`/cases/${item.id}`} className="block rounded-3xl border border-slate-200 bg-slate-50 px-4 py-3 transition hover:-translate-y-0.5 hover:bg-white hover:shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">{item.customer_name}</div>
                    <div className="mt-1 text-sm text-slate-600">{item.product_name}</div>
                  </div>
                  <div className="text-right">
                    <div className={`inline-flex rounded-full px-2.5 py-1 text-xs ${badgeTone(item.risk_level)}`}>{item.risk_level}</div>
                    <div className="mt-2 font-mono text-sm text-slate-700">{item.risk_score.toFixed(1)}</div>
                  </div>
                </div>
                <div className="mt-3 text-xs text-slate-500">{item.return_reason}</div>
              </Link>
            )) : (
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">No elevated cases available yet.</div>
            )}
          </div>
        </Panel>

        <Panel title="Decisioning overview" subtitle="The AI stack feeds into a single fraud decision and analyst workflow.">
          <div className="space-y-3 text-sm text-slate-700">
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">Rules and supervised ML form the live decision path. NLP, graph, and anomaly signals remain available for explanation and manual review.</div>
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">Explainability converts the score into reason codes, evidence summaries, and action guidance for analysts.</div>
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">Feedback from approve / reject / fraud labels is stored for future retraining.</div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link to="/decision-engine" className="rounded-2xl bg-slate-950 px-4 py-2 text-sm font-medium text-white">Open decision engine</Link>
            <Link to="/cases" className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-800">Open case queue</Link>
          </div>
        </Panel>
      </div>
    </div>
  );
}

const actions = [
  { label: 'Approve Return', value: 'AUTO_APPROVE', icon: ThumbsUp, tone: 'success' as const, needsConfirm: false },
  { label: 'Reject Return', value: 'REJECT_RETURN', icon: Ban, tone: 'destructive' as const, needsConfirm: true },
  { label: 'Hold Refund', value: 'HOLD_REFUND_HIGH_RISK', icon: Hand, tone: 'destructive' as const, needsConfirm: true },
  { label: 'Escalate', value: 'MANUAL_REVIEW', icon: ShieldAlert, tone: 'warning' as const, needsConfirm: true },
  { label: 'Confirmed Fraud', value: 'Mark Confirmed Fraud', icon: Flag, tone: 'destructive' as const, needsConfirm: true },
  { label: 'False Positive', value: 'Mark False Positive', icon: CheckCircle2, tone: 'warning' as const, needsConfirm: false },
];

const actionToneMap = {
  success: 'border-green-border bg-green-background text-green-primary hover:bg-green-border',
  destructive: 'border-red-border bg-red-background text-red-primary hover:bg-red-border',
  warning: 'border-yellow-border bg-yellow-background text-yellow-primary hover:bg-yellow-border',
  default: 'border-grey-border bg-grey-background text-grey-primary hover:bg-grey-background-light',
};

function InvestigationPage({ caseDetail, onAction }: { caseDetail?: CaseDetail; onAction?: (decision: string, notes: string) => Promise<void> }) {
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<{ label: string; value: string } | null>(null);
  const [investigationReport, setInvestigationReport] = useState<Record<string, unknown> | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const { showToast } = useToast();
  const { id } = useParams();

  useEffect(() => {
    if (!id) return;
    setReportLoading(true);
    api.getInvestigationReport(id).then((report) => {
      setInvestigationReport(report as Record<string, unknown>);
      setReportLoading(false);
    }).catch(() => setReportLoading(false));
  }, [id]);

  if (!caseDetail) {
    return <Panel title="Investigations" subtitle="Select a case from the queue to inspect the evidence chain.">Loading…</Panel>;
  }

  const returnData = caseDetail.return_data ?? caseDetail.return;
  const graph = caseDetail.advanced_signals?.graph_fraud as Record<string, unknown> | undefined;
  const explanationChips = caseDetail.reason_codes.slice(0, 4);
  const tracePreview = caseDetail.decision_trace.slice(0, 4);

  const handle = async (decisionValue: string) => {
    if (!onAction) return;
    setBusy(decisionValue);
    try {
      await onAction(decisionValue, notes);
      showToast('success', 'Action completed', `Case updated with decision: ${decisionValue}`);
    } catch {
      showToast('error', 'Action failed', 'Unable to update the case. Please try again.');
    } finally {
      setBusy(null);
      setConfirmAction(null);
    }
  };

  const statusColor =
    caseDetail.status === 'CLOSED'
      ? 'border-green-border bg-green-background text-green-primary'
      : caseDetail.status === 'OPEN'
        ? 'border-blue-96 bg-blue-96 text-blue-58'
        : 'border-yellow-border bg-yellow-background text-yellow-primary';

  const decisionColor =
    caseDetail.decision === 'AUTO_APPROVE'
      ? 'border-green-border bg-green-background text-green-primary'
      : caseDetail.decision === 'HOLD_REFUND_HIGH_RISK'
        ? 'border-red-border bg-red-background text-red-primary'
        : caseDetail.decision === 'MANUAL_REVIEW'
          ? 'border-yellow-border bg-yellow-background text-yellow-primary'
          : 'border-grey-border bg-grey-background text-grey-primary';

  return (
    <div className="space-y-4">
      <ConfirmDialog
        open={confirmAction !== null}
        title={confirmAction ? `Confirm: ${confirmAction.label}` : ''}
        message="This action will update the case decision and record your feedback for model retraining."
        confirmLabel={confirmAction?.label ?? ''}
        confirmTone={
          actions.find((a) => a.value === confirmAction?.value)?.tone === 'destructive'
            ? 'destructive'
            : 'default'
        }
        onConfirm={() => confirmAction && handle(confirmAction.value)}
        onCancel={() => setConfirmAction(null)}
      />

      <Panel title={`Case ${caseDetail.id.slice(0, 8)}`} subtitle={caseDetail.explanation}>
        <div className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <span className={`rounded-full px-3 py-1 text-xs ${badgeTone(caseDetail.risk_level)}`}>{caseDetail.risk_level} risk</span>
              <span className="rounded-full border border-grey-border bg-grey-background px-3 py-1 text-xs text-grey-secondary">Customer risk {caseDetail.customer_risk_score.toFixed(1)}</span>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${decisionColor}`}>{caseDetail.decision}</span>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusColor}`}>{caseDetail.status}</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <MetricCard label="Final score" value={caseDetail.risk_score.toFixed(1)} accent="text-purple-primary" />
              <MetricCard label="Customer risk" value={caseDetail.customer_risk_score.toFixed(1)} accent="text-orange-primary" />
              <MetricCard label="Rule score" value={caseDetail.score_breakdown.rule_score.toFixed(1)} />
              <MetricCard label="Structured" value={caseDetail.score_breakdown.structured_ml_score.toFixed(1)} />
              <MetricCard label="NLP score" value={caseDetail.score_breakdown.nlp_score.toFixed(1)} />
            </div>
          </div>
          <div className="rounded-xl border border-grey-border bg-surface-elevated p-4">
            <div className="text-xs uppercase tracking-[0.24em] text-grey-secondary">Recommended action</div>
            <div className="mt-2 text-lg font-semibold text-grey-primary">{caseDetail.recommended_action}</div>
            <div className="mt-4 space-y-2 text-sm text-grey-secondary">
              {tracePreview.map((item) => (
                <div key={item.stage} className="flex items-center justify-between rounded-lg border border-grey-border bg-grey-background-light px-3 py-2">
                  <span>{item.stage}</span>
                  <span className="mono text-grey-primary">{String(item.value)}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 rounded-lg border border-grey-border bg-grey-background-light px-3 py-3 text-xs leading-5 text-grey-secondary">
              Analyst notes are stored back into feedback so future model runs can learn from the decision.
            </div>
          </div>
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel title="Evidence wall" subtitle="Customer, order, return, and reason-code evidence in one place.">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary">
              <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Customer</div>
              <div className="mt-1 font-medium text-grey-primary">{caseDetail.customer.name}</div>
              <div className="mt-2 text-xs text-grey-secondary">{caseDetail.customer.email}</div>
            </div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary">
              <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Product</div>
              <div className="mt-1 font-medium text-grey-primary">{caseDetail.order.product_name}</div>
              <div className="mt-2 text-xs text-grey-secondary">SKU {caseDetail.order.sku}</div>
            </div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary">
              <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Expected weight</div>
              <div className="mt-1 font-medium text-grey-primary">{caseDetail.order.expected_weight} kg</div>
            </div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary">
              <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Returned weight</div>
              <div className="mt-1 font-medium text-grey-primary">{returnData?.returned_weight ?? '—'} kg</div>
            </div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary sm:col-span-2">
              <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Return reason</div>
              <div className="mt-1 font-medium text-grey-primary">{returnData?.return_reason ?? caseDetail.return_reason}</div>
            </div>
          </div>

          <div className="mt-4 rounded-lg border border-grey-border bg-surface-card p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-grey-secondary">Reason codes</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {explanationChips.length ? explanationChips.map((reason) => (
                <span key={reason} className="rounded-full border border-purple-border-light bg-purple-background px-3 py-1 text-xs text-purple-primary">{reason}</span>
              )) : <span className="text-sm text-grey-secondary">No reason codes available.</span>}
            </div>
          </div>

          <div className="mt-4 rounded-lg border border-grey-border bg-grey-background-light p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-grey-secondary">Analyst summary</div>
            <div className="mt-2 text-sm leading-6 text-grey-primary">{caseDetail.explanation}</div>
          </div>
        </Panel>

        <Panel title="Decision trail" subtitle="Trace the path from intake to final score and decision.">
          <div className="space-y-2">
            {caseDetail.decision_trace.map((item, index) => (
              <div key={item.stage} className="rounded-lg border border-grey-border bg-grey-background-light p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Step {index + 1}</div>
                    <div className="mt-0.5 text-sm font-medium text-grey-primary">{item.stage}</div>
                  </div>
                  <div className="rounded-full border border-grey-border bg-surface-card px-2.5 py-0.5 font-mono text-xs text-grey-primary">
                    {String(item.value)}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-lg border border-grey-border bg-surface-card p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-grey-secondary">Analyst actions</div>
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className="mt-3 min-h-[100px] w-full rounded-lg border border-grey-border bg-grey-background p-3 text-sm outline-none placeholder:text-grey-placeholder transition-colors focus:border-purple-border"
              placeholder="Add notes for retraining..."
            />
            <div className="mt-3 grid grid-cols-2 gap-2">
              {actions.map(({ label, value, icon: Icon, tone, needsConfirm }) => (
                <button
                  key={value}
                  disabled={busy !== null}
                  onClick={() => {
                    if (needsConfirm) {
                      setConfirmAction({ label, value });
                    } else {
                      handle(value);
                    }
                  }}
                  className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-xs font-medium transition-colors disabled:opacity-40 ${actionToneMap[tone]}`}
                >
                  <Icon className="size-4 shrink-0" />
                  {busy === value ? 'Processing...' : label}
                </button>
              ))}
            </div>
          </div>
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.08fr_0.92fr]">
        <Panel title="Customer profile" subtitle="The customer and shipment context behind the return request.">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary"><div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Name</div><div className="mt-1 font-medium text-grey-primary">{caseDetail.customer.name}</div></div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary"><div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Email</div><div className="mt-1 break-all font-medium text-grey-primary">{caseDetail.customer.email}</div></div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary"><div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Account age</div><div className="mt-1 font-medium text-grey-primary">{caseDetail.customer.account_age_days} days</div></div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary"><div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Returns</div><div className="mt-1 font-medium text-grey-primary">{caseDetail.customer.lifetime_returns}</div></div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary sm:col-span-2"><div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Address</div><div className="mt-1 font-medium text-grey-primary">{caseDetail.customer.address}</div></div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary sm:col-span-2"><div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Device</div><div className="mt-1 font-medium text-grey-primary">{caseDetail.customer.device_id}</div></div>
          </div>
        </Panel>
        <Panel title="Order and return" subtitle="Shipment and reverse-logistics evidence used by the decision engine.">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary"><div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Product</div><div className="mt-1 font-medium text-grey-primary">{caseDetail.order.product_name}</div></div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary"><div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">SKU</div><div className="mt-1 font-medium text-grey-primary">{caseDetail.order.sku}</div></div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary"><div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Value</div><div className="mt-1 font-medium text-grey-primary">${caseDetail.order.product_value.toLocaleString()}</div></div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary"><div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Expected weight</div><div className="mt-1 font-medium text-grey-primary">{caseDetail.order.expected_weight} kg</div></div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary"><div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Returned weight</div><div className="mt-1 font-medium text-grey-primary">{returnData?.returned_weight ?? "—"} kg</div></div>
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary sm:col-span-2"><div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Reason</div><div className="mt-1 font-medium text-grey-primary">{returnData?.return_reason ?? caseDetail.return_reason}</div></div>
          </div>
        </Panel>
      </div>

      <Panel title="Fraud ring graph" subtitle="Connected identities, payments, devices, and repeated return stories">
        <FraudRingPanelView graph={graph} />
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Explainability" subtitle="Signal-level evidence, drivers, and the human summary behind the score">
          <ExplainabilityPanelView explainability={caseDetail.explainability} />
        </Panel>
        <TimelinePanel timeline={caseDetail.timeline} />
      </div>

      <Panel title="Supporting signals" subtitle="Behavioral models, NLP, image/OCR checks, graph fraud, and the investigation summary">
        <AdvancedSignalsPanelView advancedSignals={caseDetail.advanced_signals} />
      </Panel>

      <Panel title="Investigation report" subtitle="LLM-generated summary of evidence, signals, and recommended next steps.">
        {reportLoading ? (
          <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-secondary">Loading investigation report...</div>
        ) : investigationReport ? (
          (() => {
            const r = investigationReport as Record<string, unknown>;
            const inv = r.investigation as Record<string, unknown> | undefined;
            const summary = String(r.summary ?? inv?.summary ?? 'No summary available.');
            const evidence = (r.evidence ?? inv?.evidence ?? []) as Array<Record<string, unknown>>;
            const recommendation = (r.recommendation ?? inv?.recommendation) as string | undefined;
            const riskFactors = (r.risk_factors ?? inv?.risk_factors ?? []) as string[];
            return (
              <div className="space-y-4">
                <div className="rounded-lg border border-grey-border bg-grey-background-light p-4">
                  <div className="text-xs uppercase tracking-[0.22em] text-grey-secondary">Summary</div>
                  <div className="mt-2 text-sm leading-6 text-grey-primary">{summary}</div>
                </div>
                {evidence.length > 0 && (
                  <div className="rounded-lg border border-grey-border bg-grey-background-light p-4">
                    <div className="text-xs uppercase tracking-[0.22em] text-grey-secondary">Evidence items</div>
                    <div className="mt-3 space-y-2">
                      {evidence.slice(0, 6).map((item, i) => (
                        <div key={i} className="flex items-start gap-3 rounded-lg border border-grey-border bg-surface-card p-3 text-sm">
                          <div className="size-2 mt-1.5 shrink-0 rounded-full bg-purple-primary" />
                          <div>
                            <div className="font-medium text-grey-primary">{String(item.label ?? item.type ?? 'Evidence')}</div>
                            <div className="mt-0.5 text-xs text-grey-secondary">{String(item.detail ?? item.description ?? '')}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {recommendation && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                    <div className="text-xs uppercase tracking-[0.22em] text-amber-700">Recommendation</div>
                    <div className="mt-1 text-sm font-medium text-amber-900">{String(recommendation)}</div>
                  </div>
                )}
                {riskFactors.length > 0 && (
                  <div className="rounded-lg border border-grey-border bg-grey-background-light p-4">
                    <div className="text-xs uppercase tracking-[0.22em] text-grey-secondary">Risk factors</div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {riskFactors.map((factor, i) => (
                        <span key={i} className="rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs text-red-700">{factor}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })()
        ) : (
          <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-secondary">No investigation report available for this case.</div>
        )}
      </Panel>
    </div>
  );
}

function DecisionEnginePage({ latest }: { latest?: ScoreResponse }) {
  const pipeline = [
    "Return request ingestion",
    "Data normalization",
    "Feature extraction",
    "Rule engine",
    "Supervised ML",
    "NLP signals",
    "Fraud graph",
    "Decision engine",
    "Analyst feedback",
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Decision intelligence"
        title="Decision engine"
        subtitle="See how rules and supervised ML drive the current decision path, with NLP, graph, and anomaly signals used for explanation."
      />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Latest final score" value={latest?.risk_score?.toFixed(1) ?? "—"} accent="text-blue-700" />
        <MetricCard label="Customer risk" value={latest?.customer_risk_score?.toFixed(1) ?? "—"} accent="text-sky-700" />
        <MetricCard label="Decision" value={latest?.decision ?? "—"} />
        <MetricCard label="Risk level" value={latest?.risk_level ?? "—"} />
      </div>

      <Panel title="Decisioning architecture" subtitle="Rule-led flow with supervised scoring and analyst feedback">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-3">
          {pipeline.map((step, index) => (
            <div key={step} className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Step {index + 1}</div>
              <div className="mt-2 text-sm font-medium text-slate-800">{step}</div>
            </div>
          ))}
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Scoring path" subtitle="How the current signals combine into the final decision">
          <div className="space-y-3">
            {[["Customer risk", "Persistent behavioral exposure from history and shared identity patterns"], ["Rule engine", "Hard business controls such as weight mismatch and fast returns"], ["Supervised ML", "Tabular fraud probability from PostgreSQL-trained models"], ["NLP and graph", "Detects refund pressure, repeated scripts, and connected accounts"], ["Fallback", "Heuristic scoring when a promoted model is unavailable"]].map(([title, body]) => (
              <div key={title} className="rounded-3xl border border-slate-200 bg-white p-4">
                <div className="text-sm font-medium text-slate-800">{title}</div>
                <div className="mt-1 text-sm text-slate-600">{body}</div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Latest decision trace" subtitle="The last submitted return request, when available">
          {latest ? (
            <div className="space-y-2 text-sm text-slate-700">
              {latest.decision_trace.map((item) => (
                <div key={item.stage} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <span>{item.stage}</span>
                  <span className="mono">{String(item.value)}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Submit a return request to populate the decision trace.</div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function RulesPage({ rules = [], setRules }: { rules?: Rule[]; setRules: Dispatch<SetStateAction<Rule[]>> }) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string>();
  const [creating, setCreating] = useState(false);
  const [newRule, setNewRule] = useState({
    name: "High return frequency",
    description: "Customer has unusually high return frequency",
    condition: "customer_return_count_30d >= 5",
    score: 20,
  });

  useEffect(() => {
    setDrafts(Object.fromEntries(rules.map((rule) => [rule.id, String(rule.score)])));
  }, [rules]);

  const enabledCount = rules.filter((rule) => rule.enabled).length;
  const averageScore = rules.length ? (rules.reduce((sum, rule) => sum + rule.score, 0) / rules.length).toFixed(1) : "0.0";
  const disabledCount = rules.length - enabledCount;

  const saveRuleScore = async (rule: Rule) => {
    const nextScore = Number(drafts[rule.id] ?? rule.score);
    if (Number.isNaN(nextScore)) return;
    const updated = await api.updateRule(rule.id, { score: nextScore });
    setRules((current) => current.map((item) => (item.id === rule.id ? updated : item)));
    setMessage(`Updated ${rule.name}`);
  };

  const toggleRule = async (rule: Rule) => {
    const updated = await api.updateRule(rule.id, { enabled: !rule.enabled });
    setRules((current) => current.map((item) => (item.id === rule.id ? updated : item)));
    setMessage(`${updated.enabled ? "Enabled" : "Disabled"} ${rule.name}`);
  };

  const createRule = async () => {
    setCreating(true);
    try {
      const created = await api.createRule(newRule);
      setRules((current) => [created, ...current]);
      setDrafts((current) => ({ ...current, [created.id]: String(created.score) }));
      setMessage(`Created ${created.name}`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Rules"
        title="Rules"
        subtitle="Create, enable, and tune JSON-backed controls for return fraud detection."
      />

      <div className="grid gap-4 xl:grid-cols-[1.12fr_0.88fr]">
        <Panel title="Rule controls" subtitle="Create a rule, review coverage, and keep the active policy set lean.">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Total rules</div>
              <div className="mt-2 text-2xl font-semibold text-slate-950">{rules.length}</div>
            </div>
            <div className="rounded-[22px] border border-emerald-100 bg-emerald-50 p-4">
              <div className="text-[11px] uppercase tracking-[0.24em] text-emerald-700">Enabled</div>
              <div className="mt-2 text-2xl font-semibold text-emerald-700">{enabledCount}</div>
            </div>
            <div className="rounded-[22px] border border-slate-200 bg-white p-4">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Disabled</div>
              <div className="mt-2 text-2xl font-semibold text-slate-950">{disabledCount}</div>
            </div>
            <div className="rounded-[22px] border border-blue-100 bg-blue-50 p-4">
              <div className="text-[11px] uppercase tracking-[0.24em] text-blue-700">Average score</div>
              <div className="mt-2 text-2xl font-semibold text-blue-800">{averageScore}</div>
            </div>
          </div>
          <div className="mt-4 rounded-[22px] border border-slate-200 bg-white p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Create rule</div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <input value={newRule.name} onChange={(event) => setNewRule((value) => ({ ...value, name: event.target.value }))} placeholder="Rule name" className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none" />
              <input value={newRule.condition} onChange={(event) => setNewRule((value) => ({ ...value, condition: event.target.value }))} placeholder="Condition" className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none" />
              <input value={newRule.description} onChange={(event) => setNewRule((value) => ({ ...value, description: event.target.value }))} placeholder="Description" className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none md:col-span-2" />
              <div className="flex flex-wrap items-center gap-3 md:col-span-2">
                <input type="number" value={newRule.score} onChange={(event) => setNewRule((value) => ({ ...value, score: Number(event.target.value) }))} className="w-28 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none" />
                <button onClick={createRule} disabled={creating} className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white disabled:opacity-60">{creating ? "Creating..." : "Create rule"}</button>
                {message ? <span className="text-sm text-slate-600">{message}</span> : null}
              </div>
            </div>
          </div>
        </Panel>

        <Panel title="Policy notes" subtitle="Keep the rule set easy to audit and change.">
          <div className="space-y-3 text-sm text-slate-700">
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">JSON-backed conditions keep the system editable without a custom rule builder.</div>
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">Rules and supervised ML drive the live score. NLP, graph, and anomaly signals remain supporting evidence for the analyst workflow.</div>
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">Analyst feedback should drive future rule tuning when patterns are repeatedly confirmed.</div>
          </div>
        </Panel>
      </div>

      <Panel title="Configured rules" subtitle="Toggle rules and adjust score weights inline.">
        <div className="overflow-auto rounded-[28px] border border-slate-200">
          <table className="min-w-full text-left text-sm">
            <thead className="sticky top-0 bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Condition</th>
                <th className="px-4 py-3">Description</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">State</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} className="border-t border-white/6 bg-white hover:bg-slate-50">
                  <td className="px-4 py-4 font-medium text-slate-900">{rule.name}</td>
                  <td className="px-4 py-4 font-mono text-xs text-slate-600">{rule.condition}</td>
                  <td className="px-4 py-4 text-slate-600">{rule.description || "—"}</td>
                  <td className="px-4 py-4">
                    <input type="number" value={drafts[rule.id] ?? String(rule.score)} onChange={(event) => setDrafts((current) => ({ ...current, [rule.id]: event.target.value }))} className="w-24 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none" />
                  </td>
                  <td className="px-4 py-4">
                    <span className={`rounded-full px-2.5 py-1 text-xs ${rule.enabled ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>{rule.enabled ? "Enabled" : "Disabled"}</span>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <button onClick={() => saveRuleScore(rule)} className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">Save score</button>
                      <button onClick={() => toggleRule(rule)} className="rounded-2xl bg-slate-100 px-3 py-2 text-xs text-slate-700">{rule.enabled ? "Disable" : "Enable"}</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function FeedbackPage({ feedback = [] }: { feedback?: FeedbackRecord[] }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const labelCounts = feedback.reduce<Record<string, number>>((acc, item) => {
    acc[item.confirmed_label] = (acc[item.confirmed_label] ?? 0) + 1;
    return acc;
  }, {});
  const totalItems = feedback.length || 1;
  const fraudLabels = labelCounts.confirmed_fraud ?? 0;
  const falsePositives = labelCounts.false_positive ?? 0;
  const paginated = feedback.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Feedback"
        title="Analyst feedback"
        subtitle="Closed-loop labels that improve the model over time."
      />

      <div className="grid gap-4 xl:grid-cols-[1.08fr_0.92fr]">
        <Panel title="Feedback summary" subtitle="Track how often analysts confirm fraud versus mark false positives.">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Total labels</div>
              <div className="mt-2 text-2xl font-semibold text-slate-950">{feedback.length}</div>
            </div>
            <div className="rounded-[22px] border border-rose-100 bg-rose-50 p-4">
              <div className="text-[11px] uppercase tracking-[0.24em] text-rose-700">Confirmed fraud</div>
              <div className="mt-2 text-2xl font-semibold text-rose-700">{fraudLabels}</div>
            </div>
            <div className="rounded-[22px] border border-emerald-100 bg-emerald-50 p-4">
              <div className="text-[11px] uppercase tracking-[0.24em] text-emerald-700">False positives</div>
              <div className="mt-2 text-2xl font-semibold text-emerald-700">{falsePositives}</div>
            </div>
            <div className="rounded-[22px] border border-blue-100 bg-blue-50 p-4">
              <div className="text-[11px] uppercase tracking-[0.24em] text-blue-700">Coverage</div>
              <div className="mt-2 text-2xl font-semibold text-blue-800">{Math.round((feedback.length / totalItems) * 100)}%</div>
            </div>
          </div>
          <div className="mt-4 rounded-[22px] border border-slate-200 bg-white p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Label mix</div>
            <div className="mt-3 space-y-2 text-sm text-slate-700">
              {Object.entries(labelCounts).length ? Object.entries(labelCounts).map(([label, count]) => (
                <div key={label} className="flex items-center justify-between rounded-2xl bg-slate-50 px-3 py-2">
                  <span className="capitalize">{label.replace(/_/g, ' ')}</span>
                  <span className="font-mono text-slate-700">{count}</span>
                </div>
              )) : <div className="rounded-2xl bg-slate-50 px-3 py-2 text-slate-500">No feedback labels collected yet.</div>}
            </div>
          </div>
        </Panel>

        <Panel title="Learning loop" subtitle="Analyst decisions feed model retraining and rule tuning.">
          <div className="space-y-3 text-sm text-slate-700">
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">Confirmed fraud labels strengthen future fraud recall.</div>
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">False positives help reduce overblocking and improve analyst trust.</div>
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">The retraining job can use labeled cases to refresh the structured model and text features.</div>
          </div>
        </Panel>
      </div>

      <Panel title="Analyst feedback" subtitle="Closed-loop labels that improve the model over time.">
        <div className="space-y-3 md:hidden">
          {paginated.map((item) => (
            <div key={item.id} className="rounded-[22px] border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-900">{item.customer_name}</div>
                  <div className="mt-1 text-xs text-slate-500">Case {item.case_id.slice(0, 8)} · {item.product_name}</div>
                </div>
                <div className="text-right text-xs text-slate-500">{new Date(item.created_at).toLocaleDateString()}</div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2"><span className="text-slate-400">Analyst</span><div className="mt-1 font-medium text-slate-800">{item.analyst_decision}</div></div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2"><span className="text-slate-400">Label</span><div className="mt-1 font-medium text-slate-800">{item.confirmed_label}</div></div>
              </div>
              <div className="mt-3 rounded-2xl bg-slate-50 px-3 py-2 text-sm text-slate-600">{item.notes || "—"}</div>
            </div>
          ))}
        </div>

        <div className="hidden overflow-auto rounded-[28px] border border-slate-200 md:block">
          <table className="min-w-full text-left text-sm">
            <thead className="sticky top-0 bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3">Case</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Analyst Decision</th>
                <th className="px-4 py-3">Confirmed Label</th>
                <th className="px-4 py-3">Notes</th>
                <th className="px-4 py-3">Created At</th>
              </tr>
            </thead>
            <tbody>
              {paginated.map((item) => (
                <tr key={item.id} className="border-t border-white/6 bg-white hover:bg-slate-50">
                  <td className="px-4 py-4 font-mono text-xs text-slate-700">{item.case_id.slice(0, 8)}</td>
                  <td className="px-4 py-4 font-medium text-slate-900">{item.customer_name}</td>
                  <td className="px-4 py-4 text-slate-700">{item.product_name}</td>
                  <td className="px-4 py-4 text-slate-700">{item.analyst_decision}</td>
                  <td className="px-4 py-4 text-slate-700">{item.confirmed_label}</td>
                  <td className="px-4 py-4 text-slate-600">{item.notes || "—"}</td>
                  <td className="px-4 py-4 text-slate-500">{new Date(item.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <Pagination
          currentPage={page}
          totalItems={feedback.length}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
        />
      </Panel>
    </div>
  );
}

function scoreResponseFromCase(detail: CaseDetail): ScoreResponse {
  return {
    return_id: detail.return_id,
    case_id: detail.id,
    customer_risk_score: detail.customer_risk_score,
    risk_score: detail.risk_score,
    risk_level: detail.risk_level,
    decision: detail.decision,
    recommended_action: detail.recommended_action,
    score_breakdown: detail.score_breakdown,
    reason_codes: detail.reason_codes,
    explanation: detail.explanation,
    decision_trace: detail.decision_trace,
    explainability: detail.explainability,
    advanced_signals: detail.advanced_signals,
  };
}

function InvestigationHome({ cases = [] }: { cases?: CaseSummary[] }) {
  const navigate = useNavigate();
  const spotlight = cases.filter((item) => item.risk_level !== "LOW").slice(0, 6);
  const highRisk = spotlight.filter((item) => item.risk_level === 'HIGH').length;

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Investigation workspace"
        title="Investigations"
        subtitle="Select a case to inspect the evidence chain or jump straight into a high-risk return."
      />

      <div className="grid gap-4 xl:grid-cols-[1.08fr_0.92fr]">
        <Panel title="Spotlight queue" subtitle="Quick access to the highest-priority cases.">
          {spotlight.length ? (
            <div className="grid gap-3 md:grid-cols-2">
              {spotlight.map((item) => (
                <button key={item.id} onClick={() => navigate(`/investigations/${item.id}`)} className="rounded-[22px] border border-slate-200 bg-slate-50 p-4 text-left transition hover:bg-white hover:shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-slate-900">{item.customer_name}</div>
                    <span className={`rounded-full px-2.5 py-1 text-xs ${badgeTone(item.risk_level)}`}>{item.risk_level}</span>
                  </div>
                  <div className="mt-2 text-sm text-slate-600">{item.product_name}</div>
                  <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                    <span>{item.decision}</span>
                    <span className="mono">score {item.risk_score.toFixed(1)}</span>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">No cases are loaded yet.</div>
          )}
        </Panel>

        <Panel title="Queue summary" subtitle="Useful context before opening a case.">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Visible cases</div>
              <div className="mt-2 text-2xl font-semibold text-slate-950">{spotlight.length}</div>
            </div>
            <div className="rounded-[22px] border border-rose-100 bg-rose-50 p-4">
              <div className="text-[11px] uppercase tracking-[0.24em] text-rose-700">High risk</div>
              <div className="mt-2 text-2xl font-semibold text-rose-700">{highRisk}</div>
            </div>
          </div>
          <div className="mt-4 space-y-3 text-sm text-slate-700">
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">High-risk cases can be routed straight into the case detail view for evidence review and analyst action.</div>
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">This queue stays intentionally compact so analysts can get to a decision faster.</div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function CaseDetailRoute({ onAction, onLoaded }: { onAction: (decision: string, notes: string, id: string) => Promise<void>; onLoaded?: (value: ScoreResponse) => void }) {
  const params = useParams();
  const id = params.id;
  const [caseDetail, setCaseDetail] = useState<CaseDetail>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    if (!id) {
      setCaseDetail(undefined);
      setLoading(false);
      return undefined;
    }
    setLoading(true);
    api.getCase(id)
      .then((value) => {
        if (!active) return;
        setCaseDetail(value);
        setLoading(false);
        onLoaded?.(scoreResponseFromCase(value));
      })
      .catch(() => {
        if (!active) return;
        setCaseDetail(undefined);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, onLoaded]);

  if (loading) {
    return <Panel title="Investigations" subtitle="Loading case details…">Loading…</Panel>;
  }

  if (!caseDetail) {
    return <Panel title="Investigations" subtitle="Unable to load this case.">Case not found.</Panel>;
  }

  return <InvestigationPage caseDetail={caseDetail} onAction={async (decision, notes) => { if (!id) return; await onAction(decision, notes, id); const refreshed = await api.getCase(id); setCaseDetail(refreshed); onLoaded?.(scoreResponseFromCase(refreshed)); }} />;
}

function FraudRingExplorerPage() {
  const [graphData, setGraphData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.getGraphSummary().then(setGraphData).catch(() => setGraphData(null)).finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Intelligence" title="Graph Signals" subtitle="Connected identities, devices, and patterns across the fraud graph." />
      <Panel title="Graph overview" subtitle="NetworkX-based fraud ring detection with community analysis">
        {loading ? <div className="p-8 text-center text-grey-secondary">Loading graph data...</div> : !graphData ? (
          <div className="p-8 text-center text-grey-secondary">No graph data available.</div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Total nodes" value={Number(graphData.total_nodes ?? 0)} accent="text-purple-primary" />
            <MetricCard label="Total edges" value={Number(graphData.total_edges ?? 0)} accent="text-orange-primary" />
            <MetricCard label="Graph density" value={String(Number(graphData.graph_density ?? 0).toFixed(4))} />
            <MetricCard label="Components" value={Number(graphData.components ?? 0)} accent="text-purple-primary" />
            <MetricCard label="Largest cluster" value={Number(graphData.largest_cluster ?? 0)} accent="text-red-primary" />
            <MetricCard label="Fraud customers" value={Number(graphData.confirmed_fraud_customers ?? 0)} accent="text-red-primary" />
          </div>
        )}
      </Panel>
      <Panel title="Connected clusters" subtitle="Customer clusters with 2+ linked accounts">
        {graphData?.customer_clusters ? (
          <div className="overflow-auto rounded-lg border border-grey-border">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-grey-background text-grey-secondary">
                <tr>
                  <th className="px-4 py-3">#</th>
                  <th className="px-4 py-3">Cluster size</th>
                  <th className="px-4 py-3">Risk level</th>
                </tr>
              </thead>
              <tbody>
                {(graphData.customer_clusters as number[]).map((size, i) => (
                  <tr key={i} className="border-t border-grey-border bg-surface-card">
                    <td className="px-4 py-3 font-mono text-xs text-grey-secondary">{i + 1}</td>
                    <td className="px-4 py-3 font-medium text-grey-primary">{size}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs ${
                        size >= 5 ? 'bg-red-background text-red-primary' :
                        size >= 3 ? 'bg-yellow-background text-yellow-primary' :
                        'bg-green-background text-green-primary'
                      }`}>
                        {size >= 5 ? 'High' : size >= 3 ? 'Medium' : 'Low'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="p-4 text-sm text-grey-secondary">No clusters found.</div>}
      </Panel>
    </div>
  );
}

function EvidenceExplorerPage() {
  const [caseId, setCaseId] = useState("");
  const [evidence, setEvidence] = useState<Array<Record<string, unknown>> | null>(null);
  const [loading, setLoading] = useState(false);

  const loadEvidence = async () => {
    if (!caseId.trim()) return;
    setLoading(true);
    try {
      const detail = await api.getCase(caseId.trim());
      const resp = await fetch('/api/evidence', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scores: { rule_score: detail.score_breakdown.rule_score, structured_ml_score: detail.score_breakdown.structured_ml_score, nlp_score: detail.score_breakdown.nlp_score, anomaly_score: detail.score_breakdown.anomaly_score },
          reason_codes: detail.reason_codes,
          advanced_signals: detail.advanced_signals,
          customer_risk_score: detail.customer_risk_score,
        }),
      });
      const data = await resp.json();
      setEvidence(data.evidence);
    } catch {
      setEvidence(null);
    } finally {
      setLoading(false);
    }
  };

  const categories = evidence ? [...new Set(evidence.map((e) => e.category as string))] : [];

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Intelligence" title="Evidence Explorer" subtitle="Drill into structured evidence for every fraud decision." />
      <Panel title="Search evidence" subtitle="Enter a case ID to generate structured evidence.">
        <div className="flex gap-3">
          <input
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
            placeholder="Enter case UUID"
            className="flex-1 rounded-lg border border-grey-border bg-grey-background px-4 py-3 text-sm outline-none focus:border-purple-border"
          />
          <button onClick={loadEvidence} disabled={loading || !caseId.trim()}
            className="rounded-lg bg-purple-primary px-4 py-3 text-sm font-medium text-white hover:bg-purple-hover disabled:opacity-40">
            {loading ? 'Loading...' : 'Load evidence'}
          </button>
        </div>
      </Panel>

      {evidence && (
        <div className="space-y-4">
          {categories.map((cat) => (
            <Panel key={cat} title={cat.charAt(0).toUpperCase() + cat.slice(1)} subtitle={`${evidence.filter((e) => e.category === cat).length} items`}>
              <div className="space-y-3">
                {evidence.filter((e) => e.category === cat).map((item, i) => (
                  <div key={i} className="flex items-start justify-between gap-4 rounded-lg border border-grey-border bg-grey-background-light p-4">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-grey-primary">{item.label as string}</div>
                      <div className="mt-1 text-xs text-grey-secondary">{item.detail as string}</div>
                      <div className="mt-1 text-[10px] text-grey-placeholder">Source: {item.source as string} &middot; {item.timestamp as string}</div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm font-semibold text-grey-primary">{Number(item.confidence ?? 0).toFixed(0)}%</div>
                      <div className="text-[10px] text-grey-secondary">confidence</div>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          ))}
        </div>
      )}
      {evidence && evidence.length === 0 && (
        <Panel title="No evidence" subtitle="No structured evidence was generated for this case.">
          <div className="p-4 text-sm text-grey-secondary">The case scoring did not produce any evidence items above threshold.</div>
        </Panel>
      )}
    </div>
  );
}

function TimelineExplorerPage() {
  const { id } = useParams();
  const [events, setEvents] = useState<Array<{ label: string; time: string; type: string; detail: string }> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    api.getCaseTimeline(id).then((data) => setEvents(data.events)).catch(() => setEvents(null)).finally(() => setLoading(false));
  }, [id]);

  const typeColors: Record<string, string> = {
    customer: 'border-purple-border bg-purple-background text-purple-primary',
    order: 'border-blue-96 bg-blue-96 text-blue-58',
    return: 'border-yellow-border bg-yellow-background text-yellow-primary',
    communication: 'border-purple-border-light bg-purple-background text-purple-primary',
    decision: 'border-green-border bg-green-background text-green-primary',
    alert: 'border-red-border bg-red-background text-red-primary',
    review: 'border-grey-border bg-grey-background text-grey-primary',
  };

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Intelligence" title="Timeline Explorer" subtitle="Fraud event timeline for case {id}." />
      <Panel title="Case timeline" subtitle={`${events?.length ?? 0} events`}>
        {loading ? <div className="p-8 text-center text-grey-secondary">Loading timeline...</div> :
         !events ? <div className="p-4 text-sm text-grey-secondary">Timeline not available.</div> : (
          <div className="relative">
            <div className="absolute left-4 top-0 h-full w-px bg-grey-border" />
            <div className="space-y-4">
              {events.map((event, i) => (
                <div key={i} className="relative pl-12">
                  <span className={`absolute left-2.5 flex size-3 -translate-x-1/2 items-center justify-center rounded-full ring-2 ring-white ${typeColors[event.type] ?? 'bg-grey-background'}`} />
                  <div className="rounded-lg border border-grey-border bg-surface-card p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${typeColors[event.type] ?? 'bg-grey-background text-grey-secondary'}`}>{event.type}</span>
                        <div className="mt-1 text-sm font-medium text-grey-primary">{event.label}</div>
                        {event.detail && <div className="mt-1 text-xs text-grey-secondary">{event.detail}</div>}
                      </div>
                      <div className="shrink-0 text-right">
                        <div className="text-xs text-grey-placeholder">{new Date(event.time).toLocaleDateString()}</div>
                        <div className="text-[10px] text-grey-placeholder">{new Date(event.time).toLocaleTimeString()}</div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

function PatternLibraryPage() {
  const [patterns, setPatterns] = useState<Array<Record<string, unknown>>>([]);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    api.getPatterns().then((data) => setPatterns(data.patterns)).catch(() => undefined);
  }, []);

  const severityColor = (s: string) =>
    s === 'CRITICAL' ? 'bg-red-background text-red-primary' :
    s === 'HIGH' ? 'bg-red-background text-red-primary' :
    s === 'MEDIUM' ? 'bg-yellow-background text-yellow-primary' :
    'bg-green-background text-green-primary';

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Intelligence" title="Fraud Pattern Library" subtitle={`${patterns.length} reusable fraud patterns for detection and response.`} />
      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel title="Patterns" subtitle="Click a pattern for details.">
          <div className="space-y-3">
            {patterns.map((p) => (
              <button key={p.id as string} onClick={() => setSelected(p)}
                className={`w-full rounded-lg border p-4 text-left transition ${
                  selected?.id === p.id ? 'border-purple-border bg-purple-background' : 'border-grey-border bg-surface-card hover:bg-grey-background-light'
                }`}>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-grey-primary">{p.name as string}</div>
                    <div className="mt-0.5 text-xs text-grey-secondary">{p.description as string}</div>
                  </div>
                  <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-medium ${severityColor(p.severity as string)}`}>
                    {p.severity as string}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </Panel>
        <Panel title="Pattern details" subtitle={selected ? (selected.name as string) : 'Select a pattern'}>
          {selected ? (
            <div className="space-y-4">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">ID</div>
                <div className="mt-1 font-mono text-sm text-grey-primary">{selected.id as string}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Rules</div>
                <div className="mt-2 space-y-1">
                  {(selected.rules as string[]).map((r, i) => (
                    <div key={i} className="rounded bg-grey-background px-3 py-1.5 font-mono text-xs text-grey-primary">{r}</div>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Recommended actions</div>
                <div className="mt-2 space-y-1">
                  {(selected.recommended_actions as string[]).map((a, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm text-grey-primary">
                      <span className="size-1.5 rounded-full bg-purple-primary" />
                      {a}
                    </div>
                  ))}
                </div>
              </div>
              {(selected.ml_features as string[]).length > 0 && (
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">ML Features</div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {(selected.ml_features as string[]).map((f, i) => (
                      <span key={i} className="rounded-full bg-grey-background px-2 py-0.5 text-xs text-grey-secondary">{f}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-4 text-sm text-grey-secondary">Select a pattern to view details.</div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function GraphAnalyticsPage() {
  const [graphData, setGraphData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.getGraphSummary().then(setGraphData).catch(() => setGraphData(null)).finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Analytics" title="Network Graph" subtitle="Fraud network topology and community analysis." />
      <div className="grid gap-4 sm:grid-cols-3">
        <MetricCard label="Network size" value={String(Number(graphData?.total_nodes ?? 0) + Number(graphData?.total_edges ?? 0))} accent="text-purple-primary" subtext="nodes + edges" />
        <MetricCard label="Avg. cluster size" value={graphData?.customer_clusters ? (graphData.customer_clusters as number[]).length > 0 ? ((graphData.customer_clusters as number[]).reduce((a, b) => a + b, 0) / (graphData.customer_clusters as number[]).length).toFixed(1) : '0' : '—'} accent="text-orange-primary" />
        <MetricCard label="Fraud concentration" value={graphData ? `${(Number(graphData.confirmed_fraud_customers ?? 0) / Math.max(Number(graphData.total_nodes ?? 1), 1) * 100).toFixed(1)}%` : '—'} />
      </div>
      <Panel title="Metrics" subtitle="Graph topology statistics">
        <div className="space-y-3">
          {[
            ["Total nodes", "Network nodes (customers, orders, returns, entities)", graphData?.total_nodes],
            ["Total edges", "Connections between entities", graphData?.total_edges],
            ["Graph density", "How connected the network is (0-1)", graphData?.graph_density],
            ["Connected components", "Disconnected subgraphs", graphData?.components],
            ["Largest cluster", "Biggest connected customer group", graphData?.largest_cluster],
            ["Fraud customers", "Confirmed fraud accounts", graphData?.confirmed_fraud_customers],
          ].map(([label, desc, value]) => (
            <div key={label as string} className="flex items-center justify-between gap-4 rounded-lg border border-grey-border bg-grey-background-light p-4">
              <div>
                <div className="text-sm font-medium text-grey-primary">{label as string}</div>
                <div className="mt-0.5 text-xs text-grey-secondary">{desc as string}</div>
              </div>
              <div className="shrink-0 text-lg font-semibold text-grey-primary">{String(value ?? '—')}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function ImportBatchMonitor() {
  const [jobs, setJobs] = useState<Record<string, unknown>[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  const loadJobs = async () => {
    setJobsLoading(true);
    try {
      const res = await api.getImportJobs(0, 24);
      setJobs(res as Record<string, unknown>[]);
    } catch {
      setJobs([]);
    } finally {
      setJobsLoading(false);
    }
  };

  useEffect(() => { loadJobs(); }, []);

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Data Import"
        title="Batch Monitor"
        subtitle="Completed load chunks recorded in the database. Refresh to see the latest batches land while the loader runs."
      />
      <Panel title="Batch history" subtitle="Each row is a completed loader batch or import job.">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="text-sm text-slate-600">Shows the latest `import_jobs` rows created by the loader or Kaggle import flow.</div>
          <button onClick={loadJobs} className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            {jobsLoading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Batches</div>
            <div className="mt-2 text-lg font-semibold text-slate-900">{jobs.length}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Rows loaded</div>
            <div className="mt-2 text-lg font-semibold text-slate-900">{jobs.reduce((sum, job) => sum + Number(job.processed_rows ?? 0), 0).toLocaleString()}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Latest batch</div>
            <div className="mt-2 text-lg font-semibold text-slate-900">{String(jobs[0]?.status ?? '—')}</div>
          </div>
        </div>
        <div className="mt-4 overflow-x-auto rounded-3xl border border-slate-200">
          <table className="min-w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Rows</th>
                <th className="px-4 py-3 font-medium">Batch info</th>
              </tr>
            </thead>
            <tbody>
              {jobs.length ? jobs.map((job) => (
                <tr key={String(job.id)} className="border-t border-slate-100 bg-white">
                  <td className="px-4 py-3 text-slate-700">{String(job.created_at ?? '—')}</td>
                  <td className="px-4 py-3 text-slate-700">{String(job.source_name ?? '—')}</td>
                  <td className="px-4 py-3 text-slate-700">{String(job.status ?? '—')}</td>
                  <td className="px-4 py-3 text-slate-700">{`${Number(job.processed_rows ?? 0).toLocaleString()} / ${Number(job.total_rows ?? 0).toLocaleString()}`}</td>
                  <td className="px-4 py-3 text-slate-700">{job.metadata_json ? JSON.stringify(job.metadata_json) : '—'}</td>
                </tr>
              )) : (
                <tr><td className="px-4 py-6 text-slate-500" colSpan={5}>No completed batches yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function KaggleImportPage() {
  const [datasetInput, setDatasetInput] = useState("");
  const [maxRows, setMaxRows] = useState(5000);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | string | null>(null);
  const [modelFields, setModelFields] = useState<Record<string, Record<string, unknown>>>({});
  const [jobs, setJobs] = useState<Record<string, unknown>[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  useEffect(() => {
    fetch('/api/kaggle/model-fields').then((r) => r.json()).then((d) => setModelFields(d.model_fields as Record<string, Record<string, unknown>>)).catch(() => undefined);
  }, []);

  const loadJobs = async () => {
    setJobsLoading(true);
    try {
      const res = await api.getImportJobs(0, 12);
      setJobs(res as Record<string, unknown>[]);
    } catch {
      setJobs([]);
    } finally {
      setJobsLoading(false);
    }
  };

  useEffect(() => { loadJobs(); }, []);

  const handlePreview = async () => {
    const datasetId = datasetInput.trim();
    if (!datasetId) return;
    setPreviewLoading(true);
    setPreviewError(null);
    setPreview(null);
    setResult(null);
    try {
      const res = await api.previewKaggle(datasetId);
      if (res.error) { setPreviewError(String(res.error)); return; }
      setPreview(res);
      setMapping((res.auto_mapping ?? {}) as Record<string, string>);
    } catch (e) {
      setPreviewError(String(e));
    } finally {
      setPreviewLoading(false);
    }
  };

  const setMap = (target: string, source: string) => {
    setMapping((prev) => ({ ...prev, [target]: source }));
  };
  const clearMap = (target: string) => {
    setMapping((prev) => { const { [target]: _, ...rest } = prev; return rest; });
  };

  const usableColumns = preview?.columns as string[] ?? [];

  const handleImport = async () => {
    const datasetId = datasetInput.trim();
    if (!datasetId || Object.keys(mapping).length === 0) return;
    setImporting(true);
    setResult(null);
    try {
      const res = await api.importKaggleWithMapping(datasetId, mapping, maxRows);
      setResult(res);
      void loadJobs();
    } catch (e) {
      setResult(String(e));
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Data Import"
        title="Kaggle Dataset Import"
        subtitle="Enter any Kaggle dataset ID, preview its schema, configure column mappings, then import. The batch monitor below shows completed load chunks from the database."
      />

      <Panel title="Dataset" subtitle="Enter a Kaggle dataset identifier (e.g. akrambelha/global-e-commerce-dataset-1m-records-20242026)">
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            value={datasetInput}
            onChange={(e) => setDatasetInput(e.target.value)}
            placeholder="username/dataset-name"
            className="flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono text-sm outline-none focus:border-purple-300"
          />
          <div className="flex gap-2">
            <button onClick={handlePreview} disabled={previewLoading || !datasetInput.trim()}
              className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white shadow-sm hover:bg-slate-800 disabled:opacity-40">
              {previewLoading ? 'Downloading...' : 'Preview'}
            </button>
            <input type="number" value={maxRows}
              onChange={(e) => setMaxRows(Number(e.target.value))}
              min={100} max={100000} step={100}
              className="w-24 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm outline-none" title="Max rows to import" />
          </div>
        </div>
      </Panel>

      {previewError && (
        <div className="rounded-3xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{previewError}</div>
      )}

      {preview && !previewError && (
        <>
          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="Schema" subtitle={`${(preview.columns as string[]).length} columns detected`}>
              <div className="max-h-64 space-y-1 overflow-y-auto font-mono text-xs">
                {(preview.columns as string[]).map((col) => {
                  const dt = (preview.dtypes as Record<string, string>)[col] ?? 'unknown';
                  const mappedTo = Object.entries(mapping).find(([, v]) => v === col)?.[0];
                  return (
                    <div key={col} className="flex items-center justify-between gap-2 rounded bg-slate-50 px-3 py-1.5">
                      <div>
                        <span className="text-slate-800">{col}</span>
                        <span className="ml-2 text-slate-400">({dt})</span>
                      </div>
                      {mappedTo && (
                        <span className="rounded bg-purple-100 px-2 py-0.5 text-purple-700">→ {mappedTo}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </Panel>

            <Panel title="Sample rows" subtitle="First rows of the dataset">
              <div className="overflow-auto max-h-64">
                <table className="min-w-full text-left text-xs">
                  <thead className="sticky top-0 bg-slate-100 text-slate-600">
                    <tr>
                      {(preview.columns as string[]).slice(0, 8).map((col) => (
                        <th key={col} className="px-2 py-1.5 font-medium truncate max-w-[120px]">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(preview.sample_rows as Array<Record<string, string>>).slice(0, 5).map((row, ri) => (
                      <tr key={ri} className="border-t border-slate-100">
                        {(preview.columns as string[]).slice(0, 8).map((col) => (
                          <td key={col} className="px-2 py-1.5 truncate max-w-[120px] text-slate-700">{row[col] ?? '—'}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>

          <Panel title="Column Mapping" subtitle="Assign source columns to model fields. At minimum map customer_id, order_id, and product_name.">
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {Object.entries(modelFields).filter(([, info]) => (info as Record<string, unknown>).required).map(([target, info]) => {
                const cur = mapping[target] ?? '';
                return (
                  <div key={target} className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-slate-900">
                        {target} {String((info as Record<string, unknown>).required) === 'true' && <span className="text-red-500">*</span>}
                      </div>
                      <div className="text-xs text-slate-500">{String((info as Record<string, unknown>).description ?? '')}</div>
                    </div>
                    <select value={cur} onChange={(e) => { const v = e.target.value; v ? setMap(target, v) : clearMap(target); }}
                      className="min-w-[160px] rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none">
                      <option value="">— skip —</option>
                      {usableColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                    </select>
                    <div className="text-xs text-slate-400">({(info as Record<string, unknown>).type as string})</div>
                  </div>
                );
              })}
              <details className="rounded-2xl border border-slate-200 p-3">
                <summary className="cursor-pointer text-sm font-medium text-slate-700">Optional fields</summary>
                <div className="mt-3 space-y-3">
                  {Object.entries(modelFields).filter(([, info]) => !(info as Record<string, unknown>).required).map(([target, info]) => {
                    const cur = mapping[target] ?? '';
                    return (
                      <div key={target} className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-100 bg-white p-2.5">
                        <div className="min-w-0 flex-1">
                          <div className="text-sm text-slate-800">{target}</div>
                          <div className="text-xs text-slate-500">{String((info as Record<string, unknown>).description ?? '')}</div>
                        </div>
                        <select value={cur} onChange={(e) => { const v = e.target.value; v ? setMap(target, v) : clearMap(target); }}
                          className="min-w-[140px] rounded-xl border border-slate-200 bg-white px-2 py-1.5 text-xs outline-none">
                          <option value="">— skip —</option>
                          {usableColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                        </select>
                        <div className="text-xs text-slate-400">({(info as Record<string, unknown>).type as string})</div>
                      </div>
                    );
                  })}
                </div>
              </details>
            </div>
            <div className="mt-4 flex items-center justify-between gap-3">
              <div className="text-sm text-slate-600">
                {Object.keys(mapping).length} field(s) mapped
                {!mapping.customer_id ? <span className="ml-2 text-red-500">(customer_id required)</span> : ''}
                {!mapping.order_id ? <span className="ml-2 text-red-500">(order_id required)</span> : ''}
                {!mapping.product_name ? <span className="ml-2 text-red-500">(product_name required)</span> : ''}
              </div>
              <button onClick={handleImport} disabled={importing || !mapping.customer_id || !mapping.order_id || !mapping.product_name}
                className="rounded-2xl bg-slate-950 px-6 py-3 text-sm font-medium text-white shadow-sm hover:bg-slate-800 disabled:opacity-40">
                {importing ? 'Importing...' : `Import up to ${maxRows} rows`}
              </button>
            </div>
          </Panel>
        </>
      )}

      {result && (
        <Panel title="Import result" subtitle="Status of the dataset import.">
          {typeof result === 'string' ? (
            <div className="rounded-3xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{result}</div>
          ) : (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  ["Customers", (result as Record<string, unknown>).customers],
                  ["Orders", (result as Record<string, unknown>).orders],
                  ["Returns (flagged)", (result as Record<string, unknown>).returns_with_flag],
                  ["Cases created", (result as Record<string, unknown>).cases_created],
                  ["Fraud scores", (result as Record<string, unknown>).fraud_scores],
                  ["Files processed", (result as Record<string, unknown>).files_processed],
                  ["Skipped", (result as Record<string, unknown>).skipped_no_return_flag],
                ].map(([label, value]) => (
                  <div key={label as string} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">{label as string}</div>
                    <div className="mt-2 text-lg font-semibold text-slate-900">{String(value ?? '—')}</div>
                  </div>
                ))}
              </div>
              <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
                Import complete: {String((result as Record<string, unknown>).cases_created ?? 0)} fraud cases created.
              </div>
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}

function ModuleDashboardPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [seedResult, setSeedResult] = useState<string | null>(null);
  const [retrainResult, setRetrainResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const d = await api.getModuleDashboard();
      setData(d);
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleSeed = async () => {
    setSeedResult('Seeding...');
    try {
      const result = await api.seedModuleData();
      setSeedResult(`Seeded OK: ${JSON.stringify(result.results)}`);
      await load();
    } catch (e) {
      setSeedResult(`Seed failed: ${e}`);
    }
  };

  const handleRetrain = async () => {
    setRetrainResult('Retraining...');
    try {
      const result = await api.retrain();
      const r = result as Record<string, unknown>;
      const m = (r.metrics ?? {}) as Record<string, unknown>;
      setRetrainResult(`Retrained: ${String(r.model_version ?? '?')}  prec=${String(m.precision ?? '—')}  rec=${String(m.recall ?? '—')}`);
      await load();
    } catch (e) {
      setRetrainResult(`Retrain failed: ${e}`);
    }
  };

  const metrics = data?.monitoring as Record<string, unknown> | undefined;
  const embeddings = data?.embeddings as Record<string, unknown> | undefined;
  const models = data?.models as Record<string, unknown> | undefined;
  const merchants = data?.merchants as Record<string, unknown> | undefined;

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="System"
        title="Module Dashboard"
        subtitle="Status of all fraud intelligence modules."
        action={
          <div className="flex gap-2">
            <button onClick={handleRetrain} className="rounded-2xl bg-slate-950 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-slate-800">
              Retrain models
            </button>
            <button onClick={handleSeed} className="rounded-2xl bg-slate-950 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-slate-800">
              Re-seed module data
            </button>
          </div>
        }
      />
      {seedResult && (
        <div className="rounded-[22px] border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">{seedResult}</div>
      )}
      {retrainResult && (
        <div className="rounded-[22px] border border-green-200 bg-green-50 p-4 text-sm text-green-800">{retrainResult}</div>
      )}
      {seedResult && (
        <div className="rounded-[22px] border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">{seedResult}</div>
      )}
      {loading ? (
        <Panel title="Loading" subtitle="Fetching module status...">
          <div className="p-8 text-center text-grey-secondary">Loading...</div>
        </Panel>
      ) : (
        <div className="grid gap-4 xl:grid-cols-3">
          <Panel title="Embeddings" subtitle={`${Number(embeddings?.size ?? 0)} vectors indexed`}>
            <div className="space-y-3">
              <MetricCard label="Vector count" value={Number(embeddings?.size ?? 0)} accent="text-purple-primary" />
              <div className="rounded-lg border border-grey-border bg-grey-background-light p-3 text-sm">
                <span className="text-grey-secondary">Model: </span>
                <span className="font-mono text-grey-primary">{String(embeddings?.active_model ?? '—')}</span>
              </div>
            </div>
          </Panel>
          <Panel title="Model Registry" subtitle="Versioned supervised models by category">
            <div className="space-y-2">
              {models ? Object.entries(models).map(([cat, info]) => {
                const i = info as Record<string, unknown>;
                return (
                  <div key={cat} className="flex items-center justify-between rounded-lg border border-grey-border bg-grey-background-light p-3">
                    <span className="text-sm font-medium text-grey-primary capitalize">{cat}</span>
                    <div className="text-right text-xs text-grey-secondary">
                      <div className="font-mono text-grey-primary">v{i.current_version as string ?? '—'}</div>
                      <div>{String(i.versions ?? 0)} versions</div>
                    </div>
                  </div>
                );
              }) : <div className="text-sm text-grey-secondary">No model data.</div>}
            </div>
          </Panel>
          <Panel title="Model Health" subtitle="Performance metrics">
            <div className="space-y-3">
              <MetricCard label="Avg prediction" value={Number(metrics?.avg_prediction ?? 0).toFixed(1)} />
              <MetricCard label="Avg latency" value={`${Number(metrics?.avg_latency_ms ?? 0).toFixed(0)} ms`} accent="text-orange-primary" />
              <MetricCard label="Samples" value={Number(metrics?.samples ?? 0)} />
            </div>
          </Panel>
        </div>
      )}
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Merchants" subtitle={`${Number(merchants?.count ?? 0)} configured`}>
          <div className="flex flex-wrap gap-2">
            {(merchants?.ids as string[] ?? []).map((id: string) => (
              <span key={id} className="rounded-full bg-purple-background px-3 py-1 text-xs text-purple-primary">{id}</span>
            ))}
          </div>
        </Panel>
        <Panel title="Alert Rules" subtitle="Configured alert triggers">
          <MetricCard label="Alert rules" value={Number(data?.alert_rules ?? 0)} accent="text-red-primary" />
        </Panel>
      </div>
    </div>
  );
}

function AlertsPage() {
  const [rules, setRules] = useState<Array<Record<string, unknown>>>([]);
  const [evalResult, setEvalResult] = useState<string | null>(null);
  const [evalPayload, setEvalPayload] = useState('{"risk_score": 85, "risk_level": "HIGH", "product_value": 420}');

  useEffect(() => {
    fetch('/api/alerts/rules').then(r => r.json()).then(d => setRules(d.rules ?? [])).catch(() => {});
  }, []);

  const runEval = async () => {
    try {
      const res = await api.evaluateAlerts(JSON.parse(evalPayload));
      setEvalResult(`Alerts fired: ${(res.alerts_fired ?? []).length} — ${JSON.stringify(res.alerts_fired.map(a => a.rule ?? a.name ?? a.alert ?? '?'))}`);
    } catch { setEvalResult('Evaluation failed'); }
  };

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Control" title="Alerts" subtitle="Configured alert rules and live evaluation." />
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Alert rules" subtitle={`${rules.length} rules configured`}>
          <div className="space-y-2">
            {rules.length ? rules.map((rule, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-grey-border bg-grey-background-light p-3">
                <div>
                  <div className="text-sm font-medium text-grey-primary">{String(rule.name ?? 'Rule ' + (i + 1))}</div>
                  <div className="text-xs text-grey-secondary">{String(rule.description ?? rule.condition ?? '')}</div>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-xs ${String(rule.severity ?? 'medium') === 'critical' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>
                  {String(rule.severity ?? 'medium')}
                </span>
              </div>
            )) : <div className="text-sm text-grey-secondary">No alert rules configured.</div>}
          </div>
        </Panel>
        <Panel title="Live evaluation" subtitle="Test a payload against alert rules.">
          <textarea value={evalPayload} onChange={e => setEvalPayload(e.target.value)} className="min-h-[180px] w-full rounded-lg border border-grey-border bg-grey-background p-3 font-mono text-xs outline-none" />
          <button onClick={runEval} className="mt-3 rounded-2xl bg-slate-950 px-4 py-2.5 text-sm font-medium text-white">Evaluate</button>
          {evalResult && <div className="mt-3 rounded-lg border border-grey-border bg-grey-background-light p-3 text-sm text-grey-primary">{evalResult}</div>}
        </Panel>
      </div>
    </div>
  );
}

function MerchantsPage() {
  const [merchantIds, setMerchantIds] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);

  useEffect(() => { api.getMerchants().then(d => setMerchantIds(d.merchants)).catch(() => {}); }, []);

  const loadConfig = async (id: string) => {
    setSelected(id);
    try { const c = await api.getMerchantConfig(id); setConfig(c as Record<string, unknown>); }
    catch { setConfig(null); }
  };

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Control" title="Merchants" subtitle={`${merchantIds.length} configured merchant profiles.`} />
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Merchant profiles" subtitle="Click a merchant to view its configuration.">
          <div className="space-y-2">
            {merchantIds.length ? merchantIds.map((id) => (
              <button key={id} onClick={() => loadConfig(id)}
                className={`w-full rounded-lg border p-3 text-left text-sm transition-colors ${selected === id ? 'border-purple-border bg-purple-background text-purple-primary' : 'border-grey-border bg-grey-background-light text-grey-primary hover:bg-grey-background'}`}>
                {id}
              </button>
            )) : <div className="text-sm text-grey-secondary">No merchants configured.</div>}
          </div>
        </Panel>
        <Panel title={selected ? `Config: ${selected}` : 'Merchant config'} subtitle="Risk thresholds, scoring weights, and rules.">
          {config ? (
            <div className="space-y-3">
              {Object.entries(config).map(([key, value]) => (
                <div key={key} className="rounded-lg border border-grey-border bg-grey-background-light p-3">
                  <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">{key.replace(/_/g, ' ')}</div>
                  <div className="mt-1 text-sm font-mono text-grey-primary">{typeof value === 'object' ? JSON.stringify(value, null, 1) : String(value)}</div>
                </div>
              ))}
            </div>
          ) : <div className="text-sm text-grey-secondary">{selected ? 'Failed to load config.' : 'Select a merchant to view config.'}</div>}
        </Panel>
      </div>
    </div>
  );
}

function ModelsPage() {
  const [models, setModels] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try { const d = await api.getModels(); setModels(d as Record<string, unknown>); }
    catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="System" title="Model Registry" subtitle="Browse and manage versioned supervised models across all categories." />
      {loading ? (
        <Panel title="Loading" subtitle="Fetching model registry..."><div className="p-8 text-center text-grey-secondary">Loading...</div></Panel>
      ) : models ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Object.entries(models).map(([cat, info]) => {
            const i = info as Record<string, unknown>;
            const versions = (i.versions ?? []) as Array<Record<string, unknown>>;
            const current = String(i.current ?? i.current_version ?? '—');
            return (
              <Panel key={cat} title={cat.charAt(0).toUpperCase() + cat.slice(1)} subtitle={`Current: v${current}`}>
                <div className="space-y-2">
                  {versions.length ? versions.map((v, idx) => {
                    const ver = String(v.version ?? idx);
                    const meta = v.metadata as Record<string, unknown> | undefined;
                    const desc = String(meta?.description ?? v.description ?? '');
                    return (
                      <div key={idx} className={`flex items-center justify-between rounded-lg border p-3 ${ver === current ? 'border-purple-border bg-purple-background' : 'border-grey-border bg-grey-background-light'}`}>
                        <span className="text-sm font-mono text-grey-primary">v{ver}</span>
                        <span className="text-xs text-grey-secondary">{desc}</span>
                      </div>
                    );
                  }) : <div className="text-sm text-grey-secondary">No versions saved.</div>}
                </div>
              </Panel>
            );
          })}
        </div>
      ) : <Panel title="Error" subtitle="Could not load models."><div className="p-8 text-center text-grey-secondary">Failed to load model registry.</div></Panel>}
    </div>
  );
}

function MonitoringPage() {
  const [perf, setPerf] = useState<Record<string, unknown> | null>(null);
  const [drift, setDrift] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const p = await api.getMonitoringPerformance();
      setPerf(p as Record<string, unknown>);
    } catch {}
    try {
      const d = await (await fetch('/api/monitoring/drift')).json();
      setDrift(d.message ?? String(d.drift_checked ?? ''));
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const runDrift = async () => {
    setDrift('Checking drift...');
    try {
      const d = await (await fetch('/api/monitoring/drift/check', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({reference: [{rule_score: 25, structured_ml_score: 30, nlp_score: 20, anomaly_score: 15}], current: [{rule_score: 65, structured_ml_score: 78, nlp_score: 84, anomaly_score: 73}]})})).json();
      setDrift(`Drift detected: ${String(d.drift_detected)} — columns: ${(d.drifted_columns ?? []).join(', ') || 'none'}`);
    } catch { setDrift('Drift check failed.'); }
  };

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="System" title="Model Health" subtitle="Performance metrics and data drift detection."
        action={<button onClick={runDrift} className="rounded-2xl bg-slate-950 px-4 py-2.5 text-sm font-medium text-white shadow-sm">Check drift</button>}
      />
      {loading ? (
        <Panel title="Loading" subtitle="Fetching monitoring data..."><div className="p-8 text-center text-grey-secondary">Loading...</div></Panel>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          <Panel title="Model performance" subtitle="Prediction metrics across recent samples.">
            <div className="grid gap-3 sm:grid-cols-3">
              <MetricCard label="Avg prediction" value={Number(perf?.avg_prediction ?? 0).toFixed(1)} />
              <MetricCard label="Avg latency" value={`${Number(perf?.avg_latency_ms ?? 0).toFixed(0)} ms`} accent="text-orange-primary" />
              <MetricCard label="Samples" value={Number(perf?.samples ?? 0)} />
            </div>
            {(perf?.recent_predictions as Array<Record<string, unknown>> ?? []).length > 0 && (
              <div className="mt-4 rounded-lg border border-grey-border bg-grey-background-light p-3">
                <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Recent predictions</div>
                <div className="mt-2 space-y-1 text-xs text-grey-primary">
                  {((perf?.recent_predictions ?? []) as Array<Record<string, unknown>>).slice(0, 10).map((p, i) => (
                    <div key={i} className="flex items-center justify-between rounded bg-surface-card px-2 py-1">
                      <span>pred={Number(p.prediction ?? 0).toFixed(1)}</span>
                      <span>actual={Number(p.actual ?? 0).toFixed(1)}</span>
                      <span>{Number(p.latency_ms ?? 0).toFixed(0)}ms</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Panel>
          <Panel title="Data drift" subtitle="Distribution shift detection.">
            {drift ? (
              <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-primary">{drift}</div>
            ) : (
              <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-secondary">Click "Check drift" to run a drift analysis.</div>
            )}
            <div className="mt-4 rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-secondary">Drift monitoring compares reference vs. current score distributions and flags columns that have shifted beyond the configured threshold.</div>
          </Panel>
        </div>
      )}
    </div>
  );
}

function NlpAnalyzerPage() {
  const [text, setText] = useState('I want a refund immediately, or I will open a chargeback.');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const analyze = async () => {
    setLoading(true);
    try {
      const res = await (await fetch('/api/nlp/analyze', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ text }) })).json();
      setResult(res as Record<string, unknown>);
    } catch { setResult({ error: 'Analysis failed' }); }
    setLoading(false);
  };

  const analysis = result?.analysis as Record<string, unknown> | undefined;
  const fraudScore = String(analysis?.fraud_score ?? result?.fraud_score ?? '—');
  const phrases = (analysis?.flagged_phrases ?? result?.flagged_phrases ?? []) as string[];

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Intelligence" title="Text Signals" subtitle="Analyze return reason text for fraud signals, urgency, and manipulation." />
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Input text" subtitle="Enter a customer's return reason or chat transcript.">
          <textarea value={text} onChange={e => setText(e.target.value)} className="min-h-[200px] w-full rounded-lg border border-grey-border bg-grey-background p-3 text-sm outline-none" />
          <button onClick={analyze} disabled={loading} className="mt-3 rounded-2xl bg-slate-950 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">{loading ? 'Analyzing...' : 'Analyze'}</button>
        </Panel>
        <Panel title="Analysis result" subtitle="Fraud signals, sentiment, and flagged phrases.">
          {result ? (
            <div className="space-y-3">
              {result.error ? (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{String(result.error)}</div>
              ) : (
                <>
                  <div className="rounded-lg border border-grey-border bg-grey-background-light p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Fraud score</div>
                    <div className="mt-1 text-2xl font-semibold text-grey-primary">{fraudScore}</div>
                  </div>
                  <div className="rounded-lg border border-grey-border bg-grey-background-light p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Flagged phrases</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {phrases.length ? phrases.map((p, i) => (
                        <span key={i} className="rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs text-red-700">{p}</span>
                      )) : <span className="text-sm text-grey-secondary">No phrases flagged.</span>}
                    </div>
                  </div>
                  <div className="rounded-lg border border-grey-border bg-grey-background-light p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-grey-secondary">Full analysis</div>
                    <div className="mt-2 text-sm text-grey-primary font-mono whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</div>
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="rounded-lg border border-grey-border bg-grey-background-light p-4 text-sm text-grey-secondary">Enter text and click Analyze to see results.</div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function EmbeddingsPage() {
  const [query, setQuery] = useState('empty box refund request');
  const [results, setResults] = useState<Array<{ score: number; metadata: Record<string, unknown> }>>([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<Record<string, unknown>>({});

  useEffect(() => { api.getEmbeddingStats().then(d => setStats(d as Record<string, unknown>)).catch(() => {}); }, []);

  const search = async () => {
    setLoading(true);
    try {
      const res = await api.searchEmbeddings(query, 10);
      setResults(res.results);
    } catch {}
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Intelligence" title="Embeddings Explorer" subtitle={`${String(stats.size ?? '?')} vectors · ${String(stats.active_model ?? '—')}`} />
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Semantic search" subtitle="Find similar cases by natural language query.">
          <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && search()} placeholder="Search for similar cases..." className="w-full rounded-lg border border-grey-border bg-grey-background px-4 py-3 text-sm outline-none" />
          <button onClick={search} disabled={loading} className="mt-3 rounded-2xl bg-slate-950 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">{loading ? 'Searching...' : 'Search'}</button>
        </Panel>
        <Panel title="Results" subtitle={`${results.length} similar cases`}>
          <div className="space-y-2">
            {results.length ? results.map((r, i) => (
              <div key={i} className="rounded-lg border border-grey-border bg-grey-background-light p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-grey-primary">{String(r.metadata?.customer_name ?? r.metadata?.case_id ?? 'Case ' + (i + 1)).slice(0, 40)}</span>
                  <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs text-purple-700">{r.score.toFixed(3)}</span>
                </div>
                <div className="mt-1 text-xs text-grey-secondary">{String(r.metadata?.return_reason ?? r.metadata?.decision ?? '')}</div>
              </div>
            )) : <div className="text-sm text-grey-secondary">Enter a query and click Search.</div>}
          </div>
        </Panel>
      </div>
    </div>
  );
}

const fmtMoney = (v: unknown) =>
  typeof v === 'number' && Number.isFinite(v)
    ? v.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
    : '—';
const fmtDate = (v: unknown) => (v ? new Date(String(v)).toLocaleString() : '—');
const shortId = (v: unknown) => (v ? String(v).slice(0, 8) : '—');
const num = (v: unknown) => (typeof v === 'number' ? v : Number(v) || 0);
const str = (v: unknown) => (v === null || v === undefined || v === '' ? '—' : String(v));

function OrdersBrowsePage() {
  const [data, setData] = useState<RecordsPage | null>(null);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [qInput, setQInput] = useState('');
  const [q, setQ] = useState('');
  const [category, setCategory] = useState('');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [res, st] = await Promise.all([
        api.getOrders({ skip: (page - 1) * pageSize, limit: pageSize, q: q || undefined, category: category || undefined }),
        api.getOrderStats(),
      ]);
      setData(res);
      setStats(st);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page, pageSize, q, category]);

  const applySearch = () => { setQ(qInput.trim()); setPage(1); };
  const categories = (stats?.by_category as Array<Record<string, unknown>> ?? []).map((c) => String(c.category));

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Records" title="Orders" subtitle="Browse every imported order across the catalog." />
      {error && <div className="rounded-[22px] border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Total orders" value={num(stats?.total_orders).toLocaleString()} />
        <MetricCard label="Total value" value={fmtMoney(num(stats?.total_value))} accent="text-purple-primary" />
        <MetricCard label="Avg order value" value={fmtMoney(num(stats?.avg_value))} />
        <MetricCard label="Categories" value={categories.length} />
      </div>
      <Panel title="Orders" subtitle="Search by order ID, SKU, or product name. Filter by category.">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') applySearch(); }}
            placeholder="Search order ID, SKU, product…"
            className="min-w-[16rem] flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-400"
          />
          <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none">
            <option value="">All categories</option>
            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <button onClick={applySearch} className="rounded-lg bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">Search</button>
          {(q || category) && <button onClick={() => { setQInput(''); setQ(''); setCategory(''); setPage(1); }} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">Clear</button>}
        </div>
        <div className="overflow-x-auto rounded-3xl border border-slate-200">
          <table className="min-w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                {['Order ID', 'Product', 'Category', 'Value', 'Qty', 'Method', 'Order date'].map((h) => (
                  <th key={h} className="px-4 py-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td className="px-4 py-6 text-slate-500" colSpan={7}>Loading…</td></tr>
              ) : data?.items.length ? data.items.map((o) => (
                <tr key={String(o.id)} className="border-t border-slate-100 bg-white">
                  <td className="px-4 py-3 font-mono text-slate-700">{str(o.external_order_id)}</td>
                  <td className="px-4 py-3 text-slate-700">{str(o.product_name)}</td>
                  <td className="px-4 py-3 text-slate-700">{str(o.category)}</td>
                  <td className="px-4 py-3 text-slate-700">{fmtMoney(num(o.product_value))}</td>
                  <td className="px-4 py-3 text-slate-700">{str(o.quantity)}</td>
                  <td className="px-4 py-3 text-slate-700">{str(o.payment_method)}</td>
                  <td className="px-4 py-3 text-slate-500">{fmtDate(o.order_date)}</td>
                </tr>
              )) : (
                <tr><td className="px-4 py-6 text-slate-500" colSpan={7}>No orders found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {data && <RecordsPagination currentPage={page} totalItems={data.total} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />}
      </Panel>
    </div>
  );
}

function PaymentsBrowsePage() {
  const [data, setData] = useState<RecordsPage | null>(null);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [qInput, setQInput] = useState('');
  const [q, setQ] = useState('');
  const [chargebackOnly, setChargebackOnly] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [res, st] = await Promise.all([
        api.getPayments({ skip: (page - 1) * pageSize, limit: pageSize, q: q || undefined, chargeback: chargebackOnly || undefined }),
        api.getPaymentStats(),
      ]);
      setData(res);
      setStats(st);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page, pageSize, q, chargebackOnly]);

  const applySearch = () => { setQ(qInput.trim()); setPage(1); };

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Records" title="Payments" subtitle="Browse payments and chargebacks across all orders." />
      {error && <div className="rounded-[22px] border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Total payments" value={num(stats?.total_payments).toLocaleString()} />
        <MetricCard label="Total amount" value={fmtMoney(num(stats?.total_amount))} accent="text-purple-primary" />
        <MetricCard label="Chargebacks" value={num(stats?.chargeback_count).toLocaleString()} accent="text-red-primary" />
        <MetricCard label="Chargeback rate" value={`${num(stats?.chargeback_rate).toFixed(2)}%`} accent="text-orange-primary" />
      </div>
      <Panel title="Payments" subtitle="Search by method or card BIN. Toggle chargebacks-only.">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') applySearch(); }}
            placeholder="Search method, card BIN…"
            className="min-w-[16rem] flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-400"
          />
          <label className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
            <input type="checkbox" checked={chargebackOnly} onChange={(e) => { setChargebackOnly(e.target.checked); setPage(1); }} />
            Chargebacks only
          </label>
          <button onClick={applySearch} className="rounded-lg bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">Search</button>
          {(q || chargebackOnly) && <button onClick={() => { setQInput(''); setQ(''); setChargebackOnly(false); setPage(1); }} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">Clear</button>}
        </div>
        <div className="overflow-x-auto rounded-3xl border border-slate-200">
          <table className="min-w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                {['Amount', 'Method', 'Card BIN', 'Chargeback', 'Customer', 'Order', 'Created'].map((h) => (
                  <th key={h} className="px-4 py-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td className="px-4 py-6 text-slate-500" colSpan={7}>Loading…</td></tr>
              ) : data?.items.length ? data.items.map((p) => (
                <tr key={String(p.id)} className="border-t border-slate-100 bg-white">
                  <td className="px-4 py-3 font-medium text-slate-700">{fmtMoney(num(p.amount))}</td>
                  <td className="px-4 py-3 text-slate-700">{str(p.payment_method)}</td>
                  <td className="px-4 py-3 font-mono text-slate-700">{str(p.card_bin)}</td>
                  <td className="px-4 py-3">
                    {p.chargeback_flag ? <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-600">Chargeback</span> : <span className="text-slate-400">—</span>}
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-500">{shortId(p.customer_id)}</td>
                  <td className="px-4 py-3 font-mono text-slate-500">{shortId(p.order_id)}</td>
                  <td className="px-4 py-3 text-slate-500">{fmtDate(p.created_at)}</td>
                </tr>
              )) : (
                <tr><td className="px-4 py-6 text-slate-500" colSpan={7}>No payments found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {data && <RecordsPagination currentPage={page} totalItems={data.total} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />}
      </Panel>
    </div>
  );
}

function ReturnsBrowsePage() {
  const [data, setData] = useState<RecordsPage | null>(null);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [qInput, setQInput] = useState('');
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [res, st] = await Promise.all([
        api.getReturnsList({ skip: (page - 1) * pageSize, limit: pageSize, q: q || undefined, status: status || undefined }),
        api.getReturnStats(),
      ]);
      setData(res);
      setStats(st);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page, pageSize, q, status]);

  const applySearch = () => { setQ(qInput.trim()); setPage(1); };
  const statuses = (stats?.by_status as Array<Record<string, unknown>> ?? []).map((s) => String(s.status));
  const topReasons = (stats?.top_reasons as Array<Record<string, unknown>> ?? []).slice(0, 5);

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Records" title="Returns" subtitle="Browse return requests with reasons, conditions, and timing." />
      {error && <div className="rounded-[22px] border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Total returns" value={num(stats?.total_returns).toLocaleString()} />
        <MetricCard label="Avg hrs after delivery" value={num(stats?.avg_hours_after_delivery).toFixed(1)} accent="text-orange-primary" />
        <MetricCard label="Distinct statuses" value={statuses.length} />
        <MetricCard label="Top reason" value={topReasons[0] ? String(topReasons[0].reason) : '—'} />
      </div>
      <Panel title="Returns" subtitle="Search by reason or condition. Filter by status.">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') applySearch(); }}
            placeholder="Search reason, condition, return ID…"
            className="min-w-[16rem] flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-400"
          />
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none">
            <option value="">All statuses</option>
            {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button onClick={applySearch} className="rounded-lg bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">Search</button>
          {(q || status) && <button onClick={() => { setQInput(''); setQ(''); setStatus(''); setPage(1); }} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">Clear</button>}
        </div>
        <div className="overflow-x-auto rounded-3xl border border-slate-200">
          <table className="min-w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                {['Reason', 'Condition', 'Status', 'Return date', 'Hrs after delivery', 'Customer', 'Order'].map((h) => (
                  <th key={h} className="px-4 py-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td className="px-4 py-6 text-slate-500" colSpan={7}>Loading…</td></tr>
              ) : data?.items.length ? data.items.map((r) => (
                <tr key={String(r.id)} className="border-t border-slate-100 bg-white">
                  <td className="px-4 py-3 text-slate-700">{str(r.return_reason)}</td>
                  <td className="px-4 py-3 text-slate-700">{str(r.condition_reported)}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">{str(r.return_status)}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{fmtDate(r.return_date)}</td>
                  <td className="px-4 py-3 text-slate-700">{r.hours_after_delivery !== null && r.hours_after_delivery !== undefined ? num(r.hours_after_delivery).toFixed(0) : '—'}</td>
                  <td className="px-4 py-3 font-mono text-slate-500">{shortId(r.customer_id)}</td>
                  <td className="px-4 py-3 font-mono text-slate-500">{shortId(r.order_id)}</td>
                </tr>
              )) : (
                <tr><td className="px-4 py-6 text-slate-500" colSpan={7}>No returns found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {data && <RecordsPagination currentPage={page} totalItems={data.total} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />}
      </Panel>
    </div>
  );
}

function AppInner() {
  const [metrics, setMetrics] = useState<Metrics>();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [feedback, setFeedback] = useState<FeedbackRecord[]>([]);
  const [lastScore, setLastScore] = useState<ScoreResponse>();
  const [filters, setFilters] = useState({ q: "", decision: "", risk: "" });
  const navigate = useNavigate();

  const refreshData = async () => {
    const [freshMetricsRes, freshCasesRes] = await Promise.allSettled([api.getMetrics(), api.getCases(undefined, 50)]);
    if (freshMetricsRes.status === "fulfilled") setMetrics(freshMetricsRes.value);
    if (freshCasesRes.status === "fulfilled") setCases(freshCasesRes.value.items);
  };

  useEffect(() => {
    refreshData().catch(() => undefined);
    api.getRules().then((res) => setRules(res.items)).catch(() => undefined);
    api.getFeedback(undefined, 25).then((res) => setFeedback(res.items)).catch(() => undefined);
  }, []);

  const handleDecision = async (decision: string, notes: string, id: string) => {
    const confirmedLabel = decision === "Mark Confirmed Fraud" ? "confirmed_fraud" : decision === "Mark False Positive" ? "false_positive" : undefined;
    await api.updateDecision(id, { decision, notes, confirmed_label: confirmedLabel });
    await Promise.all([refreshData(), api.getFeedback(undefined, 25).then((res) => setFeedback(res.items))]);
  };

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<OverviewPage metrics={metrics} onReturnCreated={async (result) => { setLastScore(result); await refreshData(); navigate(`/investigations/${result.case_id}`); }} />} />
        <Route path="/cases" element={<CasesPage cases={cases} filters={filters} setFilters={setFilters} />} />
        <Route path="/orders" element={<OrdersBrowsePage />} />
        <Route path="/payments" element={<PaymentsBrowsePage />} />
        <Route path="/returns" element={<ReturnsBrowsePage />} />
        <Route path="/cases/:id" element={<CaseDetailRoute onAction={handleDecision} onLoaded={setLastScore} />} />
        <Route path="/decision-engine" element={<DecisionEnginePage latest={lastScore} />} />
        <Route path="/enhancements" element={<EnhancementsPage latest={lastScore} cases={cases} />} />
        <Route path="/investigations" element={<InvestigationHome cases={cases} />} />
        <Route path="/investigations/:id" element={<CaseDetailRoute onAction={handleDecision} onLoaded={setLastScore} />} />
        <Route path="/rules" element={<RulesPage rules={rules} setRules={setRules} />} />
        <Route path="/feedback" element={<FeedbackPage feedback={feedback} />} />
        <Route path="/fraud-ring" element={<FraudRingExplorerPage />} />
        <Route path="/evidence" element={<EvidenceExplorerPage />} />
        <Route path="/timeline/:id" element={<TimelineExplorerPage />} />
        <Route path="/patterns" element={<PatternLibraryPage />} />
        <Route path="/graph-analytics" element={<GraphAnalyticsPage />} />
        <Route path="/modules" element={<ModuleDashboardPage />} />
        <Route path="/kaggle" element={<KaggleImportPage />} />
        <Route path="/batch-monitor" element={<ImportBatchMonitor />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/merchants" element={<MerchantsPage />} />
        <Route path="/models" element={<ModelsPage />} />
        <Route path="/monitoring" element={<MonitoringPage />} />
        <Route path="/nlp" element={<NlpAnalyzerPage />} />
        <Route path="/embeddings" element={<EmbeddingsPage />} />
      </Routes>
    </AppShell>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AppInner />
      </ToastProvider>
    </BrowserRouter>
  );
}
