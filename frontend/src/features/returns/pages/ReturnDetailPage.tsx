import { useEffect, useMemo, useState, type ChangeEvent, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../../../api/client';
import type { ReturnAnalysisResponse, ReturnDetail } from '../../../types';
import { ReturnStatusBadge } from '../components/ReturnStatusBadge';

type WizardStep = 'overview' | 'ocr' | 'scores' | 'explainability' | 'timeline';

const WIZARD_STEPS: Array<{ id: WizardStep; label: string; description: string }> = [
  { id: 'overview', label: 'Overview', description: 'Result summary and action' },
  { id: 'ocr', label: 'OCR Review', description: 'Vision and text evidence' },
  { id: 'scores', label: 'Scores', description: 'Rule and ML signal mix' },
  { id: 'explainability', label: 'Explainability', description: 'Why the model flagged it' },
  { id: 'timeline', label: 'Timeline', description: 'Audit trail and trace' },
];

export function ReturnDetailPage() {
  const { returnId } = useParams();
  const [detail, setDetail] = useState<ReturnDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [analysisPreview, setAnalysisPreview] = useState<string | null>(null);
  const [analysisName, setAnalysisName] = useState<string | null>(null);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisStage, setAnalysisStage] = useState<WizardStep>('overview');
  const [analysisResult, setAnalysisResult] = useState<ReturnAnalysisResponse | null>(null);
  const [analysisMessage, setAnalysisMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!returnId) return;
    api.getReturn(returnId).then(setDetail).catch((caught) => setError(String(caught)));
  }, [returnId]);

  const readFileAsDataUrl = (file: File) =>
    new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result === 'string') resolve(reader.result);
        else reject(new Error('Failed to read image file.'));
      };
      reader.onerror = () => reject(new Error('Failed to read image file.'));
      reader.readAsDataURL(file);
    });

  const handleAnalysisUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const dataUrl = await readFileAsDataUrl(file);
    setAnalysisPreview(dataUrl);
    setAnalysisName(file.name);
    event.target.value = '';
  };

  const runAnalysis = async () => {
    if (!returnId) return;
    if (!analysisPreview) {
      setReviewError('Upload a return image first.');
      return;
    }
    setAnalysisOpen(true);
    setAnalysisStage('overview');
    setAnalysisLoading(true);
    setAnalysisMessage(null);
    setReviewing(true);
    setReviewError(null);
    try {
      const result = await api.runReturnAnalysis(returnId, {
        image_data_url: analysisPreview,
        filename: analysisName ?? undefined,
        mime_type: 'image/*',
      });
      setAnalysisResult(result);
      setDetail(result.return_detail);
      setAnalysisMessage('Return OCR review completed successfully.');
      setAnalysisStage('overview');
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to run return analysis.';
      setReviewError(message);
      setAnalysisMessage(message);
    } finally {
      setAnalysisLoading(false);
      setReviewing(false);
    }
  };

  const finalScore = analysisResult?.score?.final_score ?? analysisResult?.score_result.final_score ?? detail?.fraud_risk_score ?? null;
  const decision = analysisResult?.score?.decision ?? analysisResult?.score_result.decision ?? detail?.fraud_decision ?? 'Pending';
  const riskLevel = analysisResult?.score?.risk_level ?? analysisResult?.score_result.risk_level ?? null;
  const scoreBreakdown = analysisResult?.score?.score_breakdown_json ?? analysisResult?.score_result.score_breakdown ?? {};

  const scoreCards = useMemo(
    () => [
      { label: 'Rule score', value: analysisResult?.score?.rule_score ?? analysisResult?.score_result.rule_score ?? 0 },
      { label: 'Structured ML', value: analysisResult?.score?.structured_ml_score ?? analysisResult?.score_result.structured_ml_score ?? 0 },
      { label: 'NLP score', value: analysisResult?.score?.nlp_score ?? analysisResult?.score_result.nlp_score ?? 0 },
      { label: 'Graph score', value: analysisResult?.score?.graph_score ?? analysisResult?.score_result.graph_score ?? 0 },
      { label: 'Anomaly score', value: analysisResult?.score?.anomaly_score ?? analysisResult?.score_result.anomaly_score ?? 0 },
      { label: 'Final score', value: finalScore ?? 0 },
    ],
    [analysisResult, finalScore],
  );

  if (!returnId) return <div className="rounded-3xl border border-slate-200 bg-white p-5 text-sm text-slate-600">Missing return id.</div>;
  if (error) return <div className="rounded-3xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">{error}</div>;
  if (!detail) return <div className="rounded-3xl border border-slate-200 bg-white p-5 text-sm text-slate-600">Loading return detail...</div>;

  return (
    <div className="space-y-4">
      <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Return Detail</div>
            <h1 className="mt-2 text-2xl font-semibold text-slate-950">{detail.external_return_id ?? detail.id}</h1>
            <div className="mt-2 text-sm text-slate-600">
              Created by {detail.created_by ?? 'system'} on {new Date(detail.created_at).toLocaleString()}
            </div>
          </div>
          <div className="space-y-2 text-right">
            <ReturnStatusBadge status={detail.return_status} />
            <div className="text-sm text-slate-600">Fraud score {detail.fraud_risk_score != null ? Number(detail.fraud_risk_score).toFixed(1) : '—'}</div>
            <div className="text-sm text-slate-600">Decision {detail.fraud_decision ?? 'Pending'}</div>
          </div>
        </div>
      </div>

      {reviewError ? <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{reviewError}</div> : null}

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Order</div>
          <div className="mt-2 text-lg font-semibold text-slate-900">{String(detail.order.product_name ?? detail.order.external_order_id ?? detail.order_id)}</div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <Summary label="Reason category" value={detail.return_reason_category ?? '—'} />
            <Summary label="Condition" value={detail.condition_reported ?? '—'} />
            <Summary label="Return method" value={detail.return_method ?? '—'} />
            <Summary label="Refund method" value={detail.preferred_refund_method ?? '—'} />
            <Summary label="Refund amount" value={detail.refund_amount != null ? `$${Number(detail.refund_amount).toFixed(2)}` : '—'} />
            <Summary label="Hours after delivery" value={detail.hours_after_delivery != null ? Number(detail.hours_after_delivery).toFixed(1) : '—'} />
          </div>
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Detailed description</div>
            <div className="mt-2 leading-6">{detail.detailed_description ?? detail.return_reason ?? '—'}</div>
          </div>
        </section>

        <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Manual OCR + Fraud Review</div>
          <div className="mt-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
            Upload a return image here to rerun OCR and fraud scoring on an existing return.
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <label className="cursor-pointer rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700">
              Upload image
              <input type="file" accept="image/*" className="hidden" onChange={handleAnalysisUpload} />
            </label>
            <button
              type="button"
              onClick={runAnalysis}
              disabled={reviewing || !analysisPreview}
              className="rounded-2xl bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {reviewing ? 'Running review...' : 'Run OCR + Fraud Review'}
            </button>
          </div>
          {analysisPreview ? (
            <div className="mt-4 grid gap-4 xl:grid-cols-[220px_1fr]">
              <div className="overflow-hidden rounded-3xl border border-slate-200 bg-slate-50">
                <img src={analysisPreview} alt={analysisName ?? 'Analysis evidence'} className="h-full w-full object-cover" />
              </div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Selected image</div>
                <div className="mt-2 text-sm font-medium text-slate-900">{analysisName ?? 'Return evidence image'}</div>
                <div className="mt-2">The review action will OCR this image and add its findings to the return track record.</div>
              </div>
            </div>
          ) : null}
          <div className="mt-4 text-xs uppercase tracking-[0.24em] text-slate-500">Supporting Evidence</div>
          <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">The return timeline will include the manual review events after the action completes.</div>
          <div className="mt-4 text-xs uppercase tracking-[0.24em] text-slate-500">Timeline</div>
          <div className="mt-3 space-y-2">
            {detail.timeline.map((event) => (
              <div key={`${event.label}-${event.time}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="text-sm font-medium text-slate-900">{event.label}</div>
                <div className="mt-1 text-xs text-slate-500">{new Date(event.time).toLocaleString()}</div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex gap-2">
            <Link to={`/orders/${detail.order_id}?tab=returns`} className="rounded-2xl bg-slate-950 px-4 py-2 text-sm font-medium text-white">Back to order</Link>
            <Link to={`/orders/${detail.order_id}/returns/create`} className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700">Create another return</Link>
          </div>
        </section>
      </div>

      <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
        <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Return Items</div>
        <div className="mt-3 overflow-hidden rounded-3xl border border-slate-200">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Qty</th>
                <th className="px-4 py-3">Condition</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {(detail.items ?? []).map((item) => (
                <tr key={item.id} className="border-t border-slate-100 bg-white">
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{item.product_name ?? 'Product'}</div>
                    <div className="text-xs text-slate-500">SKU {item.sku ?? '—'}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{item.quantity}</td>
                  <td className="px-4 py-3 text-slate-700">{item.declared_condition ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-700">{item.item_match_status ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {analysisOpen ? (
        <AnalysisWizardModal
          open={analysisOpen}
          loading={analysisLoading}
          step={analysisStage}
          onClose={() => setAnalysisOpen(false)}
          onStepChange={setAnalysisStage}
          analysisResult={analysisResult}
          analysisMessage={analysisMessage}
          analysisPreview={analysisPreview}
          analysisName={analysisName}
          detail={detail}
          scoreCards={scoreCards}
          finalScore={finalScore}
          decision={decision}
          riskLevel={riskLevel}
          scoreBreakdown={scoreBreakdown}
        />
      ) : null}
    </div>
  );
}

function AnalysisWizardModal({
  open,
  loading,
  step,
  onClose,
  onStepChange,
  analysisResult,
  analysisMessage,
  analysisPreview,
  analysisName,
  detail,
  scoreCards,
  finalScore,
  decision,
  riskLevel,
  scoreBreakdown,
}: {
  open: boolean;
  loading: boolean;
  step: WizardStep;
  onClose: () => void;
  onStepChange: (step: WizardStep) => void;
  analysisResult: ReturnAnalysisResponse | null;
  analysisMessage: string | null;
  analysisPreview: string | null;
  analysisName: string | null;
  detail: ReturnDetail;
  scoreCards: Array<{ label: string; value: number }>;
  finalScore: number | null;
  decision: string;
  riskLevel: string | null;
  scoreBreakdown: Record<string, unknown>;
}) {
  const currentStep = WIZARD_STEPS.find((entry) => entry.id === step) ?? WIZARD_STEPS[0];
  const imageReview = analysisResult?.image_review;
  const explainability = analysisResult?.explainability;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 px-4 py-6 backdrop-blur-sm">
      <div className="max-h-[92vh] w-full max-w-6xl overflow-hidden rounded-[32px] border border-white/10 bg-[#0f172a] text-slate-50 shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-white/10 px-6 py-5">
          <div>
            <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Return Review Wizard</div>
            <h2 className="mt-2 text-2xl font-semibold text-white">OCR, scoring, and explainability in one review</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
              {analysisMessage ?? 'The analysis result appears here after OCR and fraud scoring complete.'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 transition hover:bg-white/10"
          >
            Close
          </button>
        </div>

        <div className="grid max-h-[calc(92vh-86px)] gap-0 overflow-hidden lg:grid-cols-[260px_1fr]">
          <aside className="border-b border-white/10 bg-white/5 p-5 lg:border-b-0 lg:border-r">
            <div className="space-y-3">
              {WIZARD_STEPS.map((entry, index) => {
                const active = entry.id === currentStep.id;
                return (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => onStepChange(entry.id)}
                    className={`w-full rounded-3xl border px-4 py-4 text-left transition ${
                      active
                        ? 'border-amber-400/40 bg-amber-400/15 text-amber-100 shadow-[0_0_0_1px_rgba(251,191,36,0.2)]'
                        : 'border-white/10 bg-white/5 text-slate-200 hover:bg-white/10'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold ${active ? 'bg-amber-400 text-slate-950' : 'bg-slate-700 text-slate-200'}`}>
                        {String(index + 1).padStart(2, '0')}
                      </div>
                      <div>
                        <div className="text-sm font-semibold">{entry.label}</div>
                        <div className="text-xs text-slate-400">{entry.description}</div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </aside>

          <div className="overflow-y-auto p-6">
            {loading && !analysisResult ? (
              <div className="rounded-[28px] border border-white/10 bg-white/5 p-8 text-center text-slate-300">
                <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-amber-400/25 border-t-amber-400" />
                <div className="mt-4 text-lg font-medium text-white">Running OCR review and fraud scoring</div>
                <div className="mt-2 text-sm text-slate-400">The modal stays open while the backend stores the evidence and builds the explanation.</div>
              </div>
            ) : null}

            {!loading && analysisResult ? (
              <div className="space-y-5">
                <div className="grid gap-4 md:grid-cols-3">
                  <StatCard label="Final score" value={finalScore != null ? `${Number(finalScore).toFixed(1)}` : '—'} accent="amber" />
                  <StatCard label="Decision" value={decision} accent="emerald" />
                  <StatCard label="Risk level" value={riskLevel ?? 'Pending'} accent="rose" />
                </div>

                <div className="rounded-[28px] border border-white/10 bg-white/5 p-5">
                  <div className="flex flex-wrap items-end justify-between gap-3">
                    <div>
                      <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Current step</div>
                      <div className="mt-2 text-xl font-semibold text-white">{currentStep.label}</div>
                    </div>
                    <div className="text-right text-sm text-slate-300">
                      <div>{analysisResult.recommended_action}</div>
                      <div className="mt-1 text-xs text-slate-500">Return {detail.external_return_id ?? detail.id}</div>
                    </div>
                  </div>

                  <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full rounded-full bg-gradient-to-r from-amber-400 via-orange-400 to-emerald-400" style={{ width: `${Math.min(100, Math.max(0, finalScore ?? 0))}%` }} />
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2 text-xs uppercase tracking-[0.22em] text-slate-300">
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">{analysisResult.score_result.reason_codes.length} reason codes</span>
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">{analysisResult.score_result.risk_level}</span>
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">{analysisResult.image_review?.provider_model ?? 'Vision unavailable'}</span>
                  </div>
                </div>

                {step === 'overview' ? (
                  <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                    <Panel title="Overview summary">
                      <p className="text-sm leading-6 text-slate-300">{analysisResult.explanation}</p>
                      <div className="mt-4 grid gap-3 md:grid-cols-2">
                        <SummaryChip label="Return ID" value={analysisResult.return_detail.external_return_id ?? analysisResult.return_detail.id} />
                        <SummaryChip label="Order" value={String(detail.order.product_name ?? detail.order.external_order_id ?? detail.order_id)} />
                        <SummaryChip label="Refund method" value={analysisResult.return_detail.preferred_refund_method ?? '—'} />
                        <SummaryChip label="Image verdict" value={imageReview ? (imageReview.matched ? 'Matched' : 'Mismatch detected') : 'No image review result'} />
                      </div>
                    </Panel>

                    <Panel title="Evidence snapshot">
                      <div className="space-y-3 text-sm text-slate-300">
                        <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">OCR text: {imageReview?.ocr_text || 'No OCR text available.'}</div>
                        <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">Summary: {imageReview?.summary || analysisResult.explanation}</div>
                        <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">Recommended action: {analysisResult.recommended_action}</div>
                      </div>
                    </Panel>
                  </div>
                ) : null}

                {step === 'ocr' ? (
                  <div className="grid gap-4 xl:grid-cols-[300px_1fr]">
                    <Panel title="Image preview">
                      {analysisPreview ? (
                        <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-950/40">
                          <img src={analysisPreview} alt={analysisName ?? 'Return evidence'} className="h-full w-full object-cover" />
                        </div>
                      ) : (
                        <EmptyState text="No uploaded image available." />
                      )}
                    </Panel>
                    <Panel title="OCR readout">
                      {imageReview ? (
                        <div className="space-y-4 text-sm text-slate-300">
                          <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">OCR text</div>
                            <div className="mt-2 whitespace-pre-wrap leading-6 text-slate-100">{imageReview.ocr_text || 'No OCR text returned.'}</div>
                          </div>
                          <div className="grid gap-3 md:grid-cols-2">
                            <SummaryChip label="Matched" value={imageReview.matched ? 'Yes' : 'No'} />
                            <SummaryChip label="Confidence" value={`${Number(imageReview.confidence).toFixed(1)}%`} />
                            <SummaryChip label="Detected SKU" value={imageReview.detected_sku ?? '—'} />
                            <SummaryChip label="Detected product" value={imageReview.detected_product_name ?? '—'} />
                            <SummaryChip label="Detected serial" value={imageReview.detected_serial_number ?? '—'} />
                            <SummaryChip label="Detected IMEI" value={imageReview.detected_imei ?? '—'} />
                          </div>
                          <div className="grid gap-3 lg:grid-cols-2">
                            <ListPanel title="Mismatch reasons" items={imageReview.mismatch_reasons} emptyLabel="No mismatch reasons reported." />
                            <ListPanel title="Evidence" items={imageReview.evidence} emptyLabel="No evidence items reported." />
                          </div>
                        </div>
                      ) : (
                        <EmptyState text="The OCR review did not return a result. The return is still scored and recorded." />
                      )}
                    </Panel>
                  </div>
                ) : null}

                {step === 'scores' ? (
                  <div className="space-y-4">
                    <Panel title="Score breakdown">
                      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                        {scoreCards.map((card) => (
                          <div key={card.label} className="rounded-3xl border border-white/10 bg-slate-950/40 p-4">
                            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">{card.label}</div>
                            <div className="mt-2 text-2xl font-semibold text-white">{Number(card.value).toFixed(1)}</div>
                          </div>
                        ))}
                      </div>
                    </Panel>
                    <Panel title="Raw score payload">
                      <pre className="overflow-x-auto rounded-3xl border border-white/10 bg-slate-950/60 p-4 text-xs leading-6 text-slate-200">
{JSON.stringify(scoreBreakdown, null, 2)}
                      </pre>
                    </Panel>
                  </div>
                ) : null}

                {step === 'explainability' ? (
                  <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
                    <Panel title="Why it was flagged">
                      <p className="text-sm leading-6 text-slate-300">{explainability?.why_flagged_summary ?? analysisResult.explanation}</p>
                      <div className="mt-4 grid gap-3">
                        {(explainability?.top_positive_drivers ?? []).map((driver) => (
                          <div key={driver.label} className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm text-emerald-50">
                            <div className="font-medium">{driver.label}</div>
                            <div className="mt-1 text-emerald-100/80">{driver.detail}</div>
                          </div>
                        ))}
                      </div>
                    </Panel>
                    <Panel title="Signal contributions">
                      <div className="space-y-3">
                        {(explainability?.signal_contributions ?? []).map((signal) => (
                          <div key={signal.label} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <div className="font-medium text-white">{signal.label}</div>
                                <div className="text-xs text-slate-500">Weight {signal.weight}</div>
                              </div>
                              <div className="text-sm text-slate-200">Impact {signal.impact.toFixed(1)}</div>
                            </div>
                            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800">
                              <div className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-400" style={{ width: `${Math.min(100, signal.score)}%` }} />
                            </div>
                            <div className="mt-2 text-sm text-slate-300">{signal.detail}</div>
                          </div>
                        ))}
                      </div>
                    </Panel>
                  </div>
                ) : null}

                {step === 'timeline' ? (
                  <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
                    <Panel title="Decision trace">
                      <div className="space-y-3">
                        {analysisResult.decision_trace.map((entry) => (
                          <div key={entry.stage} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">{entry.stage}</div>
                            <div className="mt-2 text-lg font-semibold text-white">{String(entry.value)}</div>
                          </div>
                        ))}
                      </div>
                    </Panel>
                    <Panel title="Return timeline">
                      <div className="space-y-3">
                        {detail.timeline.map((event) => (
                          <div key={`${event.label}-${event.time}`} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                            <div className="font-medium text-white">{event.label}</div>
                            <div className="mt-1 text-xs text-slate-500">{new Date(event.time).toLocaleString()}</div>
                          </div>
                        ))}
                      </div>
                    </Panel>
                  </div>
                ) : null}
              </div>
            ) : null}

            {!loading && !analysisResult ? (
              <div className="rounded-[28px] border border-white/10 bg-white/5 p-6 text-sm text-slate-300">
                No analysis result is available yet. Run OCR review to populate this wizard.
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-[28px] border border-white/10 bg-white/5 p-5">
      <div className="text-xs uppercase tracking-[0.28em] text-slate-500">{title}</div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string; accent: 'amber' | 'emerald' | 'rose' }) {
  const tone = accent === 'amber' ? 'from-amber-400/25 to-amber-400/5 border-amber-400/30' : accent === 'emerald' ? 'from-emerald-400/25 to-emerald-400/5 border-emerald-400/30' : 'from-rose-400/25 to-rose-400/5 border-rose-400/30';
  return (
    <div className={`rounded-[26px] border bg-gradient-to-br ${tone} p-5`}>
      <div className="text-xs uppercase tracking-[0.22em] text-slate-400">{label}</div>
      <div className="mt-3 text-3xl font-semibold text-white">{value}</div>
    </div>
  );
}

function SummaryChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
      <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-medium text-slate-100">{value}</div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/30 p-6 text-sm text-slate-300">{text}</div>;
}

function ListPanel({ title, items, emptyLabel }: { title: string; items: string[]; emptyLabel: string }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-950/40 p-4">
      <div className="text-xs uppercase tracking-[0.22em] text-slate-500">{title}</div>
      <div className="mt-3 space-y-2">
        {items.length > 0 ? items.map((item) => (
          <div key={item} className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">{item}</div>
        )) : <div className="text-sm text-slate-400">{emptyLabel}</div>}
      </div>
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">{label}</div>
      <div className="mt-2 text-sm font-medium text-slate-900">{value}</div>
    </div>
  );
}
