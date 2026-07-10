import { Link } from 'react-router-dom';
import type { ReturnEligibility } from '../../../types';

export function ReturnEligibilityBanner({ orderId, eligibility }: { orderId: string; eligibility?: ReturnEligibility | null }) {
  if (!eligibility) {
    return <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">Checking return eligibility...</div>;
  }

  if (eligibility.eligible) {
    return (
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
        Return is available. Window expires {eligibility.return_window_expires_at ? new Date(eligibility.return_window_expires_at).toLocaleDateString() : 'soon'}.
        <div className="mt-2">
          <Link to={`/orders/${orderId}/returns/create`} className="inline-flex rounded-xl bg-emerald-700 px-3 py-2 text-xs font-medium text-white hover:bg-emerald-600">Create Return</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <div className="font-medium">Return unavailable</div>
      <div className="mt-1">{eligibility.message ?? eligibility.reason ?? 'This order is not eligible for return.'}</div>
      {eligibility.can_override ? <div className="mt-1 text-xs text-amber-800">Users with override permission can still submit a return.</div> : null}
    </div>
  );
}
