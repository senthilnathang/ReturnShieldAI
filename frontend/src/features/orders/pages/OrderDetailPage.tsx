import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../../api/client';
import type { OrderReturnRecord, ReturnEligibility, ReturnableOrderItem } from '../../../types';
import { OrderReturnsPanel } from '../components/OrderReturnsPanel';
import { OrderActionsMenu } from '../components/OrderActionsMenu';
import { ReturnEligibilityBanner } from '../../returns/components/ReturnEligibilityBanner';

const tabs = ['overview', 'items', 'shipment', 'payment', 'returns', 'fraud', 'timeline'] as const;

export function OrderDetailPage({ orderId }: { orderId: string }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [order, setOrder] = useState<Record<string, unknown> | null>(null);
  const [returns, setReturns] = useState<OrderReturnRecord[]>([]);
  const [eligibility, setEligibility] = useState<ReturnEligibility | null>(null);
  const [items, setItems] = useState<ReturnableOrderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const activeTab = (searchParams.get('tab') ?? 'overview').toLowerCase();

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([api.getOrder(orderId), api.getOrderReturns(orderId), api.getOrderEligibility(orderId), api.getOrderReturnableItems(orderId)])
      .then(([orderRes, returnsRes, eligibilityRes, itemsRes]) => {
        if (!active) return;
        setOrder(orderRes);
        setReturns(returnsRes.items);
        setEligibility(eligibilityRes);
        setItems(itemsRes);
      })
      .catch((caught) => {
        if (!active) return;
        setError(String(caught));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [orderId]);

  const orderTitle = useMemo(() => {
    if (!order) return 'Order';
    return String(order.external_order_id ?? order.id ?? orderId);
  }, [order, orderId]);

  if (loading) return <div className="rounded-3xl border border-slate-200 bg-white p-5 text-sm text-slate-600">Loading order detail...</div>;
  if (error) return <div className="rounded-3xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">{error}</div>;
  if (!order) return <div className="rounded-3xl border border-slate-200 bg-white p-5 text-sm text-slate-600">Order not found.</div>;

  const setTab = (tab: string) => setSearchParams((current) => {
    current.set('tab', tab);
    return current;
  });

  return (
    <div className="space-y-4">
      <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Order Detail</div>
            <h1 className="mt-2 text-2xl font-semibold text-slate-950">{orderTitle}</h1>
            <div className="mt-2 text-sm text-slate-600">{String(order.product_name ?? 'Product')} · {String(order.order_status ?? 'UNKNOWN')}</div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {eligibility?.eligible ? (<Link to={`/orders/${orderId}/returns/create`} className="rounded-2xl bg-slate-950 px-4 py-2.5 text-sm font-medium text-white">Create Return</Link>) : (<button disabled title={eligibility?.message ?? eligibility?.reason ?? "Return not available"} className="cursor-not-allowed rounded-2xl bg-slate-300 px-4 py-2.5 text-sm font-medium text-slate-600">Create Return</button>)}
            <OrderActionsMenu orderId={orderId} eligibility={eligibility} />
          </div>
        </div>
        <div className="mt-4"><ReturnEligibilityBanner orderId={orderId} eligibility={eligibility} /></div>
      </div>

      <div className="flex flex-wrap gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm">
        {tabs.map((tab) => (
          <button key={tab} onClick={() => setTab(tab)} className={`rounded-xl px-4 py-2 text-sm capitalize ${activeTab === tab ? 'bg-slate-950 text-white' : 'text-slate-700 hover:bg-slate-50'}`}>
            {tab === 'fraud' ? 'Fraud & Risk' : tab}
          </button>
        ))}
      </div>

      {activeTab === 'overview' ? (
        <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
          <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Overview</div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <Summary label="Customer" value={String(order.customer_id ?? '—')} />
              <Summary label="Status" value={String(order.order_status ?? '—')} />
              <Summary label="Order date" value={order.order_date ? new Date(String(order.order_date)).toLocaleString() : '—'} />
              <Summary label="Delivery date" value={order.delivery_date ? new Date(String(order.delivery_date)).toLocaleString() : '—'} />
              <Summary label="Total" value={order.product_value != null ? `$${Number(order.product_value).toFixed(2)}` : '—'} />
              <Summary label="Payment" value={String(order.payment_method ?? '—')} />
            </div>
          </section>
          <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Fraud & Risk</div>
            <div className="mt-3 text-sm text-slate-700">Return window and refund eligibility are checked before the form submits.</div>
            <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              <div>Delivery date: {order.delivery_date ? new Date(String(order.delivery_date)).toLocaleString() : '—'}</div>
              <div className="mt-1">Returnable quantity: {items[0]?.available_return_quantity ?? 0}</div>
              <div className="mt-1">Existing returns: {returns.length}</div>
            </div>
          </section>
        </div>
      ) : null}

      {activeTab === 'items' ? (
        <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Items</div>
          <div className="mt-3 overflow-hidden rounded-3xl border border-slate-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr><th className="px-4 py-3">Product</th><th className="px-4 py-3">Ordered</th><th className="px-4 py-3">Previously returned</th><th className="px-4 py-3">Available</th></tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.order_item_id} className="border-t border-slate-100 bg-white">
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900">{item.product_name ?? 'Product'}</div>
                      <div className="text-xs text-slate-500">SKU {item.sku ?? '—'}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{item.ordered_quantity}</td>
                    <td className="px-4 py-3 text-slate-700">{item.previously_returned_quantity}</td>
                    <td className="px-4 py-3 text-slate-700">{item.available_return_quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {activeTab === 'shipment' ? (
        <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Shipment</div>
          <div className="mt-3 text-sm text-slate-600">Shipment tracking is currently stored as a hashed placeholder in the database.</div>
          <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">Delivery date: {order.delivery_date ? new Date(String(order.delivery_date)).toLocaleString() : '—'}</div>
        </section>
      ) : null}

      {activeTab === 'payment' ? (
        <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Payment</div>
          <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">Method: {String(order.payment_method ?? '—')} · Risk score: {String(order.payment_method_risk_score ?? 0)}</div>
        </section>
      ) : null}

      {activeTab === 'returns' ? (
        <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Returns</div>
              <div className="mt-2 text-sm text-slate-600">Existing returns, their status, and their fraud screening outcome.</div>
            </div>
            {eligibility?.eligible ? <Link to={`/orders/${orderId}/returns/create`} className="rounded-2xl bg-slate-950 px-4 py-2 text-sm font-medium text-white">Create Return</Link> : null}
          </div>
          <OrderReturnsPanel orderId={orderId} returns={returns} eligibility={eligibility} />
        </section>
      ) : null}

      {activeTab === 'fraud' ? (
        <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Fraud & Risk</div>
          <div className="mt-3 text-sm text-slate-700">The return form is checked against delivery status, return window expiry, prior returns, and refund status before submission.</div>
        </section>
      ) : null}

      {activeTab === 'timeline' ? (
        <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Timeline</div>
          <div className="mt-3 space-y-2 text-sm text-slate-700">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">Order created / placed</div>
            {returns.map((item) => (
              <div key={item.id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                Return {item.external_return_id ?? item.id.slice(0, 8)} created on {new Date(item.created_at).toLocaleString()}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="flex gap-2">
        <button onClick={() => navigate('/orders')} className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700">Back to orders</button>
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
