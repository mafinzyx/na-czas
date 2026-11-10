// Small shared building blocks.

import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { useI18n } from '../i18n'
import { describeError } from '../lib/errors'

export function Loading() {
  const { t } = useI18n()
  return <p className="muted">{t('common.loading')}</p>
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n()
  return (
    <div className="note note-error" role="alert">
      <span>{describeError(error, t)}</span>
      {onRetry && (
        <button type="button" className="btn btn-small" onClick={onRetry}>
          {t('common.retry')}
        </button>
      )}
    </div>
  )
}

export function PageHeader({ title, intro, action }: { title: string; intro: string; action?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        <p className="muted">{intro}</p>
      </div>
      {action}
    </header>
  )
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const { t } = useI18n()

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button type="button" className="btn-icon" onClick={onClose} aria-label={t('common.close')}>
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

/** Delete button that asks for confirmation in place instead of a browser dialog. */
export function DeleteButton({ onConfirm, disabled }: { onConfirm: () => void; disabled?: boolean }) {
  const { t } = useI18n()
  const [asking, setAsking] = useState(false)

  if (!asking) {
    return (
      <button type="button" className="btn btn-small btn-danger" onClick={() => setAsking(true)} disabled={disabled}>
        {t('common.delete')}
      </button>
    )
  }
  return (
    <span className="confirm">
      {t('common.confirmDelete')}
      <button type="button" className="btn btn-small btn-danger" onClick={onConfirm} disabled={disabled}>
        {t('common.yes')}
      </button>
      <button type="button" className="btn btn-small" onClick={() => setAsking(false)}>
        {t('common.no')}
      </button>
    </span>
  )
}

interface SegmentedProps<T extends string> {
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
  label: string
}

export function Segmented<T extends string>({ value, options, onChange, label }: SegmentedProps<T>) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          className={option.value === value ? 'active' : ''}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
