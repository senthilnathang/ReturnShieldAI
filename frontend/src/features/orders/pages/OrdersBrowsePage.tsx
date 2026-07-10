import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../../api/client';
import type { RecordsPage, ReturnEligibility } from '../../../types';
import { RecordsPagination } from '../../../components/RecordsPagination';
import { OrderActionsMenu } from '../components/OrderActionsMenu';

const fmtMoney = (v: unknown) =>
  typeof v === 'number' && Number.isFinite(v)
    ? v.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
    : '—';
const fmtDate = (v: unknown) => (v ? new Date(String(v)).toLocaleString() : '—');
const str = (v: unknown) => (v === null || v === undefined || v === '' ? '—' : String(v));

export function OrdersBrowsePage() {
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
  const categories = useMemo(() => (stats?.by_category as Array<Record<string, unknown>> ?? []).map((c) => String(c.category)), [stats]);

  return (
    <div className="space-y-4">
      <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
        <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Records</div>
        <h1 className="mt-2 text-2xl font-semibold text-slate-950">Orders</h1>
        <p className="mt-2 text-sm text-slate-600">Browse orders and launch returns directly from the order actions menu.</p>
      </div>
      {error && <div className="rounded-[22px] border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Total orders" value={Number(stats?.total_orders ?? 0).toLocaleString()} />
        <MetricCard label="Total value" value={fmtMoney(Number(stats?.total_value ?? 0))} accent="text-purple-primary" />
        <MetricCard label="Avg order value" value={fmtMoney(Number(stats?.avg_value ?? 0))} />
        <MetricCard label="Categories" value={categories.length} />
      </div>
      <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input value={qInput} onChange={(e) => setQInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') applySearch(); }} placeholder="Search order ID, SKU, product…" className="min-w-[16rem] flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-400" />
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
                {['Order ID', 'Product', 'Category', 'Value', 'Qty', 'Method', 'Order date', 'Actions'].map((h) => (
                  <th key={h} className="px-4 py-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td className="px-4 py-6 text-slate-500" colSpan={8}>Loading…</td></tr>
              ) : data?.items.length ? data.items.map((o) => {
                const eligibility = o.return_eligibility as ReturnEligibility | undefined;
                return (
                  <tr key={String(o.id)} className="border-t border-slate-100 bg-white">
                    <td className="px-4 py-3 font-mono text-slate-700">{str(o.external_order_id)}</td>
                    <td className="px-4 py-3 text-slate-700"><Link to={`/orders/${String(o.id)}`} className="font-medium text-slate-900 underline-offset-4 hover:underline">{str(o.product_name)}</Link></td>
                    <td className="px-4 py-3 text-slate-700">{str(o.category)}</td>
                    <td className="px-4 py-3 text-slate-700">{fmtMoney(Number(o.product_value ?? 0))}</td>
                    <td className="px-4 py-3 text-slate-700">{str(o.quantity)}</td>
                    <td className="px-4 py-3 text-slate-700">{str(o.payment_method)}</td>
                    <td className="px-4 py-3 text-slate-500">{fmtDate(o.order_date)}</td>
                    <td className="px-4 py-3"><OrderActionsMenu orderId={String(o.id)} eligibility={eligibility} /></td>
                  </tr>
                );
              }) : (
                <tr><td className="px-4 py-6 text-slate-500" colSpan={8}>No orders found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {data && <RecordsPagination currentPage={page} totalItems={data.total} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />}
      </section>
    </div>
  );
}

function MetricCard({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div className="rounded-[22px] border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">{label}</div>
      <div className={`mt-2 text-2xl font-semibold text-slate-950 ${accent ?? ''}`}>{value}</div>
    </div>
  );
}
