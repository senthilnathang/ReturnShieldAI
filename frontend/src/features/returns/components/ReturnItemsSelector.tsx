import { useMemo } from 'react';
import type { ReturnableOrderItem } from '../../../types';

export function ReturnItemsSelector({
  items,
  selectedIds,
  quantities,
  onToggle,
  onQuantityChange,
}: {
  items: ReturnableOrderItem[];
  selectedIds: string[];
  quantities: Record<string, number>;
  onToggle: (id: string) => void;
  onQuantityChange: (id: string, quantity: number) => void;
}) {
  const selectedCount = useMemo(() => selectedIds.length, [selectedIds]);
  return (
    <div className="space-y-3">
      <div className="text-sm text-slate-600">Select one or more eligible items. Return quantity cannot exceed what is available.</div>
      <div className="overflow-hidden rounded-3xl border border-slate-200">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">Select</th>
              <th className="px-4 py-3">Product</th>
              <th className="px-4 py-3">Qty</th>
              <th className="px-4 py-3">Available</th>
              <th className="px-4 py-3">Return Qty</th>
              <th className="px-4 py-3">Value</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const selected = selectedIds.includes(item.order_item_id);
              return (
                <tr key={item.order_item_id} className="border-t border-slate-100 bg-white">
                  <td className="px-4 py-3">
                    <input type="checkbox" checked={selected} onChange={() => onToggle(item.order_item_id)} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{item.product_name ?? 'Product'}</div>
                    <div className="text-xs text-slate-500">SKU {item.sku ?? '—'}{item.requires_serial ? ' · Serialized' : ''}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{item.ordered_quantity}</td>
                  <td className="px-4 py-3 text-slate-700">{item.available_return_quantity}</td>
                  <td className="px-4 py-3">
                    <input
                      type="number"
                      min={1}
                      max={item.available_return_quantity}
                      value={quantities[item.order_item_id] ?? item.return_quantity ?? 0}
                      onChange={(event) => onQuantityChange(item.order_item_id, Number(event.target.value))}
                      disabled={!selected}
                      className="w-24 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none disabled:bg-slate-50"
                    />
                  </td>
                  <td className="px-4 py-3 text-slate-700">{item.product_value != null ? `$${Number(item.product_value).toFixed(2)}` : '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="text-xs text-slate-500">{selectedCount} item group(s) selected.</div>
    </div>
  );
}
