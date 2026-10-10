import { Modal } from './Modal'

interface ConfirmDialogProps {
  open: boolean
  title: string
  description?: string
  confirmLabel: string
  cancelLabel?: string
  tone?: 'primary' | 'danger'
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel = 'Отмена',
  tone = 'primary',
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal labelledBy="confirm-dialog-title" onClose={onCancel} open={open} panelClassName="relative w-full max-w-md rounded-panel bg-raised p-6 shadow-raised-lg">
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <h2 className="font-mono text-h2 font-bold text-ink" id="confirm-dialog-title">
            {title}
          </h2>
          {description !== undefined ? <p className="font-sans text-body text-ink-secondary">{description}</p> : null}
        </div>
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button className="btn-ghost" disabled={busy} onClick={onCancel} type="button">
            {cancelLabel}
          </button>
          <button
            className={tone === 'danger' ? 'btn-danger' : 'btn-primary'}
            disabled={busy}
            onClick={onConfirm}
            type="button"
          >
            {busy ? 'Выполняется...' : confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  )
}
