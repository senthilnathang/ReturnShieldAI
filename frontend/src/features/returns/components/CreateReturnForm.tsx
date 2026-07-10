import { useEffect, useMemo, useRef, useState, type ChangeEvent, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../../../api/client';
import type { OrderImageCompareResponse, OrderReturnRecord, ReturnEligibility, ReturnableOrderItem } from '../../../types';
import { ReturnEligibilityBanner } from './ReturnEligibilityBanner';
import { ReturnItemsSelector } from './ReturnItemsSelector';

const reasonCategories = [
  'Damaged Product',
  'Wrong Product',
  'Defective Product',
  'Item Not Received',
  'Missing Accessories',
  'Size Issue',
  'Color Issue',
  'Product Not as Described',
  'Changed Mind',
  'Empty Box',
  'Other',
];

const conditionValues = [
  'Unopened',
  'Opened but Unused',
  'Used',
  'Damaged',
  'Defective',
  'Missing Parts',
  'Wrong Item Received',
  'Unknown',
];

const returnMethods = ['Pickup', 'Drop-off', 'Store Return', 'Courier Self-Ship'];
const refundMethods = ['Original Payment', 'Store Credit', 'Bank Transfer'];

const needsDescription = new Set(['Damaged Product', 'Defective Product', 'Wrong Product', 'Empty Box', 'Missing Accessories']);

const orderValue = (order: Record<string, unknown>, key: string) => order[key];

export function CreateReturnForm({ orderId, onCreated }: { orderId: string; onCreated?: (result: OrderReturnRecord) => void }) {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [order, setOrder] = useState<Record<string, unknown> | null>(null);
  const [eligibility, setEligibility] = useState<ReturnEligibility | null>(null);
  const [items, setItems] = useState<ReturnableOrderItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const [reasonCategory, setReasonCategory] = useState('Damaged Product');
  const [reason, setReason] = useState('');
  const [description, setDescription] = useState('');
  const [conditionReported, setConditionReported] = useState('Damaged');
  const [returnMethod, setReturnMethod] = useState('Pickup');
  const [pickupAddressId, setPickupAddressId] = useState('');
  const [refundMethod, setRefundMethod] = useState('Original Payment');
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageName, setImageName] = useState<string | null>(null);
  const [compareResult, setCompareResult] = useState<OrderImageCompareResponse | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([api.getOrder(orderId), api.getOrderEligibility(orderId), api.getOrderReturnableItems(orderId)])
      .then(([orderRes, eligibilityRes, itemsRes]) => {
        if (!active) return;
        setOrder(orderRes);
        setEligibility(eligibilityRes);
        setItems(itemsRes);
        const defaultSelected = itemsRes.filter((item) => item.available_return_quantity > 0).map((item) => item.order_item_id);
        setSelectedIds(defaultSelected);
        const qtys: Record<string, number> = {};
        for (const item of itemsRes) qtys[item.order_item_id] = Math.max(1, Math.min(item.available_return_quantity || 1, 1));
        setQuantities(qtys);
      })
      .catch((error) => {
        if (!active) return;
        setSubmitError(String(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [orderId]);

  const selectedItems = useMemo(() => items.filter((item) => selectedIds.includes(item.order_item_id)), [items, selectedIds]);

  const validate = () => {
    if (!selectedItems.length) return 'Select at least one item to return.';
    if (!reason.trim()) return 'Return reason is required.';
    if (needsDescription.has(reasonCategory) && !description.trim()) return 'Detailed description is required for the selected return reason.';
    if (returnMethod === 'Pickup' && !pickupAddressId.trim()) return 'Pickup address is required for pickup returns.';
    for (const item of selectedItems) {
      const quantity = quantities[item.order_item_id] ?? 0;
      if (quantity <= 0) return 'Return quantity must be greater than zero.';
      if (quantity > item.available_return_quantity) return 'Return quantity cannot exceed available quantity.';
    }
    return null;
  };

  const toggleItem = (id: string) => {
    setSelectedIds((current) => (current.includes(id) ? current.filter((value) => value !== id) : [...current, id]));
  };

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

  const compareImage = async (file: File) => {
    setCompareLoading(true);
    setCompareError(null);
    setCompareResult(null);
    try {
      const dataUrl = await readFileAsDataUrl(file);
      setImagePreview(dataUrl);
      setImageName(file.name);
      const result = await api.compareOrderImage(orderId, {
        image_data_url: dataUrl,
        filename: file.name,
        mime_type: file.type || undefined,
      });
      setCompareResult(result);
    } catch (error) {
      setCompareError(error instanceof Error ? error.message : 'Unable to compare the uploaded image.');
    } finally {
      setCompareLoading(false);
    }
  };

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await compareImage(file);
    event.target.value = '';
  };

  const submit = async () => {
    const validationError = validate();
    if (validationError) {
      setSubmitError(validationError);
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = {
        return_reason_category: reasonCategory.toUpperCase().replace(/\s+/g, '_'),
        return_reason: reason,
        detailed_description: description,
        condition_reported: conditionReported.toUpperCase().replace(/\s+/g, '_'),
        return_method: returnMethod.toUpperCase().replace(/\s+/g, '_'),
        pickup_address_id: returnMethod === 'Pickup' ? pickupAddressId || null : null,
        preferred_refund_method: refundMethod.toUpperCase().replace(/\s+/g, '_'),
        items: selectedItems.map((item) => ({
          order_item_id: item.order_item_id,
          quantity: quantities[item.order_item_id] ?? 1,
          serial_number: item.serial_number ?? null,
          imei: item.imei ?? null,
        })),
        attachments: imagePreview
          ? [
              {
                id: null,
                file_type: 'image',
                file_url: imagePreview,
                image_type: 'CUSTOMER_RETURN_IMAGE',
                uploaded_by: 'customer',
                uploaded_at: new Date().toISOString(),
                analysis_status: compareResult ? (compareResult.matched ? 'MATCHED' : 'REVIEW_NEEDED') : 'PENDING',
              },
            ]
          : [],
      };
      const created = await api.createOrderReturn(orderId, payload);
      onCreated?.(created);
      navigate(`/returns/${created.id}`);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Unable to create return request.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="rounded-3xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Loading return form...</div>;
  }

  if (!order) {
    return <div className="rounded-3xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">Order not found.</div>;
  }

  const returnWindowExpiry = eligibility?.return_window_expires_at ? new Date(eligibility.return_window_expires_at).toLocaleString() : '—';
  const comparePassed = compareResult ? (compareResult.matched ? 'Match' : 'Mismatch') : null;

  return (
    <div className="space-y-4">
      <ReturnEligibilityBanner orderId={orderId} eligibility={eligibility} />
      {submitError ? <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{submitError}</div> : null}

      <section className="space-y-4 rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Order Summary</div>
          <div className="mt-2 text-lg font-semibold text-slate-900">Order {String(orderValue(order, 'external_order_id') ?? orderId)}</div>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Summary label="Customer" value={String(orderValue(order, 'customer_id') ?? '—')} />
          <Summary label="Order date" value={orderValue(order, 'order_date') ? new Date(String(orderValue(order, 'order_date'))).toLocaleString() : '—'} />
          <Summary label="Delivery date" value={orderValue(order, 'delivery_date') ? new Date(String(orderValue(order, 'delivery_date'))).toLocaleString() : '—'} />
          <Summary label="Order total" value={orderValue(order, 'product_value') != null ? `$${Number(orderValue(order, 'product_value')).toFixed(2)}` : '—'} />
          <Summary label="Shipment tracking" value={String(orderValue(order, 'tracking_number_hash') ?? '—')} />
          <Summary label="Return window expiry" value={returnWindowExpiry} />
          <Summary label="Order status" value={String(orderValue(order, 'order_status') ?? '—')} />
          <Summary label="Payment method" value={String(orderValue(order, 'payment_method') ?? '—')} />
        </div>
      </section>

      <section className="space-y-4 rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Return Items</div>
          <div className="mt-2 text-sm text-slate-600">Select items and quantities from the available returnable quantity.</div>
        </div>
        <ReturnItemsSelector items={items} selectedIds={selectedIds} quantities={quantities} onToggle={toggleItem} onQuantityChange={(id, quantity) => setQuantities((current) => ({ ...current, [id]: quantity }))} />
      </section>

      <section className="space-y-4 rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Return Details</div>
          <div className="mt-2 text-sm text-slate-600">Provide the return reason, condition, and fulfillment method.</div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Return reason category">
            <select value={reasonCategory} onChange={(event) => setReasonCategory(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none">
              {reasonCategories.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </Field>
          <Field label="Condition reported">
            <select value={conditionReported} onChange={(event) => setConditionReported(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none">
              {conditionValues.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </Field>
          <Field label="Return reason">
            <input value={reason} onChange={(event) => setReason(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none" />
          </Field>
          <Field label="Preferred refund method">
            <select value={refundMethod} onChange={(event) => setRefundMethod(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none">
              {refundMethods.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </Field>
          <Field label="Return method">
            <select value={returnMethod} onChange={(event) => setReturnMethod(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none">
              {returnMethods.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </Field>
          <Field label="Pickup address">
            <input value={pickupAddressId} onChange={(event) => setPickupAddressId(event.target.value)} placeholder="Address UUID or reference" className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none" />
          </Field>
        </div>
        <Field label="Detailed customer description">
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} className="min-h-[120px] w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none" />
        </Field>
      </section>

      <section className="space-y-4 rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Supporting Evidence</div>
            <div className="mt-2 text-sm text-slate-600">Upload a picture now so the return workflow can run OCR comparison against the order details.</div>
          </div>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="rounded-2xl border border-slate-200 bg-slate-950 px-4 py-2 text-sm font-medium text-white"
          >
            Upload picture
          </button>
          <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
        </div>

        {compareLoading ? <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Reading image and comparing against the order...</div> : null}
        {compareError ? <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{compareError}</div> : null}

        {imagePreview ? (
          <div className="grid gap-4 xl:grid-cols-[240px_1fr]">
            <div className="overflow-hidden rounded-3xl border border-slate-200 bg-slate-50">
              <img src={imagePreview} alt={imageName ?? 'Uploaded return evidence'} className="h-full w-full object-cover" />
            </div>
            <div className="space-y-3 rounded-3xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Uploaded File</div>
              <div className="text-sm font-medium text-slate-900">{imageName ?? 'Return evidence image'}</div>
              <div className="text-sm text-slate-600">The form will keep this image ready for future attachment storage and inspection workflows.</div>
              {compareResult ? (
                <div className={`rounded-2xl border p-4 text-sm ${compareResult.matched ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
                  <div className="text-xs uppercase tracking-[0.24em] text-slate-500">OCR Comparison Result</div>
                  <div className="mt-2 text-base font-semibold">{comparePassed} - confidence {Number(compareResult.confidence).toFixed(1)}%</div>
                  <div className="mt-2 text-sm">{compareResult.summary || 'No summary was returned by the vision model.'}</div>
                  {compareResult.ocr_text ? <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-3 text-xs text-slate-700"><span className="font-semibold">OCR text:</span> {compareResult.ocr_text}</div> : null}
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    <Summary label="Detected product" value={compareResult.detected_product_name ?? '—'} />
                    <Summary label="Detected SKU" value={compareResult.detected_sku ?? '—'} />
                    <Summary label="Detected serial" value={compareResult.detected_serial_number ?? '—'} />
                    <Summary label="Detected IMEI" value={compareResult.detected_imei ?? '—'} />
                  </div>
                  {compareResult.mismatch_reasons.length ? <div className="mt-3 text-sm"><span className="font-semibold">Mismatch reasons:</span> {compareResult.mismatch_reasons.join(', ')}</div> : null}
                  {compareResult.evidence.length ? <div className="mt-2 text-sm"><span className="font-semibold">Evidence:</span> {compareResult.evidence.join(' | ')}</div> : null}
                  {compareResult.provider_model ? <div className="mt-2 text-xs text-slate-500">Model: {compareResult.provider_model}</div> : null}
                </div>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-600">
            No image uploaded yet. Uploading a picture will compare it to order details using the vision model and prepare the workflow for future attachment storage.
          </div>
        )}
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <button onClick={submit} disabled={submitting || !!(eligibility && !eligibility.eligible)} className="rounded-2xl bg-slate-950 px-5 py-3 text-sm font-medium text-white disabled:opacity-60">
          {submitting ? 'Creating return...' : 'Create Return'}
        </button>
        <Link to={`/orders/${orderId}`} className="rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm text-slate-700">Cancel</Link>
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

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="space-y-2">
      <div className="text-xs uppercase tracking-[0.22em] text-slate-500">{label}</div>
      {children}
    </label>
  );
}
