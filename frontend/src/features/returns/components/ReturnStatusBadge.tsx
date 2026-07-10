export function ReturnStatusBadge({ status }: { status?: string | null }) {
  const tone =
    status === 'REQUESTED' ? 'bg-blue-50 text-blue-700 ring-blue-100' :
    status === 'APPROVED' ? 'bg-emerald-50 text-emerald-700 ring-emerald-100' :
    status === 'REJECTED' ? 'bg-red-50 text-red-700 ring-red-100' :
    status === 'REFUNDED' ? 'bg-slate-100 text-slate-700 ring-slate-200' :
    'bg-slate-50 text-slate-600 ring-slate-200';

  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${tone}`}>{status ?? 'UNKNOWN'}</span>;
}
