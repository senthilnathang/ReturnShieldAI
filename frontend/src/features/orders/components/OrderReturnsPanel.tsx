import { Link } from 'react-router-dom';
import type { OrderReturnRecord, ReturnEligibility } from '../../../types';
import { ReturnStatusBadge } from '../../returns/components/ReturnStatusBadge';

export function OrderReturnsPanel({
  orderId,
  returns,
  eligibility,
}: {
  orderId: string;
  returns: OrderReturnRecord[];
  eligibility?: ReturnEligibility | null;
}) {
  if (!returns.length) {
    return (
      <div className="space-y-3 rounded-3xl border border-slate-200 bg-slate-50 p-4">
        <div className="text-sm text-slate-600">No return requests have been created for this order.</div>
        {eligibility?.eligible ? <Link to={`/orders/${orderId}/returns/create`} className="inline-flex rounded-xl bg-slate-950 px-3 py-2 text-xs font-medium text-white">Create Return</Link> : null}
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-3xl border border-slate-200">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-slate-50 text-slate-500">
          <tr>
            <th className="px-4 py-3">Return ID</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Reason</th>
            <th className="px-4 py-3">Refund</th>
            <th className="px-4 py-3">Fraud score</th>
            <th className="px-4 py-3">Action</th>
          </tr>
        </thead>
        <tbody>
          {returns.map((item) => (
            <tr key={item.id} className="border-t border-slate-100 bg-white">
              <td className="px-4 py-3 font-mono text-xs text-slate-700">{item.external_return_id ?? item.id.slice(0, 8)}</td>
              <td className="px-4 py-3"><ReturnStatusBadge status={item.return_status} /></td>
              <td className="px-4 py-3 text-slate-700">{item.return_reason_category ?? item.return_reason ?? '—'}</td>
              <td className="px-4 py-3 text-slate-700">{item.refund_amount != null ? `$${Number(item.refund_amount).toFixed(2)}` : '—'}</td>
              <td className="px-4 py-3 text-slate-700">{item.fraud_risk_score != null ? Number(item.fraud_risk_score).toFixed(1) : '—'}</td>
              <td className="px-4 py-3"><Link to={`/returns/${item.id}`} className="text-sm text-slate-950 underline underline-offset-4">Open</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
