import { useSearchParams } from 'react-router-dom';
import { CreateReturnForm } from '../components/CreateReturnForm';

export function CreateReturnPage({ orderId }: { orderId?: string }) {
  const [searchParams] = useSearchParams();
  const resolvedOrderId = orderId ?? searchParams.get('order_id') ?? '';

  if (!resolvedOrderId) {
    return <div className="rounded-3xl border border-slate-200 bg-white p-5 text-sm text-slate-600">Select an order first to create a return.</div>;
  }

  return <CreateReturnForm orderId={resolvedOrderId} />;
}
