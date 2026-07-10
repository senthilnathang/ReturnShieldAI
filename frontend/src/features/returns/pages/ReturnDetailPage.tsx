import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../../../api/client';
import type { ReturnDetail } from '../../../types';
import { ReturnStatusBadge } from '../components/ReturnStatusBadge';

export function ReturnDetailPage() {
  const { returnId } = useParams();
  const [detail, setDetail] = useState<ReturnDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!returnId) return;
    api.getReturn(returnId).then(setDetail).catch((caught) => setError(String(caught)));
  }, [returnId]);

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
            <div className="mt-2 text-sm text-slate-600">Created by {detail.created_by ?? 'system'} on {new Date(detail.created_at).toLocaleString()}</div>
          </div>
          <div className="space-y-2 text-right">
            <ReturnStatusBadge status={detail.return_status} />
            <div className="text-sm text-slate-600">Fraud score {detail.fraud_risk_score != null ? Number(detail.fraud_risk_score).toFixed(1) : '—'}</div>
            <div className="text-sm text-slate-600">Decision {detail.fraud_decision ?? 'Pending'}</div>
          </div>
        </div>
      </div>

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
          <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Supporting Evidence</div>
          <div className="mt-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">Image upload will be available in the next release.</div>
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
