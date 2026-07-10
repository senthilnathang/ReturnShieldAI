import { Link } from 'react-router-dom';
import type { ReturnEligibility } from '../../../types';

export function OrderActionsMenu({ orderId, eligibility }: { orderId: string; eligibility?: ReturnEligibility | null }) {
  const eligible = !!eligibility?.eligible;
  const reason = eligibility?.message ?? eligibility?.reason ?? 'Return not available';

  return (
    <details className="relative">
      <summary className="list-none cursor-pointer rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">Actions</summary>
      <div className="absolute right-0 z-10 mt-2 w-52 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lg">
        <Link to={`/orders/${orderId}`} className="block px-4 py-3 text-sm text-slate-700 hover:bg-slate-50">View Order</Link>
        <Link to={`/orders/${orderId}?tab=returns`} className="block px-4 py-3 text-sm text-slate-700 hover:bg-slate-50">View Returns</Link>
        {eligible ? (
          <Link to={`/orders/${orderId}/returns/create`} className="block px-4 py-3 text-sm text-slate-900 hover:bg-slate-50">Create Return</Link>
        ) : (
          <button title={reason} disabled className="block w-full cursor-not-allowed px-4 py-3 text-left text-sm text-slate-400">Create Return</button>
        )}
      </div>
    </details>
  );
}
