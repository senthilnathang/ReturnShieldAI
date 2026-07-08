import { AlertTriangle } from 'lucide-react';

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  confirmTone = 'destructive',
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  confirmTone?: 'destructive' | 'warning' | 'default';
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;

  const confirmColor =
    confirmTone === 'destructive'
      ? 'bg-red-primary text-white hover:bg-red-hover'
      : confirmTone === 'warning'
        ? 'bg-yellow-primary text-white hover:bg-yellow-hover'
        : 'bg-purple-primary text-white hover:bg-purple-hover';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-grey-background/60 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-xl border border-grey-border bg-surface-card p-5 shadow-sticky-top animate-slide-up-fade">
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-red-background">
            <AlertTriangle className="size-5 text-red-primary" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold text-grey-primary">{title}</h3>
            <p className="mt-1 text-xs text-grey-secondary">{message}</p>
          </div>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded-lg border border-grey-border bg-grey-background px-3 py-2 text-xs font-medium text-grey-primary hover:bg-grey-background-light transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`rounded-lg px-3 py-2 text-xs font-medium transition-colors ${confirmColor}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
